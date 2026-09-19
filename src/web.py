#!/usr/bin/env python3
"""小六壬占卜 Web Interface，使用 NiceGUI 展示本地三传和可选AI解读。"""

import os
import re
import sys
import json
import math
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nicegui import core, ui
from nicegui.events import ValueChangeEventArguments

from hand_technique import HandTechnique
from symbols import SYMBOLS
from ai_agent import DivinationAgent, SupportedModels
from utils.stroke_count import get_stroke_counts
from utils.calendar_converter import date_to_numbers, solar_to_lunar, format_bazi_output, format_tai_sui_section
from utils.validation import validate_numbers, validate_chinese, parse_datetime, normalize_gender
from utils.bazi_calculator import calculate_bazi, analyze_day_master_strength, analyze_spouse_palace
from utils.five_elements_utils import analyze_wuxing, analyze_missing_wuxing
from utils.symbol_relations import describe_relation

THEME_DIR = Path(__file__).with_name('themes')
HERO_TITLE = '一念起，观三传。'
# 五行→CSS 展示钩子；供各页面与皮肤分色，不参与计算。
ELEMENT_KEYS = {'木': 'wood', '火': 'fire', '土': 'earth', '金': 'metal', '水': 'water'}

# 三传阶段：完整名与环上记号用的简写。
PALACE_STAGES = (('初传', '初'), ('中传', '中'), ('末传', '末'))
PALACE_STAGE_KEYS = ('initial', 'middle', 'final')
# 环半径（相对正方形容器的百分比）；order=1 在正上方，其余顺时针均分。
PALACE_RADIUS = 38.0


def _palace_coordinates(index: int, count: int) -> tuple[float, float]:
    """返回节点中心相对容器的 (left%, top%)；index=0 为正上方，顺时针递增。"""
    angle = math.radians(360.0 * index / count)
    return round(50.0 + PALACE_RADIUS * math.sin(angle), 3), round(50.0 - PALACE_RADIUS * math.cos(angle), 3)


@dataclass(frozen=True)
class PalaceSegment:
    """一个输入数字对应的一段数宫轨迹，仅用于展示。"""
    stage: str
    short: str
    number: int
    start_index: int
    sequence: tuple
    visit_counts: tuple
    landing_index: int
    moves: int
    full_cycles: int
    remainder_steps: int


@dataclass(frozen=True)
class PalaceWalk:
    """按 order 排序的九宫与三段轨迹；索引指向 palaces。"""
    palaces: tuple
    segments: tuple


def build_palace_walk(numbers) -> PalaceWalk:
    """按「本宫算第 1 数」复现 HandTechnique 的计数路径；不修改核心算法，只做展示推导。"""
    values = validate_numbers(numbers)
    palaces = tuple(sorted(SYMBOLS, key=lambda symbol: symbol.order))
    segments = []
    position = 0
    for (stage, short), number in zip(PALACE_STAGES, values):
        sequence = tuple((position + step) % len(palaces) for step in range(number))
        visit_counts = [0] * len(palaces)
        for index in sequence:
            visit_counts[index] += 1
        landing = sequence[-1]
        moves = number - 1
        segments.append(PalaceSegment(
            stage=stage, short=short, number=number, start_index=position,
            sequence=sequence, visit_counts=tuple(visit_counts), landing_index=landing,
            moves=moves, full_cycles=moves // len(palaces), remainder_steps=moves % len(palaces),
        ))
        position = landing
    return PalaceWalk(palaces=palaces, segments=tuple(segments))


@dataclass(frozen=True)
class PalaceHand:
    """指针只映射既有落点；0°朝上，顺时针旋转。"""
    stage: str
    key: str
    target_index: int
    target_order: int
    angle: float


def build_palace_hands(walk: PalaceWalk) -> tuple[PalaceHand, ...]:
    return tuple(
        PalaceHand(segment.stage, key, segment.landing_index,
                   walk.palaces[segment.landing_index].order,
                   segment.landing_index * 360.0 / len(walk.palaces))
        for key, segment in zip(PALACE_STAGE_KEYS, walk.segments)
    )


@dataclass(frozen=True)
class PalaceStep:
    """一次计数（含本宫），重复访问也保留独立的时间窗口。"""
    stage_index: int
    count: int
    palace_index: int
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class PalaceAnimation:
    steps: tuple[PalaceStep, ...]
    first_visits: tuple[tuple[Optional[int], ...], ...]
    landing_ms: tuple[int, ...]
    relations_ms: int


def build_palace_animation(walk: PalaceWalk) -> PalaceAnimation:
    """只消费既有 sequence，不重新推导宫位；起算 300ms、逐数 160ms、落点 240ms。"""
    steps, first_visits, landings = [], [], []
    time_ms = 300
    for stage_index, segment in enumerate(walk.segments):
        first = [None] * len(walk.palaces)
        for count, index in enumerate(segment.sequence, 1):
            steps.append(PalaceStep(stage_index, count, index, time_ms, time_ms + 160))
            if first[index] is None:
                first[index] = time_ms
            time_ms += 160
        first_visits.append(tuple(first))
        landings.append(time_ms)
        time_ms += 240
    return PalaceAnimation(tuple(steps), tuple(first_visits), tuple(landings), time_ms)


