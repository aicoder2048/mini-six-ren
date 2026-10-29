#!/usr/bin/env python3
"""Electron 专用入口：复用 Web 页面，不修改领域计算或独立 Web 启动方式。"""

import argparse
import hmac
import multiprocessing
import os
from pathlib import Path
import sys
import threading

TOKEN_HEADER = b'x-mini-six-ren-token'


class DesktopAuth:
    """覆盖 HTTP（含资源）及 Socket.IO WebSocket 的 ASGI 鉴权。"""

    def __init__(self, app, *, token: str, origin: str):
        self.app = app
        self.token = token.encode('utf-8')
        self.origin = origin.encode('ascii')

    async def __call__(self, scope, receive, send):
        if scope['type'] in {'http', 'websocket'}:
            headers = dict(scope.get('headers', []))
            valid_token = hmac.compare_digest(headers.get(TOKEN_HEADER, b''), self.token)
            valid_origin = headers.get(b'origin', self.origin) == self.origin
            if not (valid_token and valid_origin):
                if scope['type'] == 'websocket':
                    await send({'type': 'websocket.close', 'code': 4403})
                else:
                    body = b'Forbidden'
                    await send({'type': 'http.response.start', 'status': 403,
                                'headers': [(b'content-type', b'text/plain'),
                                            (b'content-length', str(len(body)).encode())]})
                    await send({'type': 'http.response.body', 'body': body})
                return
        await self.app(scope, receive, send)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='小六壬 Electron 本地后端')
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('port 必须在 1–65535 之间')
    return args


def exit_when_parent_closes_pipe():
    """Electron 崩溃或被强制关闭时，stdin EOF 避免遗留孤儿后端。"""
    try:
        while sys.stdin.buffer.read(1):
            pass
    finally:
        os._exit(0)


def main(argv=None):
    args = parse_args(argv)
    token = os.environ.get('MSR_DESKTOP_TOKEN', '')
    if len(token) < 32:
        raise SystemExit('请通过 Electron 启动桌面后端（缺少有效的 MSR_DESKTOP_TOKEN）。')

    from dotenv import load_dotenv

    config_file = os.environ.get('MSR_CONFIG_FILE')
    if config_file:
        load_dotenv(config_file)
    elif not getattr(sys, 'frozen', False):
        load_dotenv(Path(__file__).resolve().parents[1] / '.env')

    from nicegui import app, ui
    from web import create_page
    from utils.api_settings import APISettings

    settings = APISettings(Path(config_file) if config_file else Path(__file__).resolve().parents[1] / '.env')
    app.add_middleware(DesktopAuth, token=token, origin=f'http://127.0.0.1:{args.port}')

    @app.get('/desktop/health')
    def health():
        return {'application': 'mini-six-ren-desktop', 'protocol': 1}

    @ui.page('/', dark=False)
    def desktop_page():
        return create_page(api_settings=settings)

    @ui.page('/settings', dark=False)
    def settings_page():
        return create_page(api_settings=settings, show_settings=True)

    threading.Thread(target=exit_when_parent_closes_pipe, daemon=True).start()
    ui.run(host='127.0.0.1', port=args.port, title='小六壬 · 三传',
           show=False, reload=False, dark=False, favicon='☯', language='zh-CN',
           show_welcome_message=False)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
