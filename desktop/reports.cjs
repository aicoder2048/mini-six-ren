// PDF rendering uses an isolated session with no backend credentials or remote resources.
const fs = require('node:fs/promises');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

const MAX_HTML_BYTES = 4 * 1024 * 1024;
class ReportLayoutError extends Error {}
const CSP = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">';

function validReport(payload) {
  return payload && ['print', 'wechat'].includes(payload.variant) &&
    typeof payload.html === 'string' && payload.html.startsWith('<!doctype html>') &&
    Buffer.byteLength(payload.html, 'utf8') <= MAX_HTML_BYTES;
}

async function renderPDF({ BrowserWindow, session }, payload) {
  if (!validReport(payload)) throw new Error('无效的报告内容');
  const isolated = session.fromPartition(`report-${randomUUID()}`);
  isolated.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  isolated.setPermissionCheckHandler(() => false);
  isolated.on('will-download', event => event.preventDefault());
  isolated.webRequest.onBeforeRequest((details, callback) => callback({
    cancel: !details.url.startsWith('data:text/html;charset=utf-8,'),
  }));
  const renderer = new BrowserWindow({ show: false, width: 800, height: 1100,
    webPreferences: { session: isolated, nodeIntegration: false, contextIsolation: true,
      sandbox: true, webSecurity: true, backgroundThrottling: false },
  });
  renderer.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  renderer.webContents.on('will-navigate', event => event.preventDefault());
  renderer.webContents.on('will-attach-webview', event => event.preventDefault());
  try {
    // A first restrictive policy cannot be weakened by later markup from the payload.
    await renderer.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(payload.html.replace('<!doctype html>', '<!doctype html>' + CSP))}`);
    await renderer.webContents.executeJavaScript('document.fonts.ready.then(() => true)');
    let scale = 1;
    if (payload.variant === 'print') {
      // Measure at the printable A4 width, not at the hidden window's viewport width.
      const height = await renderer.webContents.executeJavaScript(`(() => {
        document.body.style.width = '178mm';
        return document.querySelector('article').getBoundingClientRect().height;
      })()`);
      scale = Math.min(1, (266 * 96 / 25.4 - 4) / height);
      if (!Number.isFinite(scale) || scale < 0.85) throw new ReportLayoutError('单页摘要超出可读范围，请使用微信版');
    }
    return await renderer.webContents.printToPDF({ printBackground: true,
      preferCSSPageSize: true, pageSize: 'A4', scale,
      displayHeaderFooter: false, tagged: true, generateDocumentOutline: true });
  } finally {
    if (!renderer.isDestroyed()) renderer.destroy();
    // In-memory sessions have no persistent cache; close connections after each export.
    await isolated.closeAllConnections();
  }
}

function createReportExporter({ dialog, render, write = atomicWrite }) {
  let busy = false;
  return async (owner, payload) => {
    if (!validReport(payload)) return { status: 'error', message: '报告内容无效或过长，请重新生成。' };
    if (busy) return { status: 'busy' };
    busy = true;
    try {
      const label = payload.variant === 'print' ? '打印版' : '微信版';
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      const { canceled, filePath } = await dialog.showSaveDialog(owner, {
        title: `保存${label}报告`, defaultPath: `小六壬-${label}-${stamp}.pdf`,
        filters: [{ name: 'PDF 文档', extensions: ['pdf'] }],
      });
      if (canceled || !filePath) return { status: 'cancelled' };
      const pdf = await render(payload);
      await write(filePath, pdf);
      return { status: 'saved' };
    } catch (error) {
      if (error instanceof ReportLayoutError) return { status: 'error', code: 'layout' };
      return { status: 'error', message: '报告保存失败，请检查保存位置、文件权限或磁盘空间后重试。' };
    } finally { busy = false; }
  };
}

async function atomicWrite(filePath, pdf) {
  const temporary = path.join(path.dirname(filePath), `.msr-report-${randomUUID()}.tmp`);
  try {
    await fs.writeFile(temporary, pdf, { mode: 0o600, flag: 'wx' });
    await fs.rename(temporary, filePath);
  } finally { await fs.rm(temporary, { force: true }).catch(() => {}); }
}

module.exports = { MAX_HTML_BYTES, ReportLayoutError, validReport, renderPDF, createReportExporter, atomicWrite };
