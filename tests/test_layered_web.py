"""NiceGUI lifecycle tests for same-snapshot updates and page ownership."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ai_agent import SupportedModels
from hand_technique import HandTechnique
from nicegui import Client, ui
from reading import ReadingSession
from reading_fixtures import complete
from web import create_page

MODEL = SupportedModels.OPENAI_GPT61_SOL


class LayeredWeb(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch('web.DivinationAgent.get_available_models', return_value=[MODEL]))
        self.enterContext(patch('web.DivinationAgent.__init__', return_value=None))

    def labels(self, area):
        return [e.text for e in area.descendants() if hasattr(e, 'text')]

    async def ready(self, app, **changes):
        app.question_input.value = '原问题'

        async def respond(session, *, supplement=None):
            return complete(session, supplement=supplement, **changes)

        with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=respond)):
            await app._perform_divination()
        self.assertIsNotNone(app.reading_session.reading)
        return app.reading_session

    async def test_text_first_collapsed_rationale_and_visible_risk(self):
        with Client(ui.page('/layered-view'), request=None):
            app = create_page()
            session = await self.ready(app, answer='<script>alert(1)</script>', caution='请及时就医。')
            elements = list(app.ai_result_area.descendants())
            labels = self.labels(app.ai_result_area)
            self.assertIn(session.reading.answer, labels)
            self.assertLess(labels.index(session.reading.answer), labels.index('下一步'))
            rationale = next(e for e in elements if 'reading-rationale' in e.classes)
            self.assertFalse(rationale.value)
            self.assertIn(session.reading.rationale, self.labels(rationale))
            self.assertTrue(any('金克木' in value for value in self.labels(rationale)))
            self.assertIn('请及时就医。', labels)
            caution = next(e for e in elements if getattr(e, 'text', '') == '请及时就医。')
            self.assertNotIn(caution, list(rationale.descendants()))
            self.assertFalse(any(e.tag in ('q-markdown', 'script') for e in elements))
            self.assertIn(session.reading.follow_up, self.labels(app.supplement_area))
            self.assertEqual(app.reading_tabs.value, 'observation')

    async def test_supplement_failure_preserves_input_answer_and_snapshot_then_retries(self):
        with Client(ui.page('/layered-supplement'), request=None):
            app = create_page()
            base = await self.ready(app)
            app.question_input.value = '未提交的问题'
            app.number_inputs[0].value = 9
            app.supplement_input.value = '新的情况'
            with patch('web.HandTechnique.predict', side_effect=AssertionError('recalculated')), \
                 patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=RuntimeError('raw secret'))):
                await app._submit_supplement()
            self.assertIs(app.reading_session, base)
            self.assertEqual(app.supplement_input.value, '新的情况')
            self.assertEqual(app.interpretation_status.props['data-state'], 'ready')
            self.assertEqual(app.error_message.text, '')
            self.assertIn('已有解读已保留', app.supplement_error.text)
            self.assertNotIn('raw secret', app.supplement_error.text)
            self.assertIn(base.reading.answer, self.labels(app.ai_result_area))

            async def respond(session, *, supplement=None):
                self.assertIs(session, base)
                self.assertEqual(session.snapshot.question, '原问题')
                self.assertEqual(supplement, '新的情况')
                self.assertFalse(app.submit_button.enabled)
                return complete(session, supplement=supplement, answer='更新后回答')

            with patch('web.HandTechnique.predict', side_effect=AssertionError('recalculated')), \
                 patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=respond)) as request:
                await app._submit_supplement()
                request.assert_awaited_once()
            self.assertIs(app.reading_session.snapshot, base.snapshot)
            self.assertEqual(app.reading_session.supplements, ('新的情况',))
            self.assertEqual(app.supplement_input.value, '')
            self.assertEqual(app.supplement_error.text, '')
            self.assertTrue(app.submit_button.enabled)
            self.assertEqual(app.divination_result, HandTechnique.predict(1, 2, 3))

    async def test_initial_failure_retry_ignores_unsubmitted_form(self):
        with Client(ui.page('/layered-initial-retry'), request=None):
            app = create_page()
            app.question_input.value = '原问题'
            with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=RuntimeError('secret'))):
                await app._perform_divination()
            base = app.reading_session
            self.assertIsNotNone(base)
            self.assertIsNone(base.reading)
            self.assertTrue(app.retry_button.visible)
            app.question_input.value = 'changed'
            app.number_inputs[0].value = 8

            async def respond(session, *, supplement=None):
                self.assertIs(session, base)
                app.reading_tabs.set_value('interpretation')
                return complete(session)

            with patch('web.HandTechnique.predict', side_effect=AssertionError('recalculated')), \
                 patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=respond)):
                await app._retry_reading()
            self.assertIs(app.reading_session.snapshot, base.snapshot)
            self.assertEqual(app.reading_tabs.value, 'interpretation')
            self.assertEqual(app.error_message.text, '')
            self.assertFalse(app.retry_button.visible)

    async def test_limits_new_start_and_duplicate_submission(self):
        with Client(ui.page('/layered-limits'), request=None):
            app = create_page()
            base = await self.ready(app)
            for invalid in [' ', '字' * 1001]:
                app.supplement_input.value = invalid
                with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock()) as request:
                    await app._submit_supplement()
                    request.assert_not_awaited()
                self.assertEqual(app.supplement_input.value, invalid)
            entered, release = asyncio.Event(), asyncio.Event()

            async def respond(session, *, supplement=None):
                entered.set()
                await release.wait()
                return complete(session, supplement=supplement)

            app.supplement_input.value = '一次'
            with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=respond)) as request:
                task = asyncio.create_task(app._submit_supplement())
                await asyncio.wait_for(entered.wait(), 2)
                self.assertIs(app.reading_session, base)
                self.assertIn(base.reading.answer, self.labels(app.ai_result_area))
                await app._submit_supplement()
                await app._retry_reading()
                await app._perform_divination()
                self.assertEqual(request.await_count, 1)
                release.set()
                await task
            session = app.reading_session
            for i in range(4):
                session = complete(session, supplement=f'第{i + 2}次')
            app.reading_session = session
            app._sync_reading_controls()
            self.assertFalse(app.supplement_button.enabled)
            app.supplement_input.value = '第六次'
            with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock()) as request:
                await app._submit_supplement()
                request.assert_not_awaited()
            self.assertIs(app.reading_session, session)
            self.assertIn('5', app.supplement_error.text)
            app.current_model = None
            await app._perform_divination()
            self.assertIsNone(app.reading_session)
            self.assertEqual(app.supplement_input.value, '')
            self.assertFalse(app.supplement_area.visible)

    async def test_pages_isolate_sessions_and_late_result_cannot_publish(self):
        one_client = Client(ui.page('/layered-one'), request=None)
        two_client = Client(ui.page('/layered-two'), request=None)
        with one_client:
            one = create_page()
            await self.ready(one)
        with two_client:
            two = create_page()
            await self.ready(two, answer='第二页')
        untouched = two.reading_session
        with one_client:
            original = one.reading_session
            replacement = ReadingSession.start(HandTechnique.predict(9, 2, 3), '另一课')

            async def stale(session, *, supplement=None):
                self.assertIs(session, original)
                one.reading_session = replacement
                return complete(session, supplement=supplement, answer='迟到回答')

            one.supplement_input.value = '待提交'
            with patch('web.DivinationAgent.interpret_prediction_async', new=AsyncMock(side_effect=stale)):
                await one._submit_supplement()
            self.assertIs(one.reading_session, replacement)
            self.assertNotIn('迟到回答', self.labels(one.ai_result_area))
            self.assertEqual(one.supplement_input.value, '待提交')
        self.assertIs(two.reading_session, untouched)
        self.assertIn('第二页', self.labels(two.ai_result_area))


if __name__ == '__main__':
    unittest.main()
