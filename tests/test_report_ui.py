"""Desktop report controls use only the completed calculation's submitted snapshot."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from nicegui import Client, ui
from ai_agent import SupportedModels
from web import create_page
from reading import ReadingSession
from reading_fixtures import complete


class ReportUI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch('web.DivinationAgent.get_available_models', return_value=[]))

    async def test_web_has_no_report_menu_and_desktop_requires_completed_result(self):
        with Client(ui.page('/report-web'), request=None):
            self.assertIsNone(create_page().report_button)
        with Client(ui.page('/report-desktop'), request=None):
            app = create_page(desktop=True)
            self.assertFalse(app.report_button.enabled)
            with patch('web.ui.run_javascript', new=AsyncMock()) as run:
                await app._export_report('print')
                run.assert_not_awaited()
            await app._perform_divination()
            self.assertTrue(app.report_button.enabled)
            self.assertTrue(all(item.enabled for item in app.report_options))
            app._set_running(True)
            self.assertFalse(app.report_button.enabled)
            app._set_running(False)
            self.assertTrue(app.report_button.enabled)
            app.number_inputs[0].value = 0
            await app._perform_divination()
            self.assertFalse(app.report_button.enabled)

    async def test_snapshot_and_latest_success_are_exported_without_recalculation(self):
        with Client(ui.page('/report-snapshot'), request=None):
            app = create_page(desktop=True)
            app.question_input.value = '原问题'
            await app._perform_divination()
            app.reading_session = complete(ReadingSession.start(app.divination_result, '原问题'), answer='最新成功的回答')
            original = app.reading_session
            app.question_input.value = '未提交的新问题'
            app.number_inputs[0].value = 8

            async def run(script, **_kwargs):
                self.assertFalse(app.report_button.enabled)
                self.assertTrue(app.is_exporting)
                self.assertIn(json.dumps('原问题', ensure_ascii=True)[1:-1], script)
                self.assertIn(json.dumps('最新成功的回答', ensure_ascii=True)[1:-1], script)
                self.assertNotIn(json.dumps('未提交的新问题', ensure_ascii=True)[1:-1], script)
                await app._export_report('wechat')  # Duplicate request is ignored.
                return {'status': 'saved'}

            with patch('web.ui.run_javascript', new=AsyncMock(side_effect=run)) as request, \
                 patch('web.HandTechnique.predict', side_effect=AssertionError('recalculated')):
                await app._export_report('print')
                request.assert_awaited_once()
            self.assertIs(app.reading_session, original)
            self.assertEqual(app.report_status.text, 'PDF 报告已保存。')
            self.assertTrue(app.report_button.enabled)

    async def test_ai_failure_exports_local_facts_and_failed_supplement_keeps_latest_reading(self):
        with Client(ui.page('/report-ai-failure'), request=None):
            app = create_page(desktop=True)
            app.current_model = SupportedModels.OPENAI_GPT61_SOL
            app.question_input.value = '本次问题'
            with patch('web.DivinationAgent.__init__', return_value=None), \
                 patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=RuntimeError('offline'))):
                await app._perform_divination()
                self.assertTrue(app.report_button.enabled)
                self.assertIsNone(app.reading_session.reading)
                app.reading_session = complete(app.reading_session, answer='最近成功解读')
                original = app.reading_session
                app.supplement_input.value = '未接纳的补充'
                await app._submit_supplement()
            self.assertIs(app.reading_session, original)
            self.assertTrue(app.report_button.enabled)
            with patch('web.ui.run_javascript', new=AsyncMock(return_value={'status': 'saved'})) as request:
                await app._export_report('wechat')
            script = request.call_args.args[0]
            self.assertIn(json.dumps('最近成功解读', ensure_ascii=True)[1:-1], script)
            self.assertNotIn(json.dumps('未接纳的补充', ensure_ascii=True)[1:-1], script)

    async def test_cancel_error_and_transport_failure_preserve_results_and_allow_retry(self):
        with Client(ui.page('/report-errors'), request=None):
            app = create_page(desktop=True)
            await app._perform_divination()
            original = app.divination_result
            for result, expected in [({'status': 'cancelled'}, '已取消'), ({'status': 'error'}, '保存失败'),
                                     ({'status': 'busy'}, '正在导出'), ({'status': 'error', 'code': 'layout'}, '请选择微信版'), (None, '保存失败')]:
                with patch('web.ui.run_javascript', new=AsyncMock(return_value=result)):
                    await app._export_report('wechat')
                self.assertIn(expected, app.report_status.text)
                self.assertIs(app.divination_result, original)
                self.assertTrue(app.report_button.enabled)
            with patch('web.ui.run_javascript', new=AsyncMock(side_effect=TimeoutError)):
                await app._export_report('print')
            self.assertIn('导出失败', app.report_status.text)
            self.assertTrue(app.report_button.enabled)
            self.assertFalse(app.is_exporting)


if __name__ == '__main__':
    unittest.main()
