"""Presentation checks use handwritten facts, not values inferred from the new UI."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ai_agent import DivinationAgent
from hand_technique import HandTechnique
from nicegui import Client, ui
from reading import ReadingSession
from reading_fixtures import complete
from web import create_page

ROOT = Path(__file__).resolve().parents[1]


class ReadingDesign(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch('web.DivinationAgent.get_available_models', return_value=[]))

    @staticmethod
    def texts(area):
        return [e.text for e in area.descendants() if hasattr(e, 'text')]

    def test_snapshot_axis_and_question_ignore_unsubmitted_form(self):
        with Client(ui.page('/design-snapshot'), request=None):
            app = create_page()
            app.question_input.value = '未提交的新问题'
            app.number_inputs[0].value = 9
            base = ReadingSession.start(HandTechnique.predict(1, 2, 3), '合作前应确认什么？')
            session = complete(complete(base), supplement='分工未定')
            app._display_ai_result(session)
            elements = list(app.ai_result_area.descendants())
            axis = next(e for e in elements if 'reading-transmission-axis' in e.classes)
            self.assertEqual(self.texts(axis), [
                '初传 · 起点', '大安', '木', '比和',
                '中传 · 过程', '留连', '木', '被克', '末传 · 趋势', '赤口', '金',
            ])
            labels = self.texts(app.ai_result_area)
            self.assertIn('合作前应确认什么？', labels)
            self.assertIn('第 1 次补充', labels)
            self.assertNotIn('未提交的新问题', labels)
            self.assertLess(labels.index('核心判断'), labels.index(session.reading.answer))
            self.assertLess(labels.index(session.reading.answer), labels.index('下一步'))

    def test_action_list_is_semantic_and_model_text_stays_literal(self):
        with Client(ui.page('/design-text'), request=None):
            app = create_page()
            attack = '<img src=x onerror=alert(1)> **不要作为 HTML 渲染**'
            base = ReadingSession.start(HandTechnique.predict(1, 2, 3), attack)
            for count in (1, 2, 3):
                actions = [f'{attack} {i}' for i in range(count)]
                session = complete(base, answer=attack, actions=actions, rationale=attack, follow_up=None)
                app._display_ai_result(session)
                elements = list(app.ai_result_area.descendants())
                action_list = next(e for e in elements if 'reading-action-list' in e.classes)
                self.assertEqual(action_list.tag, 'ol')
                self.assertEqual(len(action_list.default_slot.children), count)
                self.assertTrue(all(e.tag == 'li' for e in action_list.default_slot.children))
                self.assertEqual([e.text for e in elements if 'reading-action' in e.classes], actions)
                self.assertFalse(any(e.tag in ('img', 'script', 'q-markdown') for e in elements))
                self.assertNotIn('必要提醒', self.texts(app.ai_result_area))
                self.assertIn('初次解读', self.texts(app.ai_result_area))

    def test_no_invented_transition_for_repeated_transmissions(self):
        with Client(ui.page('/design-repeated'), request=None):
            app = create_page()
            session = complete(ReadingSession.start(HandTechnique.predict(1, 1, 1), '怎样维持稳定？'))
            app._display_ai_result(session)
            axis = next(e for e in app.ai_result_area.descendants() if 'reading-transmission-axis' in e.classes)
            self.assertEqual(self.texts(axis).count('大安'), 3)
            self.assertEqual(self.texts(axis).count('比和'), 2)

    def test_prompt_has_professional_content_without_changing_contract(self):
        prompt = DivinationAgent._get_system_prompt(None)
        for requirement in ('判断和成立条件', '什么现实信息会改变判断', '可观察的完成或核验条件',
                            '如何支持answer', '不来自断言、评分', '不能混用', '左传为主语', '末传不是注定结局'):
            self.assertIn(requirement, prompt)
        for invented in ('confidence:', 'score:', '胜率', '必须输出五段'):
            self.assertNotIn(invented, prompt)

    def test_new_stylesheet_is_included_in_desktop_bundle(self):
        self.assertTrue((ROOT / 'src' / 'reading.css').is_file())
        self.assertIn("(str(root / 'src' / 'reading.css'), '.')", (ROOT / 'desktop' / 'backend.spec').read_text())


if __name__ == '__main__':
    unittest.main()
