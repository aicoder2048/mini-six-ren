const { app, BrowserWindow, Menu, dialog, ipcMain, session, shell } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { Backend, TOKEN_HEADER } = require('./backend.cjs');
const { THEMES, isBackendUrl, isExternalUrl } = require('./security.cjs');

app.setName('小六壬');
const root = path.resolve(__dirname, '..');
if (process.env.MSR_DESKTOP_USER_DATA) app.setPath('userData', path.resolve(process.env.MSR_DESKTOP_USER_DATA));
let window;
let backend;
let quitting = false;
let booting = true;
let logPath;
let desktopSession;
let preferences = {};
let preferencesPath;

function writeLog(text) {
  try { fs.appendFileSync(logPath, text, { mode: 0o600 }); }
  catch { /* 日志失败不能阻止应用退出 */ }
}

function trustedSender(event) {
  return window && event.sender === window.webContents &&
    event.senderFrame === window.webContents.mainFrame &&
    isBackendUrl(event.senderFrame.url, backend.origin);
}

function configureSession() {
  desktopSession = session.fromPartition('mini-six-ren-desktop');
  desktopSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  desktopSession.setPermissionCheckHandler(() => false);
  desktopSession.on('will-download', event => event.preventDefault());
  desktopSession.webRequest.onBeforeRequest((details, callback) => {
    // 启动页仅来自应用自身；远程页面/脚本不能进入有后端鉴权能力的会话。
    const startupUrl = require('node:url').pathToFileURL(path.join(__dirname, 'startup.html')).href;
    callback({ cancel: !isBackendUrl(details.url, backend.origin) && details.url !== startupUrl &&
      !details.url.startsWith('devtools:') });
  });
  desktopSession.webRequest.onBeforeSendHeaders((details, callback) => {
    const headers = { ...details.requestHeaders };
    if (isBackendUrl(details.url, backend.origin)) headers[TOKEN_HEADER] = backend.token;
    callback({ requestHeaders: headers });
  });
}

async function createWindow() {
  window = new BrowserWindow({
    title: '小六壬 · 三传', width: 1440, height: 960, minWidth: 960, minHeight: 680,
    backgroundColor: '#f7f4ed', show: false, autoHideMenuBar: process.platform !== 'darwin',
    webPreferences: {
      session: desktopSession,
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true,
    },
  });
  const currentWindow = window;
  currentWindow.once('ready-to-show', () => currentWindow.show());
  currentWindow.on('closed', () => { if (window === currentWindow) window = null; });
  currentWindow.webContents.on('will-navigate', (event, url) => {
    if (!isBackendUrl(url, backend.origin)) event.preventDefault();
  });
  currentWindow.webContents.on('will-attach-webview', event => event.preventDefault());
  currentWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isExternalUrl(url) && !isBackendUrl(url, backend.origin)) {
      shell.openExternal(url).catch(error => writeLog(`打开链接失败：${error.message}\n`));
    }
    return { action: 'deny' };
  });
  currentWindow.webContents.on('render-process-gone', (_event, details) => {
    if (!quitting) {
      writeLog(`渲染进程退出：${details.reason}\n`);
      dialog.showErrorBox('界面意外退出', '可通过「显示 → 重新加载」恢复界面。');
    }
  });
  if (backend.ready) await currentWindow.loadURL(backend.origin);
  else await currentWindow.loadFile(path.join(__dirname, 'startup.html'));
}

