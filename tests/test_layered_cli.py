"""Drive the CLI submenu, including transactional supplement retries."""
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import cli
from ai_agent import SupportedModels
from hand_technique import HandTechnique
from reading_fixtures import complete


class LayeredCLI(unittest.TestCase):
    def drive(self, prompts, respond):
        output = io.StringIO()
        console = cli.Console(file=output, width=120)
        with patch('cli.get_menu_choice', side_effect=[1, 'home']), \
             patch('cli.select_llm_model', return_value=SupportedModels.OPENAI_GPT61_SOL), \
             patch('cli.Prompt.ask', side_effect=prompts), \
             patch('cli.DivinationAgent') as factory, \
             patch('cli.HandTechnique.predict', wraps=HandTechnique.predict) as predict, \
             patch('cli.console', console), patch('cli.Console', return_value=console):
            factory.return_value.interpret_prediction.side_effect = respond
            cli.xiaoliu_submenu()
            predict.assert_called_once_with(1, 2, 3)
        return output.getvalue(), factory.return_value.interpret_prediction

    def test_actual_entry_prints_all_fields_as_text_and_updates_same_snapshot(self):
        seen = []

        def respond(session, *, supplement=None):
            seen.append(session)
            return complete(session, supplement=supplement, answer='<script>[red]回答</script>',
                            caution='有症状请及时就医，不要据此停药。')

        output, request = self.drive(['1,2,3', '原问题', 's', '新的情况', 'b'], respond)
        self.assertEqual(request.call_count, 2)
        self.assertIs(seen[0].snapshot, seen[1].snapshot)
        self.assertEqual(seen[1].snapshot.question, '原问题')
        for value in ['<script>[red]回答</script>', '下一步', '三传依据', '金克木',
                      '大安', '目前最需要确认的是分工还是报酬？', '不要据此停药']:
            self.assertIn(value, output)

    def test_script_entry_completes_local_prediction_without_credentials(self):
        root = Path(__file__).resolve().parents[1]
        env = {name: os.environ[name] for name in ('PATH', 'HOME', 'SYSTEMROOT', 'WINDIR')
               if name in os.environ}
        env.update({'OPENAI_API_KEY': '', 'DEEPSEEK_API_KEY': '', 'TERM': 'dumb',
                    'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'PYTHONNOUSERSITE': '1'})
        script = dedent('''
            import runpy
            import sys
            from pathlib import Path
            from unittest.mock import patch

            root = Path(sys.argv[1])
            sys.path.insert(0, str(root / 'src'))
            with patch('dotenv.load_dotenv', return_value=False) as load, \\
                 patch('dotenv.main.find_dotenv', side_effect=AssertionError('dotenv search forbidden')) as find, \\
                 patch('dotenv.main.open', create=True,
                       side_effect=AssertionError('dotenv file access forbidden')) as dotenv_open:
                from pydantic_ai import models
                models.ALLOW_MODEL_REQUESTS = False
                try:
                    runpy.run_path(str(root / 'src' / 'cli.py'), run_name='__main__')
                finally:
                    load.assert_called()
                    find.assert_not_called()
                    dotenv_open.assert_not_called()
        ''')
        result = subprocess.run(
            [sys.executable, '-c', script, str(root)], input='1\n1\n1,2,3\nh\nq\n',
            env=env, cwd=root, text=True, encoding='utf-8', capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for value in ['本地模式', '大安', '留连', '赤口', '金克木', '感谢使用']:
            self.assertIn(value, result.stdout)
        self.assertEqual(result.stdout.count('解读用于梳理思路'), 1)

    def test_failure_retry_keeps_last_success_and_pending_input(self):
        snapshots, supplements = [], []

        def respond(session, *, supplement=None):
            snapshots.append(session.snapshot)
            supplements.append((session.supplements, supplement))
            if len(supplements) in (1, 3):
                raise RuntimeError('raw secret-api-key')
            return complete(session, supplement=supplement)

        output, request = self.drive(['1,2,3', '原问题', 'r', 's', 'pending', 'r', 'b'], respond)
        self.assertEqual(request.call_count, 4)
        self.assertTrue(all(s is snapshots[0] for s in snapshots))
        self.assertEqual(supplements, [((), None), ((), None), ((), 'pending'), ((), 'pending')])
        self.assertIn('本地结果已保留', output)
        self.assertIn('已有解读已保留', output)
        self.assertNotIn('secret-api-key', output)
        self.assertNotIn('raw', output)


if __name__ == '__main__':
    unittest.main()
