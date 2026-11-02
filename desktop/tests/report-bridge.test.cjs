const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function bridge() {
  const window = new EventTarget();
  const timers = new Map();
  const calls = [];
  let timerId = 0;
  const context = vm.createContext({ window, document: {}, CustomEvent, console,
    MutationObserver: class { observe() {} },
    setTimeout: callback => { const id = ++timerId; timers.set(id, callback); return id; },
    clearTimeout: id => timers.delete(id),
    require: name => {
      assert.equal(name, 'electron');
      return { ipcRenderer: { sendSync: () => null, send: () => {},
        invoke: (channel, payload) => new Promise((resolve, reject) => calls.push({ channel, payload, resolve, reject })),
      } };
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../preload.cjs'), 'utf8'), context);
  const web = fs.readFileSync(path.join(__dirname, '../../src/web.py'), 'utf8');
  const template = web.match(/result = await ui\.run_javascript\(f'''([\s\S]*?)''', timeout=600\)/)[1];
  const run = payload => {
    const script = template.replaceAll('{{', '{').replaceAll('}}', '}').replace('{payload}', JSON.stringify(payload));
    return vm.runInContext(`(async () => { ${script} })()`, context);
  };
  return { window, timers, calls, run };
}

const payload = id => ({ variant: 'print', html: '<!doctype html><p>报告</p>', request_id: id.repeat(32) });

test('real preload and page script correlate timeout/retry/late responses', async () => {
  const { timers, calls, run, window } = bridge();
  const first = run(payload('a'));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].channel, 'report:export');
  const timeout = [...timers.values()][0];
  timers.clear();
  timeout();
  assert.equal((await first).status, 'error');
  const retry = await run({ ...payload('b'), variant: 'wechat' });
  assert.equal(retry.status, 'busy');
  assert.equal(retry.request_id, 'b'.repeat(32));
  assert.equal(calls.length, 1, 'busy retry cannot silently launch or impersonate the old export');
  calls[0].resolve({ status: 'saved' });
  await new Promise(resolve => setImmediate(resolve));
  let resolved = false;
  const third = run(payload('c')).then(result => { resolved = true; return result; });
  assert.equal(calls.length, 2);
  window.dispatchEvent(new CustomEvent('msr:report-result', { detail: JSON.stringify({ status: 'saved', request_id: 'a'.repeat(32) }) }));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(resolved, false, 'late old responses must be ignored');
  calls[1].resolve({ status: 'saved' });
  assert.equal((await third).request_id, 'c'.repeat(32));
  assert.equal(timers.size, 0);
});

test('transport failure is correlated and releases the preload busy lock', async () => {
  const { run, calls, window } = bridge();
  window.dispatchEvent(new CustomEvent('msr:export-report', { detail: 'not JSON' }));
  window.dispatchEvent(new CustomEvent('msr:export-report', { detail: JSON.stringify(payload('!')) }));
  assert.equal(calls.length, 0);
  const first = run(payload('a'));
  calls[0].reject(new Error('private transport details'));
  const result = await first;
  assert.equal(result.status, 'error');
  assert.equal(result.request_id, 'a'.repeat(32));
  assert.equal(JSON.stringify(result).includes('private'), false);
  const retry = run(payload('b'));
  calls[1].resolve({ status: 'cancelled' });
  assert.equal((await retry).status, 'cancelled');
});
