import sys
import unittest
import asyncio
import io
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch, AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from utils.bazi_calculator import calculate_bazi, analyze_day_master_strength
from web import DivinationWebApp
from utils.calendar_converter import solar_to_lunar, lunar_to_solar, date_to_numbers
from utils.validation import validate_numbers, parse_datetime, normalize_gender
from utils.stroke_count import get_stroke_counts
from hand_technique import HandTechnique
import cli


class ReviewRegressions(unittest.TestCase):
    def test_day_branch_advances_across_month(self):
        branches = '子丑寅卯辰巳午未申酉戌亥'
        before = calculate_bazi(2026, 1, 31, 12, 0)['day'][1]
        after = calculate_bazi(2026, 2, 1, 12, 0)['day'][1]
        self.assertEqual((branches.index(before) + 1) % 12, branches.index(after))

    def test_male_input_uses_male_analysis(self):
        self.assertIn('男性', analyze_day_master_strength({'day': '甲子'}, 'M'))

    def test_web_date_uses_lunar_month_and_twelve_hours(self):
        app = DivinationWebApp.__new__(DivinationWebApp)
        self.assertEqual(app._validate_date_time('2026-09-15', '12:00'),
                         (True, '', [8, 5, 7]))

    def test_fractional_numbers_rejected(self):
        app = DivinationWebApp.__new__(DivinationWebApp)
        self.assertFalse(app._validate_numbers(1.5, 2, 3)[0])

    def test_no_credentials_still_builds_inputs(self):
        from nicegui import Client, ui
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/offline-test'), request=None):
                app = DivinationWebApp()
                app.create_ui()
                self.assertEqual(len(app.number_inputs), 3)

    def test_calendar_reference_pillars(self):
        # Published reference fixtures: 6tail/lunar-python/test/EightCharTest.py.
        for inputs, expected in [
            ((2005, 12, 23, 8, 37), ('乙酉', '戊子', '辛巳', '壬辰')),
            ((2022, 8, 28, 1, 50), ('壬寅', '戊申', '癸丑', '癸丑')),
            ((1988, 2, 15, 23, 30), ('戊辰', '甲寅', '庚子', '戊子')),
        ]:
            with self.subTest(inputs=inputs):
                self.assertEqual(tuple(calculate_bazi(*inputs).values()), expected)

    def test_continuous_days_and_midnight_boundary(self):
        stems, branches = '甲乙丙丁戊己庚辛壬癸', '子丑寅卯辰巳午未申酉戌亥'
        for before in [date(2024, 2, 28), date(2024, 2, 29), date(2025, 12, 31)]:
            after = before + timedelta(days=1)
            first = calculate_bazi(before.year, before.month, before.day, 12, 0)['day']
            late = calculate_bazi(before.year, before.month, before.day, 23, 30)['day']
            second = calculate_bazi(after.year, after.month, after.day, 0, 0)['day']
            self.assertEqual(first, late)
            self.assertEqual((stems.index(first[0]) + 1) % 10, stems.index(second[0]))
            self.assertEqual((branches.index(first[1]) + 1) % 12, branches.index(second[1]))

    def test_solar_term_year_month_boundary(self):
        # Li Chun 2024 falls on February 4, between these civil-time samples.
        before = calculate_bazi(2024, 2, 4, 0, 0)
        after = calculate_bazi(2024, 2, 5, 0, 0)
        self.assertEqual((before['year'], before['month']), ('癸卯', '乙丑'))
        self.assertEqual((after['year'], after['month']), ('甲辰', '丙寅'))

    def test_lunar_roundtrips_and_leap_month(self):
        self.assertEqual(solar_to_lunar(2023, 3, 22), (2023, 2, 1, True))
        self.assertEqual(lunar_to_solar(2023, 2, 1, True), (2023, 3, 22))
        self.assertNotEqual(lunar_to_solar(2023, 2, 1, False), (2023, 3, 22))
        for solar in [(1900, 1, 1), (2024, 2, 29), (2026, 9, 15), (2099, 12, 31)]:
            self.assertEqual(lunar_to_solar(*solar_to_lunar(*solar)), solar)
        for lunar in [(2024, 2, 1, True), (2023, 2, 30, True), (2023, 13, 1, False)]:
            with self.assertRaises(ValueError):
                lunar_to_solar(*lunar)

    def test_lunar_requires_integer_date_and_boolean_leap_flag(self):
        for values in [(2024, 1, 1.5, False), (2024, 1.0, 1, False),
                       (2024, True, 1, False), (2024, 1, True, False),
                       ('2024', 1, 1, False), (2024, 1, 1, 'false')]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                lunar_to_solar(*values)

    def test_shared_input_validation(self):
        for invalid in [None, '', True, False, float('nan'), float('inf'), 1.5, 0, -1, 1000]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_numbers([invalid, 2, 3])
        self.assertEqual(validate_numbers(['1', 2.0, 999]), [1, 2, 999])
        for day, hour in [('2026-02-30', '12:00'), ('2026-01-01', '25:99'), ('2100-01-01', '00:00')]:
            with self.assertRaises(ValueError):
                parse_datetime(day, hour)
        self.assertEqual(normalize_gender(' m '), '男')
        with self.assertRaises(ValueError):
            normalize_gender('unknown')

    def test_all_hour_periods(self):
        expected = [1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 1]
        for hour, period in enumerate(expected):
            self.assertEqual(date_to_numbers('2026-09-15', f'{hour:02d}:00'), [8, 5, period])

    def test_strokes_cached_and_missing_characters_rejected(self):
        with patch('builtins.open', side_effect=AssertionError('dictionary reopened')):
            self.assertEqual(get_stroke_counts('中国人'), [4, 8, 2])
        with patch('utils.stroke_count.STROKE_COUNTS', {'中': 4, '国': 8}):
            with self.assertRaises(ValueError):
                get_stroke_counts('中国人')

    def test_prediction_wraps_without_ai(self):
        from symbols import SYMBOLS
        for values in [(1, 2, 3), (9, 9, 9), (999, 2, 12)]:
            result = HandTechnique.predict(*values)
            positions = [(values[0] - 1) % 9, (sum(values[:2]) - 2) % 9, (sum(values) - 3) % 9]
            self.assertEqual(result.symbols, tuple(SYMBOLS[i] for i in positions))
        # Preserve Claude Code overview §4's nontrivial relationship example.
        result = HandTechnique.predict(3, 5, 8)
        self.assertEqual([symbol.name for symbol in result.symbols], ['速喜', '病符', '小吉'])
        self.assertEqual(result.relations, ('生', '克'))

    def test_cli_local_modes_and_date_parity(self):
        for mode, prompts, expected in [
            (1, ['1,2,3'], [1, 2, 3]),
            (2, ['2026-09-15', '12:00'], [8, 5, 7]),
            (3, ['中,国,人'], [4, 8, 2]),
        ]:
            with self.subTest(mode=mode), \
                 patch('cli.get_menu_choice', side_effect=[mode, 'home']), \
                 patch('cli.Prompt.ask', side_effect=prompts), \
                 patch('cli.DivinationAgent.get_available_models', return_value=[]), \
                 patch('cli.HandTechnique.predict', wraps=HandTechnique.predict) as predict, \
                 patch('cli.display_divination_result') as display, \
                 patch('cli.console', cli.Console(file=io.StringIO(), width=100)):
                cli.xiaoliu_submenu()
                predict.assert_called_once_with(*expected)
                display.assert_called_once()

    def test_cli_bazi_gender_and_invalid_time(self):
        from rich.console import Console
        output = io.StringIO()
        with patch('cli.Prompt.ask', side_effect=['2005-12-23', '08:37', 'M']), \
             patch('cli.console', Console(file=output, width=120)):
            cli.bazi_calculation()
        self.assertIn('性别：男', output.getvalue())
        self.assertIn('男性', output.getvalue())
        with patch('cli.Prompt.ask', side_effect=['2005-12-23', '25:99', 'M']), \
             patch('cli.calculate_bazi') as calculation, patch('cli.console'):
            cli.bazi_calculation()
            calculation.assert_not_called()

    def test_cli_reverse_conversion(self):
        from rich.console import Console
        output = io.StringIO()
        with patch('cli.Prompt.ask', side_effect=['2023-02-01', 'y']), \
             patch('cli.console', Console(file=output)):
            cli.lunar_to_solar_conversion()
        self.assertIn('2023-03-22', output.getvalue())

    def test_loaders_work_outside_project(self):
        src = str(Path(__file__).resolve().parents[1] / 'src')
        script = f"import sys; sys.path.insert(0, {src!r}); import bagua, symbols, celestial_stems_earthly_branches; from utils.stroke_count import get_stroke_counts; assert get_stroke_counts('中国人') == [4, 8, 2]"
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([sys.executable, '-c', script], cwd=directory, check=True, capture_output=True)


