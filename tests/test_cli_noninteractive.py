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
from ai_agent import SupportedModels

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


def offline_agent(models=(SupportedModels.DEEPSEEK_FLASH,),
                  interpretation='【离线替身解读】', error=None):
    """离线 AI 替身：patch cli.DivinationAgent 用，绝不发起网络请求。"""
    agent = Mock()
    agent.get_available_models.return_value = list(models)
    if error is not None:
        agent.return_value.interpret_prediction.side_effect = error
    else:
        agent.return_value.interpret_prediction.return_value = interpretation
    return agent


class NonInteractiveQuestion(unittest.TestCase):
    """--question/--model 契约。所有 AI 路径都用进程内离线替身，不发起付费请求。"""

    def test_question_prints_local_table_then_interpretation(self):
        agent = offline_agent()
        with patch('cli.DivinationAgent', agent):
            code, stdout, stderr = run_cli(['--numbers', '1,2,3', '--question', '近期求职'])
        self.assertEqual(code, 0)
        self.assertIn('大安', stdout)
        self.assertIn('【离线替身解读】', stdout)
        self.assertLess(stdout.index('大安'), stdout.index('【离线替身解读】'))
        self.assertEqual(stderr, '')

    def test_interpretation_receives_symbols_and_question(self):
        agent = offline_agent()
        with patch('cli.DivinationAgent', agent):
            code, _, _ = run_cli(['--numbers', '1,2,3', '--question', '近期求职'])
        self.assertEqual(code, 0)
        symbols, question = agent.return_value.interpret_prediction.call_args[0]
        self.assertEqual([symbol.name for symbol in symbols], ['大安', '留连', '赤口'])
        self.assertEqual(question, '近期求职')

    def test_default_model_is_first_available(self):
        agent = offline_agent(models=(SupportedModels.DEEPSEEK_FLASH, SupportedModels.OPENAI_GPT56))
        with patch('cli.DivinationAgent', agent):
            code, _, _ = run_cli(['--numbers', '1,2,3', '--question', 'x'])
        self.assertEqual(code, 0)
        agent.assert_called_once_with(SupportedModels.DEEPSEEK_FLASH)

    def test_explicit_model_is_used(self):
        agent = offline_agent(models=())
        with patch('cli.DivinationAgent', agent):
            code, _, _ = run_cli(
                ['--numbers', '1,2,3', '--question', 'x', '--model', 'deepseek:deepseek-flash'])
        self.assertEqual(code, 0)
        agent.assert_called_once_with(SupportedModels.DEEPSEEK_FLASH)
        agent.get_available_models.assert_not_called()

    def test_model_without_question_stays_local_only(self):
        baseline_code, baseline_stdout, _ = run_cli(['--numbers', '1,2,3'])
        agent = offline_agent()
        with patch('cli.DivinationAgent', agent):
            code, stdout, stderr = run_cli(
                ['--numbers', '1,2,3', '--model', 'deepseek:deepseek-flash'])
        self.assertEqual(baseline_code, 0)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, baseline_stdout)
        self.assertEqual(stderr, '')
        agent.assert_not_called()

    def test_invalid_model_exits_usage_error(self):
        code, stdout, stderr = run_cli(['--numbers', '1,2,3', '--model', 'not-a-model'])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, '')
        self.assertIn('参数错误', stderr)
        self.assertIn('--model', stderr)

    def test_question_without_input_mode_exits_usage_error(self):
        for argv in (['--question', '近期求职'], ['--model', 'deepseek:deepseek-flash']):
            with self.subTest(argv=argv), \
                 patch('cli.DivinationAgent') as agent, \
                 patch('cli.interactive_main') as interactive:
                code, stdout, stderr = run_cli(argv)
            self.assertEqual(code, 2)
            self.assertEqual(stdout, '')
            self.assertIn('参数错误', stderr)
            agent.assert_not_called()
            interactive.assert_not_called()

    def test_blank_question_stays_local_only(self):
        _, baseline_stdout, _ = run_cli(['--numbers', '1,2,3'])
        baseline_payload = json.loads(run_cli(['--numbers', '1,2,3', '--json'])[1])
        agent = offline_agent()
        with patch('cli.DivinationAgent', agent):
            code, stdout, stderr = run_cli(['--numbers', '1,2,3', '--question', '   '])
            json_code, json_stdout, _ = run_cli(['--numbers', '1,2,3', '--json', '--question', '  '])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, baseline_stdout)
        self.assertEqual(stderr, '')
        self.assertEqual(json_code, 0)
        self.assertEqual(json.loads(json_stdout), baseline_payload)
        agent.assert_not_called()

    def test_no_available_model_with_question_exits_three(self):
        agent = offline_agent(models=())
        with patch('cli.DivinationAgent', agent):
            code, stdout, stderr = run_cli(['--numbers', '1,2,3', '--question', 'x'])
        self.assertEqual(code, 3)
        self.assertIn('大安', stdout)
        self.assertIn('模型', stderr)
        self.assertIn('AI解读失败', stderr)
        agent.assert_not_called()
        agent.return_value.assert_not_called()

    def test_no_available_model_json_payload(self):
        agent = offline_agent(models=())
        with patch('cli.DivinationAgent', agent):
            code, stdout, stderr = run_cli(['--numbers', '1,2,3', '--json', '--question', 'x'])
        self.assertEqual(code, 3)
        payload = json.loads(stdout)
        self.assertEqual(payload['question'], 'x')
        self.assertIsNone(payload['interpretation'])
        self.assertTrue(payload['error'])
        self.assertEqual([symbol['name'] for symbol in payload['symbols']], ['大安', '留连', '赤口'])
        self.assertEqual(payload['relations'], ['比和', '被克'])
        self.assertNotEqual(stderr, '')

    def test_ai_failure_keeps_local_result_text(self):
        agent = offline_agent(error=RuntimeError('provider down'))
        with patch('cli.DivinationAgent', agent):
            code, stdout, stderr = run_cli(['--numbers', '1,2,3', '--question', 'x'])
        self.assertEqual(code, 3)
        for fragment in ('大安', '留连', '赤口', '金克木，后传克前传'):
            self.assertIn(fragment, stdout)
        self.assertNotIn('【离线替身解读】', stdout)
        self.assertIn('AI解读失败', stderr)
        self.assertIn('provider down', stderr)

    def test_ai_failure_keeps_local_result_json(self):
        baseline = json.loads(run_cli(['--numbers', '1,2,3', '--json'])[1])
        agent = offline_agent(error=RuntimeError('provider down'))
        with patch('cli.DivinationAgent', agent):
            code, stdout, stderr = run_cli(['--numbers', '1,2,3', '--json', '--question', 'x'])
        self.assertEqual(code, 3)
        payload = json.loads(stdout)
        self.assertIsNone(payload['interpretation'])
        self.assertIn('provider down', payload['error'])
        self.assertEqual(payload['symbols'], baseline['symbols'])
        self.assertEqual(payload['relations'], baseline['relations'])
        self.assertEqual(payload['relation_descriptions'], baseline['relation_descriptions'])
        self.assertIn('provider down', stderr)

    def test_json_with_question_success_adds_two_fields(self):
        agent = offline_agent()
        with patch('cli.DivinationAgent', agent):
            code, stdout, stderr = run_cli(['--numbers', '1,2,3', '--json', '--question', '近期求职'])
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(set(payload), {'input', 'symbols', 'relations', 'relation_descriptions',
                                        'question', 'interpretation'})
        self.assertEqual(payload['question'], '近期求职')
        self.assertEqual(payload['interpretation'], '【离线替身解读】')
        self.assertEqual(stderr, '')

    def test_ai_progress_output_never_reaches_stdout(self):
        def chatty(symbols, question):
            print('PROGRESS-CHATTER')
            return '【离线替身解读】'

        agent = offline_agent()
        agent.return_value.interpret_prediction.side_effect = chatty
        with patch('cli.DivinationAgent', agent):
            json_code, json_stdout, _ = run_cli(['--numbers', '1,2,3', '--json', '--question', 'x'])
            text_code, text_stdout, _ = run_cli(['--numbers', '1,2,3', '--question', 'x'])
        self.assertEqual(json_code, 0)
        json.loads(json_stdout)
        self.assertNotIn('PROGRESS-CHATTER', json_stdout)
        self.assertEqual(text_code, 0)
        self.assertNotIn('PROGRESS-CHATTER', text_stdout)
        self.assertEqual(text_stdout.count('【离线替身解读】'), 1)

    def test_question_stdout_keeps_local_prefix(self):
        _, plain_stdout, _ = run_cli(['--numbers', '1,2,3'])
        agent = offline_agent()
        with patch('cli.DivinationAgent', agent):
            code, stdout, _ = run_cli(['--numbers', '1,2,3', '--question', '近期求职'])
        self.assertEqual(code, 0)
        self.assertTrue(stdout.startswith(plain_stdout))


class NonInteractiveSubprocess(unittest.TestCase):
    """进程级用法/取值错误。带输入模式的 --question 会用 .env 真实密钥发起付费请求，
    因此 AI 路径只在 NonInteractiveQuestion 里用进程内替身验证。"""

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

    def test_invalid_model_exit_code(self):
        result = self._run('--numbers', '1,2,3', '--model', 'not-a-model')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('参数错误', result.stderr)

    def test_question_without_input_mode_exit_code(self):
        result = self._run('--question', '近期求职')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