def palace_animation_css(animation: PalaceAnimation, scope: str) -> str:
    """每宫一条离散透明度时间线；仅接收程序生成的 CSS 标识，不插入用户文本。"""
    if not re.fullmatch(r'palace-[a-f0-9]+', scope):
        raise ValueError('无效的九宫动画标识')
    rules = []
    for index in range(len(animation.first_visits[0])):
        frames = {0: 0, animation.relations_ms: 0}
        for step in animation.steps:
            if step.palace_index == index:
                frames[step.start_ms] = 1
                frames[step.end_ms] = 0
        keyframes = ' '.join(
            f'{time_ms / animation.relations_ms * 100:.9f}% {{ opacity: {opacity}; }}'
            for time_ms, opacity in sorted(frames.items())
        )
        rules.append(f'@keyframes {scope}-{index} {{ {keyframes} }}')
    return '\n'.join(rules)


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    description: str
    stylesheet: Optional[str]  # 相对 THEME_DIR；None 表示只用 web.css 的默认皮肤

    def __post_init__(self):
        # id 会不加引号地写入 HTML 属性与 CSS 选择器，文案会写入带引号的属性，导入时即拒绝不安全的值。
        if not re.fullmatch(r'[a-z][a-z0-9-]*', self.id):
            raise ValueError(f'主题 id 只能由小写字母、数字和连字符组成：{self.id!r}')
        if '"' in self.label or '"' in self.description:
            raise ValueError(f'主题文案不能包含双引号：{self.id}')


# 首项为默认皮肤；切换、记忆与效果启停全部在浏览器端完成，见 themes/theme.js。
THEMES = (
    Theme('paper', '素纸', '暖白纸感 · 朱砂主色', None),
    Theme('night', '星夜', '深空星图 · 鎏金流光', 'night.css'),
    Theme('ink', '水墨', '宣纸留白 · 朱文印章', 'ink.css'),
    Theme('neon', '霓虹', '赛博终端 · 荧光扫描', 'neon.css'),
)
DEFAULT_THEME = THEMES[0]

AI_SECTION_TITLES = ('一句话判断', '初传｜起点', '中传｜过程', '末传｜趋势', '行动建议')


def project_streaming_interpretation(text: str) -> str:
    """保留累计正文（含未完整分片），只补尚未到达的完整标题；不用于最终结果。"""
    arrived = set(re.findall(r'^### ([^\n]+?)[ \t]*$', text, flags=re.MULTILINE))
    missing = [f'### {title}' for title in AI_SECTION_TITLES if title not in arrived]
    return '\n\n'.join(([text] if text else []) + missing)


def create_page_nav(current_path):
    """两页共用纯导航，不保存控制器或 UI 状态。"""
    with ui.element('nav').classes('page-nav').props('aria-label="测算页面"'):
        for path, label in (('/', '小六壬'), ('/bazi', '八字')):
            link = ui.link(label, path).classes('page-nav-link')
            if path == current_path:
                link.props('aria-current=page')


