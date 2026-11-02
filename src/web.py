#!/usr/bin/env python3
"""小六壬占卜 Web Interface，使用 NiceGUI 展示本地三传和可选AI解读。"""

import os
import re
import sys
import json
from uuid import uuid4
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from hand_technique import HandTechnique
from ai_agent import DivinationAgent, SupportedModels
from reading import ReadingSession, MAX_SUPPLEMENTS
from utils.stroke_count import get_stroke_counts
from utils.calendar_converter import date_to_numbers
from utils.validation import validate_numbers, validate_chinese
from utils.symbol_relations import describe_relation

THEME_DIR = Path(__file__).with_name('themes')
HERO_TITLE = '一念起，观三传。'
# 五行→CSS 钩子；默认皮肤不使用这些类，仅供主题分色。
ELEMENT_KEYS = {'木': 'wood', '火': 'fire', '土': 'earth', '金': 'metal', '水': 'water'}


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


class DivinationWebApp:
    def __init__(self, *, api_settings=None, desktop=False):
        self.desktop = desktop
        self.report_button = None
        self.report_options = []
        self.report_status = None
        self.is_exporting = False
        self.api_settings = api_settings
        self.api_settings_panel = None
        self.model_hint = None
        self.current_model = None
        self.is_running = False
        self.submit_button = None
        self.available_models = []
        self.divination_result = None
        self.reading_session = None
        self.supplement_area = None
        self.supplement_form = None
        self.supplement_input = None
        self.supplement_button = None
        self.supplement_status = None
        self.supplement_error = None
        self.follow_up_label = None
        self.retry_button = None
        self.input_summary = ''
        self.question_snapshot = ''
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
        self.reading_tabs = None
        self.interpretation_status = None
        self.error_message = None
        self.status_message = None
        self._check_available_models()

    def _check_available_models(self):
        self.available_models = (self.api_settings.available_models if self.api_settings is not None
                                 else DivinationAgent.get_available_models())
        self.current_model = self.available_models[0] if self.available_models else None

    def open_api_settings(self):
        if self.api_settings_panel is not None:
            self.api_settings_panel.open()

    def _model_options(self):
        return {'local': '仅本地计算（不使用AI）'} | {
            model.value: SupportedModels.get_display_name(model) for model in self.available_models
        }

    def _optional_caption(self):
        return '选填 · 填写问题后可获得 AI 解读' if self.available_models else '选填 · 留空只看三传，本地无需 AI'

    def _refresh_ai_options(self):
        self._check_available_models()
        self.model_select.set_options(self._model_options(), value=self.current_model.value if self.current_model else 'local')
        self.optional_panel.props(f'caption="{self._optional_caption()}"')
        self.optional_panel.set_value(bool(self.available_models))
        self.model_hint.set_text(self._model_hint_text())

    def _model_hint_text(self):
        return ('选择 AI 并填写问题后生成解读；问题留空则只计算三传。' if self.available_models
                else '本地即可查看完整三传，无需 AI。')

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
        self.submit_button.set_text('正在计算…')
        self.status_message.set_text('正在计算本地三传…')
        try:
            self.result_area.clear()
            self._set_interpretation_status('idle')
            self._display_ai_placeholder()
            self.reading_tabs.set_value('observation')
            self.error_message.set_text('')
            self.divination_result = None
            self.reading_session = None
            self.supplement_input.set_value('')
            self.supplement_error.set_text('')
            self._sync_reading_controls()
            self.input_summary = ''
            current_tab = self.input_tabs.value
            question = (self.question_input.value or '').strip()
            self.question_snapshot = question
            model = self.current_model
            api_key = self.api_settings.key_for(model) if self.api_settings is not None and model else None
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
            result = HandTechnique.predict(*numbers)
            self.divination_result = result
            self._display_results(result.symbols, result.relations)
            self.status_message.set_text('本地三传已完成。选择AI并填写问题，可再次提交获取解读。')
            if model is not None and question:
                self.reading_session = ReadingSession.start(result, question)
                await self._generate_reading(self.reading_session, model, api_key)
        except Exception:
            self._show_error('计算失败，请检查输入后重试。')
            self._display_ai_placeholder()
        finally:
            self._set_running(False)

    def _set_running(self, running):
        self.is_running = running
        self.submit_button.set_enabled(not running)
        if not running:
            self.submit_button.set_text('开始占卜')
        self.ai_result_area.props(f'aria-busy={str(running).lower()}')
        self._sync_reading_controls()

    def _sync_reading_controls(self):
        session = self.reading_session
        ready = session is not None and session.reading is not None
        self.supplement_area.set_visibility(session is not None)
        self.supplement_form.set_visibility(ready)
        self.retry_button.set_visibility(session is not None and not ready)
        self.retry_button.set_enabled(not self.is_running)
        count = len(session.supplements) if session else 0
        self.supplement_button.set_enabled(not self.is_running and ready and count < MAX_SUPPLEMENTS)
        self.supplement_input.set_enabled(not self.is_running and count < MAX_SUPPLEMENTS)
        self.follow_up_label.set_text((session.reading.follow_up or '') if ready else '')
        self.follow_up_label.set_visibility(ready and bool(session.reading.follow_up))
        self.supplement_status.set_text(
            '补充解读中…' if self.is_running and ready else
            ('已补充5/5次，请重新起课。' if count >= MAX_SUPPLEMENTS else f'已补充{count}/5次，每次最多1000字。')
        )
        self.supplement_area.props(f'aria-busy={str(self.is_running).lower()}')
        self._sync_report_controls()

    async def _retry_reading(self):
        base = self.reading_session
        if self.is_running or base is None or base.reading is not None:
            return
        await self._update_reading(base)

    async def _submit_supplement(self):
        base = self.reading_session
        if self.is_running or base is None or base.reading is None:
            return
        supplement = self.supplement_input.value or ''
        try:
            base.validate_supplement(supplement)
        except ValueError as exc:
            self.supplement_error.set_text(str(exc))
            return
        await self._update_reading(base, supplement=supplement)

    async def _update_reading(self, base, *, supplement=None):
        self._set_running(True)
        try:
            model = self.current_model
            api_key = self.api_settings.key_for(model) if self.api_settings is not None and model else None
            await self._generate_reading(base, model, api_key, supplement=supplement)
        finally:
            self._set_running(False)

    async def _generate_reading(self, base, model, api_key, *, supplement=None):
        initial = base.reading is None
        self.supplement_error.set_text('')
        if initial:
            self.error_message.set_text('')
            self._set_interpretation_status('loading')
            self.submit_button.set_text('正在解读…')
            self.status_message.set_text('本地三传已完成，正在等待 AI 解读…')
            self.ai_result_area.clear()
            with self.ai_result_area:
                with ui.column().classes('reading-loading').props('role=status aria-live=polite'):
                    ui.label('三传已成 · 正在研读').classes('reading-kicker')
                    ui.label('循三传，理清所问。').classes('serif reading-loading-title')
                    with ui.row().classes('items-center gap-3'):
                        ui.spinner('dots').props('color=primary')
                        ui.label('本地三传已呈现，AI将结合您的问题生成完整解读。').classes('helper-text')
                    ui.label('可切换「三传观照」核对本地结果，无需重复起课。').classes('helper-text')
        self._sync_reading_controls()
        try:
            if model is None:
                raise RuntimeError('请先选择可用的 AI 模型。')
            agent = (DivinationAgent(model, api_key=api_key) if self.api_settings is not None
                     else DivinationAgent(model))
            candidate = await agent.interpret_prediction_async(base, supplement=supplement)
        except Exception:
            if self.reading_session is not base:
                return
            if initial:
                self._set_interpretation_status('error')
                self._show_error('AI解读失败，请检查 API Key、网络、余额及模型权限。本地结果已保留。')
                self._display_ai_placeholder('解读失败，本地三传已保留。可点击「重试解读」，沿用本次问题与三传。')
            else:
                self.supplement_error.set_text('补充解读失败，已有解读已保留。请检查模型设置后重试，输入不会清空。')
            return
        if self.reading_session is not base:
            return
        self.reading_session = candidate
        self._display_ai_result(candidate)
        if supplement is not None:
            self.supplement_input.set_value('')
        self._set_interpretation_status('ready')
        self.status_message.set_text('三传与AI解读已完成。可补充情况，或修改输入后重新起课。')
        self._sync_reading_controls()

    def _sync_report_controls(self):
        if self.report_button is None:
            return
        enabled = self.divination_result is not None and not self.is_running and not self.is_exporting
        self.report_button.set_enabled(enabled)
        for option in self.report_options:
            option.set_enabled(enabled)

    async def _export_report(self, variant):
        if (not self.desktop or self.is_running or self.is_exporting
                or self.divination_result is None or variant not in ('print', 'wechat')):
            return
        from reports import render_report
        self.is_exporting = True
        self._sync_report_controls()
        self.report_status.set_text('请选择 PDF 保存位置…')
        try:
            html = render_report(self.divination_result, variant=variant,
                                 input_summary=self.input_summary, question=self.question_snapshot,
                                 session=self.reading_session)
            payload = json.dumps({'variant': variant, 'html': html, 'request_id': uuid4().hex}, ensure_ascii=True)
            result = await ui.run_javascript(f'''return await new Promise(resolve => {{
                const payload = {payload};
                let timer;
                const finish = event => {{
                    let result;
                    try {{ result = JSON.parse(event.detail); }} catch {{ return; }}
                    if (!result || result.request_id !== payload.request_id) return;
                    clearTimeout(timer);
                    window.removeEventListener('msr:report-result', finish);
                    resolve(result);
                }};
                window.addEventListener('msr:report-result', finish);
                timer = setTimeout(() => {{
                    window.removeEventListener('msr:report-result', finish);
                    resolve({{status: 'error'}});
                }}, 590000);
                window.dispatchEvent(new CustomEvent('msr:export-report', {{ detail: JSON.stringify(payload) }}));
            }});''', timeout=600)
            status = result.get('status') if isinstance(result, dict) else 'error'
            messages = {'saved': 'PDF 报告已保存。', 'cancelled': '已取消保存，结果未改变。',
                        'busy': '已有报告正在导出，请稍后重试。'}
            message = messages.get(status, '报告保存失败，请检查保存位置、权限或磁盘空间后重试。')
            if isinstance(result, dict) and result.get('code') == 'layout':
                message = '当前内容无法排入可读的 A4 单页，请选择微信版保留完整内容。'
            self.report_status.set_text(message)
        except Exception:
            self.report_status.set_text('报告导出失败，请重试。已有结果未改变。')
        finally:
            self.is_exporting = False
            self._sync_report_controls()

    def _create_report_menu(self):
        with ui.column().classes('report-tools items-end gap-1'):
            self.report_button = ui.button('报告', icon='description').props('outline no-caps').classes('report-button')
            with self.report_button, ui.menu().props('auto-close'):
                self.report_options = [
                    ui.menu_item('打印版 · A4 单页 PDF', on_click=lambda: self._export_report('print')),
                    ui.menu_item('微信版 · 手机多页 PDF', on_click=lambda: self._export_report('wechat')),
                ]
                ui.separator()
                ui.label('打印版为摘要；微信版保留完整内容。').classes('text-xs q-pa-sm')
            self.report_status = ui.label('').classes('helper-text report-status').props('role=status aria-live=polite')
        self._sync_report_controls()

    def _display_results(self, symbols, relations):
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

    def _display_ai_result(self, session: ReadingSession):
        reading = session.reading
        self.ai_result_area.clear()
        with self.ai_result_area:
            with ui.card().classes('ai-card reading-brief'):
                with ui.element('header').classes('reading-brief-header'):
                    with ui.row().classes('reading-brief-topline'):
                        ui.label('三传研判 / AI READING').classes('reading-kicker')
                        ui.label(f'第 {len(session.supplements)} 次补充' if session.supplements else '初次解读').classes('reading-edition')
                    ui.label('三传解读').classes('serif reading-brief-title').props('role=heading aria-level=2')
                    ui.label(session.snapshot.question).classes('reading-question')
                    with ui.element('div').classes('reading-transmission-axis').props('role=group aria-label=本次三传与关系'):
                        for i, (stage, fact) in enumerate(zip(('初传 · 起点', '中传 · 过程', '末传 · 趋势'), session.snapshot.transmissions)):
                            with ui.column().classes('reading-axis-stage'):
                                ui.label(stage).classes('reading-axis-label')
                                with ui.row().classes('reading-axis-symbol'):
                                    ui.label(fact.name).classes('serif')
                                    ui.label(fact.element).classes('reading-axis-element')
                            if i < 2:
                                with ui.column().classes('reading-axis-link'):
                                    ui.label(session.snapshot.relations[i].name)
                                    ui.icon('east').props('aria-hidden=true')
                with ui.element('div').classes('reading-brief-body'):
                    with ui.element('section').classes('reading-verdict').props('aria-label=核心判断'):
                        ui.label('核心判断').classes('reading-section-title reading-section-label')
                        ui.label(reading.answer).classes('reading-text reading-answer ai-interpretation')
                    with ui.element('section').classes('reading-actions').props('aria-label=下一步'):
                        ui.label('下一步').classes('reading-section-title reading-section-label')
                        ui.label('把判断落到行动').classes('reading-action-intro')
                        with ui.element('ol').classes('reading-action-list'):
                            for i, action in enumerate(reading.actions, 1):
                                with ui.element('li').classes('reading-action-item'):
                                    ui.label(f'{i:02}').classes('reading-action-number').props('aria-hidden=true')
                                    ui.label(action).classes('reading-text reading-action')
                if reading.caution:
                    with ui.column().classes('reading-caution').props('role=note aria-label=必要提醒'):
                        ui.label('必要提醒').classes('reading-section-title')
                        ui.label(reading.caution).classes('reading-text')
                with ui.expansion('查看三传依据', caption='核对本地事实与象征解释', icon='account_tree', value=False).classes('reading-rationale w-full'):
                    ui.label('象征解释').classes('reading-section-title')
                    ui.label(reading.rationale).classes('reading-text')
                    ui.label('本地事实 · 不随解读改变').classes('reading-section-title')
                    for stage, fact in zip(('初传', '中传', '末传'), session.snapshot.transmissions):
                        ui.label(f'{stage} · {fact.name} · {fact.element}').classes('reading-fact')
                    for stage, fact in zip(('初传→中传', '中传→末传'), session.snapshot.relations):
                        ui.label(f'{stage} · {fact.name} · {fact.explanation}').classes('reading-fact reading-text')

    def _set_interpretation_status(self, state):
        labels = {'idle': '未生成', 'loading': '解读中…', 'ready': '可查看', 'error': '失败'}
        self.interpretation_status.set_text(labels[state])
        self.interpretation_status.props(f'data-state={state}')

    def _display_ai_placeholder(self, message='在「心中所问 · 解读方式」中填写问题并选择可用的 AI 模型，再点「开始占卜」即可在这里查看解读。'):
        self.ai_result_area.clear()
        with self.ai_result_area:
            with ui.column().classes('interpretation-placeholder'):
                ui.label('解').classes('serif reading-emblem').props('aria-hidden=true')
                ui.label('由象入理，由理而行').classes('reading-kicker')
                ui.label('三传解读').classes('serif reading-placeholder-title')
                ui.label(message).classes('helper-text').props('role=status aria-live=polite')
                with ui.row().classes('reading-placeholder-guide').props('aria-hidden=true'):
                    for title in ('回应所问', '明确行动', '追溯依据'):
                        ui.label(title)

    def _display_empty_state(self):
        with self.result_area:
            with ui.column().classes('empty-state'):
                ui.html('''<div class="compass" aria-hidden="true">
                    <span class="compass-top">起</span><span class="compass-right">承</span>
                    <span class="compass-bottom">转</span><span class="compass-left">合</span>
                    <div class="compass-inner"><span>壬</span></div>
                </div>''')
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
        ui.add_css(Path(__file__).with_name('reading.css'))
        with ui.dialog() as guide, ui.card().classes('guide-dialog'):
            ui.label('从一问，到三传').classes('serif text-2xl')
            for title, copy in [
                ('01 · 选择起课方式', '输入三个 1–999 的整数、一个北京时间，或三个汉字。三种方式任选其一。'),
                ('02 · 点「开始占卜」', '本地立即呈现三传：初传看起点，中传看过程，末传看趋势。结合两段五行关系阅读，文化背景可按需展开。'),
                ('03 · 心中所问（选填）', '展开「心中所问 · 解读方式」，填写问题并选择可用的 AI 模型，再次点「开始占卜」即可获得针对性解读。'),
            ]:
                ui.label(title).classes('font-semibold mt-3')
                ui.label(copy).classes('helper-text')
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
                    self._create_theme_switcher()
                    if self.api_settings is not None:
                        ui.button('API 设置', icon='key', on_click=self.open_api_settings).props('flat no-caps').classes('guide-button api-settings-button')
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
                    with ui.card().classes('form-card'):
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
                        self.optional_panel = ui.expansion('心中所问 · 解读方式', caption=self._optional_caption(), icon='edit_note', value=bool(self.available_models)).classes('optional-panel')
                        with self.optional_panel:
                            self.question_input = ui.textarea('想了解的具体问题', placeholder='例如：准备换工作，接下来应先做好哪些准备？').classes('question-field w-full').props('outlined autogrow rows=2 hide-bottom-space')
                            self.model_select = ui.select(self._model_options(), label='解读方式', value=self.current_model.value if self.current_model else 'local', on_change=self._on_model_change).classes('w-full model-select').props('outlined hide-bottom-space')
                            self.model_hint = ui.label(self._model_hint_text()).classes('helper-text')

                    with ui.element('section').classes('reading-panel').props('aria-label=三传结果'):
                        with ui.row().classes('reading-heading'):
                            with ui.tabs().classes('reading-tabs').props('dense no-caps inline-label align=left') as reading_tabs:
                                ui.tab('observation', label='三传观照', icon='auto_stories')
                                with ui.tab('interpretation', label='三传解读', icon='auto_awesome'):
                                    self.interpretation_status = ui.badge('未生成', color=None).classes('interpretation-status').props('data-state=idle role=status aria-live=polite aria-atomic=true')
                            self.reading_tabs = reading_tabs
                            if self.desktop:
                                self._create_report_menu()
                            else:
                                ui.label('由始而终，循序而观').classes('reading-heading-note')
                        with ui.tab_panels(reading_tabs, value='observation', animated=False).classes('reading-panels'):
                            with ui.tab_panel('observation'):
                                self.result_area = ui.column().classes('result-area')
                                self._display_empty_state()
                            with ui.tab_panel('interpretation'):
                                self.ai_result_area = ui.column().classes('ai-result-area')
                                self._display_ai_placeholder()
                                with ui.column().classes('supplement-area') as self.supplement_area:
                                    self.retry_button = ui.button('重试解读', on_click=self._retry_reading).props('outline no-caps')
                                    with ui.column().classes('supplement-form') as self.supplement_form:
                                        with ui.row().classes('reading-supplement-heading'):
                                            ui.icon('forum', size='18px').props('aria-hidden=true')
                                            ui.label('同课追问').classes('serif')
                                            ui.label('沿用三传，不重新起课').classes('helper-text')
                                        self.follow_up_label = ui.label('').classes('reading-text reading-follow-up')
                                        self.supplement_input = ui.textarea('补充情况（沿用本次三传）', placeholder='可回答上方问题，或更正、补充背景。').classes('w-full').props('outlined autogrow rows=2')
                                        self.supplement_status = ui.label('').classes('helper-text').props('role=status aria-live=polite')
                                        self.supplement_button = ui.button('补充解读', on_click=self._submit_supplement).props('outline no-caps')
                                    self.supplement_error = ui.label('').classes('error-message').props('role=alert')
                                self._sync_reading_controls()

                with ui.element('section').classes('wisdom-strip'):
                    ui.label('观').classes('serif wisdom-mark').props('aria-hidden=true')
                    with ui.column().classes('gap-1'):
                        ui.label('知其势，也尽其力。').classes('serif wisdom-title')
                        ui.label('三传是一种观察问题的方式。带着具体的问题来，带着更清晰的思路前行。').classes('helper-text')
                    ui.button('了解如何阅读', icon='east', on_click=guide.open).props('flat no-caps').classes('wisdom-button')
            with ui.element('footer').classes('site-footer'):
                ui.label('小六壬 · 传统文化探索')
                ui.label('解读用于梳理思路，现实决定仍需事实依据。')
        if self.api_settings is not None:
            from api_settings_ui import APISettingsPanel
            self.api_settings_panel = APISettingsPanel(
                self.api_settings, on_saved=self._refresh_ai_options, is_running=lambda: self.is_running,
            )
            if self.api_settings.needs_onboarding:
                self.open_api_settings()


def create_page(*, api_settings=None, show_settings=False, desktop=False):
    """Each page owns its controller and every callback's widget references."""
    web_app = DivinationWebApp(api_settings=api_settings, desktop=desktop)
    web_app.create_ui()
    if show_settings:
        web_app.open_api_settings()
    return web_app


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    ui.page('/', dark=False)(create_page)
    ui.run(title='小六壬 · 三传', port=8080, host='0.0.0.0', reload=True, favicon='☯', dark=False)


if __name__ in {'__main__', '__mp_main__'}:
    main()
