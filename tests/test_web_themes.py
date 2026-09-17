import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from web import THEMES, DEFAULT_THEME, THEME_DIR, ELEMENT_KEYS, Theme, create_page
from hand_technique import HandTechnique


class ThemeRegistry(unittest.TestCase):
    def test_default_theme_is_current_paper_ui(self):
        self.assertIs(THEMES[0], DEFAULT_THEME)
        self.assertEqual(DEFAULT_THEME.id, 'paper')
        self.assertIsNone(DEFAULT_THEME.stylesheet)
        self.assertEqual(len({theme.id for theme in THEMES}), len(THEMES))

    def test_theme_constants_reject_values_unsafe_for_markup(self):
        for bad in [dict(id='Night'), dict(id='night css'), dict(label='星"夜'), dict(description='a"b')]:
            fields = dict(id='night', label='星夜', description='深空', stylesheet='night.css') | bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Theme(**fields)

    def test_theme_stylesheets_only_target_their_own_skin(self):
        # 每个主题文件的每条规则都以 html[data-theme="<id>"] 开头，切换后不会泄漏到其他皮肤。
        for theme in THEMES[1:]:
            css = (THEME_DIR / theme.stylesheet).read_text(encoding='utf-8')
            prefix = f'html[data-theme="{theme.id}"]'
            with self.subTest(theme=theme.id):
                for line in css.splitlines():
                    stripped = line.strip()
                    if stripped.startswith('@keyframes'):
                        self.assertTrue(stripped.split()[1].startswith(f'{theme.id}-'), f'{theme.id}: {stripped[:40]}')
                    if '{' not in stripped or stripped.startswith(('/*', '@keyframes', '@media')):
                        continue
                    selectors = stripped.split('{', 1)[0].split(',')
                    for selector in selectors:
                        self.assertTrue(selector.strip().startswith(prefix), f'{theme.id}: {selector.strip()}')

    def test_theme_script_is_safe_to_inline_and_exposes_runtime(self):
        script = (THEME_DIR / 'theme.js').read_text(encoding='utf-8')
        self.assertIn('window.msrTheme', script)
        self.assertNotIn('</script>', script)


class ThemePage(unittest.IsolatedAsyncioTestCase):
    async def test_page_injects_assets_and_client_side_switcher(self):
        from nicegui import Client, ui
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/themes'), request=None) as client:
                create_page()
                head = client._head_html  # NiceGUI 没有公开的 head 读取接口
                self.assertIn(json.dumps([theme.id for theme in THEMES], ensure_ascii=False), head)
                self.assertIn('window.msrTheme', head)
                for theme in THEMES[1:]:
                    self.assertIn(f'html[data-theme="{theme.id}"]', head)
                swatches = [element for element in client.elements.values() if 'theme-swatch' in element.classes]
                self.assertEqual([swatch.props['data-theme-id'] for swatch in swatches], [theme.id for theme in THEMES])
                self.assertEqual([swatch.props['aria-pressed'] for swatch in swatches], ['true'] + ['false'] * (len(THEMES) - 1))
                for swatch in swatches:
                    self.assertEqual(swatch.props['type'], 'button')
                    self.assertEqual(swatch.props['aria-label'], next(t.label for t in THEMES if t.id == swatch.props['data-theme-id']))
                    listeners = list(swatch._event_listeners.values())
                    self.assertEqual(len(listeners), 1)
                    self.assertIsNone(listeners[0].handler)
                    self.assertIn(f'msrTheme.apply({json.dumps(swatch.props["data-theme-id"])})', listeners[0].js_handler)

    async def test_results_expose_five_element_hooks_for_skins(self):
        from nicegui import Client, ui
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/theme-hooks'), request=None) as client:
                app = create_page()
                await app._perform_divination()
                expected = [ELEMENT_KEYS[symbol.element.name] for symbol in HandTechnique.predict(1, 2, 3).symbols]
                cards = [element for element in client.elements.values() if 'transmission-card' in element.classes]
                self.assertEqual([card.props['data-element'] for card in cards], expected)
                badges = [element for element in client.elements.values() if 'element-badge' in element.classes]
                self.assertEqual([[c for c in badge.classes if c.startswith('element-') and c != 'element-badge'] for badge in badges],
                                 [[f'element-{key}'] for key in expected])


