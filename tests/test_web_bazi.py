"""八字页接线和真实 NiceGUI 元素树验收；不以 Web 接线函数产生期望值。"""
import copy
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from nicegui import Client, ui
import web
from utils.bazi_calculator import calculate_bazi, analyze_day_master_strength, analyze_spouse_palace
from utils.calendar_converter import solar_to_lunar, format_bazi_output, format_tai_sui_section
from utils.five_elements_utils import analyze_wuxing, analyze_missing_wuxing
from utils.validation import parse_datetime, normalize_gender


def descendants(element):
    for slot in element.slots.values():
        for child in slot.children:
            yield child
            yield from descendants(child)


def texts(element):
    return [child.text for child in descendants(element) if hasattr(child, 'text')]


def expected_report(date='1990-01-01', time='10:30', gender='男', year=2023):
    birth = parse_datetime(date, time)
    gender = normalize_gender(gender)
    bazi = calculate_bazi(birth.year, birth.month, birth.day, birth.hour, birth.minute)
    wuxing = analyze_wuxing(bazi)
    lunar = solar_to_lunar(birth.year, birth.month, birth.day)
    return dict(
        formatted=format_bazi_output(bazi, wuxing, birth.strftime('%Y-%m-%d'), birth.strftime('%H:%M'),
                                     lunar, gender, target_year=year),
        bazi=bazi, wuxing=wuxing,
        analysis=[('日主强弱', analyze_day_master_strength(bazi, gender)),
                  ('配偶宫', analyze_spouse_palace(bazi, gender)),
                  ('缺失影响', analyze_missing_wuxing(wuxing['missing'], gender))],
    )


