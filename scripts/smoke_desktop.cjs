// 通过仅测试时启用的 Chromium 调试端口验证真实主进程、preload、页面及 Python 服务。
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { setTimeout: delay } = require('node:timers/promises');
const { findAvailablePort } = require('../desktop/backend.cjs');

const root = path.resolve(__dirname, '..');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'mini-six-ren-smoke-'));
let child;
let socket;
let output = '';
let id = 0;
const pending = new Map();

async function waitFor(action, description, timeout = 30000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const result = await action();
    if (result) return result;
    await delay(100);
  }
  throw new Error(`等待超时：${description}\n${output.slice(-4000)}`);
}

function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const requestId = ++id;
    const timer = setTimeout(() => { pending.delete(requestId); reject(new Error(`CDP 超时：${method}`)); }, 10000);
    pending.set(requestId, message => {
      clearTimeout(timer);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    });
    socket.send(JSON.stringify({ id: requestId, method, params }));
  });
}

async function evaluate(expression) {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result?.value;
}

async function start() {
  const port = await findAvailablePort();
  const packagedIndex = process.argv.indexOf('--packaged');
  const packaged = packagedIndex >= 0 ? process.argv[packagedIndex + 1] : null;
  const executable = packaged || require('electron');
  const args = [...(packaged ? [] : ['.']), `--remote-debugging-port=${port}`, '--remote-debugging-address=127.0.0.1'];
  child = spawn(executable, args, { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], env: {
    ...process.env, MSR_DESKTOP_USER_DATA: temp, MSR_CONFIG_FILE: path.join(temp, '.env'),
    OPENAI_API_KEY: '', DEEPSEEK_API_KEY: '',
  } });
  child.on('error', error => { output += error.stack; });
  child.stdout.on('data', chunk => { output += chunk; });
  child.stderr.on('data', chunk => { output += chunk; });
  const target = await waitFor(async () => {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      return targets.find(item => item.type === 'page' && item.url.startsWith('http://127.0.0.1:'));
    } catch { return null; }
  }, '桌面页面启动', 90000);
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id); }
  };
  await waitFor(() => evaluate(`Boolean(document.querySelector('.submit-button') && window.socket?.connected)`), 'NiceGUI WebSocket 连接');
  return target.url;
}

async function stop() {
  socket?.close();
  socket = null;
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  const processToStop = child;
  await new Promise(resolve => {
    const timer = setTimeout(() => processToStop.kill('SIGKILL'), 7000);
    processToStop.once('exit', () => { clearTimeout(timer); resolve(); });
    processToStop.kill('SIGTERM');
  });
}

async function stopWindowsGracefully(origin) {
  const processToStop = child;
  // Query only direct backend children; never collect environment variables or command lines.
  const query = `Get-CimInstance Win32_Process -Filter 'ParentProcessId=${processToStop.pid}' | Where-Object { $_.Name -eq 'mini-six-ren-backend.exe' -or $_.Name -match '^python' } | ForEach-Object { $_.ProcessId }`;
  const backendPids = execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', query], {
    encoding: 'utf8', timeout: 15000,
  }).trim().split(/\s+/).filter(Boolean).map(Number);
  assert.ok(backendPids.length > 0, '关闭前必须找到运行中的内置后端');
  // Page.close requests a native window close; unlike SIGTERM it exercises app.quit/before-quit.
  socket.send(JSON.stringify({ id: ++id, method: 'Page.close' }));
  await waitFor(() => processToStop.exitCode !== null || processToStop.signalCode !== null, 'Windows 正常关闭窗口并退出', 15000);
  assert.equal(processToStop.exitCode, 0);
  assert.equal(processToStop.signalCode, null);
  await waitFor(() => backendPids.every(pid => {
    try { process.kill(pid, 0); return false; } catch { return true; }
  }), '正常退出后后端进程停止', 10000);
  await waitFor(async () => {
    try { await fetch(`${new URL(origin).origin}/desktop/health`, { signal: AbortSignal.timeout(500) }); return false; }
    catch { return true; }
  }, '正常退出后释放后端端口');
  socket?.close();
  socket = null;
  console.log('Windows 正常关闭验证通过：窗口正常退出、后端进程消失、监听端口释放。');
}