@unittest.skipUnless(shutil.which('node'), 'node 不可用时跳过脚本逻辑测试')
class ThemeScriptLogic(unittest.TestCase):
    """用最小 DOM 桩在 node 中执行 theme.js，验证读取、回落、持久化与效果启停清理。"""

    HARNESS = r'''
    const fs = require('fs');
    const [scriptPath, search, stored] = process.argv.slice(2);
    const store = {}; if (stored) store['msr-theme'] = stored;
    const docListeners = {}, winListeners = {}, styleVars = {}, bodyChildren = [];
    const html = { dataset: {}, classList: { add() {}, remove() {} },
      style: { setProperty(k, v) { styleVars[k] = v; }, removeProperty(k) { delete styleVars[k]; } } };
    const body = { appendChild(el) { bodyChildren.push(el); } };
    const ctx = new Proxy({}, { get: () => () => ({ addColorStop() {} }) });
    const makeCanvas = () => ({ style: {}, setAttribute() {}, getContext: () => ctx,
      remove() { bodyChildren.splice(bodyChildren.indexOf(this), 1); } });
    const on = (map) => (type, fn) => { (map[type] = map[type] || []).push(fn); };
    const off = (map) => (type, fn) => { map[type] = (map[type] || []).filter(f => f !== fn); };
    global.window = global;
    global.location = { search };
    global.localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } };
    global.matchMedia = () => ({ matches: false });
    global.MutationObserver = class { observe() {} disconnect() {} };
    global.innerWidth = 800; global.innerHeight = 600; global.devicePixelRatio = 1;
    global.requestAnimationFrame = () => 1; global.cancelAnimationFrame = () => {};
    global.addEventListener = on(winListeners); global.removeEventListener = off(winListeners);
    global.document = { documentElement: html, body, hidden: false,
      createElement: () => makeCanvas(), querySelectorAll: () => [], querySelector: () => null,
      addEventListener: on(docListeners), removeEventListener: off(docListeners) };
    global.MSR_THEME_IDS = ['paper', 'night', 'ink', 'neon']; global.MSR_THEME_DEFAULT = 'paper';
    new Function(fs.readFileSync(scriptPath, 'utf8'))();
    const count = (map, type) => (map[type] || []).length;
    const snapshot = () => ({ theme: html.dataset.theme, stored: store['msr-theme'] || null, canvases: bodyChildren.length,
      listeners: { resize: count(winListeners, 'resize'), pointermove: count(winListeners, 'pointermove'), visibilitychange: count(docListeners, 'visibilitychange') },
      vars: Object.keys(styleVars).sort() });
    const beforeLoad = html.dataset.theme;
    (docListeners.DOMContentLoaded || []).forEach(fn => fn());
    const afterLoad = snapshot();
    msrTheme.apply('night');
    (winListeners.pointermove || []).forEach(fn => fn({ clientX: 10, clientY: 20 }));
    const afterNight = snapshot();
    msrTheme.apply('bogus');
    const afterBogus = snapshot();
    msrTheme.apply('ink');
    const afterInk = snapshot();
    process.stdout.write(JSON.stringify({ beforeLoad, afterLoad, afterNight, afterBogus, afterInk, ids: msrTheme.ids }));
    process.exit(0);  // theme.js 的兜底定时器会让 node 事件循环多等 15 秒
    '''

    def run_script(self, search, stored):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / 'harness.js'
            harness.write_text(self.HARNESS, encoding='utf-8')
            output = subprocess.run(['node', str(harness), str(THEME_DIR / 'theme.js'), search, stored],
                                    check=True, capture_output=True, text=True).stdout
        return json.loads(output)

    def test_stored_theme_applies_before_paint_and_starts_its_effect(self):
        result = self.run_script('', 'night')
        self.assertEqual(result['beforeLoad'], 'night')
        self.assertEqual(result['afterLoad']['theme'], 'night')
        self.assertEqual(result['afterLoad']['stored'], 'night')
        self.assertEqual(result['afterLoad']['canvases'], 1)
        self.assertEqual(result['ids'], ['paper', 'night', 'ink', 'neon'])

    def test_url_parameter_wins_and_is_remembered(self):
        result = self.run_script('?theme=neon', 'night')
        self.assertEqual(result['beforeLoad'], 'neon')
        self.assertEqual((result['afterLoad']['theme'], result['afterLoad']['stored']), ('neon', 'neon'))

    def test_invalid_values_fall_back_to_default_and_apply_persists(self):
        result = self.run_script('?theme=hacker', 'nonsense')
        self.assertEqual(result['beforeLoad'], 'paper')
        self.assertEqual((result['afterLoad']['theme'], result['afterLoad']['stored']), ('paper', 'nonsense'))  # 加载不改写存储
        self.assertEqual((result['afterBogus']['theme'], result['afterBogus']['stored']), ('paper', 'paper'))
        self.assertEqual((result['afterInk']['theme'], result['afterInk']['stored']), ('ink', 'ink'))

    def test_night_effect_starts_on_activation_and_cleans_up_on_switch(self):
        result = self.run_script('', '')
        self.assertEqual(result['afterLoad']['canvases'], 0)
        night = result['afterNight']
        self.assertEqual(night['canvases'], 1)
        self.assertEqual(night['listeners'], {'resize': 1, 'pointermove': 1, 'visibilitychange': 1})
        self.assertEqual(night['vars'], ['--msr-mx', '--msr-my'])
        gone = result['afterBogus']
        self.assertEqual((gone['canvases'], gone['listeners'], gone['vars']),
                         (0, {'resize': 0, 'pointermove': 0, 'visibilitychange': 0}, []))


if __name__ == '__main__':
    unittest.main()
