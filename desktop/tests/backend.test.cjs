const assert = require('node:assert/strict');
const { once } = require('node:events');
const path = require('node:path');
const { test } = require('node:test');
const { Backend, checkHealth } = require('../backend.cjs');
const { THEMES, isBackendUrl, isExternalUrl } = require('../security.cjs');

function fixture(options = {}) {
  return new Backend({ command: process.execPath, args: [path.join(__dirname, 'fixtures/backend.cjs')],
    timeoutMs: 2000, stopTimeoutMs: 100, pollIntervalMs: 20, ...options });
}

function isAlive(pid) {
  try { process.kill(pid, 0); return true; } catch { return false; }
}

test('ready waits for authenticated health; stop is idempotent and reaps child', async t => {
  const backend = fixture();
  t.after(() => backend.stop());
  const origin = await backend.start();
  assert.match(origin, /^http:\/\/127\.0\.0\.1:\d+$/);
  assert.equal(await checkHealth(origin, backend.token), true);
  assert.equal(await checkHealth(origin, 'wrong'), false);
  const pid = backend.child.pid;
  await Promise.all([backend.stop(), backend.stop()]);
  assert.equal(isAlive(pid), false);
});

test('startup failures include early exit and missing executable', async () => {
  for (const backend of [fixture({ env: { FIXTURE_EXIT: '1' } }), fixture({ command: '/not/a/real/python' })]) {
    await assert.rejects(backend.start(), /已退出|ENOENT/);
    await backend.stop();
  }
});

test('wrong health identity times out instead of connecting to another service', async () => {
  const backend = fixture({ env: { FIXTURE_WRONG_APP: '1' }, timeoutMs: 250 });
  await assert.rejects(backend.start(), /超时/);
  assert.equal(isAlive(backend.child.pid), false);
});

test('unexpected exit after ready emits crashed', async t => {
  const backend = fixture();
  t.after(() => backend.stop());
  await backend.start();
  const crashed = once(backend, 'crashed');
  backend.child.kill('SIGKILL');
  const [error] = await crashed;
  assert.match(error.message, /已退出/);
});

test('stubborn child is forcibly terminated after shutdown grace period', async t => {
  const backend = fixture({ env: { FIXTURE_IGNORE_TERM: '1' } });
  t.after(() => backend.stop());
  await backend.start();
  await backend.stop();
  assert.equal(isAlive(backend.child.pid), false);
});

test('cancelling during port allocation does not spawn a child', async () => {
  let finish;
  const backend = fixture({ portFactory: () => new Promise(resolve => { finish = resolve; }) });
  const starting = backend.start();
  await backend.stop();
  finish(1234);
  await assert.rejects(starting, /取消/);
  assert.equal(backend.child, undefined);
});

test('backend token is not written to logs', async t => {
  let output = '';
  const backend = fixture({ env: { FIXTURE_LOG_TOKEN: '1' }, log: chunk => { output += chunk; } });
  t.after(() => backend.stop());
  await backend.start();
  assert.equal(output.includes(backend.token), false);
  assert.match(output, /REDACTED/);
});

test('only exact loopback backend origin can receive authentication headers', () => {
  const origin = 'http://127.0.0.1:1234';
  for (const url of [`${origin}/`, 'ws://127.0.0.1:1234/_nicegui_ws/socket.io']) {
    assert.equal(isBackendUrl(url, origin), true);
  }
  for (const url of ['http://127.0.0.1:9999', 'http://127.0.0.1.evil:1234', 'http://localhost:1234',
    'https://127.0.0.1:1234', 'file:///etc/passwd', 'javascript:alert(1)', 'http://name@127.0.0.1:1234', 'garbage']) {
    assert.equal(isBackendUrl(url, origin), false, url);
  }
});

test('external links are limited to browser HTTP(S); themes are a fixed whitelist', () => {
  assert.equal(isExternalUrl('https://example.com'), true);
  for (const url of ['file:///etc/passwd', 'javascript:alert(1)', 'shell:AppsFolder', 'garbage']) {
    assert.equal(isExternalUrl(url), false);
  }
  assert.deepEqual(THEMES, ['paper', 'night', 'ink', 'neon']);
});
