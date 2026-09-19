import asyncio
import json
import math
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from symbols import SYMBOLS
from hand_technique import HandTechnique
from web import (build_palace_walk, build_palace_animation, palace_animation_css,
                 build_palace_hands, _palace_coordinates, PALACE_RADIUS)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYMBOLS_JSON = json.loads((PROJECT_ROOT / 'data' / 'symbols.json').read_text(encoding='utf-8'))
JSON_BY_ORDER = sorted(SYMBOLS_JSON, key=lambda row: row['order'])
JSON_NAMES = [row['name'] for row in JSON_BY_ORDER]


class PalaceWalkModel(unittest.TestCase):
    """纯展示模型的独立样例：期望值全部手写，不由实现反推。"""

    def test_palace_order_and_names_follow_readonly_json(self):
        walk = build_palace_walk((1, 1, 1))
        self.assertEqual([symbol.order for symbol in walk.palaces], list(range(1, 10)))
        self.assertEqual([symbol.name for symbol in walk.palaces], JSON_NAMES)
        # 当前 SYMBOLS 的加载顺序必须与 order 排序一致，否则显示会与核心分叉。
        self.assertEqual([symbol.name for symbol in SYMBOLS], JSON_NAMES)

    def test_single_step_stays_in_place(self):
        walk = build_palace_walk((1, 1, 1))
        self.assertEqual([segment.sequence for segment in walk.segments], [(0,), (0,), (0,)])
        self.assertEqual([segment.landing_index for segment in walk.segments], [0, 0, 0])
        self.assertEqual([segment.number for segment in walk.segments], [1, 1, 1])
        self.assertEqual([segment.moves for segment in walk.segments], [0, 0, 0])
        self.assertEqual([walk.palaces[index].name for index in (0, 0, 0)], ['大安', '大安', '大安'])

    def test_walk_keeps_inclusive_counting_and_continues_from_landing(self):
        walk = build_palace_walk((1, 2, 3))
        self.assertEqual([segment.sequence for segment in walk.segments],
                         [(0,), (0, 1), (1, 2, 3)])
        self.assertEqual([segment.start_index for segment in walk.segments], [0, 0, 1])
        self.assertEqual([segment.landing_index for segment in walk.segments], [0, 1, 3])
        self.assertEqual([walk.palaces[segment.landing_index].name for segment in walk.segments],
                         ['大安', '留连', '赤口'])
        self.assertEqual(walk.segments[0].visit_counts, (1, 0, 0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(walk.segments[1].visit_counts, (1, 1, 0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(walk.segments[2].visit_counts, (0, 1, 1, 1, 0, 0, 0, 0, 0))

    def test_crossing_the_boundary(self):
        walk = build_palace_walk((9, 9, 9))
        self.assertEqual([segment.landing_index for segment in walk.segments], [8, 7, 6])
        self.assertEqual([walk.palaces[segment.landing_index].name for segment in walk.segments],
                         ['天德', '桃花', '病符'])
        self.assertEqual(walk.segments[0].sequence[0], 0)
        self.assertEqual(walk.segments[0].sequence[-1], 8)
        self.assertEqual(walk.segments[1].sequence[:3], (8, 0, 1))

    def test_full_cycle_and_repeated_visits(self):
        walk = build_palace_walk((10, 10, 10))
        self.assertEqual([segment.landing_index for segment in walk.segments], [0, 0, 0])
        for segment in walk.segments:
            self.assertEqual(sum(segment.visit_counts), 10)
            self.assertEqual(segment.visit_counts[0], 2)
            self.assertEqual(sum(segment.visit_counts[1:]), 8)
            self.assertEqual((segment.moves, segment.full_cycles, segment.remainder_steps), (9, 1, 0))

    def test_large_input_aggregates_without_losing_counts(self):
        walk = build_palace_walk((999, 999, 999))
        self.assertEqual([segment.landing_index for segment in walk.segments], [8, 7, 6])
        for segment in walk.segments:
            self.assertEqual(len(segment.sequence), 999)
            self.assertEqual(sum(segment.visit_counts), 999)
            self.assertEqual((segment.moves, segment.full_cycles, segment.remainder_steps), (998, 110, 8))

    def test_walk_landings_match_prediction_across_grid_and_boundaries(self):
        cases = [(a, b, c) for a in range(1, 10) for b in range(1, 10) for c in range(1, 10)]
        cases += [(10, 10, 10), (18, 27, 9), (19, 1, 998), (998, 999, 10), (999, 1, 18)]
        for numbers in cases:
            with self.subTest(numbers=numbers):
                walk = build_palace_walk(numbers)
                expected = [symbol.name for symbol in HandTechnique.predict(*numbers).symbols]
                actual = [walk.palaces[segment.landing_index].name for segment in walk.segments]
                self.assertEqual(actual, expected)
                # 每段落点就是下一段起点，本宫算第 1 数。
                self.assertEqual(walk.segments[1].start_index, walk.segments[0].landing_index)
                self.assertEqual(walk.segments[2].start_index, walk.segments[1].landing_index)
                for segment in walk.segments:
                    self.assertEqual(segment.sequence[0], segment.start_index)
                    self.assertEqual(segment.sequence[-1], segment.landing_index)
                    self.assertEqual(segment.visit_counts[segment.landing_index], segment.sequence.count(segment.landing_index))

    def test_metadata_comes_from_readonly_fields(self):
        by_name = {symbol.name: symbol for symbol in SYMBOLS}
        self.assertEqual(by_name['空亡'].finger_position, '左手中指中段')
        self.assertEqual(by_name['空亡'].bagua, '中 (zhōng)')
        self.assertEqual(by_name['大安'].finger_position, '左手中指中段')
        self.assertEqual(by_name['大安'].bagua, '震 (zhèn)')
        for row in SYMBOLS_JSON:
            symbol = by_name[row['name']]
            self.assertEqual(symbol.finger_position, row['finger_position'])
            self.assertEqual(symbol.bagua, row['bagua'])
            self.assertTrue(symbol.finger_position and symbol.bagua)


class PalaceHandModel(unittest.TestCase):
    def test_handwritten_targets_and_clockwise_angles(self):
        for numbers, indices, orders, angles in (
            ((1, 2, 3), [0, 1, 3], [1, 2, 4], [0, 40, 120]),
            ((9, 9, 9), [8, 7, 6], [9, 8, 7], [320, 280, 240]),
            ((999, 999, 999), [8, 7, 6], [9, 8, 7], [320, 280, 240]),
            ((1, 1, 1), [0, 0, 0], [1, 1, 1], [0, 0, 0]),
            ((10, 10, 10), [0, 0, 0], [1, 1, 1], [0, 0, 0]),
        ):
            with self.subTest(numbers=numbers):
                hands = build_palace_hands(build_palace_walk(numbers))
                self.assertEqual(len(hands), 3)
                self.assertEqual([h.target_index for h in hands], indices)
                self.assertEqual([h.target_order for h in hands], orders)
                self.assertEqual([h.angle for h in hands], angles)
                self.assertEqual([h.key for h in hands], ['initial', 'middle', 'final'])
                self.assertEqual([h.stage for h in hands], ['初传', '中传', '末传'])

    def test_hand_targets_match_prediction_and_node_coordinates(self):
        cases = [(a, b, c) for a in range(1, 10) for b in range(1, 10) for c in range(1, 10)]
        cases += [(10, 10, 10), (18, 27, 9), (19, 1, 998), (998, 999, 10), (999, 1, 18)]
        for numbers in cases:
            walk = build_palace_walk(numbers)
            hands = build_palace_hands(walk)
            predicted = HandTechnique.predict(*numbers).symbols
            for hand, symbol in zip(hands, predicted):
                self.assertEqual(walk.palaces[hand.target_index].name, symbol.name)
                # CSS 向上线段绕中心正角旋转：x 向右、y 向下，与原节点坐标独立核对。
                angle = math.radians(hand.angle)
                tip = (50 + PALACE_RADIUS * math.sin(angle), 50 - PALACE_RADIUS * math.cos(angle))
                node = _palace_coordinates(hand.target_index, len(walk.palaces))
                for actual, expected in zip(tip, node):
                    self.assertAlmostEqual(actual, expected, places=3)
                self.assertEqual(hand.target_order, symbol.order)


class PalaceAnimationModel(unittest.TestCase):
    def test_handwritten_timeline(self):
        animation = build_palace_animation(build_palace_walk((1, 2, 3)))
        self.assertEqual([(s.stage_index, s.count, s.palace_index, s.start_ms, s.end_ms)
                          for s in animation.steps], [
            (0, 1, 0, 300, 460),
            (1, 1, 0, 700, 860), (1, 2, 1, 860, 1020),
            (2, 1, 1, 1260, 1420), (2, 2, 2, 1420, 1580), (2, 3, 3, 1580, 1740),
        ])
        self.assertEqual(animation.landing_ms, (460, 1020, 1740))
        self.assertEqual(animation.relations_ms, 1980)

    def test_repeated_and_boundary_steps_are_not_deduplicated(self):
        for numbers in ((1, 1, 1), (10, 1, 1), (9, 9, 9), (999, 999, 999)):
            with self.subTest(numbers=numbers):
                walk = build_palace_walk(numbers)
                animation = build_palace_animation(walk)
                prediction = HandTechnique.predict(*numbers)
                self.assertEqual(len(animation.steps), sum(numbers))
                self.assertEqual(animation.relations_ms, 1020 + 160 * sum(numbers))
                if numbers == (10, 1, 1):
                    self.assertEqual([s.palace_index for s in animation.steps[:10]], list(range(9)) + [0])
                    self.assertEqual(animation.first_visits[0][0], 300)
                    self.assertEqual(animation.landing_ms[0], 1900)
                if numbers == (1, 1, 1):
                    self.assertEqual([s.palace_index for s in animation.steps], [0, 0, 0])
                    self.assertEqual(animation.landing_ms, (460, 860, 1260))
                if numbers[0] in (9, 999):
                    self.assertEqual([segment.landing_index for segment in walk.segments], [8, 7, 6])
                for stage, segment in enumerate(walk.segments):
                    steps = [s for s in animation.steps if s.stage_index == stage]
                    self.assertEqual(tuple(s.palace_index for s in steps), segment.sequence)
                    self.assertEqual([s.count for s in steps], list(range(1, numbers[stage] + 1)))
                    self.assertEqual(walk.palaces[steps[-1].palace_index].name, prediction.symbols[stage].name)
                    self.assertEqual(steps[0].start_ms, 300 if stage == 0 else animation.landing_ms[stage - 1] + 240)
                    self.assertEqual(steps[-1].end_ms, animation.landing_ms[stage])
                    for before, after in zip(steps, steps[1:]):
                        self.assertEqual(before.end_ms, after.start_ms)
                    for index, first in enumerate(animation.first_visits[stage]):
                        visits = [s for s in steps if s.palace_index == index]
                        self.assertEqual(first, visits[0].start_ms if visits else None)
                self.assertEqual(animation.relations_ms, animation.landing_ms[-1] + 240)

    def test_rendered_css_windows_match_every_step_including_revisits(self):
        for numbers in ((1, 1, 1), (1, 2, 3), (10, 1, 1), (999, 999, 999)):
            animation = build_palace_animation(build_palace_walk(numbers))
            css = palace_animation_css(animation, 'palace-abc123')
            timelines = css.splitlines()
            self.assertEqual(len(timelines), 9)
            for index, timeline in enumerate(timelines):
                self.assertTrue(timeline.startswith(f'@keyframes palace-abc123-{index}'))
                frames = [(float(percent) * animation.relations_ms / 100, int(opacity))
                          for percent, opacity in re.findall(r'([0-9.]+)% \{ opacity: ([01]); \}', timeline)]
                expected = [(0, 0)]
                for step in animation.steps:
                    if step.palace_index == index:
                        expected.extend([(step.start_ms, 1), (step.end_ms, 0)])
                expected.append((animation.relations_ms, 0))
                self.assertEqual(len(frames), len(expected))
                for actual, reference in zip(frames, expected):
                    self.assertAlmostEqual(actual[0], reference[0], places=5)
                    self.assertEqual(actual[1], reference[1])
        with self.assertRaises(ValueError):
            palace_animation_css(animation, 'bad; user text')


class PalaceRingPage(unittest.IsolatedAsyncioTestCase):
    async def test_empty_state_ring_is_static_and_marked_not_fabricated(self):
        from nicegui import Client, ui
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/palace-empty'), request=None) as client:
                from web import create_page
                create_page()
                nodes = [element for element in client.elements.values() if 'palace-node' in element.classes]
                self.assertEqual([node.props['data-order'] for node in nodes], [str(i) for i in range(1, 10)])
                self.assertEqual([node.props['data-name'] for node in nodes], JSON_NAMES)
                origins = [element for element in client.elements.values() if 'palace-origin' in element.classes]
                self.assertEqual(len(origins), 1)
                self.assertIs(origins[0].parent_slot.parent, nodes[0])
                self.assertEqual([element for element in client.elements.values() if 'palace-landing' in element.classes], [])
                self.assertEqual([element for element in client.elements.values() if 'palace-visit' in element.classes], [])
                self.assertEqual([element for element in client.elements.values() if 'palace-summary' in element.classes], [])
                self.assertFalse(any('palace-hand' in e.classes or 'palace-hand-layer' in e.classes
                                     for e in client.elements.values()))
                self.assertFalse(any('palace-playing' in e.classes or 'palace-animation-style' in e.classes
                                     for e in client.elements.values()))

    async def test_results_render_landings_metadata_and_relations(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/palace-results'), request=None) as client:
                app = create_page()
                await app._perform_divination()
                self.assertEqual(app.number_snapshot, (1, 2, 3))
                nodes = [element for element in client.elements.values() if 'palace-node' in element.classes]
                self.assertEqual(len(nodes), 9)
                self.assertEqual(len({node.props['data-order'] for node in nodes}), 9)
                prediction = HandTechnique.predict(1, 2, 3)
                landings = [element for element in client.elements.values() if 'palace-landing' in element.classes]
                by_stage = {element.props['data-stage']: element for element in landings}
                self.assertEqual(set(by_stage), {'初传', '中传', '末传'})
                for stage, symbol in zip(('初传', '中传', '末传'), prediction.symbols):
                    element = by_stage[stage]
                    node = element.parent_slot.parent
                    self.assertEqual(node.props['data-name'], symbol.name)
                    self.assertEqual(element.props['data-finger-position'], symbol.finger_position)
                    self.assertEqual(element.props['data-bagua'], symbol.bagua)
                    self.assertEqual(element.props['data-element'],
                                     {'木': 'wood', '火': 'fire', '土': 'earth', '金': 'metal', '水': 'water'}[symbol.element.name])
                # 三次逐数经过的九宫访问标记固定 27 个槽位，访问到的写阶段，未访问的隐藏。
                visits = [element for element in client.elements.values() if 'palace-visit' in element.classes]
                self.assertEqual(len(visits), 27)
                self.assertEqual(sum(1 for element in visits if element.props['data-visited'] == 'true'), 6)
                # 三个落点摘要都完整暴露手指位置与八卦，且没有混入旧卡片查询。
                summaries = [element for element in client.elements.values() if 'palace-summary' in element.classes]
                self.assertEqual(len(summaries), 3)
                for index, summary in enumerate(summaries):
                    symbol = prediction.symbols[index]
                    self.assertEqual(summary.props['data-finger-position'], symbol.finger_position)
                    self.assertEqual(summary.props['data-bagua'], symbol.bagua)
                metas = [element.text for element in client.elements.values() if 'palace-meta' in element.classes]
                self.assertIn('手指位置：左手中指中段', metas)
                self.assertIn('八卦：震 (zhèn)', metas)
                self.assertIn('八卦：兌 (duì)', metas)
                titles = [element.text for element in client.elements.values() if 'palace-relation-title' in element.classes]
                self.assertEqual(titles, ['初传·大安 → 中传·留连 · 比和', '中传·留连 → 末传·赤口 · 被克'])
                descs = [element.text for element in client.elements.values() if 'palace-relation-desc' in element.classes]
                self.assertTrue(any('金克木' in text for text in descs))
                self.assertEqual(len([element for element in client.elements.values() if 'transmission-card' in element.classes]), 3)
                self.assertEqual(len([element for element in client.elements.values() if 'element-badge' in element.classes]), 3)

    async def test_animation_hooks_delays_and_same_input_replay(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/palace-animation'), request=None) as client:
                app = create_page()
                original_head = client.head_html
                scopes = []
                previous_hands = []
                for _ in range(2):
                    await app._perform_divination()
                    elements = list(client.elements.values())
                    roots = [e for e in elements if 'palace-playing' in e.classes]
                    self.assertEqual(len(roots), 1)
                    scope = roots[0].props['data-animation']
                    scopes.append(scope)
                    animation = build_palace_animation(build_palace_walk((1, 2, 3)))
                    styles = [e for e in elements if 'palace-animation-style' in e.classes]
                    self.assertEqual(len(styles), 1)
                    self.assertEqual(styles[0].tag, 'style')
                    self.assertIs(styles[0].parent_slot.parent, roots[0])
                    self.assertEqual(styles[0].content, palace_animation_css(animation, scope))
                    self.assertEqual(client.head_html, original_head)
                    hands = [e for e in elements if 'palace-hand' in e.classes]
                    self.assertEqual(len(hands), 3)
                    self.assertTrue(all(hand.id not in client.elements for hand in previous_hands))
                    previous_hands = hands
                    for stage, hand in enumerate(hands):
                        self.assertEqual(hand.props['data-target-index'], str([0, 1, 3][stage]))
                        self.assertEqual(hand.props['data-target-order'], str([1, 2, 4][stage]))
                        self.assertEqual(hand.style['--palace-hand-angle'], f'{[0., 40., 120.][stage]}deg')
                        self.assertEqual(hand.style['--palace-delay'], f'{[460, 1020, 1740][stage]}ms')
                        next_time = (animation.landing_ms[stage] + 240 if stage < 2 else animation.relations_ms)
                        self.assertLessEqual(animation.landing_ms[stage] + 180, next_time)
                    layers = [e for e in elements if 'palace-hand-layer' in e.classes]
                    self.assertEqual(len(layers), 1)
                    self.assertEqual(layers[0].props['aria-hidden'], 'true')
                    self.assertEqual(layers[0].style['--palace-hand-length'], f'{PALACE_RADIUS}%')
                    for node in (e for e in elements if 'palace-node' in e.classes):
                        self.assertEqual(node.style['--palace-highlight'], f'{scope}-{node.props["data-index"]}')
                    for chip in (e for e in elements if 'palace-visit' in e.classes):
                        if chip.props['data-visited'] == 'true':
                            stage = ('初传', '中传', '末传').index(chip.props['data-stage'])
                            index = int(chip.parent_slot.parent.parent_slot.parent.props['data-index'])
                            self.assertEqual(chip.style['--palace-delay'], f'{animation.first_visits[stage][index]}ms')
                        else:
                            self.assertNotIn('--palace-delay', chip.style)
                    for landing in (e for e in elements if 'palace-landing' in e.classes):
                        stage = ('初传', '中传', '末传').index(landing.props['data-stage'])
                        self.assertEqual(landing.style['--palace-delay'], f'{animation.landing_ms[stage]}ms')
                    relations = next(e for e in elements if 'palace-relations' in e.classes)
                    self.assertEqual(relations.style['--palace-delay'], '1980ms')
                    origin = next(e for e in elements if 'palace-origin' in e.classes)
                    self.assertNotIn('--palace-delay', origin.style)
                self.assertNotEqual(*scopes)

    async def test_each_stage_shares_one_colour_class_independent_of_element(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/palace-stage-colours'), request=None) as client:
                app = create_page()
                for numbers in ((1, 1, 1), (1, 2, 3), (9, 9, 9)):
                    for field, value in zip(app.number_inputs, numbers):
                        field.value = value
                    await app._perform_divination()
                    elements = list(client.elements.values())
                    for stage, key in zip(('初传', '中传', '末传'), ('initial', 'middle', 'final')):
                        group = [e for e in elements if e.props.get('data-stage') == stage and
                                 any(c in e.classes for c in ('palace-visit', 'palace-landing', 'palace-hand'))]
                        self.assertEqual(len(group), 11)  # 九个经过槽、一枚落点、一根手
                        for element in group:
                            self.assertEqual([c for c in element.classes if c.startswith('palace-stage-')],
                                             [f'palace-stage-{key}'])
                    hands = [e for e in elements if 'palace-hand' in e.classes]
                    for hand, symbol in zip(hands, HandTechnique.predict(*numbers).symbols):
                        self.assertEqual(hand.props['data-target-order'], str(symbol.order))
                        landing = next(e for e in elements if 'palace-landing' in e.classes and
                                       e.props['data-stage'] == hand.props['data-stage'])
                        self.assertEqual(landing.props['data-finger-position'], symbol.finger_position)
                        self.assertEqual(landing.props['data-bagua'], symbol.bagua)
                        self.assertEqual(hand.style['--palace-delay'], landing.style['--palace-delay'])

    async def test_duplicate_landings_keep_all_three_stages(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/palace-triple'), request=None) as client:
                app = create_page()
                for field in app.number_inputs:
                    field.value = 1
                await app._perform_divination()
                self.assertEqual(app.number_snapshot, (1, 1, 1))
                hands = [e for e in client.elements.values() if 'palace-hand' in e.classes]
                self.assertEqual(len(hands), 3)
                self.assertEqual([h.style['--palace-hand-angle'] for h in hands], ['0.0deg'] * 3)
                landings = [element for element in client.elements.values() if 'palace-landing' in element.classes]
                self.assertEqual([element.props['data-stage'] for element in landings], ['初传', '中传', '末传'])
                self.assertEqual({element.parent_slot.parent.props['data-order'] for element in landings}, {'1'})
                triple_node = next(element for element in client.elements.values()
                                   if 'palace-node' in element.classes and element.props['data-order'] == '1')
                self.assertEqual(sum(1 for element in landings if element.parent_slot.parent is triple_node), 3)

    async def test_large_input_keeps_dom_bounded(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/palace-large'), request=None) as client:
                app = create_page()
                for field in app.number_inputs:
                    field.value = 999
                await app._perform_divination()
                self.assertEqual(app.number_snapshot, (999, 999, 999))
                hands = [e for e in client.elements.values() if 'palace-hand' in e.classes]
                self.assertEqual(len(hands), 3)
                self.assertEqual([h.props['data-target-index'] for h in hands], ['8', '7', '6'])
                self.assertEqual(len([e for e in client.elements.values() if 'palace-node' in e.classes]), 9)
                self.assertEqual(len([e for e in client.elements.values() if 'palace-visit' in e.classes]), 27)
                self.assertEqual(len([e for e in client.elements.values() if 'palace-landing' in e.classes]), 3)
                summaries = [e for e in client.elements.values() if 'palace-summary' in e.classes]
                self.assertEqual(len(summaries), 3)
                segment_metas = [e.text for e in client.elements.values() if 'palace-segment-meta' in e.classes]
                self.assertTrue(any('整圈 110' in text for text in segment_metas))

    async def test_all_three_input_modes_use_converted_snapshot(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/palace-modes'), request=None) as client:
                app = create_page()
                for numbers, configure in [
                    ((8, 5, 7), lambda: self._configure_date(app)),
                    ((4, 8, 2), lambda: self._configure_chinese(app)),
                ]:
                    configure()
                    await app._perform_divination()
                    self.assertEqual(app.number_snapshot, numbers)
                    prediction = HandTechnique.predict(*numbers)
                    landings = [element for element in client.elements.values() if 'palace-landing' in element.classes]
                    by_stage = {element.props['data-stage']: element.parent_slot.parent.props['data-name']
                                for element in landings}
                    self.assertEqual(by_stage,
                                     dict(zip(('初传', '中传', '末传'), [symbol.name for symbol in prediction.symbols])))

    @staticmethod
    def _configure_date(app):
        app.input_tabs.value = 'date'
        app.date_input.value, app.time_input.value = '2026-09-15', '12:00'

    @staticmethod
    def _configure_chinese(app):
        app.input_tabs.value = 'chinese'
        app.chinese_input.value = '中国人'

    async def test_editing_inputs_does_not_change_existing_ring(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            with Client(ui.page('/palace-edit'), request=None) as client:
                app = create_page()
                await app._perform_divination()
                before = {element.props['data-stage']: element.parent_slot.parent.props['data-name']
                          for element in client.elements.values() if 'palace-landing' in element.classes}
                self.assertEqual(before,
                                 dict(zip(('初传', '中传', '末传'),
                                          [symbol.name for symbol in HandTechnique.predict(1, 2, 3).symbols])))
                for field in app.number_inputs:
                    field.value = 9
                after_edit = {element.props['data-stage']: element.parent_slot.parent.props['data-name']
                              for element in client.elements.values() if 'palace-landing' in element.classes}
                self.assertEqual(after_edit, before)
                await app._perform_divination()
                self.assertEqual(app.number_snapshot, (9, 9, 9))
                after_submit = {element.props['data-stage']: element.parent_slot.parent.props['data-name']
                                for element in client.elements.values() if 'palace-landing' in element.classes}
                self.assertEqual(after_submit,
                                 dict(zip(('初传', '中传', '末传'),
                                          [symbol.name for symbol in HandTechnique.predict(9, 9, 9).symbols])))

    async def test_ring_survives_ai_failure_and_snapshot_is_kept(self):
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
                patch('web.DivinationAgent.interpret_prediction_async', side_effect=failing_ai):
            with Client(ui.page('/palace-ai-failure'), request=None) as client:
                app = create_page()
                app.question_input.value = 'test'
                task = asyncio.create_task(app._perform_divination())
                await asyncio.wait_for(entered.wait(), timeout=2)
                self.assertEqual(app.number_snapshot, (1, 2, 3))
                scope = next(e.props['data-animation'] for e in client.elements.values() if 'palace-playing' in e.classes)
                hands = [e for e in client.elements.values() if 'palace-hand' in e.classes]
                self.assertEqual(len(hands), 3)
                self.assertTrue(app.is_running)
                self.assertEqual(len([e for e in client.elements.values() if 'palace-landing' in e.classes]), 3)
                await app._perform_divination()
                release.set()
                await task
                self.assertIn('simulated outage', app.error_message.text)
                self.assertEqual(next(e.props['data-animation'] for e in client.elements.values()
                                      if 'palace-playing' in e.classes), scope)
                self.assertEqual(app.number_snapshot, (1, 2, 3))
                self.assertEqual(len([e for e in client.elements.values() if 'palace-node' in e.classes]), 9)
                self.assertEqual(len([e for e in client.elements.values() if 'palace-landing' in e.classes]), 3)
                self.assertEqual([e for e in client.elements.values() if 'palace-hand' in e.classes], hands)
                self.assertFalse(app.is_running)
                self.assertTrue(app.submit_button.enabled)

    async def test_two_clients_keep_independent_rings(self):
        from nicegui import Client, ui
        from web import create_page
        with patch('web.DivinationAgent.get_available_models', return_value=[]):
            first_client = Client(ui.page('/palace-first'), request=None)
            second_client = Client(ui.page('/palace-second'), request=None)
            with first_client:
                first = create_page()
                await first._perform_divination()
            with second_client:
                second = create_page()
                self.assertIsNone(second.number_snapshot)
            self.assertEqual(first.number_snapshot, (1, 2, 3))
            self.assertIsNone(second.number_snapshot)
            with second_client:
                for field in second.number_inputs:
                    field.value = 9
                await second._perform_divination()
                self.assertEqual(second.number_snapshot, (9, 9, 9))
            first_scope = next(e.props['data-animation'] for e in first_client.elements.values() if 'palace-playing' in e.classes)
            second_scope = next(e.props['data-animation'] for e in second_client.elements.values() if 'palace-playing' in e.classes)
            self.assertNotEqual(first_scope, second_scope)
            first_hands = [e for e in first_client.elements.values() if 'palace-hand' in e.classes]
            second_hands = [e for e in second_client.elements.values() if 'palace-hand' in e.classes]
            self.assertEqual([h.props['data-target-index'] for h in first_hands], ['0', '1', '3'])
            self.assertEqual([h.props['data-target-index'] for h in second_hands], ['8', '7', '6'])
            self.assertEqual(first.number_snapshot, (1, 2, 3))


class PalaceRingStyles(unittest.TestCase):
    STYLE_DIR = PROJECT_ROOT / 'src'

    def test_all_four_themes_style_the_palace_ring(self):
        base = (self.STYLE_DIR / 'web.css').read_text(encoding='utf-8')
        self.assertIn('.palace-ring {', base)
        self.assertIn('.palace-node {', base)
        self.assertIn('.palace-landing {', base)
        self.assertIn('--palace-walk-color:', base)
        self.assertIn('--palace-walk-shadow:', base)
        for theme in ('night', 'ink', 'neon'):
            css = (self.STYLE_DIR / 'themes' / f'{theme}.css').read_text(encoding='utf-8')
            with self.subTest(theme=theme):
                self.assertIn(f'html[data-theme="{theme}"] .palace-ring', css)
                self.assertIn(f'html[data-theme="{theme}"] .palace-node-name', css)
                self.assertIn(f'html[data-theme="{theme}"] .palace-summary', css)
                self.assertRegex(css, rf'html\[data-theme="{theme}"\] \.palace-ring-block \{{[^}}]*--palace-walk-color:')

    def test_stage_colour_and_hand_style_contracts(self):
        base = (self.STYLE_DIR / 'web.css').read_text(encoding='utf-8')
        for theme in ('paper', 'night', 'ink', 'neon'):
            css = base if theme == 'paper' else (self.STYLE_DIR / 'themes' / f'{theme}.css').read_text(encoding='utf-8')
            colours = [re.search(rf'--palace-{key}-color: (#[a-f0-9]{{6}})', css).group(1)
                       for key in ('initial', 'middle', 'final')]
            self.assertEqual(len(set(colours)), 3)
            self.assertNotIn('.palace-landing[data-element=', css)
            for selector in ('palace-visit', 'palace-landing'):
                rule = re.search(rf'\.{selector} \{{([^}}]+)', css).group(1)
                self.assertIn('color: var(--palace-stage-color)', rule)
                self.assertIn('box-shadow: inset 0 0 0 1px var(--palace-stage-color)', rule)
        for key, width, depth in (('initial', 6, 0), ('middle', 4, 1), ('final', 2, 2)):
            rule = re.search(rf'\.palace-stage-{key} \{{([^}}]+)', base).group(1)
            self.assertIn(f'--palace-stage-color: var(--palace-{key}-color)', rule)
            self.assertIn(f'--palace-hand-width: {width}px', rule)
            self.assertIn(f'--palace-hand-depth: {depth}', rule)
        line = re.search(r'\.palace-hand-line \{([^}]+)', base).group(1)
        self.assertIn('background: var(--palace-stage-color)', line)
        self.assertIn('transform: scaleY(1); opacity: 1;', line)
        self.assertIn('transform-origin: 50% 100%', line)
        self.assertIn('height: var(--palace-hand-length)', line)
        self.assertIn('overflow: hidden; pointer-events: none;', base)
        self.assertIn('.palace-playing .palace-node,\n.palace-playing .palace-ring-core > * { background: var(--palace-label-bg); }', base)
        normal = base.split('@media (prefers-reduced-motion: no-preference)', 1)[1].split('\n}', 1)[0]
        self.assertIn('.palace-playing .palace-hand-line { animation: palace-hand-reveal 180ms ease-out var(--palace-delay) backwards; }', normal)

    def test_reduced_motion_disables_ring_animation(self):
        base = (self.STYLE_DIR / 'web.css').read_text(encoding='utf-8')
        reduced = base.split('@media (prefers-reduced-motion: reduce)', 1)[1]
        self.assertIn('.palace-ring-block, .palace-ring-block *', reduced)
        self.assertIn('.palace-ring-block *::after', reduced)
        self.assertIn('animation: none !important; transition: none !important;', reduced)
        self.assertNotIn('visibility:', reduced)
        self.assertIn('.palace-visit[data-visited="false"] { visibility: hidden; }', base)
        normal = base.split('@media (prefers-reduced-motion: no-preference)', 1)[1].split('\n}', 1)[0]
        self.assertIn('.palace-playing .palace-relations { animation: palace-reveal 0s linear var(--palace-delay) backwards; }', normal)
        self.assertIn('steps(1, end)', normal)
        self.assertIn('pointer-events: none; opacity: 0;', base)


if __name__ == '__main__':
    unittest.main()