class DivinationWebApp:
    def __init__(self):
        self.current_model = None
        self.is_running = False
        self.submit_button = None
        self.ai_action = None
        self.ai_card = None
        self.ai_markdown = None
        self.ai_status = None
        self.ai_request_label = None
        self.form_card = None
        self.form_details = None
        self.summary_label = None
        self.edit_button = None
        self.reading_panel = None
        self.available_models = []
        self.divination_result = None
        self.ai_interpretation = None
        self.input_summary = ''
        self.question_snapshot = ''
        self.number_snapshot = None
        self.model_select = None
        self.optional_panel = None
        self.input_tabs = None
        self.number_inputs = []
        self.date_input = None
        self.time_input = None
        self.chinese_input = None
        self.question_input = None
        self.result_area = None
        self.ai_result_area = None
        self.error_message = None
        self.status_message = None
        self._check_available_models()

    def _check_available_models(self):
        self.available_models = DivinationAgent.get_available_models()
        if self.available_models:
            self.current_model = self.available_models[0]

    def _validate_numbers(self, *values) -> tuple[bool, str, List[int]]:
        try:
            return True, '', validate_numbers(values)
        except ValueError as exc:
            return False, str(exc), []

    def _validate_chinese(self, text: str) -> tuple[bool, str, List[int]]:
        try:
            return True, '', get_stroke_counts(validate_chinese(text))
        except ValueError as exc:
            return False, str(exc), []

    def _validate_date_time(self, date_str: str, time_str: str) -> tuple[bool, str, List[int]]:
        try:
            return True, '', date_to_numbers(date_str, time_str)
        except ValueError as exc:
            return False, str(exc), []

    async def _perform_divination(self):
        if self.is_running:
            return
        self._set_running(True)
        self._set_form_collapsed(False)
        self.submit_button.set_text('正在计算…')
        self.status_message.set_text('正在计算本地三传…')
        try:
            self.result_area.clear()
            self.ai_result_area.clear()
            self.ai_card = self.ai_markdown = self.ai_status = self.ai_request_label = None
            self.ai_action.set_text('生成 AI 解读')
            self.error_message.set_text('')
            self.divination_result = None
            self.ai_interpretation = None
            self.input_summary = ''
            self.number_snapshot = None
            current_tab = self.input_tabs.value
            question = (self.question_input.value or '').strip()
            self.question_snapshot = question
            model = self.current_model
            if current_tab == 'numbers':
                valid, error_msg, numbers = self._validate_numbers(*(field.value for field in self.number_inputs))
                source = '数字模式'
            elif current_tab == 'date':
                valid, error_msg, numbers = self._validate_date_time(self.date_input.value, self.time_input.value)
                source = f'时间模式 · {self.date_input.value} {self.time_input.value} UTC+8（农历月、日、时辰）'
            elif current_tab == 'chinese':
                valid, error_msg, numbers = self._validate_chinese(self.chinese_input.value)
                source = f'汉字模式 · {self.chinese_input.value}（字典笔画）'
            else:
                self._show_error('请选择输入方式')
                return
            if not valid:
                self._show_error(error_msg)
                return
            self.input_summary = f'{source} · 起课数字：' + '、'.join(map(str, numbers))
            self.number_snapshot = tuple(numbers)
            result = HandTechnique.predict(*numbers)
            self.divination_result = result
            self._display_results(result.symbols, result.relations, None)
            self._collapse_form(question, model)
            self.status_message.set_text('本地三传已完成。选择AI并填写问题，可在结果区生成解读。')
            if model is not None and question:
                await self._run_ai_interpretation(result, question, model)
            else:
                self._scroll_to(self.reading_panel)
        except Exception as exc:
            self._show_error(f'计算失败：{exc}')
        finally:
            self._set_running(False)

    def _set_running(self, running):
        self.is_running = running
        self.submit_button.set_enabled(not running)
        self.ai_action.set_enabled(not running and self.divination_result is not None)
        if not running:
            self.submit_button.set_text('开始占卜')

    async def _request_ai_interpretation(self):
        if self.is_running or self.divination_result is None:
            return
        # 捕获当前问题/模型和既有起课结果，不重算未提交的数字。
        result = self.divination_result
        question = (self.question_input.value or '').strip()
        model = self.current_model
        if model is None or not question:
            message = ('未配置可用 AI 模型，请先配置 API 密钥并刷新页面。' if not self.available_models
                       else '请选择 AI 模型。' if model is None else '请填写想了解的具体问题。')
            self.error_message.set_text(message)
            self.status_message.set_text('本地结果已保留，请补充解读设置。')
            self.optional_panel.set_value(True)
            self._edit_inputs()
            return
        self._set_running(True)
        try:
            self._collapse_form(question, model)
            await self._run_ai_interpretation(result, question, model)
        finally:
            self._set_running(False)

    async def _run_ai_interpretation(self, result, question, model):
        self.error_message.set_text('')
        self.ai_interpretation = None
        self.ai_action.set_text('生成 AI 解读')
        self.submit_button.set_text('正在解读…')
        model_name = SupportedModels.get_display_name(model)
        self.status_message.set_text(f'本地三传已完成，{model_name} 正在生成解读…')
        self._display_ai_result(project_streaming_interpretation(''))
        self.ai_card.props('aria-busy=true')
        self.ai_status.set_text('正在生成…')
        self.ai_request_label.set_text(f'本次解读：{question} · {model_name}')
        self._scroll_to(self.ai_result_area)

        async def on_update(snapshot):
            self.ai_markdown.set_content(project_streaming_interpretation(snapshot))
            # 将本次更新交给 NiceGUI outbox；不等待浏览器回执。
            await asyncio.sleep(0)

        try:
            await asyncio.sleep(0)
            interpretation = await DivinationAgent(model).interpret_prediction_async(
                result.symbols, question, on_update=on_update)
            self.ai_markdown.set_content(interpretation)
            self.ai_interpretation = interpretation
            self.ai_status.set_text('解读完成')
            self.ai_action.set_text('重新解读')
            self.status_message.set_text('三传与AI解读已完成。修改输入后可再次提交。')
        except Exception as exc:
            self.ai_markdown.set_content('')
            message = f'AI解读失败：{exc}。本地结果已保留，可重新解读。'
            self.ai_card.classes('ai-failed')
            self.ai_status.props('role=alert aria-live=assertive')
            self.ai_status.set_text(message)
            self._show_error(message)
        finally:
            self.ai_card.props('aria-busy=false')

    def _set_form_collapsed(self, collapsed):
        self.form_card.classes(add='form-collapsed' if collapsed else '',
                               remove='' if collapsed else 'form-collapsed')
        self.edit_button.props(f'aria-expanded={str(not collapsed).lower()}')

    def _collapse_form(self, question, model):
        model_name = SupportedModels.get_display_name(model) if model else '仅本地'
        summary = f'{self.input_summary} · {question or "未填写问题"} · {model_name}'
        self.summary_label.set_text(summary)
        # 属性字典避免将用户文本拼接进 props 的解析语法。
        self.summary_label._props['title'] = summary
        self.summary_label._props['aria-label'] = summary
        self.summary_label.update()
        self._set_form_collapsed(True)

    def _edit_inputs(self):
        self._set_form_collapsed(False)
        self._scroll_to(self.form_card)

    @staticmethod
    def _scroll_to(element):
        # 非阻塞增强：定位失败不能影响本地结果或模型请求。
        if core.loop is None or not core.loop.is_running():
            return
        try:
            ui.run_javascript(f"""
                requestAnimationFrame(() => requestAnimationFrame(() => {{
                    const target = document.getElementById('c{element.id}');
                    if (!target) return;
                    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                    target.scrollIntoView({{block: 'start', behavior: reduced ? 'instant' : 'smooth'}});
                }}));
            """)
        except Exception:
            pass

    def _display_results(self, symbols, relations, ai_result):
        self.result_area.clear()
        stages = [('初传｜起点', '眼下的基础与切入点'),
                  ('中传｜过程', '推进中的变化与牵制'),
                  ('末传｜趋势', '条件延续时的可能走向')]
        with self.result_area:
            with ui.row().classes('section-heading'):
                ui.label('三传已成').classes('serif result-title')
                ui.badge('本地计算完成', color=None).classes('mode-badge')
            with ui.column().classes('input-snapshot'):
                ui.label(self.input_summary)
                if self.question_snapshot:
                    ui.label(f'本次问题：{self.question_snapshot}')
            ui.label('项目九宫法 · 三传表示观察阶段，不对应确定期限。').classes('helper-text')
            if self.number_snapshot is not None:
                self._display_palace_ring(build_palace_walk(self.number_snapshot), symbols, relations)
            with ui.element('div').classes('transmission-grid'):
                for i, (symbol, (stage, hint)) in enumerate(zip(symbols, stages)):
                    element_key = ELEMENT_KEYS.get(symbol.element.name, 'unknown')
                    with ui.card().classes('transmission-card').props(f'data-element={element_key}'):
                        with ui.row().classes('section-heading'):
                            ui.label(stage).classes('stage-label')
                            ui.label(f'0{i + 1}').classes('stage-number')
                        ui.label(hint).classes('helper-text')
                        ui.label(symbol.name).classes('serif symbol-name')
                        ui.badge(f'五行 · {symbol.element.name}', color=None).classes(f'element-badge element-{element_key}')
                        ui.label(symbol.description).classes('symbol-description')
                        ui.label(symbol.interpretation).classes('symbol-interpretation')
                        if i < 2:
                            with ui.column().classes('relation-block'):
                                ui.label(f'{("初传→中传", "中传→末传")[i]} · {relations[i]}').classes('relation-title')
                                ui.label(describe_relation(symbol, symbols[i + 1], relations[i])).classes('helper-text')
            ui.label('生：生助；克：制约；比和：同类。被生、被克以箭头左侧的传为主语，不能只凭生克判定吉凶。').classes('helper-text')
            with ui.expansion('查看传统文化背景', icon='auto_stories').classes('culture-panel'):
                for symbol, (stage, _) in zip(symbols, stages):
                    ui.label(f'{stage} · {symbol.name} · 方位：{symbol.direction} · 神灵：{symbol.deity}').classes('culture-title')
                    ui.label(symbol.deity_description).classes('helper-text mb-3')
                ui.label('方位与神灵是传统文化象征，不代表现实效果。').classes('helper-text')
        self._display_ai_result(ai_result)

    def _display_palace_ring(self, walk=None, symbols=None, relations=None):
        """渲染九宫环；无 walk 时为静态空状态，不伪造落点或经过标记。"""
        palaces = walk.palaces if walk is not None else tuple(sorted(SYMBOLS, key=lambda symbol: symbol.order))
        visits = [dict() for _ in palaces]
        landings = [[] for _ in palaces]
        if walk is not None:
            for segment_index, segment in enumerate(walk.segments):
                for index, count in enumerate(segment.visit_counts):
                    if count:
                        visits[index][segment.stage] = count
                landings[segment.landing_index].append((segment_index, segment.stage))
        animation = build_palace_animation(walk) if walk is not None else None
        with ui.element('div').classes('palace-ring-block') as block:
            if animation is not None:
                scope = f'palace-{uuid4().hex}'
                block.classes('palace-playing').props(f'data-animation={scope}')
                block.style(f'--palace-duration:{animation.relations_ms}ms')
                # 当前 NiceGUI 的 HTML 组件直接设置 innerHTML；style 随结果子树一起销毁。
                ui.html(palace_animation_css(animation, scope), tag='style').classes('palace-animation-style')
            ui.label('九宫环 · 顺时针 · 本宫起数').classes('palace-ring-title')
            with ui.element('div').classes('palace-ring').props('role=group aria-label="九宫环：九个符号按九宫计数顺序顺时针排列"'):
                ui.element('div').classes('palace-ring-disc').props('aria-hidden=true')
                if walk is not None:
                    with ui.element('div').classes('palace-hand-layer').props('aria-hidden=true').style(f'--palace-hand-length:{PALACE_RADIUS}%'):
                        for stage_index, hand in enumerate(build_palace_hands(walk)):
                            with ui.element('div').classes(f'palace-hand palace-stage-{hand.key}').props(
                                    f'data-stage={hand.stage} data-target-index={hand.target_index} data-target-order={hand.target_order}').style(
                                    f'--palace-hand-angle:{hand.angle}deg;--palace-delay:{animation.landing_ms[stage_index]}ms'):
                                ui.element('div').classes('palace-hand-line')
                with ui.element('div').classes('palace-ring-core').props('aria-hidden=true'):
                    ui.label('顺时针')
                    ui.label('本宫起数')
                for index, symbol in enumerate(palaces):
                    element_key = ELEMENT_KEYS.get(symbol.element.name, 'unknown')
                    left, top = _palace_coordinates(index, len(palaces))
                    with ui.element('div').classes('palace-node').props(
                            f'data-order={symbol.order} data-index={index} data-element={element_key} data-name="{symbol.name}"').style(f'left:{left}%;top:{top}%') as node:
                        if animation is not None:
                            node.style(f'--palace-highlight:{scope}-{index}')
                        ui.label(symbol.name).classes('palace-node-name serif')
                        ui.label(str(symbol.order)).classes('palace-node-order')
                        if index == 0:
                            ui.label('起算').classes('palace-origin')
                        if walk is not None:
                            with ui.element('div').classes('palace-visits').props('role=group aria-label="数宫经过标记"'):
                                for stage_index, (stage, short) in enumerate(PALACE_STAGES):
                                    count = visits[index].get(stage, 0)
                                    marker = short if count else ''
                                    label = f'{stage}经过 {count} 次' if count else f'{stage}未经过'
                                    chip = ui.label(marker).classes(f'palace-visit palace-stage-{PALACE_STAGE_KEYS[stage_index]}').props(
                                        f'data-stage={stage} data-visited={"true" if count else "false"} data-count={count} title="{label}"')
                                    if count:
                                        chip.style(f'--palace-delay:{animation.first_visits[stage_index][index]}ms')
                            for segment_index, stage in landings[index]:
                                landed = symbols[segment_index] if symbols else symbol
                                landed_key = ELEMENT_KEYS.get(landed.element.name, 'unknown')
                                ui.label(stage).classes(f'palace-landing palace-stage-{PALACE_STAGE_KEYS[segment_index]}').props(
                                    f'data-stage={stage} data-element={landed_key} data-finger-position="{landed.finger_position}" data-bagua="{landed.bagua}"').style(f'--palace-delay:{animation.landing_ms[segment_index]}ms')
            if walk is not None and symbols is not None:
                with ui.element('div').classes('palace-summaries'):
                    for segment, symbol in zip(walk.segments, symbols):
                        element_key = ELEMENT_KEYS.get(symbol.element.name, 'unknown')
                        with ui.element('div').classes('palace-summary').props(
                                f'data-stage={segment.stage} data-element={element_key} data-finger-position="{symbol.finger_position}" data-bagua="{symbol.bagua}"'):
                            with ui.element('div').classes('palace-summary-head'):
                                ui.label(segment.stage).classes('palace-summary-stage')
                                ui.label(symbol.name).classes('palace-summary-name serif')
                            ui.label(f'五行 · {symbol.element.name}').classes(f'palace-element element-{element_key}')
                            ui.label(f'手指位置：{symbol.finger_position}').classes('palace-meta')
                            ui.label(f'八卦：{symbol.bagua}').classes('palace-meta')
                            start_symbol = walk.palaces[segment.start_index]
                            ui.label(f'{segment.short}数 {segment.number} · 从 {start_symbol.name} 起数 → {segment.stage} {symbol.name}').classes('palace-segment')
                            ui.label(f'移动 {segment.moves} 步 · 整圈 {segment.full_cycles} · 余 {segment.remainder_steps} 步').classes('palace-segment-meta')
                with ui.element('div').classes('palace-relations').style(f'--palace-delay:{animation.relations_ms}ms'):
                    for index, relation in enumerate(relations[:2]):
                        first, second = symbols[index], symbols[index + 1]
                        ui.label(f'{walk.segments[index].stage}·{first.name} → {walk.segments[index + 1].stage}·{second.name} · {relation}').classes('palace-relation-title')
                        ui.label(describe_relation(first, second, relation)).classes('palace-relation-desc helper-text')

    def _display_ai_result(self, ai_result):
        if not ai_result:
            return
        self.ai_result_area.clear()
        with self.ai_result_area:
            with ui.card().classes('ai-card').props('aria-busy=false') as self.ai_card:
                with ui.row().classes('items-center gap-2'):
                    ui.icon('auto_awesome').classes('accent-text')
                    ui.label('AI 三传解读').classes('serif text-xl')
                self.ai_request_label = ui.label('').classes('helper-text')
                self.ai_status = ui.label('').classes('ai-status').props('role=status aria-live=polite')
                self.ai_markdown = ui.markdown(ai_result).classes('ai-interpretation w-full')

    def _display_empty_state(self):
        with self.result_area:
            with ui.column().classes('empty-state'):
                self._display_palace_ring()
                ui.label('静心一刻，三传待启').classes('serif empty-title')
                ui.label('在左侧起一课，点「开始占卜」，看看事情的起点、过程与趋势。').classes('empty-copy desktop-copy')
                ui.label('在上方起一课，点「开始占卜」，看看事情的起点、过程与趋势。').classes('empty-copy mobile-copy')
                with ui.element('div').classes('stage-guide'):
                    for number, title, hint in [('一', '初传', '看见起点'), ('二', '中传', '理解过程'), ('三', '末传', '观察趋势')]:
                        with ui.column().classes('stage-guide-item'):
                            ui.label(number).classes('guide-number serif')
                            ui.label(title).classes('guide-title')
                            ui.label(hint).classes('helper-text')
                with ui.row().classes('empty-note'):
                    ui.icon('spa', size='16px')
                    ui.label('一事一问，让思绪有迹可循')

    def _show_error(self, message: str):
        if self.divination_result is None:
            self._set_form_collapsed(False)
        self.error_message.set_text(message)
        self.status_message.set_text('解读失败，本地结果仍可查看。' if self.divination_result is not None else '未能计算，请检查输入。')

    def _on_model_change(self, e: ValueChangeEventArguments):
        self.current_model = next((model for model in self.available_models if model.value == e.value), None)

    @staticmethod
    def _add_theme_assets():
        """web.css 之后注入主题脚本与各主题样式；脚本在首屏绘制前读取已保存的皮肤。"""
        ids = json.dumps([theme.id for theme in THEMES], ensure_ascii=False)
        ui.add_head_html(f'<script>window.MSR_THEME_IDS={ids};window.MSR_THEME_DEFAULT={json.dumps(DEFAULT_THEME.id)};</script>')
        ui.add_head_html(f'<script>{(THEME_DIR / "theme.js").read_text(encoding="utf-8")}</script>')
        for theme in THEMES:
            if theme.stylesheet:
                ui.add_css(THEME_DIR / theme.stylesheet)

    @staticmethod
    def _create_theme_switcher():
        """纯客户端切换：点击只调用 window.msrTheme.apply，不经服务器。"""
        with ui.element('div').classes('theme-switcher').props('role=group aria-label="切换皮肤"'):
            for theme in THEMES:
                pressed = 'true' if theme is DEFAULT_THEME else 'false'
                button = ui.element('button').classes('theme-swatch').props(
                    f'type=button data-theme-id={theme.id} aria-pressed={pressed} aria-label="{theme.label}" title="{theme.label} · {theme.description}"')
                button.on('click', js_handler=f'() => window.msrTheme && window.msrTheme.apply({json.dumps(theme.id)})')
                with button:
                    ui.element('span').classes('swatch-dot').props('aria-hidden=true')
                    ui.html(theme.label, tag='span').classes('swatch-label')

    def create_ui(self):
        now = datetime.now(timezone(timedelta(hours=8)))
        ui.colors(primary='#a34432', secondary='#69755e', negative='#b33c32')
        ui.add_css(Path(__file__).with_name('web.css'))
        self._add_theme_assets()
        with ui.dialog() as guide, ui.card().classes('guide-dialog'):
            ui.label('从一问，到三传').classes('serif text-2xl')
            for title, copy in [
                ('01 · 选择起课方式', '输入三个 1–999 的整数、一个北京时间，或三个汉字。三种方式任选其一。'),
                ('02 · 点「开始占卜」', '本地立即呈现三传：初传看起点，中传看过程，末传看趋势。结合两段五行关系阅读，文化背景可按需展开。'),
                ('03 · 心中所问（选填）', '展开「心中所问 · 解读方式」，填写问题并选择可用的 AI 模型，在结果区点「生成 AI 解读 / 重新解读」，即可实时阅读解读；也可再次点「开始占卜」。'),
            ]:
                ui.label(title).classes('font-semibold mt-3')
                ui.label(copy).classes('helper-text')
            ui.label('本工具采用项目九宫法。解读用于梳理思路，现实决定仍需事实依据。').classes('guide-footnote')
            ui.button('开始探索', on_click=guide.close).props('unelevated no-caps').classes('self-end')

        with ui.column().classes('app-shell'):
            with ui.element('header').classes('site-header'):
                with ui.row().classes('brand'):
                    ui.label('壬').classes('brand-seal serif').props('aria-hidden=true')
                    with ui.column().classes('brand-wordmark'):
                        ui.label('小六壬').classes('serif brand-name')
                        ui.label('MINI SIX REN').classes('brand-english')
                with ui.row().classes('header-actions'):
                    ui.label('传统智慧 · 当下启发').classes('header-tagline')
                    create_page_nav('/')
                    self._create_theme_switcher()
                    ui.button('使用指南', icon='help_outline', on_click=guide.open).props('flat no-caps').classes('guide-button')

            with ui.element('main').classes('page-main'):
                with ui.element('section').classes('hero'):
                    with ui.column().classes('hero-copy'):
                        ui.label('观 时 · 察 势 · 明 心').classes('eyebrow')
                        with ui.row().classes('hero-line'):
                            ui.label(HERO_TITLE).classes('serif hero-title').props(f'role=heading aria-level=1 data-text="{HERO_TITLE}"')
                            ui.label('以传统智慧为镜，理清当下，从容向前。').classes('hero-description')
                    with ui.column().classes('hero-aside'):
                        ui.label('小六壬 · 项目九宫法').classes('hero-aside-title')
                        ui.label('起点 / 过程 / 趋势').classes('hero-aside-copy')

                with ui.element('div').classes('workspace'):
                    with ui.card().classes('form-card') as self.form_card:
                        with ui.row().classes('form-summary'):
                            self.summary_label = ui.label('').classes('form-summary-text')
                            self.edit_button = ui.button('修改', on_click=self._edit_inputs).props('flat no-caps aria-expanded=true').classes('edit-inputs-button')
                        with ui.column().classes('form-details') as self.form_details:
                            with ui.row().classes('section-heading'):
                                ui.label('起一课').classes('serif panel-title')
                                ui.badge('三种方式 · 任选其一', color=None).classes('quiet-badge')
                            with ui.tabs().classes('input-tabs').props('dense no-caps align=justify') as tabs:
                                ui.tab('numbers', label='数字', icon='pin')
                                ui.tab('date', label='时间', icon='schedule')
                                ui.tab('chinese', label='汉字', icon='translate')
                            with ui.tab_panels(tabs, value='numbers').classes('input-panels'):
                                with ui.tab_panel('numbers'):
                                    ui.label('心中默想，输入三个 1–999 的整数。').classes('helper-text input-hint')
                                    with ui.element('div').classes('input-grid'):
                                        self.number_inputs = [
                                            ui.number(label=label, value=i + 1, min=1, max=999, step=1).classes('w-full').props('outlined hide-bottom-space')
                                            for i, label in enumerate(('初数', '中数', '末数'))
                                        ]
                                with ui.tab_panel('date'):
                                    ui.label('以所选时刻的农历月、日、时辰起课。').classes('helper-text input-hint')
                                    with ui.element('div').classes('date-grid'):
                                        self.date_input = ui.input('公历日期', value=now.strftime('%Y-%m-%d')).classes('w-full').props('type=date outlined hide-bottom-space min=1900-01-01 max=2099-12-31')
                                        self.time_input = ui.input('北京时间', value=now.strftime('%H:%M')).classes('w-full').props('type=time outlined hide-bottom-space')
                                    ui.label('按北京时间 UTC+8；闰月沿用同名月份，23点按当日农历日取数。').classes('helper-text mt-3')
                                with ui.tab_panel('chinese'):
                                    ui.label('让心中想到的三个字，成为起点。').classes('helper-text input-hint')
                                    self.chinese_input = ui.input('三个汉字', placeholder='例如：天行健、中国人').classes('w-full').props('outlined hide-bottom-space')
                                    ui.label('按内置字典笔画取数，支持逗号或空格分隔。').classes('helper-text mt-3')
                            self.input_tabs = tabs
                            self.error_message = ui.label('').classes('error-message').props('role=alert')
                            self.submit_button = ui.button('开始占卜', icon='auto_awesome', on_click=self._perform_divination).classes('submit-button').props('unelevated no-caps')
                            self.status_message = ui.label('准备就绪：填写输入后开始占卜。').classes('status-message').props('role=status aria-live=polite')
                            # 选填区：配置了 AI 时默认展开，否则收起，让主按钮留在首屏。
                            caption = '选填 · 填写问题后可获得 AI 解读' if self.available_models else '选填 · 留空只看三传，本地无需 AI'
                            self.optional_panel = ui.expansion('心中所问 · 解读方式', caption=caption, icon='edit_note', value=bool(self.available_models)).classes('optional-panel')
                            with self.optional_panel:
                                self.question_input = ui.textarea('想了解的具体问题', placeholder='例如：准备换工作，接下来应先做好哪些准备？').classes('question-field w-full').props('outlined autogrow rows=2 hide-bottom-space')
                                model_options = {'local': '仅本地计算（不使用AI）'}
                                model_options.update({model.value: SupportedModels.get_display_name(model) for model in self.available_models})
                                self.model_select = ui.select(model_options, label='解读方式', value=self.current_model.value if self.current_model else 'local', on_change=self._on_model_change).classes('w-full').props('outlined hide-bottom-space')
                                if not self.available_models:
                                    with ui.row().classes('local-note'):
                                        ui.icon('check_circle_outline', size='16px')
                                        ui.label('本地即可查看完整三传，无需 AI。')
                                else:
                                    ui.label('选择 AI 并填写问题后生成解读；问题留空则只计算三传。').classes('helper-text')
                        self.edit_button.props(f'aria-controls=c{self.form_details.id}')

                    with ui.element('section').classes('reading-panel').props('aria-label=三传结果') as self.reading_panel:
                        with ui.row().classes('reading-heading'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('auto_stories', size='19px')
                                ui.label('三传观照').classes('reading-heading-title')
                            ui.label('由始而终，循序而观').classes('reading-heading-note')
                            self.ai_action = ui.button('生成 AI 解读', icon='auto_awesome', on_click=self._request_ai_interpretation).props('flat no-caps').classes('ai-action-button')
                            self.ai_action.disable()
                        self.result_area = ui.column().classes('result-area')
                        self._display_empty_state()
                        self.ai_result_area = ui.column().classes('ai-result-area')

                with ui.element('section').classes('wisdom-strip'):
                    ui.label('观').classes('serif wisdom-mark').props('aria-hidden=true')
                    with ui.column().classes('gap-1'):
                        ui.label('知其势，也尽其力。').classes('serif wisdom-title')
                        ui.label('三传是一种观察问题的方式。带着具体的问题来，带着更清晰的思路前行。').classes('helper-text')
                    ui.button('了解如何阅读', icon='east', on_click=guide.open).props('flat no-caps').classes('wisdom-button')
            with ui.element('footer').classes('site-footer'):
                ui.label('小六壬 · 传统文化探索')
                ui.label('解读用于梳理思路，现实决定仍需事实依据。')


class BaziWebApp:
    """每次页面请求独立持有输入和报告；仅编排共享计算，不实现命理规则。"""

    def __init__(self):
        self.report = None
        self.date_input = self.time_input = self.gender_input = self.year_input = None
        self.submit_button = self.error_message = self.status_message = self.result_area = None

    def _perform_calculation(self):
        self.report = None
        self.result_area.clear()
        self.error_message.set_text('')
        try:
            birth = parse_datetime(self.date_input.value, self.time_input.value)
            gender = normalize_gender(self.gender_input.value)
            year = self.year_input.value
            if isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 2099:
                raise ValueError('流年必须为1900-2099之间的整数')
            lunar = solar_to_lunar(birth.year, birth.month, birth.day)
            bazi = calculate_bazi(birth.year, birth.month, birth.day, birth.hour, birth.minute)
            wuxing = analyze_wuxing(bazi)
            analysis = [
                ('日主强弱', analyze_day_master_strength(bazi, gender)),
                ('配偶宫', analyze_spouse_palace(bazi, gender)),
                ('缺失影响', analyze_missing_wuxing(wuxing['missing'], gender)),
            ]
            formatted = format_bazi_output(bazi, wuxing, birth.strftime('%Y-%m-%d'),
                                           birth.strftime('%H:%M'), lunar, gender, target_year=year)
            report = dict(formatted=formatted, bazi=bazi, wuxing=wuxing, analysis=analysis)
            self._display_report(report)
            self.report = report
            self.status_message.set_text(f'本地测算已完成，报告流年：{year}年。')
        except Exception as exc:
            self.report = None
            self.result_area.clear()
            self.error_message.set_text(str(exc) if isinstance(exc, ValueError) else f'计算失败：{exc}')
            self.status_message.set_text('未能计算，请检查输入后再次测算。')

    def _display_report(self, report):
        formatted = report['formatted']
        sections = [
            ('basic', '基本信息', [(label, formatted['basic_info'][key]) for label, key in
                                  [('性别', 'sex'), ('公历生日', 'solar_date'), ('农历生日', 'lunar_date')]]),
            ('pillars', '八字信息', [(label, formatted['bazi_info'][key]) for label, key in
                                    [('生辰八字', 'birth_info'), ('命主五行', 'day_master'), ('八字五行', 'bazi_five_elements')]]),
            ('wuxing', '五行分析', [(label, formatted['wuxing_info'][key]) for label, key in
                                   [('五行个数', 'wuxing_count'), ('五行是否所缺', 'missing'),
                                    ('帮扶日主', 'helping_wuxing'), ('克泄耗日主', 'weakening_wuxing'),
                                    ('缺失影响概要', 'missing_impact')]]),
            ('analysis', '命运解析', report['analysis']),
            ('tai-sui', '流年太岁', format_tai_sui_section(formatted['tai_sui_info'])),
        ]
        self.result_area.clear()
        with self.result_area:
            for section, title, rows in sections:
                with ui.card().classes('bazi-section').props(f'data-section={section}'):
                    ui.label(title).classes('serif bazi-section-title').props('role=heading aria-level=2')
                    if section == 'pillars':
                        with ui.element('div').classes('bazi-pillars'):
                            for key, label in [('year', '年柱'), ('month', '月柱'), ('day', '日柱'), ('time', '时柱')]:
                                with ui.column().classes('bazi-pillar'):
                                    ui.label(label).classes('helper-text')
                                    ui.label(report['bazi'][key]).classes('serif')
                    if section == 'wuxing':
                        with ui.row().classes('bazi-elements'):
                            for element, count in report['wuxing']['wuxing_count'].items():
                                key = ELEMENT_KEYS[element]
                                ui.badge(f'{element} · {count}', color=None).classes(
                                    f'bazi-element-badge element-badge element-{key}').props(f'data-element={key}')
                    for label, value in rows:
                        with ui.column().classes('bazi-field'):
                            ui.label(label).classes('bazi-field-label')
                            ui.label(value).classes('bazi-field-value')

    def create_ui(self):
        now = datetime.now(timezone(timedelta(hours=8)))
        ui.colors(primary='#a34432', secondary='#69755e', negative='#b33c32')
        ui.add_css(Path(__file__).with_name('web.css'))
        DivinationWebApp._add_theme_assets()
        with ui.column().classes('app-shell bazi-page'):
            with ui.element('header').classes('site-header'):
                with ui.row().classes('brand'):
                    ui.label('壬').classes('brand-seal serif').props('aria-hidden=true')
                    with ui.column().classes('brand-wordmark'):
                        ui.label('小六壬').classes('serif brand-name')
                        ui.label('MINI SIX REN').classes('brand-english')
                with ui.row().classes('header-actions'):
                    create_page_nav('/bazi')
                    DivinationWebApp._create_theme_switcher()
            with ui.element('main').classes('page-main'):
                with ui.element('section').classes('hero'):
                    with ui.column().classes('hero-copy'):
                        ui.label('八字测算').classes('serif hero-title').props('role=heading aria-level=1 data-text="八字测算"')
                        ui.label('四柱 · 五行 · 流年太岁，纯本地测算，无需 AI。').classes('hero-description')
                with ui.element('div').classes('workspace'):
                    with ui.card().classes('form-card'):
                        ui.label('出生信息').classes('serif panel-title')
                        self.date_input = ui.input('公历出生日期', value=now.strftime('%Y-%m-%d')).classes('w-full').props(
                            'type=date min=1900-01-01 max=2099-12-31 outlined hide-bottom-space')
                        self.time_input = ui.input('出生时间', value='00:00').classes('w-full').props(
                            'type=time step=60 outlined hide-bottom-space')
                        self.gender_input = ui.select(['男', '女'], label='性别', value='男').classes('w-full').props('outlined hide-bottom-space')
                        ui.label('按北京时间 UTC+8；公历范围1900–2099，午夜换日，不做真太阳时校正。').classes('helper-text')
                        self.year_input = ui.select(list(range(1900, 2100)), label='流年（按北京时间公历年）',
                                                    value=now.year).classes('w-full').props('outlined hide-bottom-space')
                        ui.label('更换流年后，请再次点击「开始测算」更新报告。').classes('helper-text')
                        self.error_message = ui.label('').classes('error-message').props('role=alert')
                        self.submit_button = ui.button('开始测算', on_click=self._perform_calculation).classes('submit-button').props('unelevated no-caps')
                        self.status_message = ui.label('准备就绪：填写出生信息后开始测算。').classes('status-message').props('role=status aria-live=polite')
                    with ui.element('section').classes('reading-panel').props('aria-label=八字报告'):
                        self.result_area = ui.column().classes('result-area')
                        with self.result_area:
                            ui.label('填写出生信息，查看八字与流年太岁报告。').classes('helper-text')
                with ui.element('aside').classes('bazi-disclaimer'):
                    ui.label('八字后的性格和关系解读仍为原有简化规则；历法计算修正不代表这些解读得到验证。')
                    ui.label('日主强弱、配偶宫分析属于上述简化规则，仅供传统文化参考。')
            with ui.element('footer').classes('site-footer'):
                ui.label('小六壬 · 传统文化探索')
                ui.label('现实决定仍需事实依据。')


def create_bazi_page():
    """Each page owns its controller and every callback's widget references."""
    web_app = BaziWebApp()
    web_app.create_ui()
    return web_app


def create_page():
    """Each page owns its controller and every callback's widget references."""
    web_app = DivinationWebApp()
    web_app.create_ui()
    return web_app


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    ui.page('/', dark=False)(create_page)
    ui.page('/bazi', dark=False)(create_bazi_page)
    ui.run(title='小六壬 · 三传', port=8080, host='0.0.0.0', reload=True, favicon='☯', dark=False)


if __name__ in {'__main__', '__mp_main__'}:
    main()
