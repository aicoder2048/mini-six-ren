const { ipcRenderer } = require('electron');

// 不向页面暴露 Node/IPC API；仅在隔离世界中同步一个白名单主题值。
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
