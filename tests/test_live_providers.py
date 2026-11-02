"""Opt-in live check that each configured provider returns a valid Reading.

Skipped unless MSR_LIVE_AI=1, because it calls paid provider APIs (one short request per provider with a key):
    MSR_LIVE_AI=1 uv run python -m unittest tests.test_live_providers -v
Offline fakes cannot catch provider-side request rejections, such as reasoning models refusing a forced
tool call on chat completions, which broke every AI interpretation on 2026-11-01.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from dotenv import load_dotenv

from ai_agent import DivinationAgent, SupportedModels
from hand_technique import HandTechnique
from reading import ReadingSession


@unittest.skipUnless(os.getenv('MSR_LIVE_AI') == '1', 'set MSR_LIVE_AI=1 to call real providers (paid)')
class LiveProviders(unittest.TestCase):
    def test_each_configured_provider_returns_valid_reading(self):
        load_dotenv()
        configured = [m for m in SupportedModels if os.getenv(SupportedModels.get_api_key_name(m))]
        if not configured:
            self.skipTest('no provider API key configured')
        for model in configured:
            with self.subTest(model=model.value):
                key = os.getenv(SupportedModels.get_api_key_name(model))
                agent = DivinationAgent(model, api_key=key)  # the desktop path: explicit key snapshot
                session = ReadingSession.start(HandTechnique.predict(3, 5, 7), '这周适合开始新项目吗？')
                result = agent.interpret_prediction(session)
                self.assertTrue(result.reading.answer.strip())
                self.assertTrue(1 <= len(result.reading.actions) <= 3)
                self.assertIs(result.snapshot, session.snapshot)


if __name__ == '__main__':
    unittest.main()
