const { EventEmitter } = require('node:events');
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const http = require('node:http');
const net = require('node:net');
const { setTimeout: delay } = require('node:timers/promises');

const TOKEN_HEADER = 'x-mini-six-ren-token';

function findAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(error => error ? reject(error) : resolve(port));
    });
  });
}

function checkHealth(origin, token) {
  return new Promise(resolve => {
    const request = http.get(`${origin}/desktop/health`, {
      headers: { [TOKEN_HEADER]: token }, timeout: 750,
    }, response => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', chunk => {
        body += chunk;
        if (body.length > 4096) request.destroy();
      });
      response.on('error', () => resolve(false));
      response.on('end', () => {
        try {
          const data = JSON.parse(body);
          resolve(response.statusCode === 200 && data.application === 'mini-six-ren-desktop' && data.protocol === 1);
        } catch { resolve(false); }
      });
    });
    request.on('timeout', () => request.destroy());
    request.on('error', () => resolve(false));
  });
}

class Backend extends EventEmitter {
  constructor({ command, args = [], cwd, env = {}, log = () => {}, timeoutMs = 90000,
    stopTimeoutMs = 3000, pollIntervalMs = 150, portFactory = findAvailablePort }) {
    super();
    Object.assign(this, { command, args, cwd, env, log, timeoutMs, stopTimeoutMs, pollIntervalMs, portFactory });
    this.token = randomBytes(32).toString('hex');
    this.stopping = false;
    this.ready = false;
  }

  async start() {
    if (this.child) throw new Error('后端已经启动');
    const port = await this.portFactory();
    if (this.stopping) throw new Error('启动已取消');
    this.origin = `http://127.0.0.1:${port}`;
    this.child = spawn(this.command, [...this.args, '--port', String(port)], {
      cwd: this.cwd,
      env: { ...process.env, ...this.env, MSR_DESKTOP_TOKEN: this.token, PYTHONUNBUFFERED: '1' },
      stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true, shell: false,
    });
    const log = chunk => this.log(chunk.toString().split(this.token).join('[REDACTED]'));
    this.child.stdout.on('data', log);
    this.child.stderr.on('data', log);
    this.child.stdin.on('error', () => {});
    this.child.once('error', error => { this.failure = error; });
    this.child.once('exit', (code, signal) => {
      if (!this.stopping) {
        this.failure = new Error(`本地服务已退出（${signal || code}）`);
        if (this.ready) this.emit('crashed', this.failure);
      }
    });
    try {
      const deadline = Date.now() + this.timeoutMs;
      while (Date.now() < deadline) {
        if (this.failure) throw this.failure;
        if (this.stopping) throw new Error('启动已取消');
        if (await checkHealth(this.origin, this.token)) {
          if (this.failure) throw this.failure;
          if (this.stopping) throw new Error('启动已取消');
          this.ready = true;
          return this.origin;
        }
        await delay(this.pollIntervalMs);
      }
      throw new Error('本地服务启动超时，请查看桌面日志。');
    } catch (error) {
      await this.stop();
      throw error;
    }
  }

  stop() {
    this.stopping = true;
    if (this.stopPromise) return this.stopPromise;
    const child = this.child;
    if (!child || !child.pid || child.exitCode !== null || child.signalCode !== null) return Promise.resolve();
    this.stopPromise = new Promise(resolve => {
      const timer = setTimeout(() => {
        child.kill('SIGKILL');
        child.stdin.destroy();
      }, this.stopTimeoutMs);
      child.once('exit', () => { clearTimeout(timer); resolve(); });
      child.kill('SIGTERM');
    });
    return this.stopPromise;
  }
}

module.exports = { Backend, checkHealth, findAvailablePort, TOKEN_HEADER };
