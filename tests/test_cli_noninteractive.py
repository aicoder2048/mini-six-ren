"""Behavior contracts for the non-interactive CLI entry point (--numbers/--date/--chars/--json)."""
import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import cli

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(argv):
    """Run cli.main in-process, returning (exit_code, stdout, stderr)."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class NonInteractiveEntry(unittest.TestCase):
    def test_bare_invocation_still_enters_interactive_menu(self):
        with patch('cli.interactive_main') as interactive:
            self.assertEqual(cli.main([]), 0)
        interactive.assert_called_once_with()

    def test_parameterized_invocation_skips_interactive_menu(self):
        with patch('cli.interactive_main') as interactive:
            code, _, _ = run_cli(['--numbers', '1,2,3'])
        self.assertEqual(code, 0)
        interactive.assert_not_called()

    def test_non_interactive_modes_never_touch_ai_or_menu(self):
        modes = [
            ['--numbers', '1,2,3'],
            ['--date', '2026-09-17', '--time', '14:00'],
            ['--chars', '天地人'],
        ]
        for argv in modes:
            with self.subTest(argv=argv), \
                 patch('cli.interactive_main') as interactive, \
                 patch('cli.DivinationAgent') as agent, \
                 patch('cli.select_llm_model') as select, \
                 patch('cli.get_menu_choice') as menu, \
                 patch('cli.Prompt.ask') as ask:
                code, _, _ = run_cli(argv)
                self.assertEqual(code, 0)
                interactive.assert_not_called()
                agent.assert_not_called()
                select.assert_not_called()
                menu.assert_not_called()
                ask.assert_not_called()

    def test_numbers_text_output_matches_format_prediction(self):
        code, stdout, stderr = run_cli(['--numbers', '1,2,3'])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, '')
        for fragment in ['大安', '留连', '赤口', '（木）', '（金）', '比和', '被克',
                         '同属木，性质相近', '金克木，后传克前传']:
            self.assertIn(fragment, stdout)

    def test_numbers_json_structure(self):
        code, stdout, _ = run_cli(['--numbers', '1,2,3', '--json'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout), {
            'input': {'mode': 'numbers', 'numbers': [1, 2, 3]},
            'symbols': [
                {'name': '大安', 'element': '木'},
                {'name': '留连', 'element': '木'},
                {'name': '赤口', 'element': '金'},
            ],
            'relations': ['比和', '被克'],
            'relation_descriptions': ['同属木，性质相近', '金克木，后传克前传'],
        })

    def test_json_stdout_is_a_single_clean_document(self):
        code, stdout, _ = run_cli(['--numbers', '1,2,3', '--json'])
        self.assertEqual(code, 0)
        json.loads(stdout)
        self.assertNotIn('欢迎使用', stdout)

    def test_date_mode_uses_shared_calendar_conversion(self):
        code, stdout, _ = run_cli(['--date', '2026-09-17', '--time', '14:00', '--json'])
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        # 农历八月七日 + 未时编号 8，按领域规则手工列出。
        self.assertEqual(payload['input'], {
            'mode': 'date', 'date': '2026-09-17', 'time': '14:00', 'numbers': [8, 7, 8],
        })
        self.assertEqual([symbol['name'] for symbol in payload['symbols']], ['桃花', '小吉', '速喜'])

    def test_chars_mode_uses_stroke_dictionary(self):
        code, stdout, _ = run_cli(['--chars', '天地人', '--json'])
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        # 字典笔画 天4 / 地6 / 人2。
        self.assertEqual(payload['input'], {'mode': 'chars', 'chars': '天地人', 'numbers': [4, 6, 2]})
        self.assertEqual([symbol['name'] for symbol in payload['symbols']], ['赤口', '天德', '大安'])

        separated = run_cli(['--chars', '天,地,人', '--json'])
        self.assertEqual(separated[0], 0)
        self.assertEqual(json.loads(separated[1]), payload)

    def test_invalid_numbers_exit_with_input_error(self):
        for value in ['0,2,3', '1000,2,3', '1,2', '1,2,3,4', '1.5,2,3', 'a,2,3']:
            with self.subTest(value=value):
                code, stdout, stderr = run_cli(['--numbers', value])
                self.assertEqual(code, 1)
                self.assertEqual(stdout, '')
                self.assertIn('输入错误', stderr)
        code, stdout, stderr = run_cli(['--numbers=-1,2,3'])
        self.assertEqual(code, 1)
        self.assertEqual(stdout, '')
        self.assertIn('输入错误', stderr)

    def test_invalid_date_time_exit_with_input_error(self):
        for date_text, time_text in [
            ('2026-02-30', '12:00'),
            ('1899-01-01', '12:00'),
            ('2026/09/17', '12:00'),
            ('2026-09-17', '25:00'),
        ]:
            with self.subTest(date=date_text, time=time_text):
                code, stdout, stderr = run_cli(['--date', date_text, '--time', time_text])
                self.assertEqual(code, 1)
                self.assertEqual(stdout, '')
                self.assertIn('输入错误', stderr)

    def test_invalid_chars_exit_with_input_error(self):
        for value in ['abc', '天地', '天地人四']:
            with self.subTest(value=value):
                code, stdout, stderr = run_cli(['--chars', value])
                self.assertEqual(code, 1)
                self.assertEqual(stdout, '')
                self.assertIn('输入错误', stderr)

    def test_usage_errors_exit_with_code_two(self):
        for argv in [['--date', '2026-09-17'], ['--time', '14:00'], ['--json']]:
            with self.subTest(argv=argv):
                code, stdout, stderr = run_cli(argv)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, '')
                self.assertIn('参数错误', stderr)


class NonInteractiveSubprocess(unittest.TestCase):
    def _run(self, *args):
        environment = os.environ | {'PYTHONIOENCODING': 'utf-8'}
        return subprocess.run(
            [sys.executable, 'src/cli.py', *args],
            cwd=PROJECT_ROOT,
            env=environment,
            text=True,
            encoding='utf-8',
            capture_output=True,
            check=False,
        )

    def test_json_success_exit_code(self):
        result = self._run('--numbers', '1,2,3', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['relations'], ['比和', '被克'])

    def test_out_of_range_numbers_exit_code(self):
        result = self._run('--numbers', '0,2,3')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertIn('1-999', result.stderr)

    def test_non_chinese_exit_code(self):
        result = self._run('--chars', 'abc')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')

    def test_missing_time_exit_code(self):
        result = self._run('--date', '2026-09-17')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
