import asyncio
from contextlib import redirect_stderr
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from desktop_server import DesktopAuth, parse_args


class DesktopAuthTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, kind='http', token=None, origin=None, path='/'):
        received = []

        async def downstream(scope, receive, send):
            received.append('downstream')

        headers = []
        if token is not None:
            headers.append((b'x-mini-six-ren-token', token.encode()))
        if origin is not None:
            headers.append((b'origin', origin.encode()))
        scope = {'type': kind, 'headers': headers, 'path': path}

        async def send(message):
            received.append(message)

        await DesktopAuth(downstream, token='secret', origin='http://127.0.0.1:1234')(
            scope, lambda: asyncio.sleep(0), send)
        return received

    async def test_http_and_assets_require_token(self):
        for path in ['/', '/desktop/health', '/_nicegui/2.0/static/nicegui.js']:
            for token in [None, '', 'wrong', '秘密']:
                with self.subTest(path=path, token=token):
                    messages = await self.request(token=token, path=path)
                    self.assertEqual(messages[0]['status'], 403)
            self.assertEqual(await self.request(token='secret', path=path), ['downstream'])

    async def test_websocket_requires_token_and_same_origin(self):
        for token, origin in [(None, None), ('wrong', None), ('secret', 'https://evil.example')]:
            messages = await self.request(kind='websocket', token=token, origin=origin)
            self.assertEqual(messages, [{'type': 'websocket.close', 'code': 4403}])
        self.assertEqual(await self.request(kind='websocket', token='secret', origin='http://127.0.0.1:1234'),
                         ['downstream'])

    async def test_cross_origin_http_is_rejected_even_with_token(self):
        messages = await self.request(token='secret', origin='http://127.0.0.1:9999')
        self.assertEqual(messages[0]['status'], 403)

    async def test_lifespan_is_not_authenticated(self):
        self.assertEqual(await self.request(kind='lifespan'), ['downstream'])


class DesktopArguments(unittest.TestCase):
    def test_valid_port(self):
        self.assertEqual(parse_args(['--port', '1234']).port, 1234)

    def test_invalid_port_is_rejected(self):
        for port in ['0', '-1', '65536']:
            with self.subTest(port=port), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parse_args(['--port', port])


class DesktopServerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.log = tempfile.TemporaryFile(mode='w+b')
        cls.token = secrets.token_hex(32)
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1', 0))
            cls.port = reserved.getsockname()[1]
        cls.origin = f'http://127.0.0.1:{cls.port}'
        entry = Path(__file__).resolve().parents[1] / 'src' / 'desktop_server.py'
        cls.process = subprocess.Popen([sys.executable, str(entry), '--port', str(cls.port)],
                                       cwd=cls.temp.name, stdin=subprocess.PIPE, stdout=cls.log, stderr=cls.log,
                                       env={**os.environ, 'MSR_DESKTOP_TOKEN': cls.token,
                                            'MSR_CONFIG_FILE': str(Path(cls.temp.name) / '.env'),
                                            'OPENAI_API_KEY': '', 'DEEPSEEK_API_KEY': ''})
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if cls.get('/desktop/health')[0] == 200:
                    return
            except (URLError, OSError):
                pass
            if cls.process.poll() is not None:
                break
            time.sleep(0.1)
        cls.process.kill()
        cls.process.wait(timeout=5)
        cls.log.seek(0)
        error = cls.log.read().decode(errors='replace')
        cls.log.close()
        cls.temp.cleanup()
        raise AssertionError(f'桌面后端未就绪：{error}')

    @classmethod
    def tearDownClass(cls):
        if cls.process.poll() is None:
            cls.process.terminate()
            cls.process.wait(timeout=5)
        cls.process.stdin.close()
        cls.log.close()
        cls.temp.cleanup()

    @classmethod
    def get(cls, path, *, authenticated=True, origin=None):
        headers = {'x-mini-six-ren-token': cls.token} if authenticated else {}
        if origin:
            headers['Origin'] = origin
        try:
            with urlopen(Request(cls.origin + path, headers=headers), timeout=2) as response:
                return response.status, response.read()
        except HTTPError as response:
            return response.code, response.read()

    def test_health_page_and_static_assets_are_authenticated(self):
        for path in ['/', '/settings', '/desktop/health', '/_nicegui_ws/socket.io/?EIO=4&transport=polling']:
            with self.subTest(path=path):
                self.assertEqual(self.get(path, authenticated=False)[0], 403)
                self.assertEqual(self.get(path, origin='https://evil.example')[0], 403)
        status, body = self.get('/desktop/health')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'application': 'mini-six-ren-desktop', 'protocol': 1})
        status, page = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('一念起，观三传。', page.decode())
        self.assertIn('window.msrTheme', page.decode())
        self.assertNotIn(self.token.encode(), page)
        status, settings_page = self.get('/settings')
        self.assertEqual(status, 200)
        self.assertIn('设置 API Key', settings_page.decode())
        self.assertIn('https://platform.deepseek.com/api_keys', settings_page.decode())
        self.assertNotIn(self.token.encode(), settings_page)

    def test_websocket_rejects_missing_token_and_wrong_origin(self):
        from websockets.exceptions import InvalidStatus
        from websockets.sync.client import connect
        uri = f'ws://127.0.0.1:{self.port}/_nicegui_ws/socket.io/?EIO=4&transport=websocket'
        for headers, origin in [({}, self.origin), ({'x-mini-six-ren-token': self.token}, 'https://evil.example')]:
            with self.subTest(origin=origin), self.assertRaises(InvalidStatus) as raised:
                connect(uri, origin=origin, additional_headers=headers, open_timeout=2)
            self.assertEqual(raised.exception.response.status_code, 403)
        with connect(uri, origin=self.origin, additional_headers={'x-mini-six-ren-token': self.token}, open_timeout=2) as ws:
            # Engine.IO 的服务端 open 包，证明鉴权后 WebSocket 确实可用。
            self.assertTrue(ws.recv(timeout=2).startswith('0{'))

    def test_z_parent_pipe_eof_stops_orphan_backend(self):
        self.process.stdin.close()
        self.assertEqual(self.process.wait(timeout=5), 0)


if __name__ == '__main__':
    unittest.main()