class WebRegressions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        loop_patch = patch('nicegui.core.loop', asyncio.get_running_loop())
        loop_patch.start()
        self.addCleanup(loop_patch.stop)
        network_patch = patch('pydantic_ai.models.ALLOW_MODEL_REQUESTS', False)
        network_patch.start()
        self.addCleanup(network_patch.stop)

    async def test_cli_stream_does_not_clear_local_prediction(self):
        from contextlib import asynccontextmanager
        from types import SimpleNamespace
        from ai_agent import DivinationAgent, DivinationDeps, SupportedModels
        from rich.console import Console

        class Stream:
            async def stream_text(self):
                yield 'partial interpretation'
                raise RuntimeError('simulated stream outage')

        @asynccontextmanager
        async def run_stream(*args, **kwargs):
            yield Stream()

        agent = DivinationAgent.__new__(DivinationAgent)
        agent.model_type = SupportedModels.OPENAI_GPT56
        agent.agent = SimpleNamespace(run_stream=run_stream)
        output = io.StringIO()
        console = Console(file=output)
        console.print('LOCAL PREDICTION')
        with patch('ai_agent.Console', return_value=console), \
             patch.object(console, 'clear') as clear:
            with self.assertRaisesRegex(RuntimeError, 'simulated stream outage'):
                await agent._stream_interpretation('test', DivinationDeps('unused', agent.model_type))
            clear.assert_not_called()
        self.assertIn('LOCAL PREDICTION', output.getvalue())

    async def test_web_modes_and_invalid_input_recovery(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/input-modes'), request=None):
                app = create_page()
                app.input_tabs.value = 'date'
                app.date_input.value, app.time_input.value = '2026-09-15', '12:00'
                await app._perform_divination()
                self.assertEqual(app.divination_result, HandTechnique.predict(8, 5, 7))
                app.input_tabs.value = 'chinese'
                app.chinese_input.value = '中国人'
                await app._perform_divination()
                self.assertEqual(app.divination_result, HandTechnique.predict(4, 8, 2))
                app.input_tabs.value = 'numbers'
                app.number_inputs[0].value = None
                await app._perform_divination()
                self.assertIn('整数', app.error_message.text)
                self.assertIsNone(app.divination_result)
                self.assertTrue(app.submit_button.enabled)
                app.number_inputs[0].value = 1
                await app._perform_divination()
                self.assertEqual(app.divination_result, HandTechnique.predict(1, 2, 3))
                self.assertEqual(app.error_message.text, '')

    async def test_two_clients_own_inputs_and_results(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            first_client = Client(ui.page('/first'), request=None)
            second_client = Client(ui.page('/second'), request=None)
            with first_client:
                first = create_page()
                first.question_input.value = 'first question'
            with second_client:
                second = create_page()
                second.question_input.value = 'second question'
                second.number_inputs[0].value = 9
                second_initial_content = list(second.result_area.default_slot.children)
            with first_client:
                await first._perform_divination()
            self.assertEqual(first.divination_result, HandTechnique.predict(1, 2, 3))
            self.assertIsNone(second.divination_result)
            self.assertEqual(second.question_input.value, 'second question')
            self.assertEqual(second.result_area.default_slot.children, second_initial_content)
            with second_client:
                await second._perform_divination()
            self.assertEqual(second.divination_result, HandTechnique.predict(9, 2, 3))
            self.assertEqual(first.question_input.value, 'first question')

    async def test_local_results_survive_ai_failure_and_duplicate_click(self):
        from nicegui import Client, ui
        from ai_agent import SupportedModels
        from web import create_page
        entered, release = asyncio.Event(), asyncio.Event()

        async def failing_ai(*args, **kwargs):
            entered.set()
            await release.wait()
            raise RuntimeError('simulated outage')

        with patch('web.DivinationAgent.get_available_models', return_value=[SupportedModels.OPENAI_GPT56]), \
             patch('web.DivinationAgent.__init__', return_value=None), \
             patch('web.DivinationAgent.interpret_prediction_async', side_effect=failing_ai) as ai:
            with Client(ui.page('/ai-failure'), request=None):
                app = create_page()
                app.question_input.value = 'test'
                task = asyncio.create_task(app._perform_divination())
                await asyncio.wait_for(entered.wait(), timeout=2)
                self.assertEqual(app.divination_result, HandTechnique.predict(1, 2, 3))
                self.assertTrue(app.result_area.default_slot.children)
                await app._perform_divination()
                self.assertEqual(ai.await_count, 1)
                release.set()
                await task
                self.assertIn('simulated outage', app.error_message.text)
                self.assertTrue(app.result_area.default_slot.children)
                self.assertFalse(app.is_running)
                self.assertTrue(app.submit_button.enabled)

    async def test_optional_panel_follows_ai_availability_and_button_names_the_action(self):
        from nicegui import Client, ui
        from ai_agent import SupportedModels
        from web import create_page
        for models, expanded in [([], False), ([SupportedModels.OPENAI_GPT56], True)]:
            with self.subTest(models=models), patch('web.DivinationAgent.get_available_models', return_value=models):
                with Client(ui.page(f'/optional-{expanded}'), request=None):
                    app = create_page()
                    self.assertEqual(app.optional_panel.value, expanded)
                    self.assertEqual(app.submit_button.text, '开始占卜')
                    self.assertIs(app.question_input.parent_slot.parent, app.optional_panel)
                    self.assertIs(app.model_select.parent_slot.parent, app.optional_panel)
                    siblings = app.submit_button.parent_slot.children
                    self.assertLess(siblings.index(app.submit_button), siblings.index(app.optional_panel))

    async def test_blank_question_and_local_selection_skip_ai(self):
        from nicegui import Client, ui
        from ai_agent import SupportedModels
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[SupportedModels.OPENAI_GPT56]), \
             patch('web.DivinationAgent.interpret_prediction_async', new_callable=AsyncMock) as ai:
            with Client(ui.page('/skip-ai'), request=None):
                app = create_page()
                await app._perform_divination()
                app.model_select.value = 'local'
                app.question_input.value = 'ignored in local mode'
                await app._perform_divination()
                ai.assert_not_called()
                self.assertEqual(app.divination_result, HandTechnique.predict(1, 2, 3))


    async def test_form_summary_edit_and_validation_state(self):
        from nicegui import Client, ui
        from web import create_page
        question = '求职问题 "<&>" ' * 30
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/summary'), request=None):
                app = create_page()
                self.assertNotIn('form-collapsed', app.form_card.classes)
                self.assertEqual(app.edit_button._props['aria-expanded'], 'true')
                app.question_input.value = question
                await app._perform_divination()
                self.assertIn('form-collapsed', app.form_card.classes)
                self.assertIn('1、2、3', app.summary_label.text)
                self.assertIn('仅本地', app.summary_label.text)
                self.assertIn(question.strip(), app.summary_label._props['aria-label'])
                self.assertEqual(app.summary_label.text, app.summary_label._props['title'])
                self.assertEqual(app.edit_button._props['aria-expanded'], 'false')
                details, fields = app.form_details, list(app.number_inputs)
                result = app.divination_result
                handler = next(event.handler for event in app.edit_button._event_listeners.values() if event.type == 'click')
                handler(None)
                self.assertNotIn('form-collapsed', app.form_card.classes)
                self.assertEqual(app.edit_button._props['aria-expanded'], 'true')
                self.assertEqual(app.edit_button._props['aria-controls'], f'c{details.id}')
                self.assertEqual(app.question_input.value, question)
                self.assertEqual(app.number_inputs, fields)
                self.assertIs(app.divination_result, result)
                await app._perform_divination()
                self.assertIn('form-collapsed', app.form_card.classes)
                app.number_inputs[0].value = 0
                await app._perform_divination()
                self.assertNotIn('form-collapsed', app.form_card.classes)
                self.assertFalse(app.ai_action.enabled)
        css = (Path(__file__).resolve().parents[1] / 'src/web.css').read_text()
        self.assertIn('.form-summary { display: none;', css)
        self.assertIn('@media (max-width: 900px) {\n    .form-card.form-collapsed', css)
        self.assertIn('.form-card.form-collapsed .form-details { display: none; }', css)
        self.assertIn('.form-card.form-collapsed .form-summary { display: flex; }', css)
        self.assertIn('text-overflow: ellipsis; white-space: nowrap;', css)

    async def test_result_action_missing_configuration_opens_existing_form(self):
        from nicegui import Client, ui
        from ai_agent import SupportedModels
        from web import create_page
        for models in [[], [SupportedModels.OPENAI_GPT56]]:
            with patch('web.DivinationAgent.get_available_models', return_value=models), \
                 patch('web.DivinationAgent.interpret_prediction_async', new_callable=AsyncMock) as ai:
                with Client(ui.page('/missing-settings'), request=None):
                    app = create_page()
                    await app._perform_divination()
                    result = app.divination_result
                    app.optional_panel.value = False
                    await app._request_ai_interpretation()
                    self.assertIn('问题' if models else 'API 密钥', app.error_message.text)
                    self.assertNotIn('form-collapsed', app.form_card.classes)
                    self.assertTrue(app.optional_panel.value)
                    app.model_select.value = 'local'
                    app.question_input.value = '已有问题'
                    await app._request_ai_interpretation()
                    self.assertIn('AI 模型', app.error_message.text)
                    self.assertIs(app.divination_result, result)
                    self.assertTrue(app.ai_action.enabled)
                    ai.assert_not_awaited()

    async def test_partial_failure_preserves_local_tree_and_allows_explicit_retry(self):
        from nicegui import Client, ui
        from ai_agent import SupportedModels
        from web import create_page
        entered, release = asyncio.Event(), asyncio.Event()

        async def partial_failure(*args, on_update):
            await on_update('### 一句话判断\n未完成')
            entered.set()
            await release.wait()
            raise RuntimeError('断流')

        with patch('web.DivinationAgent.get_available_models', return_value=[SupportedModels.OPENAI_GPT56]), \
             patch('web.DivinationAgent.__init__', return_value=None), \
             patch('web.DivinationAgent.interpret_prediction_async', new_callable=AsyncMock) as ai:
            with Client(ui.page('/partial-failure'), request=None):
                app = create_page()
                await app._perform_divination()
                app.question_input.value = '旧问题'
                ai.return_value = '上次成功'
                await app._request_ai_interpretation()
                self.assertEqual(app.ai_interpretation, '上次成功')
                ai.side_effect = partial_failure
                app.question_input.value = '本次问题'
                result, children = app.divination_result, list(app.result_area.default_slot.children)
                task = asyncio.create_task(app._request_ai_interpretation())
                await asyncio.wait_for(entered.wait(), 2)
                self.assertIsNone(app.ai_interpretation)
                self.assertIn('未完成', app.ai_markdown.content)
                self.assertFalse(app.submit_button.enabled)
                self.assertFalse(app.ai_action.enabled)
                app.question_input.value = '尚未提交的修改'
                app.model_select.value = 'local'
                self.assertIn('本次问题', app.ai_request_label.text)
                self.assertNotIn('尚未提交', app.summary_label.text)
                await app._perform_divination()
                await app._request_ai_interpretation()
                self.assertEqual(ai.await_count, 2)
                release.set()
                await task
                self.assertIs(app.divination_result, result)
                self.assertEqual(children, app.result_area.default_slot.children)
                self.assertIn('本地结果已保留', app.ai_status.text)
                self.assertIn('断流', app.ai_status.text)
                self.assertEqual(app.ai_status._props['role'], 'alert')
                self.assertEqual(app.ai_markdown.content, '')
                self.assertIsNone(app.ai_interpretation)
                self.assertIn('form-collapsed', app.form_card.classes)
                self.assertTrue(app.submit_button.enabled)
                self.assertTrue(app.ai_action.enabled)
                ai.side_effect, ai.return_value = None, '重试全文（无标题）'
                app.model_select.value = SupportedModels.OPENAI_GPT56.value
                await app._request_ai_interpretation()
                self.assertEqual(app.ai_markdown.content, '重试全文（无标题）')
                self.assertEqual(app.ai_interpretation, app.ai_markdown.content)
                self.assertNotIn('ai-failed', app.ai_card.classes)
                self.assertEqual(app.error_message.text, '')

    async def test_two_clients_stream_and_edit_independently(self):
        from nicegui import Client, ui
        from ai_agent import SupportedModels
        from web import create_page
        entered = {key: asyncio.Event() for key in ('甲', '乙')}
        release = {key: asyncio.Event() for key in ('甲', '乙')}

        async def stream(symbols, question, *, on_update):
            await on_update(question + '的首片')
            entered[question].set()
            await release[question].wait()
            return question + '的全文'

        with patch('web.DivinationAgent.get_available_models', return_value=[SupportedModels.OPENAI_GPT56]), \
             patch('web.DivinationAgent.__init__', return_value=None), \
             patch('web.DivinationAgent.interpret_prediction_async', side_effect=stream):
            clients, apps, tasks = {}, {}, {}
            for key in ('甲', '乙'):
                clients[key] = Client(ui.page('/isolated-' + key), request=None)
                with clients[key]:
                    apps[key] = create_page()
                    apps[key].question_input.value = key
                    tasks[key] = asyncio.create_task(apps[key]._perform_divination())
            for event in entered.values():
                await asyncio.wait_for(event.wait(), 2)
            with clients['甲']:
                apps['甲']._edit_inputs()
            self.assertNotIn('form-collapsed', apps['甲'].form_card.classes)
            self.assertIn('form-collapsed', apps['乙'].form_card.classes)
            for key in ('甲', '乙'):
                self.assertIn(key + '的首片', apps[key].ai_markdown.content)
                self.assertIs(apps[key].ai_markdown.client, clients[key])
                release[key].set()
                await tasks[key]
                self.assertEqual(apps[key].ai_interpretation, key + '的全文')


if __name__ == '__main__':
    unittest.main()
