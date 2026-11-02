"""Reports render existing facts and never interpret HTML from user/AI text."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from hand_technique import HandTechnique
from reading import ReadingSession
from reading_fixtures import complete
from reports import render_report, DISCLAIMER
from utils.symbol_relations import describe_relation


class Reports(unittest.TestCase):
    def setUp(self):
        self.prediction = HandTechnique.predict(1, 2, 3)
        self.session = complete(ReadingSession.start(self.prediction, '准备求职'))

    def render(self, variant='print', **kwargs):
        return render_report(self.prediction, variant=variant, question='准备求职',
                             input_summary='数字模式 · 起课数字：1、2、3', **kwargs)

    def test_local_report_has_actual_facts_direction_and_no_invented_reading(self):
        with patch('hand_technique.HandTechnique.predict', side_effect=AssertionError('recalculated')):
            html = self.render()
        for name in ('大安', '留连', '赤口'):
            self.assertIn(name, html)
        self.assertIn('未生成 AI 解读', html)
        self.assertNotIn('<h3>下一步</h3>', html)
        for i, relation in enumerate(self.prediction.relations):
            self.assertIn(describe_relation(self.prediction.symbols[i], self.prediction.symbols[i + 1], relation), html)
        self.assertIn(DISCLAIMER, html)

    def test_escapes_all_untrusted_text_and_uses_fixed_page_style(self):
        dangerous = '<script>alert("x")</script>&<img src="https://example.com">'
        session = complete(self.session, answer=dangerous, caution=dangerous, rationale=dangerous,
                           actions=(dangerous,), follow_up=dangerous, supplement=dangerous)
        html = render_report(self.prediction, variant='wechat', question=dangerous,
                             input_summary=dangerous, session=session)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('size: 108mm 192mm', html)
        self.assertIn('script-src \'none\'', html)
        self.assertIn('break-before: page', html)

    def test_print_explicit_excerpts_but_wechat_preserves_all_text(self):
        long = '核实实际条件。' * 500 + '末尾验收标记'
        session = complete(self.session, answer=long, actions=(long,), caution=long,
                           rationale=long, follow_up=long, supplement='补充事实')
        print_html = self.render(session=session)
        self.assertIn('…〔节选〕', print_html)
        self.assertIn('单页摘要', print_html)
        self.assertIn('必要提醒', print_html)
        self.assertIn('微信版', print_html)
        mobile = self.render('wechat', session=session)
        self.assertEqual(mobile.count(long), 5)
        self.assertIn('补充事实', mobile)
        self.assertIn('第 1 次补充', mobile)
        self.assertNotIn('〔节选〕', mobile)

    def test_timestamp_is_explicit_beijing_time_and_unknown_variant_rejected(self):
        html = self.render(generated_at=datetime(2026, 1, 1, 20, 30, tzinfo=timezone.utc))
        self.assertIn('2026-01-02 04:30 UTC+8', html)
        with self.assertRaises(ValueError):
            self.render('invalid')


if __name__ == '__main__':
    unittest.main()