class BaziPageTests(unittest.IsolatedAsyncioTestCase):
    def set_inputs(self, app, date='1990-01-01', time='10:30', gender='男', year=2023):
        app.date_input.value = date
        app.time_input.value = time
        app.gender_input.value = gender
        app.year_input.value = year

    def cards(self, app):
        return [e for e in descendants(app.result_area) if 'bazi-section' in e.classes]

    def assert_report(self, app, expected):
        self.assertEqual(app.error_message.text, '')
        self.assertEqual(app.report, expected)
        cards = self.cards(app)
        self.assertEqual([c.props['data-section'] for c in cards], ['basic', 'pillars', 'wuxing', 'analysis', 'tai-sui'])
        self.assertEqual([texts(c)[0] for c in cards], ['基本信息', '八字信息', '五行分析', '命运解析', '流年太岁'])
        for card, group in zip(cards, ['basic_info', 'bazi_info', 'wuxing_info']):
            for value in expected['formatted'][group].values():
                self.assertIn(value, texts(card))
        for key, label in [('year', '年柱'), ('month', '月柱'), ('day', '日柱'), ('time', '时柱')]:
            self.assertIn(label, texts(cards[1]))
            self.assertIn(expected['bazi'][key], texts(cards[1]))
        for label, value in expected['analysis']:
            self.assertIn(label, texts(cards[3]))
            self.assertIn(value, texts(cards[3]))
        tai_sui_rows = format_tai_sui_section(expected['formatted']['tai_sui_info'])
        self.assertEqual(texts(cards[4]), ['流年太岁'] + [item for row in tai_sui_rows for item in row])
        badges = [e for e in descendants(cards[2]) if 'bazi-element-badge' in e.classes]
        self.assertEqual([b.text for b in badges], [f'{element} · {count}' for element, count in expected['wuxing']['wuxing_count'].items()])
        self.assertEqual({b.props['data-element'] for b in badges}, set(web.ELEMENT_KEYS.values()))
        for badge in badges:
            self.assertIn('element-badge', badge.classes)
            self.assertIn(f'element-{badge.props["data-element"]}', badge.classes)

    async def test_fixed_reports_match_shared_functions_in_rendered_cards(self):
        # 男/女的规范化与原生控件可接受的标准文本均走共享验证。
        for gender in ('男', '女', ' f '):
            with self.subTest(gender=gender), Client(ui.page('/bazi-fixed'), request=None):
                app = web.create_bazi_page()
                self.set_inputs(app, gender=gender)
                # Select 会把非选项值清空；直接注入底层值验证服务端共享规范化。
                with patch.object(app.gender_input, '___value', gender):
                    app._perform_calculation()
                self.assert_report(app, expected_report(gender=gender))

    async def test_supported_boundaries_and_leap_day_use_shared_calendar(self):
        for date, time, year in [('1900-01-01', '00:00', 1900), ('2099-12-31', '23:59', 2099),
                                 ('2024-02-29', '23:00', 2024), ('2024-03-01', '00:00', 2024)]:
            with self.subTest(date=date, time=time), Client(ui.page('/bazi-boundaries'), request=None):
                app = web.create_bazi_page()
                self.set_inputs(app, date=date, time=time, year=year)
                app._perform_calculation()
                self.assert_report(app, expected_report(date=date, time=time, year=year))

    async def test_tai_sui_branches_render_all_source_explanations(self):
        cases = [
            ('1987-06-15', 2023, '卯', ['值太岁', '刑太岁'], [], 'available'),
            ('1993-06-15', 2023, '酉', ['冲太岁', '破太岁'], [], 'available'),
            ('1994-06-15', 2023, '戌', [], ['六合太岁'], 'available'),
            ('1986-06-15', 2023, '寅', [], [], 'available'),
            ('1989-06-15', 2021, '巳', ['破太岁'], ['三合太岁', '相生太岁', '得助太岁'], 'available'),
            ('1992-06-15', 2028, '申', ['值太岁', '刑太岁'], [], 'missing'),
        ]
        for date, year, branch, fan, he, status in cases:
            with self.subTest(date=date, year=year), Client(ui.page('/bazi-relations'), request=None):
                app = web.create_bazi_page()
                self.set_inputs(app, date=date, year=year)
                app._perform_calculation()
                expected = expected_report(date=date, year=year)
                self.assert_report(app, expected)
                self.assertEqual(app.report['bazi']['year'][1], branch)
                result = app.report['formatted']['tai_sui_info']
                self.assertEqual([r['relation_type'] for r in result['fan_tai_sui']], fan)
                self.assertEqual([r['relation_type'] for r in result['he_tai_sui']], he)
                self.assertEqual(result['general_status'], status)
                output = '\n'.join(texts(self.cards(app)[4]))
                for relation in result['fan_tai_sui'] + result['he_tai_sui']:
                    self.assertIn(relation['explanation'], output)
                if branch == '酉':
                    # 直接摘录资料，而非使用被测接线产生期望值。
                    self.assertIn('卯（兔）与酉（鸡）相冲，木金相克，通常代表冲突和竞争。', output)
                    self.assertIn('卯（兔）与酉（鸡）相破，木金相克，表示该年可能会出现突如其来的变化或意外事件，需保持警惕。', output)
                    self.assertIn('陈大将军', output)
                if not fan and not he:
                    self.assertIn('无特殊关系', output)
                if status == 'missing':
                    self.assertIn('数据未收录戊申年值年太岁', output)
                    self.assertNotIn('None', output)

    async def test_invalid_inputs_clear_old_report_and_recover(self):
        cases = [dict(date=d) for d in ('2023-02-29', '1899-12-31', '2100-01-01', '', None)]
        cases += [dict(time=t) for t in ('24:00', '12:60', '', None)]
        cases += [dict(gender=g) for g in ('未知', '', None)]
        cases += [dict(year=y) for y in (1899, 2100, 2023.5, 2023.0, '2023', True, False, None)]
        with Client(ui.page('/bazi-invalid'), request=None):
            app = web.create_bazi_page()
            for inputs in cases:
                with self.subTest(inputs=inputs):
                    self.set_inputs(app)
                    app._perform_calculation()
                    self.assertIsNotNone(app.report)
                    self.set_inputs(app, **inputs)
                    # 绕过 Select 选项清洗及 BindableProperty 的 2023 == 2023.0 去重，
                    # 确认服务端确实拒绝原始非法值，而不只是浏览器约束生效。
                    with ExitStack() as stack:
                        for key, widget in [('gender', app.gender_input), ('year', app.year_input)]:
                            if key in inputs:
                                stack.enter_context(patch.object(widget, '___value', inputs[key]))
                        app._perform_calculation()
                    self.assertIsNone(app.report)
                    self.assertEqual(app.error_message.props['role'], 'alert')
                    self.assertTrue(app.error_message.text)
                    self.assertEqual(app.result_area.default_slot.children, [])
                    self.set_inputs(app)
                    app._perform_calculation()
                    self.assert_report(app, expected_report())

    async def test_calculation_and_partial_render_failures_clear_report(self):
        with Client(ui.page('/bazi-failure'), request=None):
            app = web.create_bazi_page()
            self.set_inputs(app)
            for target in ('web.calculate_bazi', 'web.BaziWebApp._display_report'):
                def fail(*args):
                    with app.result_area:
                        ui.label('不应残留的半份报告')
                    raise RuntimeError('模拟异常')
                with self.subTest(target=target), patch(target, side_effect=fail):
                    app._perform_calculation()
                    self.assertIsNone(app.report)
                    self.assertEqual(app.result_area.default_slot.children, [])
                    self.assertIn('计算失败：模拟异常', app.error_message.text)
            app._perform_calculation()
            self.assert_report(app, expected_report())

    async def test_two_page_requests_have_independent_state(self):
        with Client(ui.page('/bazi-first'), request=None) as first_client:
            first = web.create_bazi_page()
            self.set_inputs(first)
        with Client(ui.page('/bazi-second'), request=None) as second_client:
            second = web.create_bazi_page()
            self.set_inputs(second, gender='女', year=2024)
            second._perform_calculation()
        for name in ('date_input', 'time_input', 'gender_input', 'year_input', 'error_message', 'status_message', 'result_area', 'submit_button'):
            self.assertIsNot(getattr(first, name), getattr(second, name))
        snapshot = copy.deepcopy(second.report)
        second_children = list(second.result_area.default_slot.children)
        with first_client:
            first._perform_calculation()
            first.year_input.value = 2028
            first._perform_calculation()
            first.date_input.value = 'bad date'
            first._perform_calculation()
        self.assertIsNone(first.report)
        with second_client:
            self.assert_report(second, snapshot)
            self.assertEqual(second.year_input.value, 2024)
            self.assertEqual(second.date_input.value, '1990-01-01')
            self.assertEqual(second.result_area.default_slot.children, second_children)

    async def test_year_selection_changes_only_tai_sui_after_resubmit(self):
        with Client(ui.page('/bazi-year'), request=None):
            app = web.create_bazi_page()
            self.set_inputs(app)
            app._perform_calculation()
            before = [texts(c) for c in self.cards(app)]
            app.year_input.value = 2024
            self.assertEqual([texts(c) for c in self.cards(app)], before)
            app._perform_calculation()
            self.assert_report(app, expected_report(year=2024))
            after = [texts(c) for c in self.cards(app)]
            self.assertEqual(before[:4], after[:4])
            self.assertNotEqual(before[4], after[4])

    async def test_beijing_year_defaults_at_new_year_boundary(self):
        for instant, year in [(datetime(2025, 12, 31, 15, 59, 59, tzinfo=timezone.utc), 2025),
                              (datetime(2025, 12, 31, 16, 0, tzinfo=timezone.utc), 2026)]:
            def now(tz):
                self.assertEqual(tz.utcoffset(instant), timedelta(hours=8))
                return instant.astimezone(tz)
            with self.subTest(instant=instant), patch('web.datetime') as clock:
                clock.now.side_effect = now
                with Client(ui.page('/bazi-clock'), request=None):
                    app = web.create_bazi_page()
                    self.assertEqual(app.year_input.value, year)
                    self.assertEqual(app.date_input.value, instant.astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d'))
                    self.assertEqual(app.time_input.value, '00:00')
                clock.now.assert_called_once()

    async def test_controls_assets_disclaimer_and_no_ai_calls(self):
        with patch('web.DivinationAgent', side_effect=AssertionError('no AI')) as agent:
            agent.get_available_models.side_effect = AssertionError('no model probing')
            with Client(ui.page('/bazi-controls'), request=None) as client:
                app = web.create_bazi_page()
                self.assertIsNone(app.report)
                self.assertEqual(self.cards(app), [])
                self.assertEqual(app.date_input.props['type'], 'date')
                self.assertEqual(app.date_input.props['min'], '1900-01-01')
                self.assertEqual(app.date_input.props['max'], '2099-12-31')
                self.assertEqual(app.time_input.props['type'], 'time')
                self.assertEqual(app.gender_input.options, ['男', '女'])
                self.assertEqual(app.gender_input.value, '男')
                self.assertEqual(app.year_input.options, list(range(1900, 2100)))
                self.assertEqual(app.status_message.props['role'], 'status')
                self.assertEqual(app.status_message.props['aria-live'], 'polite')
                page_text = [e.text for e in client.elements.values() if hasattr(e, 'text')]
                self.assertIn('八字后的性格和关系解读仍为原有简化规则；历法计算修正不代表这些解读得到验证。', page_text)
                self.assertIn('日主强弱、配偶宫分析属于上述简化规则，仅供传统文化参考。', page_text)
                self.assertIn('window.msrTheme', client._head_html)
                for theme in web.THEMES[1:]:
                    self.assertIn(f'html[data-theme="{theme.id}"]', client._head_html)
                swatches = [e for e in client.elements.values() if 'theme-swatch' in e.classes]
                self.assertEqual([e.props['data-theme-id'] for e in swatches], [t.id for t in web.THEMES])
                self.set_inputs(app)
                app._perform_calculation()
                self.assert_report(app, expected_report())
                agent.assert_not_called()
                agent.get_available_models.assert_not_called()

    async def test_navigation_both_ways_and_active_page(self):
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            for current, factory in [('/', web.create_page), ('/bazi', web.create_bazi_page)]:
                with self.subTest(current=current), Client(ui.page('/nav-check'), request=None) as client:
                    factory()
                    links = [e for e in client.elements.values() if 'page-nav-link' in e.classes]
                    self.assertEqual([e.text for e in links], ['小六壬', '八字'])
                    self.assertEqual([e.props['href'] for e in links], ['/', '/bazi'])
                    self.assertEqual([e.props.get('aria-current') for e in links],
                                     ['page' if e.props['href'] == current else None for e in links])

    async def test_main_registers_two_page_factories(self):
        registrations = {}

        def register(path, **kwargs):
            self.assertEqual(kwargs, dict(dark=False))
            return lambda factory: registrations.update({path: factory})

        with patch('web.ui.page', side_effect=register), patch('web.ui.run') as run, patch('web.os.chdir'):
            web.main()
        self.assertEqual(registrations, {'/': web.create_page, '/bazi': web.create_bazi_page})
        run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
