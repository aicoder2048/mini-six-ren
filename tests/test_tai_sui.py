import copy
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import cli
from rich.console import Console
from utils import tai_sui
from utils.bazi_calculator import calculate_bazi
from utils.calendar_converter import format_bazi_output, format_tai_sui_section, solar_to_lunar
from utils.five_elements_utils import analyze_wuxing
from utils.tai_sui import TaiSuiData, TaiSuiDataError, TAI_SUI_DATA, analyze_tai_sui


def relation(kind, combination, branches, explanation, subtype=None):
    return dict(relation_type=kind, subtype=subtype, combination=combination,
                branches=branches, explanation=explanation)


class LoaderTests(unittest.TestCase):
    def test_all_shapes_and_sparse_years(self):
        self.assertEqual(set(TAI_SUI_DATA), set('子丑寅卯辰巳午未申酉戌亥'))
        for path in (ROOT / 'data').glob('太岁_*.json'):
            raw = json.loads(path.read_text())
            label = path.stem[3:]
            with self.subTest(file=path.name):
                self.assertEqual(list(raw), [label if label in ('丑牛', '午马', '寅虎', '巳蛇') else '太岁'])
                branch, normalized = TaiSuiData.load_file(path)
                self.assertEqual(branch, label[0])
                self.assertEqual(normalized['年份'], {y['年']: y['神煞'] for y in next(iter(raw.values()))['年份']})
                for group in ('犯太岁', '合太岁'):
                    for kind, entries in next(iter(raw.values()))[group].items():
                        entries = [entries] if isinstance(entries, dict) else entries
                        self.assertEqual(normalized[group][kind], [relation(kind, e['组合'], e['地支'], e['解释'], e.get('类型')) for e in entries])
        self.assertEqual(len(TAI_SUI_DATA['申']['年份']), 4)
        self.assertEqual(len(TAI_SUI_DATA['酉']['年份']), 4)
        self.assertNotIn('相生太岁', TAI_SUI_DATA['卯']['合太岁'])
        self.assertIn('相克太岁', TAI_SUI_DATA['卯']['犯太岁'])
        self.assertEqual(TAI_SUI_DATA['卯']['犯太岁']['刑太岁'][1]['branches'], ['卯', '卯'])

    def test_missing_unreadable_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for source in (ROOT / 'data').glob('太岁_*.json'):
                shutil.copy(source, folder)
            path = folder / '太岁_卯兔.json'
            original = path.read_bytes()
            path.unlink()
            with self.assertRaisesRegex(TaiSuiDataError, str(path)):
                TaiSuiData.load_all(folder)
            for bad in (b'\xff', b'{', b'[]', ' {"太岁": {}}'.encode('utf-8')):
                path.write_bytes(bad)
                with self.subTest(bad=bad), self.assertRaisesRegex(TaiSuiDataError, str(path)):
                    TaiSuiData.load_all(folder)
            path.write_bytes(original)
            with patch.object(Path, 'read_text', side_effect=PermissionError('denied')):
                with self.assertRaisesRegex(TaiSuiDataError, str(path)) as error:
                    TaiSuiData.load_file(path)
                self.assertIsInstance(error.exception.__cause__, PermissionError)
            extra = folder / '太岁_卯兔副本.json'
            extra.write_bytes(original)
            with self.assertRaisesRegex(TaiSuiDataError, str(extra)):
                TaiSuiData.load_all(folder)
            extra.rename(folder / '太岁_未知.json')
            with self.assertRaisesRegex(TaiSuiDataError, '太岁_未知.json'):
                TaiSuiData.load_all(folder)

    def test_invalid_structures_name_file(self):
        raw = json.loads((ROOT / 'data/太岁_卯兔.json').read_text())
        mutations = [
            lambda r: r.update(年份={}),
            lambda r: r['年份'].append(copy.deepcopy(r['年份'][0])),
            lambda r: r['年份'][0].update(年='甲子年'),
            lambda r: r['年份'][0].update(神煞=['名字', 1]),
            lambda r: r.update(犯太岁=[]),
            lambda r: r['犯太岁'].update(冲太岁=42),
            lambda r: r['犯太岁']['冲太岁'].update(地支=[]),
            lambda r: r['犯太岁']['冲太岁'].update(地支=['兔']),
            lambda r: r['犯太岁']['冲太岁'].update(解释=None),
            lambda r: r['犯太岁']['冲太岁'].pop('组合'),
            lambda r: r['犯太岁']['冲太岁'].update(类型=1),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '太岁_卯兔.json'
            for mutate in mutations:
                broken = copy.deepcopy(raw)
                mutate(broken['太岁'])
                path.write_text(json.dumps(broken))
                with self.subTest(mutation=mutate), self.assertRaisesRegex(TaiSuiDataError, str(path)):
                    TaiSuiData.load_file(path)

    def test_import_from_other_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-c', 'from utils.tai_sui import TAI_SUI_DATA; assert len(TAI_SUI_DATA) == 12'],
                                    cwd=directory, env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_cached_data_and_return_isolation(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('must not read')):
            first = analyze_tai_sui('卯', 2023)
            first['fan_tai_sui'][0]['branches'].clear()
            first['fan_tai_sui'][1]['explanation'] = 'changed'
            second = analyze_tai_sui('卯', 2023)
            self.assertEqual(second['fan_tai_sui'][0]['branches'], ['卯'])
            self.assertNotEqual(second['fan_tai_sui'][1]['explanation'], 'changed')


class AnalysisTests(unittest.TestCase):
    # Fixed expectations transcribed from 太岁_卯兔.json and 太岁_丑牛.json.
    def test_value_and_self_punishment(self):
        result = analyze_tai_sui('卯', 2023)
        self.assertEqual(result['chinese_year'], '癸卯[兔]')
        self.assertEqual(result['source_file'], '太岁_卯兔.json')
        self.assertEqual(result['general'], '陈大将军')
        self.assertEqual(result['general_description'], '癸卯年值年太岁神煞，象征稳健和耐力，提醒一年中的稳定和持续发展。')
        self.assertEqual(result['fan_tai_sui'], [
            relation('值太岁', '卯值卯', ['卯'], '值太岁指的是流年太岁与自身生肖相同，表示该年运势可能会遇到更多挑战，需要谨慎行事和积极应对。'),
            relation('刑太岁', '卯自刑', ['卯', '卯'], '卯（兔）与自身相刑，意味着内心矛盾和自我冲突，需要自我反省和调整。', '自刑'),
        ])
        self.assertEqual(result['he_tai_sui'], [])
        self.assertEqual(result['summary'], '犯太岁')

    def test_clash_and_break_both_reported(self):
        result = analyze_tai_sui('酉', 2023)
        self.assertEqual(result['fan_tai_sui'], [
            relation('冲太岁', '卯酉冲', ['卯', '酉'], '卯（兔）与酉（鸡）相冲，木金相克，通常代表冲突和竞争。'),
            relation('破太岁', '卯酉破', ['卯', '酉'], '卯（兔）与酉（鸡）相破，木金相克，表示该年可能会出现突如其来的变化或意外事件，需保持警惕。'),
        ])
        self.assertEqual(result['he_tai_sui'], [])

    def test_union(self):
        result = analyze_tai_sui('戌', 2023)
        self.assertEqual(result['fan_tai_sui'], [])
        self.assertEqual(result['he_tai_sui'], [relation('六合太岁', '卯戌合', ['卯', '戌'], '卯（兔）和戌（狗）相合，木土虽有相克但也有相生之象，可能带来复杂的局面。')])
        self.assertEqual(result['summary'], '合太岁')

    def test_no_relation_and_indirect_entries_excluded(self):
        for year in (2023, 2021):
            result = analyze_tai_sui('寅', year)
            self.assertEqual(result['fan_tai_sui'], [])
            self.assertEqual(result['he_tai_sui'], [])
            self.assertEqual(result['summary'], '无特殊关系')
            self.assertEqual(result['general_status'], 'available')

    def test_sparse_years(self):
        for branch, year, label in [('申', 2028, '戊申[猴]'), ('酉', 2029, '己酉[鸡]')]:
            result = analyze_tai_sui(branch, year)
            self.assertEqual(result['chinese_year'], label)
            self.assertIsNone(result['general'])
            self.assertIsNone(result['general_description'])
            self.assertEqual(result['general_status'], 'missing')
            self.assertEqual(result['fan_tai_sui'][0]['relation_type'], '值太岁')
        self.assertEqual(analyze_tai_sui('申', 2016)['general'], '张飞大将军')

    def test_fan_and_he_simultaneous(self):
        result = analyze_tai_sui('巳', 2021)
        self.assertEqual(result['general'], '彭基大将军')
        self.assertEqual(result['summary'], '犯太岁、合太岁')
        self.assertEqual(result['fan_tai_sui'], [relation('破太岁', '丑巳破', ['丑', '巳'], '丑（牛）与巳（蛇）相破，土火相克，表示该年可能会出现突如其来的变化或意外事件，需保持警惕和灵活应对。')])
        self.assertEqual(result['he_tai_sui'], [
            relation('三合太岁', '丑巳酉三合', ['丑', '巳', '酉'], '丑（牛）、巳（蛇）和酉（鸡）形成三合金局，土火金相生，有助于事业发展和财富积累。'),
            relation('相生太岁', '火生土', ['巳', '丑'], '巳（蛇）生丑（牛），火生土，有助于丑牛的能量提升和事业发展。'),
            relation('得助太岁', '土火相助', ['丑', '巳'], '丑（牛）和巳（蛇）相助，火生土，增强丑牛的能量和活力，有利于突破和创新。'),
        ])

    def test_same_category_preserves_all_entries(self):
        data = copy.deepcopy(TAI_SUI_DATA)
        data['卯']['犯太岁']['冲太岁'] *= 2
        with patch.object(tai_sui, 'TAI_SUI_DATA', data):
            self.assertEqual([r['relation_type'] for r in analyze_tai_sui('酉', 2023)['fan_tai_sui']], ['冲太岁', '冲太岁', '破太岁'])

    def test_beijing_year_boundary(self):
        for instant, year in [(datetime(2025, 12, 31, 15, 59, 59, tzinfo=timezone.utc), 2025),
                              (datetime(2025, 12, 31, 16, 0, 0, tzinfo=timezone.utc), 2026)]:
            def now(tz):
                self.assertEqual(tz.utcoffset(instant), timedelta(hours=8))
                return instant.astimezone(tz)
            with patch.object(tai_sui, 'datetime') as clock:
                clock.now.side_effect = now
                self.assertEqual(analyze_tai_sui('子')['target_year'], year)
                clock.now.assert_called_once()
        with patch.object(tai_sui, 'datetime') as clock:
            analyze_tai_sui('子', 2023)
            clock.now.assert_not_called()

    def test_input_validation(self):
        for year in (1900, 2099):
            self.assertEqual(analyze_tai_sui('子', year)['target_year'], year)
        for year in (1899, 2100, True, False, 2023.0, '2023', []):
            with self.subTest(year=year), self.assertRaises(ValueError):
                analyze_tai_sui('子', year)
        for branch in ('', '兔', '癸卯', '子丑', 'a', None, [], 1):
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                analyze_tai_sui(branch, 2023)


class PresentationTests(unittest.TestCase):
    def test_rows_preserve_every_explanation_and_missing_status(self):
        for branch, year in [('卯', 2023), ('酉', 2023), ('戌', 2023), ('寅', 2023), ('巳', 2021), ('申', 2028), ('酉', 2029)]:
            result = analyze_tai_sui(branch, year)
            rows = format_tai_sui_section(result)
            text = '\n'.join(f'{key}：{value}' for key, value in rows)
            self.assertIn('按北京时间公历年', text)
            self.assertIn(result['summary'], text)
            for entry in result['fan_tai_sui'] + result['he_tai_sui']:
                self.assertIn(entry['explanation'], text)
                self.assertIn(entry['relation_type'], text)
                self.assertIn(entry['combination'], text)
            if result['general_status'] == 'missing':
                self.assertIn(f"数据未收录{result['chinese_year'][:2]}年值年太岁", text)
                self.assertNotIn('None', text)
            else:
                self.assertIn(result['general_description'], text)

    def test_old_output_and_cli_append_only(self):
        baseline = json.loads((ROOT / 'tests/fixtures/tai_sui_bazi_baseline.json').read_text())
        for case in baseline['cases']:
            with self.subTest(date=case['date']):
                y, m, d = map(int, case['date'].split('-'))
                h, mi = map(int, case['time'].split(':'))
                bazi = calculate_bazi(y, m, d, h, mi)
                args = (bazi, analyze_wuxing(bazi), case['date'], case['time'], solar_to_lunar(y, m, d), case['gender'])
                formatted = format_bazi_output(*args, target_year=2023)
                self.assertEqual(formatted.pop('tai_sui_info'), analyze_tai_sui(bazi['year'][1], 2023))
                self.assertEqual(formatted, case['formatted'])
                self.assertIn('tai_sui_info', format_bazi_output(*args))
                if case['date'] == '2023-01-15':
                    self.assertEqual(bazi['year'][1], '寅')
                for year in (2023, 2028):
                    stream = io.StringIO()
                    result = analyze_tai_sui(bazi['year'][1], year)
                    with patch.object(cli, 'console', Console(file=stream, width=100, color_system=None)), \
                            patch.object(cli.Prompt, 'ask', side_effect=[case['date'], case['time'], case['gender']]), \
                            patch.object(cli.random, 'randint', return_value=1234), \
                            patch.object(cli, 'analyze_tai_sui', return_value=result) as analyze:
                        cli.bazi_calculation()
                    analyze.assert_called_once_with(bazi['year'][1])
                    output = stream.getvalue()
                    before, section = output.split('\n流年太岁：\n')
                    new_section, separator = section.rsplit('\n' + '─' * 80, 1)
                    self.assertEqual(before + '\n' + '─' * 80 + separator, case['cli'])
                    self.assertIn(result['summary'], new_section)
                    # Rich may wrap explanations; compare the exact independently rendered rows.
                    expected = io.StringIO()
                    console = Console(file=expected, width=100, color_system=None)
                    for key, value in format_tai_sui_section(result):
                        console.print(f'  {key}：{value}')
                    self.assertEqual(new_section, expected.getvalue())


if __name__ == '__main__':
    unittest.main()
