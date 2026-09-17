#!/usr/bin/env python3
"""小六壬占卜 Web Interface，使用 NiceGUI 展示本地三传和可选AI解读。"""

import os
import re
import sys
import json
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from hand_technique import HandTechnique
from ai_agent import DivinationAgent, SupportedModels
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
    def __init__(self):
        self.current_model = None
        self.is_running = False
        self.submit_button = None
        self.available_models = []
        self.divination_result = None
        self.ai_interpretation = None
        self.input_summary = ''
        self.question_snapshot = ''
        self.model_select = None
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
        self.is_running = True
        self.submit_button.disable()
        self.submit_button.set_text('正在计算…')
        self.status_message.set_text('正在计算本地三传…')
        try:
            self.result_area.clear()
            self.ai_result_area.clear()
            self.error_message.set_text('')
            self.divination_result = None
            self.ai_interpretation = None
            self.input_summary = ''
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
            result = HandTechnique.predict(*numbers)
            self.divination_result = result
            self._display_results(result.symbols, result.relations, None)
            self.status_message.set_text('本地三传已完成。选择AI并填写问题，可再次提交获取解读。')
            if model is not None and question:
                model_name = SupportedModels.get_display_name(model)
                self.submit_button.set_text('正在解读…')
                self.status_message.set_text(f'本地三传已完成，正在等待 {model_name} 解读…')
                with self.ai_result_area:
                    with ui.row().classes('items-center gap-3'):
                        ui.spinner('dots').props('color=primary')
                        ui.label('本地三传已呈现，AI将结合您的问题解读。')
                await asyncio.sleep(0)
                interpretation = await DivinationAgent(model).interpret_prediction_async(result.symbols, question)
                self.ai_interpretation = interpretation
                self.ai_result_area.clear()
                self._display_ai_result(interpretation)
                self.status_message.set_text('三传与AI解读已完成。修改输入后可再次提交。')
        except Exception as exc:
            self.ai_result_area.clear()
            if self.divination_result is not None:
                self._show_error(f'AI解读失败：{exc}。本地结果已保留，可再次提交重试。')
            else:
                self._show_error(f'计算失败：{exc}')
        finally:
            self.is_running = False
            self.submit_button.set_text('查看三传')
            self.submit_button.enable()

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

    def _display_ai_result(self, ai_result):
        if not ai_result:
            return
        self.ai_result_area.clear()
        with self.ai_result_area:
            with ui.card().classes('ai-card'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('auto_awesome').classes('accent-text')
                    ui.label('AI 三传解读').classes('serif text-xl')
                ui.markdown(ai_result).classes('ai-interpretation w-full')

    def _display_empty_state(self):
        with self.result_area:
            with ui.column().classes('empty-state'):
                ui.html('''<div class="compass" aria-hidden="true">
                    <span class="compass-top">起</span><span class="compass-right">承</span>
                    <span class="compass-bottom">转</span><span class="compass-left">合</span>
                    <div class="compass-inner"><span>壬</span></div>
                </div>''')
                ui.label('静心一刻，三传待启').classes('serif empty-title')
                ui.label('从左侧选一种方式起课，看看事情的起点、过程与趋势。').classes('empty-copy desktop-copy')
                ui.label('在上方选一种方式起课，看看事情的起点、过程与趋势。').classes('empty-copy mobile-copy')
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
        with ui.dialog() as guide, ui.card().classes('guide-dialog'):
            ui.label('从一问，到三传').classes('serif text-2xl')
            for title, copy in [
                ('01 · 选择起课方式', '输入三个 1–999 的整数、一个北京时间，或三个汉字。三种方式任选其一。'),
                ('02 · 留下心中所问', '问题可留空。本地模式直接呈现三传；选择可用的 AI 模型并填写问题后，才会生成解读。'),
                ('03 · 顺着三传阅读', '初传看起点，中传看过程，末传看趋势。结合两段五行关系阅读，文化背景可按需展开。'),
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
                    self._create_theme_switcher()
                    ui.button('使用指南', icon='help_outline', on_click=guide.open).props('flat no-caps').classes('guide-button')

            with ui.element('main').classes('page-main'):
                with ui.element('section').classes('hero'):
                    with ui.column().classes('hero-copy'):
                        ui.label('观 时 · 察 势 · 明 心').classes('eyebrow')
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
                        ui.label('选一个方式，从此刻开始。').classes('helper-text')
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
                        ui.separator().classes('form-divider')
                        with ui.row().classes('section-heading'):
                            ui.label('心中所问').classes('form-section-title')
                            ui.label('选填').classes('optional-label')
                        self.question_input = ui.textarea('想了解的具体问题', placeholder='例如：准备换工作，接下来应先做好哪些准备？').classes('question-field w-full').props('outlined autogrow rows=3 hide-bottom-space')
                        model_options = {'local': '仅本地计算（不使用AI）'}
                        model_options.update({model.value: SupportedModels.get_display_name(model) for model in self.available_models})
                        self.model_select = ui.select(model_options, label='解读方式', value=self.current_model.value if self.current_model else 'local', on_change=self._on_model_change).classes('w-full').props('outlined hide-bottom-space')
                        if not self.available_models:
                            with ui.row().classes('local-note'):
                                ui.icon('check_circle_outline', size='16px')
                                ui.label('本地即可查看完整三传，无需 AI。')
                        else:
                            ui.label('选择 AI 并填写问题后生成解读；问题留空则只计算三传。').classes('helper-text')
                        self.error_message = ui.label('').classes('error-message').props('role=alert')
                        self.submit_button = ui.button('查看三传', icon='auto_awesome', on_click=self._perform_divination).classes('submit-button').props('unelevated no-caps')
                        self.status_message = ui.label('准备就绪：填写输入后查看三传。').classes('status-message').props('role=status aria-live=polite')

                    with ui.element('section').classes('reading-panel').props('aria-label=三传结果'):
                        with ui.row().classes('reading-heading'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('auto_stories', size='19px')
                                ui.label('三传观照').classes('reading-heading-title')
                            ui.label('由始而终，循序而观').classes('reading-heading-note')
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


def create_page():
    """Each page owns its controller and every callback's widget references."""
    web_app = DivinationWebApp()
    web_app.create_ui()
    return web_app


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    ui.page('/', dark=False)(create_page)
    ui.run(title='小六壬 · 三传', port=8080, host='0.0.0.0', reload=True, favicon='☯', dark=False)


if __name__ in {'__main__', '__mp_main__'}:
    main()
