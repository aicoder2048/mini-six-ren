"""Desktop credentials: independent preference table, persistence and UI contracts."""
import asyncio
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ai_agent import DivinationAgent, SupportedModels
from utils.api_settings import APISettings, APISettingsError

OPENAI = SupportedModels.OPENAI_GPT61_SOL
DEEPSEEK = SupportedModels.DEEPSEEK_FLASH


class SettingsPersistence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / '.env'

    def settings(self, environ=None):
        return APISettings(self.path, environ={} if environ is None else environ)

    def test_four_combinations_have_explicit_desktop_preference(self):
        for env, expected in [
            ({}, []),
            ({'DEEPSEEK_API_KEY': 'test-deepseek'}, [DEEPSEEK]),
            ({'OPENAI_API_KEY': 'test-openai'}, [OPENAI]),
            ({'DEEPSEEK_API_KEY': 'test-deepseek', 'OPENAI_API_KEY': 'test-openai'}, [OPENAI, DEEPSEEK]),
            ({'OPENAI_API_KEY': ' \t\n'}, []),
        ]:
            with self.subTest(keys=list(env)):
                settings = self.settings(env)
                self.assertEqual(settings.available_models, expected)
                self.assertEqual(settings.default_model, expected[0] if expected else None)
                self.assertEqual(settings.needs_onboarding, not bool(expected))

    def test_preserves_other_values_and_roundtrips_without_interpolation(self):
        self.path.write_text('# keep comment\nOTHER_SETTING="keep me"\n', encoding='utf-8')
        settings = self.settings()
        settings.save({OPENAI: '  test-$OPENAI_API_KEY-quoted\'value  ', DEEPSEEK: 'test-deepseek'})
        content = self.path.read_text(encoding='utf-8')
        self.assertIn('# keep comment', content)
        self.assertIn('OTHER_SETTING="keep me"', content)
        reloaded = self.settings()
        self.assertEqual(reloaded.key_for(OPENAI), "test-$OPENAI_API_KEY-quoted'value")
        self.assertEqual(reloaded.key_for(DEEPSEEK), 'test-deepseek')
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_file_and_explicit_deletion_override_inherited_environment(self):
        inherited = {'OPENAI_API_KEY': 'inherited-openai', 'DEEPSEEK_API_KEY': 'inherited-deepseek'}
        settings = self.settings(inherited)
        settings.save({OPENAI: 'saved-openai'})
        self.assertEqual(self.settings(inherited).key_for(OPENAI), 'saved-openai')
        self.assertEqual(self.settings(inherited).key_for(DEEPSEEK), 'inherited-deepseek')
        settings.save({OPENAI: '', DEEPSEEK: ''})
        reloaded = self.settings(inherited)
        self.assertEqual(reloaded.available_models, [])
        self.assertTrue(reloaded.needs_onboarding)

    def test_unchanged_values_and_skip_are_not_persisted_as_secrets(self):
        settings = self.settings({'DEEPSEEK_API_KEY': 'inherited'})
        settings.save({DEEPSEEK: None, OPENAI: None})
        self.assertFalse(self.path.exists())
        empty = self.settings()
        empty.dismiss_onboarding()
        self.assertFalse(empty.needs_onboarding)
        self.assertTrue(self.settings().needs_onboarding)

    def test_validation_and_write_failure_are_atomic_and_redacted(self):
        settings = self.settings()
        settings.save({DEEPSEEK: 'original'})
        before = self.path.read_bytes()
        for invalid in ['test-key\nINJECT=secret', 'test key', '秘密', 'x' * 513, 'test\x00key',
                        'fake' + chr(92), 'fake' + chr(92) * 2 + 'key']:
            with self.subTest(kind=repr(invalid[:4])), self.assertRaises(APISettingsError) as raised:
                settings.save({OPENAI: 'valid', DEEPSEEK: invalid})
            self.assertNotIn(invalid, str(raised.exception))
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(settings.available_models, [DEEPSEEK])
        with patch('utils.api_settings.os.replace', side_effect=OSError('secret-in-system-error')):
            with self.assertRaises(APISettingsError) as raised:
                settings.save({DEEPSEEK: 'replacement'})
        self.assertNotIn('secret-in-system-error', str(raised.exception))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(settings.key_for(DEEPSEEK), 'original')
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_accepted_ascii_roundtrips_next_to_deletion_and_readback_failure_is_atomic(self):
        settings = self.settings({'DEEPSEEK_API_KEY': 'inherited-deepseek'})
        for code in range(33, 127):
            if code == 92:  # dotenv cannot reliably delimit a quoted trailing backslash.
                continue
            key = 'test-' + chr(code) + '-key'
            with self.subTest(code=code):
                settings.save({OPENAI: key, DEEPSEEK: ''})
                reloaded = self.settings({'DEEPSEEK_API_KEY': 'inherited-deepseek'})
                self.assertEqual(reloaded.key_for(OPENAI), key)
                self.assertEqual(reloaded.key_for(DEEPSEEK), '')
        before = self.path.read_bytes()
        previous = settings.key_for(OPENAI)
        with patch('utils.api_settings.set_key'):
            with self.assertRaises(APISettingsError):
                settings.save({OPENAI: 'write-was-not-applied'})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(settings.key_for(OPENAI), previous)