function createMenu() {
  const template = [
    ...(process.platform === 'darwin' ? [{ role: 'appMenu', label: '小六壬' }] : []),
    { label: '文件', submenu: [
      { label: 'API Key 设置…', click: async () => {
        if (!window || !backend.ready || !isBackendUrl(window.webContents.getURL(), backend.origin)) return;
        try { await window.webContents.executeJavaScript("document.querySelector('.api-settings-button')?.click()"); }
        catch { dialog.showErrorBox('无法打开设置', '请稍后重试或重新启动应用。'); }
      } },
      { label: '打开日志目录', click: () => shell.openPath(path.dirname(logPath)) },
      { type: 'separator' }, { role: 'quit', label: '退出小六壬' },
    ] },
    { label: '编辑', submenu: [
      { role: 'undo', label: '撤销' }, { role: 'redo', label: '重做' }, { type: 'separator' },
      { role: 'cut', label: '剪切' }, { role: 'copy', label: '复制' },
      { role: 'paste', label: '粘贴' }, { role: 'selectAll', label: '全选' },
    ] },
    { label: '显示', submenu: [
      { label: '重新加载', accelerator: 'CmdOrCtrl+R', click: () => {
        if (window && backend.ready) window.loadURL(backend.origin).catch(error => writeLog(`${error}\n`));
      } },
      { role: 'resetZoom', label: '实际大小' }, { role: 'zoomIn', label: '放大' },
      { role: 'zoomOut', label: '缩小' }, { role: 'togglefullscreen', label: '切换全屏' },
      ...(!app.isPackaged ? [{ role: 'toggleDevTools', label: '开发者工具' }] : []),
    ] },
    { label: '窗口', submenu: [{ role: 'minimize', label: '最小化' }, { role: 'close', label: '关闭窗口' }] },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

async function launch() {
  const userData = app.getPath('userData');
  fs.mkdirSync(userData, { recursive: true });
  app.setAppLogsPath(path.join(userData, 'logs'));
  fs.mkdirSync(app.getPath('logs'), { recursive: true });
  logPath = path.join(app.getPath('logs'), 'desktop.log');
  if (fs.existsSync(logPath) && fs.statSync(logPath).size > 2 * 1024 * 1024) {
    fs.copyFileSync(logPath, `${logPath}.previous`);
    fs.truncateSync(logPath);
  }
  preferencesPath = path.join(userData, 'preferences.json');
  try { preferences = JSON.parse(fs.readFileSync(preferencesPath, 'utf8')) || {}; } catch { /* 首次启动 */ }
  const configFile = process.env.MSR_CONFIG_FILE || (app.isPackaged ? path.join(userData, '.env') : path.join(root, '.env'));
  const executable = process.platform === 'win32' ? 'mini-six-ren-backend.exe' : 'mini-six-ren-backend';
  const command = app.isPackaged ? path.join(process.resourcesPath, 'backend', executable) :
    (process.env.MSR_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'));
  if (!fs.existsSync(command)) throw new Error(app.isPackaged ? '安装包缺少内置后端，请重新安装。' :
    '找不到 Python 环境，请先在项目根目录执行 uv sync，再运行 npm start。');
  backend = new Backend({ command, args: app.isPackaged ? [] : [path.join(root, 'src/desktop_server.py')],
    cwd: app.isPackaged ? userData : root, env: { MSR_CONFIG_FILE: configFile }, log: writeLog });
  backend.on('crashed', async error => {
    if (quitting) return;
    writeLog(`${error.message}\n`);
    const { response } = await dialog.showMessageBox({ type: 'error', message: '本地计算服务意外退出',
      detail: `请重新启动应用。诊断日志：${logPath}`, buttons: ['退出', '打开日志目录'] });
    if (response === 1) await shell.openPath(path.dirname(logPath));
    app.quit();
  });
  configureSession();
  createMenu();
  await createWindow();
  await backend.start();
  if (quitting) return;
  booting = false;
  if (window) await window.loadURL(backend.origin);
}

ipcMain.on('theme:read', event => {
  event.returnValue = trustedSender(event) && THEMES.includes(preferences.theme) ? preferences.theme : null;
});
ipcMain.on('theme:save', (event, theme) => {
  if (!trustedSender(event) || !THEMES.includes(theme)) return;
  preferences = { theme };
  try { fs.writeFileSync(preferencesPath, JSON.stringify(preferences), { mode: 0o600 }); }
  catch (error) { writeLog(`保存主题失败：${error.message}\n`); }
});

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (window) { if (window.isMinimized()) window.restore(); window.show(); window.focus(); }
    else if (!booting && !quitting) createWindow().catch(error => dialog.showErrorBox('无法打开窗口', error.message));
  });
  app.whenReady().then(launch).catch(async error => {
    if (!quitting) {
      writeLog(`${error.stack}\n`);
      dialog.showErrorBox('小六壬启动失败', `${error.message}\n\n日志：${logPath || '尚未创建'}`);
    }
    app.quit();
  });
  app.on('activate', () => {
    if (!window && !booting && !quitting) createWindow().catch(error => dialog.showErrorBox('无法打开窗口', error.message));
  });
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
  app.on('before-quit', event => {
    if (quitting) return;
    event.preventDefault();
    quitting = true;
    Promise.resolve(backend?.stop()).finally(() => app.quit());
  });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => app.quit());
}
