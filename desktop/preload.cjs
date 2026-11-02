const { ipcRenderer } = require('electron');

// 不向页面暴露 Node/IPC API；仅同步白名单主题和固定的报告导出事件。
const themes = ['paper', 'night', 'ink', 'neon'];
const theme = ipcRenderer.sendSync('theme:read');
if (themes.includes(theme)) {
  try { localStorage.setItem('msr-theme', theme); } catch { /* 存储禁用时仍可使用默认主题 */ }
}

let lastTheme;
const observer = new MutationObserver(() => {
  const current = document.documentElement?.dataset.theme;
  if (themes.includes(current) && current !== lastTheme) {
    lastTheme = current;
    ipcRenderer.send('theme:save', current);
  }
});
observer.observe(document, { attributes: true, attributeFilter: ['data-theme'], subtree: true });

let exporting = false;
window.addEventListener('msr:export-report', async event => {
  let payload;
  try { payload = JSON.parse(event.detail); } catch { return; }
  if (!payload || !['print', 'wechat'].includes(payload.variant) || typeof payload.html !== 'string' ||
      typeof payload.request_id !== 'string' || !/^[a-f0-9]{32}$/.test(payload.request_id)) return;
  const respond = result => window.dispatchEvent(new CustomEvent('msr:report-result', {
    detail: JSON.stringify({ ...result, request_id: payload.request_id }),
  }));
  if (exporting) { respond({ status: 'busy' }); return; }
  exporting = true;
  let result;
  try { result = await ipcRenderer.invoke('report:export', payload); }
  catch { result = { status: 'error', message: '报告导出失败，请重试。' }; }
  finally { exporting = false; }
  // JSON string crosses the isolated-world boundary without sharing privileged objects.
  respond(result);
});