class ExplicitProviderContracts(unittest.IsolatedAsyncioTestCase):
    async def test_official_provider_uses_explicit_snapshot_not_environment(self):
        for model, expected_name, expected_url in [
            (OPENAI, 'gpt-6.1-sol', 'https://api.openai.com/v1/'),
            (DEEPSEEK, 'deepseek-flash', 'https://api.deepseek.com/'),
        ]:
            with self.subTest(model=model), patch.dict(os.environ, {
                'OPENAI_API_KEY': 'wrong-openai', 'DEEPSEEK_API_KEY': 'wrong-deepseek',
                'OPENAI_BASE_URL': 'https://untrusted.invalid/v1',
            }), patch('ai_agent.load_dotenv') as load:
                agent = DivinationAgent(model, api_key='explicit-offline-key')
                load.assert_not_called()
                self.assertEqual(agent.agent.model.model_name, expected_name)
                self.assertEqual(str(agent.agent.model.client.base_url).rstrip('/'), expected_url.rstrip('/'))
                self.assertEqual(agent.agent.model.client.api_key, 'explicit-offline-key')
                from hand_technique import HandTechnique
                result = HandTechnique.predict(1, 2, 3)
                with patch.object(agent, '_stream_interpretation_web', new=AsyncMock(return_value='offline result')) as stream:
                    await agent.interpret_prediction_async(result.symbols, '准备求职')
                deps = stream.call_args.args[1]
                self.assertEqual(deps.api_key, 'explicit-offline-key')
                self.assertNotIn('explicit-offline-key', repr(deps))


