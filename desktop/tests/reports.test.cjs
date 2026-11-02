const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { validReport, MAX_HTML_BYTES, ReportLayoutError, createReportExporter, atomicWrite } = require('../reports.cjs');

const payload = { variant: 'print', html: '<!doctype html><p>报告</p>' };

test('report payload has a bounded size and a fixed variant whitelist', () => {
  for (const bad of [null, {}, { ...payload, variant: 'file' }, { ...payload, html: '<script>' },
    { ...payload, html: '<!doctype html>' + '壬'.repeat(MAX_HTML_BYTES / 3) }]) {
    assert.equal(Boolean(validReport(bad)), false);
  }
  assert.ok(validReport(payload));
  assert.ok(validReport({ ...payload, variant: 'wechat' }));
});

test('cancel never renders or writes, filename excludes report content', async () => {
  const exporter = createReportExporter({ dialog: { showSaveDialog: async (_owner, options) => {
    assert.match(options.defaultPath, /^小六壬-打印版-.*\.pdf$/);
    assert.equal(options.defaultPath.includes('<p>'), false);
    return { canceled: true };
  } }, render: () => assert.fail('cancel rendered'), write: () => assert.fail('cancel wrote') });
  assert.deepEqual(await exporter({}, payload), { status: 'cancelled' });
});

test('only one export at a time, saves PDF and releases busy state after failure', async () => {
  let resolveDialog;
  let calls = 0;
  const exporter = createReportExporter({
    dialog: { showSaveDialog: () => { calls++; return new Promise(resolve => { resolveDialog = resolve; }); } },
    render: async p => { assert.equal(p, payload); return Buffer.from('%PDF'); },
    write: async (file, data) => { assert.equal(file, '/report.pdf'); assert.equal(data.toString(), '%PDF'); },
  });
  const first = exporter({}, payload);
  assert.deepEqual(await exporter({}, payload), { status: 'busy' });
  assert.equal(calls, 1);
  resolveDialog({ filePath: '/report.pdf' });
  assert.deepEqual(await first, { status: 'saved' });
  const second = exporter({}, payload);
  resolveDialog({ canceled: true });
  assert.deepEqual(await second, { status: 'cancelled' });
  assert.equal(calls, 2);
});

test('render or write failures are recoverable and never expose sensitive errors', async () => {
  for (const stage of ['render', 'write']) {
    const exporter = createReportExporter({
      dialog: { showSaveDialog: async () => ({ filePath: '/report.pdf' }) },
      render: async () => { if (stage === 'render') throw new Error('private question'); return Buffer.from('%PDF'); },
      write: async () => { throw new Error('private path'); },
    });
    for (let i = 0; i < 2; i++) {
      const result = await exporter({}, payload);
      assert.equal(result.status, 'error');
      assert.equal(result.message.includes('private'), false);
    }
  }
});

test('layout limits have a distinct actionable result instead of a disk error', async () => {
  const exporter = createReportExporter({
    dialog: { showSaveDialog: async () => ({ filePath: '/report.pdf' }) },
    render: async () => { throw new ReportLayoutError('private details'); },
    write: () => assert.fail('invalid layout must not be saved'),
  });
  assert.deepEqual(await exporter({}, payload), { status: 'error', code: 'layout' });
});

test('atomic save replaces existing output and leaves no temporary files', async () => {
  const folder = await fs.mkdtemp(path.join(os.tmpdir(), 'msr-report-test-'));
  try {
    const output = path.join(folder, 'report.pdf');
    await fs.writeFile(output, 'previous');
    await atomicWrite(output, Buffer.from('%PDF-new'));
    assert.equal(await fs.readFile(output, 'utf8'), '%PDF-new');
    assert.deepEqual(await fs.readdir(folder), ['report.pdf']);
    await assert.rejects(atomicWrite(path.join(folder, 'missing', 'report.pdf'), Buffer.from('new')));
    assert.deepEqual(await fs.readdir(folder), ['report.pdf']);
  } finally { await fs.rm(folder, { recursive: true, force: true }); }
});