async function openSettings() {
  await evaluate(`document.querySelector('.api-settings-button').click()`);
  await waitFor(() => evaluate(`Boolean(document.querySelector('.api-settings-page'))`), '打开 API 设置');
  await delay(400); // QDialog 入场动画结束后检查实际布局。
}

async function fillKey(provider, value) {
  await evaluate(`(() => { const input = document.querySelector('[data-provider="${provider}"] input'); input.value = ${JSON.stringify(value)}; input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  await delay(200);
}

async function saveSettings(expected) {
  await evaluate(`document.querySelector('.api-settings-save').click()`);
  await waitFor(() => evaluate(`!document.querySelector('.api-settings-page') && document.querySelector('.model-select')?.textContent.includes(${JSON.stringify(expected)})`), `保存后默认 ${expected}`);
}

async function run() {
  try {
    const url = await start();
    assert.equal((await fetch(`${new URL(url).origin}/desktop/health`)).status, 403);
    assert.equal(await evaluate(`typeof require + ':' + typeof process + ':' + typeof window.electron`), 'undefined:undefined:undefined');
    await waitFor(() => evaluate(`Boolean(document.querySelector('.api-settings-page'))`), '无 Key 首启自动设置');
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.api-settings-page input[type="password"]')].map(e => [e.type, e.value])`), [['password', ''], ['password', '']]);
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.api-official-link')].map(e => e.href)`), ['https://platform.openai.com/api-keys', 'https://platform.deepseek.com/api_keys']);
    await delay(400);
    const settingsScreenshot = await call('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(temp, 'api-settings.png'), Buffer.from(settingsScreenshot.data, 'base64'));
    await evaluate(`document.querySelector('.api-settings-skip').click()`);
    await waitFor(() => evaluate(`!document.querySelector('.api-settings-page')`), '跳过后可用本地占卜');
    await evaluate(`document.querySelector('.submit-button').click()`);
    await waitFor(() => evaluate(`document.querySelectorAll('.transmission-card').length === 3`), '本地数字起课');
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.symbol-name')].map(e => e.textContent)`), ['大安', '留连', '赤口']);
    assert.match(await evaluate(`document.querySelector('.input-snapshot').textContent`), /1、2、3/);
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.reading-tabs .q-tab__label')].map(e => e.textContent)`), ['三传观照', '三传解读']);
    assert.deepEqual(await evaluate(`(() => { const status = document.querySelector('.reading-tabs .interpretation-status'); return [status?.dataset.state, status?.textContent]; })()`), ['idle', '未生成']);
    await evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[1].click()`);
    await waitFor(() => evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[1].getAttribute('aria-selected') === 'true' && Boolean(document.querySelector('.interpretation-placeholder'))`), '三传解读页签与空状态');
    assert.match(await evaluate(`document.querySelector('.interpretation-placeholder').textContent`), /填写问题/);
    assert.equal(await evaluate(`document.querySelector('.interpretation-placeholder').getBoundingClientRect().top < document.querySelector('.reading-heading').getBoundingClientRect().bottom + 80`), true);
    await evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[0].click()`);
    await waitFor(() => evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[0].getAttribute('aria-selected') === 'true' && document.querySelectorAll('.transmission-card').length === 3`), '切回三传观照保留结果');

    await evaluate(`document.querySelectorAll('.input-tabs .q-tab')[2].click()`);
    await waitFor(() => evaluate(`Boolean(document.querySelector('.input-panels input[type="text"]'))`), '汉字标签页');
    await evaluate(`(() => { const input = document.querySelector('.input-panels input[type="text"]'); input.value = '天行健'; input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    await delay(250);
    await evaluate(`document.querySelector('.submit-button').click()`);
    await waitFor(() => evaluate(`document.querySelector('.input-snapshot')?.textContent.includes('汉字模式')`), '汉字起课与内置字典');
    assert.equal(await evaluate(`document.querySelectorAll('.transmission-card').length`), 3);

    await evaluate(`document.querySelectorAll('.input-tabs .q-tab')[1].click()`);
    await waitFor(() => evaluate(`Boolean(document.querySelector('input[type="date"]'))`), '时间标签页');
    await evaluate(`document.querySelector('.submit-button').click()`);
    await waitFor(() => evaluate(`document.querySelector('.input-snapshot')?.textContent.includes('时间模式')`), '时间起课与历法库');
    assert.equal(await evaluate(`document.querySelectorAll('.transmission-card').length`), 3);

    for (const theme of ['ink', 'neon', 'paper', 'night']) {
      await evaluate(`document.querySelector('[data-theme-id="${theme}"]').click()`);
      await waitFor(() => evaluate(`document.documentElement.dataset.theme === '${theme}'`), `主题 ${theme}`);
      for (const width of [1440, 1024, 375]) {
        await call('Emulation.setDeviceMetricsOverride', { width, height: 960, deviceScaleFactor: 1, mobile: false });
        await evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[1].click()`);
        await waitFor(() => evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[1].getAttribute('aria-selected') === 'true'`), `${theme} ${width}px 解读页签`);
        await evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[0].click()`);
        await waitFor(() => evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[0].getAttribute('aria-selected') === 'true'`), '留在观照时仍可查看解读进度');
        // 仅注入 badge 文案/属性验证四种状态的布局；请求生命周期由 Python 测试覆盖。
        for (const [state, text] of [['loading', '解读中…'], ['ready', '可查看'], ['error', '失败'], ['idle', '未生成']]) {
          await evaluate(`(() => { const status = document.querySelector('.interpretation-status'); status.dataset.state = '${state}'; status.textContent = '${text}'; })()`);
          assert.equal(await evaluate(`(() => {
            const tabs = [...document.querySelectorAll('.reading-tabs .q-tab')].map(e => e.getBoundingClientRect());
            const list = document.querySelector('.reading-tabs').getBoundingClientRect();
            const badge = document.querySelector('.interpretation-status').getBoundingClientRect();
            const title = document.querySelectorAll('.reading-tabs .q-tab__label')[1].getBoundingClientRect();
            return Math.abs(tabs[0].top - tabs[1].top) < 2 && tabs.every(r => r.width > 0 && r.left >= list.left - 1 && r.right <= list.right + 1)
              && badge.width > 0 && badge.left >= title.right && badge.right <= tabs[1].right
              && Math.abs((badge.top + badge.bottom) / 2 - (title.top + title.bottom) / 2) < 2
              && document.documentElement.scrollWidth <= innerWidth;
          })()`), true, `${theme} ${width}px ${state} 页签与状态同排可见且无溢出`);
        }
        await evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[0].click()`);
        await waitFor(() => evaluate(`document.querySelectorAll('.reading-tabs .q-tab')[0].getAttribute('aria-selected') === 'true' && document.querySelectorAll('.transmission-card').length === 3`), '切换页签后本地结果仍在');
        await openSettings();
        assert.equal(await evaluate(`(() => {
          const panel = document.querySelector('.api-settings-page');
          return panel.scrollWidth <= panel.clientWidth && [...panel.querySelectorAll('.api-provider-card')].every(e => {
            const r = e.getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= innerWidth;
          });
        })()`), true, `${theme} ${width}px 设置页无横向溢出`);
        await evaluate(`document.querySelector('.api-settings-skip').click()`);
        await waitFor(() => evaluate(`!document.querySelector('.api-settings-page')`), '返回观照保留结果');
      }
    }
    await call('Emulation.clearDeviceMetricsOverride');
    await waitFor(async () => {
      try { return JSON.parse(fs.readFileSync(path.join(temp, 'preferences.json'), 'utf8')).theme === 'night'; }
      catch { return false; }
    }, 'preload 将主题保存到主进程');
    await delay(1000); // 等页签指示条与主题入场动画完成后再截图。
    const screenshot = await call('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(temp, 'desktop.png'), Buffer.from(screenshot.data, 'base64'));
    await openSettings();
    await fillKey('deepseek', 'smoke-deepseek-key');
    await saveSettings('DeepSeek');
    assert.equal(await evaluate(`document.querySelectorAll('.transmission-card').length`), 3);
    await openSettings();
    assert.deepEqual(await evaluate(`[...document.querySelectorAll('.api-settings-page input[type="password"]')].map(e => e.value)`), ['', '']);
    await fillKey('openai', 'smoke-openai-key');
    await saveSettings('OpenAI');
    await openSettings();
    await fillKey('openai', 'smoke-draft-not-saved');
    await evaluate(`document.querySelector('.api-settings-skip').click()`);
    await waitFor(() => evaluate(`!document.querySelector('.api-settings-page')`), '取消不保存草稿');
    assert.equal(fs.readFileSync(path.join(temp, '.env'), 'utf8').includes('smoke-draft-not-saved'), false);
    if (process.platform === 'win32') await stopWindowsGracefully(url);
    else await stop();
    await waitFor(async () => {
      try { await fetch(`${new URL(url).origin}/desktop/health`, { signal: AbortSignal.timeout(500) }); return false; }
      catch { return true; }
    }, '退出后释放后端端口');
    await start();
    await waitFor(() => evaluate(`document.documentElement.dataset.theme === 'night'`), '跨启动恢复主题');
    assert.equal(await evaluate(`!document.querySelector('.api-settings-page') && document.querySelector('.model-select')?.textContent.includes('OpenAI')`), true);
    assert.equal(await evaluate(`document.documentElement.outerHTML.includes('smoke-openai-key') || JSON.stringify(localStorage).includes('smoke-openai-key')`), false);
    await openSettings();
    await evaluate(`document.querySelector('[data-provider="openai"] .q-checkbox').click()`);
    await delay(200);
    await saveSettings('DeepSeek');
    await stop();
    await start();
    assert.equal(await evaluate(`!document.querySelector('.api-settings-page') && document.querySelector('.model-select')?.textContent.includes('DeepSeek')`), true);
    await openSettings();
    await evaluate(`document.querySelector('[data-provider="deepseek"] .q-checkbox').click()`);
    await delay(200);
    await saveSettings('仅本地计算');
    await stop();
    await start();
    await waitFor(() => evaluate(`Boolean(document.querySelector('.api-settings-page'))`), '删除所有 Key 后重启重新引导');
    const logFile = path.join(temp, 'logs/desktop.log');
    const logs = output + (fs.existsSync(logFile) ? fs.readFileSync(logFile, 'utf8') : '');
    for (const fakeKey of ['smoke-openai-key', 'smoke-deepseek-key', 'smoke-draft-not-saved']) {
      assert.equal(logs.includes(fakeKey), false, '密钥不得进入日志');
      assert.equal(fs.readFileSync(path.join(temp, 'preferences.json'), 'utf8').includes(fakeKey), false);
    }
    console.log(`桌面冒烟通过：API 首启引导/保存/取消/删除/重启默认选择、三种输入、三传页签切换与四种状态布局、四套主题及三种宽度、跨启动记忆、渲染隔离、鉴权、退出清理。\n截图与隔离配置：${temp}`);
  } finally {
    await stop();
  }
}

run().catch(error => { console.error(error); console.error(`诊断目录：${temp}`); process.exitCode = 1; });
