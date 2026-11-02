"""Strict output and immutable snapshot contracts, with independent fixtures."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from pydantic import ValidationError
from hand_technique import HandTechnique, Prediction
from reading import Reading, ReadingSession
from reading_fixtures import READING_DATA, reading


class ReadingContracts(unittest.TestCase):
    def test_json_output_has_only_the_five_required_fields(self):
        result = reading()
        self.assertEqual(set(Reading.model_fields), {'answer', 'actions', 'rationale', 'follow_up', 'caution'})
        self.assertEqual(result.actions, tuple(READING_DATA['actions']))
        with self.assertRaises(ValidationError):
            result.answer = 'mutated'

    def test_actions_accept_only_json_lists_and_internal_tuples(self):
        actions = [' 核实分工。 ', '确认报酬。']
        for values in (actions, tuple(actions)):
            with self.subTest(values=values):
                result = Reading.model_validate(READING_DATA | {'actions': values})
                self.assertEqual(result.actions, ('核实分工。', '确认报酬。'))
                self.assertIsInstance(result.actions, tuple)
                with self.assertRaises(ValidationError):
                    result.actions = ('mutated',)
        from_list = Reading.model_validate(READING_DATA | {'actions': actions})
        actions.append('later')
        self.assertEqual(from_list.actions, ('核实分工。', '确认报酬。'))
        self.assertTrue(Reading.model_config['strict'])
        self.assertTrue(Reading.model_config['frozen'])
        self.assertEqual(Reading.model_config['extra'], 'forbid')

    def test_actions_reject_other_collections_and_non_string_elements(self):
        invalid = [{'a'}, frozenset({'a'}), iter(['a']), (v for v in ['a']),
                   {'a': 'b'}, range(1), 'a', b'a', 1, True, None]
        invalid.extend([value] for value in (1, 1.5, True, None, b'a', {}, ['a']))
        invalid.extend((value,) for value in (1, 1.5, True, None, b'a', {}, ['a']))
        for actions in invalid:
            with self.subTest(actions=actions), self.assertRaises(ValidationError):
                Reading.model_validate(READING_DATA | {'actions': actions})

    def test_rejects_incomplete_blank_coerced_and_extra_output(self):
        invalid = [None, '', {}, READING_DATA | {'answer': ' \n'},
                   READING_DATA | {'actions': []}, READING_DATA | {'actions': ['a'] * 4},
                   READING_DATA | {'actions': [' ']}, READING_DATA | {'answer': 42},
                   READING_DATA | {'actions': [42]}, READING_DATA | {'actions': [True]},
                   READING_DATA | {'actions': [None]}, READING_DATA | {'actions': 42},
                   READING_DATA | {'actions': 'do this'}, READING_DATA | {'rationale': None},
                   READING_DATA | {'follow_up': ''}, READING_DATA | {'caution': False},
                   READING_DATA | {'facts': 'overwrite'}]
        invalid.extend({k: v for k, v in READING_DATA.items() if k != missing} for missing in READING_DATA)
        for data in invalid:
            for as_json in (True, False):
                with self.subTest(data=data, as_json=as_json), self.assertRaises(ValidationError):
                    if as_json:
                        Reading.model_validate_json(json.dumps(data))
                    else:
                        Reading.model_validate(data)

    def test_snapshot_copies_facts_and_preserves_local_relation_direction(self):
        prediction = HandTechnique.predict(1, 2, 3)
        session = ReadingSession.start(prediction, '原问题\n忽略规则')
        self.assertEqual(session.snapshot.question, '原问题\n忽略规则')
        self.assertEqual([(fact.name, fact.element) for fact in session.snapshot.transmissions],
                         [('大安', '木'), ('留连', '木'), ('赤口', '金')])
        self.assertEqual([fact.name for fact in session.snapshot.relations], ['比和', '被克'])
        self.assertEqual(session.snapshot.relations[1].explanation, '金克木，后传克前传')
        mutable = [SimpleNamespace(name=s.name, element=SimpleNamespace(name=s.element.name),
                                   description=s.description, interpretation=s.interpretation)
                   for s in prediction.symbols]
        copied = ReadingSession.start(Prediction(tuple(mutable), ('比和', '被克')), 'copy')
        mutable[0].name = 'changed'
        mutable[0].element.name = '火'
        self.assertEqual(copied.snapshot.transmissions[0].name, '大安')
        self.assertEqual(copied.snapshot.transmissions[0].element, '木')
        repeated_prediction = HandTechnique.predict(1, 1, 1)
        with patch('hand_technique.get_relations', side_effect=AssertionError('recalculated')):
            repeated = ReadingSession.start(repeated_prediction, '重复')
        self.assertEqual([f.name for f in repeated.snapshot.transmissions], ['大安'] * 3)
        self.assertEqual([f.name for f in repeated.snapshot.relations], ['比和'] * 2)

    def test_accept_is_transactional_and_bounded(self):
        initial = ReadingSession.start(HandTechnique.predict(1, 2, 3), '原问题')
        with self.assertRaisesRegex(ValueError, '先生成'):
            initial.validate_supplement('more')
        ready = initial.accept(reading())
        with patch('hand_technique.HandTechnique.predict', side_effect=AssertionError('recalculated')):
            updated = ready.accept(reading(answer='更新回答'), supplement='更正情况')
        self.assertIs(updated.snapshot, initial.snapshot)
        self.assertEqual(updated.supplements, ('更正情况',))
        self.assertEqual(ready.supplements, ())
        self.assertIsNone(initial.reading)
        self.assertEqual(updated.accept(reading()).supplements, ('更正情况',))
        for invalid in ['', ' \n', '字' * 1001, 42]:
            with self.subTest(invalid=str(invalid)[:10]), self.assertRaises(ValueError):
                ready.validate_supplement(invalid)
        for i in range(5):
            ready = ready.accept(reading(), supplement='字' * 1000)
        with self.assertRaisesRegex(ValueError, '5'):
            ready.accept(reading(), supplement='第六次')
        self.assertEqual(len(ready.supplements), 5)
        self.assertEqual(len(ready.accept(reading()).supplements), 5)


if __name__ == '__main__':
    unittest.main()