class SettingsUI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = APISettings(Path(self.temp.name) / '.env', environ={})

    async def test_onboarding_save_refresh_and_cancel_do_not_clear_results(self):
        from nicegui import Client, ui
        from web import create_page
        with Client(ui.page('/settings-ui'), request=None):
            app = create_page(api_settings=self.settings)
            panel = app.api_settings_panel
            self.assertTrue(panel.dialog.value)
            self.assertEqual(app.model_select.value, 'local')
            self.assertTrue(all(not field.value for field in panel.key_inputs.values()))
            panel.skip()
            await app._perform_divination()
            result = app.divination_result
            app.question_input.value = '保留这个问题'
            app.open_api_settings()
            panel.key_inputs[DEEPSEEK].value = 'offline-deepseek'
            panel.save()
            self.assertFalse(panel.dialog.value)
            self.assertEqual(app.current_model, DEEPSEEK)
            self.assertEqual(app.model_select.value, DEEPSEEK.value)
            self.assertIs(app.divination_result, result)
            self.assertEqual(app.question_input.value, '保留这个问题')
            app.open_api_settings()
            self.assertEqual(panel.key_inputs[DEEPSEEK].value, '')
            self.assertIn('已配置', panel.provider_status[DEEPSEEK].text)
            panel.key_inputs[OPENAI].value = 'offline-openai'
            panel.save()
            self.assertEqual(app.current_model, OPENAI)
            app.open_api_settings()
            panel.key_inputs[OPENAI].value = 'do-not-save'
            panel.skip()
            self.assertEqual(panel.key_inputs[OPENAI].value, '')
            self.assertEqual(self.settings.key_for(OPENAI), 'offline-openai')
            self.assertEqual(panel.official_links[DEEPSEEK].props['href'], 'https://platform.deepseek.com/api_keys')
            self.assertEqual(panel.official_links[OPENAI].props['href'], 'https://platform.openai.com/api-keys')

    async def test_delete_failures_and_invalid_input_do_not_leak(self):
        from nicegui import Client, ui
        from web import create_page
        self.settings.save({OPENAI: 'existing-openai', DEEPSEEK: 'existing-deepseek'})
        with Client(ui.page('/settings-delete'), request=None):
            app = create_page(api_settings=self.settings)
            panel = app.api_settings_panel
            self.assertFalse(panel.dialog.value)
            app.open_api_settings()
            panel.key_inputs[OPENAI].value = 'a secret with spaces'
            panel.save()
            self.assertTrue(panel.dialog.value)
            self.assertNotIn('a secret with spaces', panel.error.text)
            self.assertEqual(self.settings.key_for(OPENAI), 'existing-openai')
            panel.key_inputs[OPENAI].value = ''
            panel.remove_checks[OPENAI].value = True
            panel.save()
            self.assertEqual(app.current_model, DEEPSEEK)
            app.open_api_settings()
            panel.remove_checks[DEEPSEEK].value = True
            panel.save()
            self.assertIsNone(app.current_model)
            self.assertEqual(app.model_select.value, 'local')

    async def test_running_request_blocks_settings_and_captures_credentials(self):
        from nicegui import Client, ui
        from web import create_page
        self.settings.save({DEEPSEEK: 'original-key'})
        with Client(ui.page('/settings-running'), request=None):
            app = create_page(api_settings=self.settings)
            app.question_input.value = '准备求职'

            async def interpret(symbols, question):
                app.open_api_settings()
                self.assertFalse(app.api_settings_panel.dialog.value)
                self.settings.save({DEEPSEEK: 'rotated-key'})
                return '离线解读'

            with patch('web.DivinationAgent') as factory:
                factory.return_value.interpret_prediction_async = AsyncMock(side_effect=interpret)
                await app._perform_divination()
                factory.assert_called_once_with(DEEPSEEK, api_key='original-key')
            self.assertEqual(app.ai_interpretation, '离线解读')

    async def test_desktop_provider_errors_do_not_echo_credentials(self):
        from nicegui import Client, ui
        from web import create_page
        self.settings.save({OPENAI: 'private-test-key'})
        with Client(ui.page('/settings-provider-error'), request=None):
            app = create_page(api_settings=self.settings)
            app.question_input.value = '准备求职'
            with patch('web.DivinationAgent', side_effect=RuntimeError('bad private-test-key')):
                await app._perform_divination()
            self.assertNotIn('private-test-key', app.error_message.text)
            self.assertIn('失败', app.error_message.text)
            self.assertIsNotNone(app.divination_result)

    async def test_public_web_has_no_settings_write_entry(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/public-web'), request=None) as client:
                app = create_page()
                self.assertIsNone(app.api_settings_panel)
                self.assertFalse(any('api-settings-button' in element.classes for element in client.elements.values()))


if __name__ == '__main__':
    unittest.main()
