"""Reading tabs keep local results and optional interpretation in one panel."""
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ai_agent import SupportedModels
from nicegui import Client, ui
from web import create_page
from reading_fixtures import complete


class ReadingTabs(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch('web.DivinationAgent.__init__', return_value=None))

    def labels(self, area):
        return [element.text for element in area.descendants() if hasattr(element, 'text')]

    def assert_status(self, app, state, text):
        self.assertEqual(app.interpretation_status.props['data-state'], state)
        self.assertEqual(app.interpretation_status.text, text)

    async def test_adjacent_tabs_own_separate_result_areas(self):
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/reading-tabs'), request=None):
                app = create_page()
                tabs = list(app.reading_tabs.default_slot.children)
                self.assertEqual([tab.props['label'] for tab in tabs], ['三传观照', '三传解读'])
                self.assertEqual(app.reading_tabs.value, 'observation')
                self.assert_status(app, 'idle', '未生成')
                self.assertIs(app.interpretation_status.parent_slot.parent, tabs[1])
                self.assertEqual(app.interpretation_status.props['role'], 'status')
                self.assertEqual(app.interpretation_status.props['aria-live'], 'polite')
                self.assertEqual(app.result_area.parent_slot.parent.props['name'], 'observation')
                self.assertEqual(app.ai_result_area.parent_slot.parent.props['name'], 'interpretation')
                self.assertTrue(any('填写问题' in text for text in self.labels(app.ai_result_area)))

    async def test_local_only_keeps_interpretation_guidance(self):
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/reading-local'), request=None):
                app = create_page()
                app.reading_tabs.set_value('interpretation')
                await app._perform_divination()
                self.assertEqual(app.reading_tabs.value, 'observation')
                self.assertIsNotNone(app.divination_result)
                self.assert_status(app, 'idle', '未生成')
                self.assertTrue(any('填写问题' in text for text in self.labels(app.ai_result_area)))
                app.reading_tabs.set_value('interpretation')
                self.assertEqual(len([e for e in app.result_area.descendants() if 'transmission-card' in e.classes]), 3)

    async def test_loading_success_and_next_run_clear_old_interpretation(self):
        model = SupportedModels.OPENAI_GPT61_SOL
        with patch('web.DivinationAgent.get_available_models', return_value=[model]):
            with Client(ui.page('/reading-success'), request=None):
                app = create_page()
                app.question_input.value = '准备求职'

                async def interpret(session, *, supplement=None):
                    self.assert_status(app, 'loading', '解读中…')
                    self.assertIsNotNone(app.divination_result)
                    self.assertTrue(any('AI将结合' in text for text in self.labels(app.ai_result_area)))
                    app.reading_tabs.set_value('interpretation')
                    return complete(session, answer='先核实岗位条件。')

                with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=interpret)) as request:
                    await app._perform_divination()
                    request.assert_awaited_once()
                self.assertEqual(app.reading_tabs.value, 'interpretation')
                self.assert_status(app, 'ready', '可查看')
                self.assertEqual(app.reading_session.reading.answer, '先核实岗位条件。')
                self.assertIn('三传解读', self.labels(app.ai_result_area))
                self.assertNotIn('AI 三传解读', self.labels(app.ai_result_area))
                self.assertEqual(len([e for e in app.ai_result_area.descendants() if 'ai-interpretation' in e.classes]), 1)
                app.current_model = None
                await app._perform_divination()
                self.assertEqual(app.reading_tabs.value, 'observation')
                self.assertIsNone(app.reading_session)
                self.assert_status(app, 'idle', '未生成')
                self.assertFalse(any('ai-interpretation' in e.classes for e in app.ai_result_area.descendants()))
                self.assertTrue(any('填写问题' in text for text in self.labels(app.ai_result_area)))

    async def test_failure_has_tab_guidance_and_keeps_local_results(self):
        with patch('web.DivinationAgent.get_available_models', return_value=[SupportedModels.OPENAI_GPT61_SOL]):
            with Client(ui.page('/reading-failure'), request=None):
                app = create_page()
                app.question_input.value = '准备求职'
                with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=RuntimeError('offline'))):
                    await app._perform_divination()
                self.assertIsNotNone(app.divination_result)
                self.assertIsNone(app.reading_session.reading)
                self.assert_status(app, 'error', '失败')
                self.assertTrue(any('失败' in text for text in self.labels(app.ai_result_area)))
                self.assertNotIn('offline', app.error_message.text)
                self.assertTrue(app.submit_button.enabled)

    async def test_blank_question_does_not_request_interpretation(self):
        with patch('web.DivinationAgent.get_available_models', return_value=[SupportedModels.OPENAI_GPT61_SOL]):
            with Client(ui.page('/reading-blank'), request=None):
                app = create_page()
                app.question_input.value = '  '
                with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock()) as request:
                    await app._perform_divination()
                    request.assert_not_awaited()
                self.assert_status(app, 'idle', '未生成')
                self.assertTrue(any('填写问题' in text for text in self.labels(app.ai_result_area)))

    async def test_failed_request_retries_and_ready_state_does_not_steal_tab(self):
        with patch('web.DivinationAgent.get_available_models', return_value=[SupportedModels.OPENAI_GPT61_SOL]):
            with Client(ui.page('/reading-status-retry'), request=None):
                app = create_page()
                app.question_input.value = '准备求职'
                with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=RuntimeError('offline'))):
                    await app._perform_divination()
                self.assert_status(app, 'error', '失败')

                async def retry(session, *, supplement=None):
                    self.assert_status(app, 'loading', '解读中…')
                    app.reading_tabs.set_value('interpretation')
                    app.reading_tabs.set_value('observation')
                    self.assert_status(app, 'loading', '解读中…')
                    await app._perform_divination()  # 重复点击不能重置正在进行的状态。
                    self.assert_status(app, 'loading', '解读中…')
                    return complete(session, answer='先核实岗位条件。')

                with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=retry)) as request:
                    await app._retry_reading()
                    request.assert_awaited_once()
                self.assert_status(app, 'ready', '可查看')
                self.assertEqual(app.reading_tabs.value, 'observation')
                self.assertEqual(app.error_message.text, '')
                app.number_inputs[0].value = 0
                await app._perform_divination()
                self.assert_status(app, 'idle', '未生成')
                self.assertIsNone(app.reading_session)

    async def test_nullable_follow_up_does_not_add_generic_question(self):
        with patch('web.DivinationAgent.get_available_models', return_value=[SupportedModels.OPENAI_GPT61_SOL]):
            with Client(ui.page('/reading-no-follow-up'), request=None):
                app = create_page()
                app.question_input.value = '准备求职'

                async def respond(session, *, supplement=None):
                    return complete(session, follow_up=None)

                with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=respond)):
                    await app._perform_divination()
                self.assert_status(app, 'ready', '可查看')
                self.assertFalse(app.follow_up_label.visible)
                self.assertEqual(app.follow_up_label.text, '')


if __name__ == '__main__':
    unittest.main()
