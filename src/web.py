#!/usr/bin/env python3
"""小六壬占卜 Web Interface，使用 NiceGUI 展示本地三传和可选AI解读。"""

import os
import sys
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List
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


ASSETS_DIR = Path(__file__).resolve().parent / 'web_assets'
WEB_STYLES = (ASSETS_DIR / 'theme.css').read_text(encoding='utf-8')
ORBIT_SVG = (ASSETS_DIR / 'orbit.svg').read_text(encoding='utf-8')


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
        self.empty_state = None
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
                    with ui.row().classes('items-center gap-3 ai-loading'):
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
        self.empty_state.set_visibility(False)
        stages = [('初传｜起点', '眼下的基础与切入点'),
                  ('中传｜过程', '推进中的变化与牵制'),
                  ('末传｜趋势', '条件延续时的可能走向')]
        with self.result_area:
            ui.label('三传已成，循序观之。').classes('result-title')
            ui.label(self.input_summary).classes('result-meta')
            if self.question_snapshot:
                ui.label(f'本次问题：{self.question_snapshot}').classes('result-meta result-question')
            ui.label('项目九宫法 · 三传表示观察阶段，不对应确定期限。').classes('field-hint')
            with ui.element('div').classes('transmission-grid'):
                for i, (symbol, (stage, hint)) in enumerate(zip(symbols, stages)):
                    with ui.card().classes('surface transmission-card'):
                        ui.label(stage).classes('stage-label')
                        ui.label(hint).classes('stage-hint')
                        with ui.column().classes('gap-2'):
                            ui.label(symbol.name).classes('symbol-name')
                            ui.label(f'五行 · {symbol.element.name}').classes('element-badge')
                        ui.label(symbol.description).classes('symbol-description')
                        ui.label(symbol.interpretation).classes('symbol-interpretation')
                        if i < 2:
                            with ui.column().classes('relation-block'):
                                ui.label(f'{("初传→中传", "中传→末传")[i]} · {relations[i]}').classes('relation-heading')
                                ui.label(describe_relation(symbol, symbols[i + 1], relations[i])).classes('relation-description')
            ui.label('生：生助；克：制约；比和：同类。被生、被克以箭头左侧的传为主语，不能只凭生克判定吉凶。').classes('field-hint')
            with ui.expansion('查看传统文化背景', icon='auto_stories').classes('culture-expansion'):
                for symbol, (stage, _) in zip(symbols, stages):
                    ui.label(f'{stage} · {symbol.name} · 方位：{symbol.direction} · 神灵：{symbol.deity}').classes('culture-title')
                    ui.label(symbol.deity_description).classes('culture-copy')
                ui.label('方位与神灵是传统文化象征，不代表现实效果。').classes('field-hint')
        self._display_ai_result(ai_result)

    def _display_ai_result(self, ai_result):
        if not ai_result:
            return
        self.ai_result_area.clear()
        with self.ai_result_area:
            with ui.card().classes('surface ai-card'):
                ui.label('AI 三传解读').classes('ai-title')
                ui.markdown(ai_result).classes('ai-interpretation w-full')

    def _show_error(self, message: str):
        self.error_message.set_text(message)
        self.empty_state.set_visibility(self.divination_result is None)
        self.status_message.set_text('解读失败，本地结果仍可查看。' if self.divination_result is not None else '未能计算，请检查输入。')

    def _on_model_change(self, e: ValueChangeEventArguments):
        self.current_model = next((model for model in self.available_models if model.value == e.value), None)

    def _create_help_dialogs(self):
        with ui.dialog() as guide, ui.card().classes('surface guide-dialog'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('一课三传，如何开始？').classes('dialog-title')
                ui.button(icon='close', on_click=guide.close).props('flat round dense aria-label=关闭使用说明')
            for title, description in [
                ('01 · 选择一种起课方式', '数字：输入三个 1–999 的整数。时间：按北京时间取农历月、日、时辰。汉字：输入三个汉字，按内置字典笔画取数。'),
                ('02 · 留下想了解的问题', '本地模式无需密钥即可查看完整三传。选用已配置的 AI 并填写问题，才会在本地结果之后请求解读。'),
                ('03 · 按阶段阅读三传', '初传看起点，中传看过程，末传看趋势。结合五行关系阅读，不凭单个符号判定吉凶，也不将三传对应为确定期限。'),
            ]:
                with ui.column().classes('guide-step'):
                    ui.label(title).classes('guide-step-title')
                    ui.label(description).classes('dialog-copy')
            ui.button('明白了，开始起课', on_click=guide.close).props('unelevated no-caps').classes('w-full')
        with ui.dialog() as about, ui.card().classes('surface guide-dialog'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('小六壬 · 三传').classes('dialog-title')
                ui.button(icon='close', on_click=about.close).props('flat round dense aria-label=关闭关于')
            ui.label('以传统为引，给思绪留一处空白。').classes('dialog-copy')
            ui.label('本项目采用九宫法，将起课结果分为初传、中传、末传，并呈现各传的五行关系与文化背景。它是探索传统文化、整理问题的一种方式。').classes('dialog-copy')
            ui.label('历法按北京时间 UTC+8 解释，支持公历 1900–2099 年。闰月沿用同名月份，23 点按当日农历日取数。').classes('dialog-copy')
            ui.label('解读用于梳理思路，现实决定仍需事实依据。').classes('dialog-copy')
            ui.button('返回', on_click=about.close).props('flat no-caps').classes('self-end')
        return guide, about

    def _create_empty_state(self):
        with ui.column().classes('empty-state') as empty_state:
            ui.html(ORBIT_SVG).classes('orbit-art').props('aria-hidden=true')
            ui.label('静心一念，起课观象').classes('empty-title')
            ui.label('选择一种起课方式，让三个线索\n陪你梳理眼前的疑问。').classes('empty-subtitle whitespace-pre-line')
            with ui.element('div').classes('stage-guide'):
                for index, title, caption in [
                    ('01', '初传 · 起点', '看见当下的基础'),
                    ('02', '中传 · 过程', '理解途中的变化'),
                    ('03', '末传 · 趋势', '探索可能的走向'),
                ]:
                    with ui.element('div').classes('stage-guide-item'):
                        ui.label(index).classes('stage-guide-index')
                        ui.label(title).classes('stage-guide-title')
                        ui.label(caption).classes('stage-guide-caption')
        return empty_state

    def _create_inputs(self, now):
        with ui.element('div').classes('section-heading'):
            ui.label('01').classes('step-number')
            ui.html('<h2>选择起课方式</h2>')
        ui.label('随心取数，或以此刻、以文字为引。').classes('section-caption')
        with ui.tabs().classes('method-tabs').props('inline-label dense no-caps align=justify') as tabs:
            ui.tab('numbers', label='数字', icon='tag')
            ui.tab('date', label='时间', icon='schedule')
            ui.tab('chinese', label='汉字', icon='translate')
        with ui.tab_panels(tabs, value='numbers'):
            with ui.tab_panel('numbers'):
                ui.label('输入三个 1–999 的整数').classes('field-hint')
                with ui.element('div').classes('input-grid'):
                    self.number_inputs = [
                        ui.number(label=label, value=i + 1, min=1, max=999, step=1)
                        .classes('number-field').props('outlined hide-bottom-space')
                        for i, label in enumerate(('初数', '中数', '末数'))
                    ]
            with ui.tab_panel('date'):
                with ui.element('div').classes('date-grid'):
                    self.date_input = ui.input('公历日期', value=now.strftime('%Y-%m-%d')).props('type=date outlined hide-bottom-space min=1900-01-01 max=2099-12-31')
                    self.time_input = ui.input('北京时间', value=now.strftime('%H:%M')).props('type=time outlined hide-bottom-space')
                ui.label('按北京时间 UTC+8，取农历月、日、时辰；闰月沿用同名月份，23点按当日农历日取数。').classes('field-hint')
            with ui.tab_panel('chinese'):
                self.chinese_input = ui.input('三个汉字', placeholder='例如：天行健、中国人').props('outlined hide-bottom-space')
                ui.label('按内置字典笔画取数，支持逗号或空格分隔。').classes('field-hint mt-3')
        self.input_tabs = tabs
        ui.element('hr').classes('input-divider')
        with ui.element('div').classes('section-heading'):
            ui.label('02').classes('step-number')
            ui.html('<h2>写下心中所问</h2>')
            ui.label('可选').classes('optional-tag')
        ui.label('问题越具体，越容易找到思考的方向。').classes('section-caption')
        model_options = {'local': '仅本地计算（不使用AI）'}
        model_options.update({model.value: SupportedModels.get_display_name(model) for model in self.available_models})
        self.model_select = ui.select(model_options, label='解读方式', value=self.current_model.value if self.current_model else 'local', on_change=self._on_model_change).classes('model-field').props('outlined dense hide-bottom-space')
        self.question_input = ui.textarea('想了解的具体问题', placeholder='例如：准备换工作，接下来应先做好哪些准备？').classes('question-field').props('outlined autogrow rows=2 hide-bottom-space')
        with ui.element('div').classes('mode-note'):
            ui.icon('info_outline', size='14px')
            ui.label('选择 AI 且填写问题时才请求解读；否则仅计算本地三传。')
        self.error_message = ui.label('').classes('error-message').props('role=alert')
        self.submit_button = ui.button('查看三传', icon='auto_awesome', on_click=self._perform_divination).classes('submit-button').props('unelevated no-caps')
        with ui.element('div').classes('privacy-note'):
            ui.icon('check_circle_outline', size='12px')
            ui.label('本地起课，无需 API 密钥' if not self.available_models else '本地三传先呈现，AI 解读随后到来')

    def create_ui(self):
        now = datetime.now(timezone(timedelta(hours=8)))
        ui.colors(primary='#526a43', secondary='#a85b46', negative='#a94335')
        ui.add_css(WEB_STYLES)
        guide, about = self._create_help_dialogs()
        with ui.element('header').classes('site-header'):
            with ui.element('div').classes('header-inner'):
                with ui.element('a').props('href=/ aria-label=小六壬首页').classes('brand'):
                    ui.label('壬').classes('brand-seal')
                    with ui.element('div'):
                        ui.label('小六壬').classes('brand-name')
                        ui.label('MINI SIX REN').classes('brand-en')
                with ui.element('nav').props('aria-label=主导航').classes('header-nav'):
                    ui.label('三传起课').classes('nav-current').props('aria-current=page')
                    ui.button('使用说明', on_click=guide.open).props('flat no-caps').classes('nav-button')
                    ui.button('关于', on_click=about.open).props('flat no-caps').classes('nav-button')
                    ui.label('一念起 · 万象生').classes('header-note')
        with ui.column().classes('page-shell'):
            with ui.element('section').classes('hero'):
                with ui.element('div'):
                    ui.label('A MOMENT OF CLARITY').classes('eyebrow')
                    ui.html('<h1>起一课，<span>理一念。</span></h1>')
                    ui.label('从起点、过程到趋势，在传统智慧中找到思考的线索。').classes('hero-description')
                with ui.element('div').classes('hero-aside').props('aria-hidden=true'):
                    ui.label('观象以明理，\n静心以知行。').classes('hero-verse whitespace-pre-line')
                    ui.label('观照').classes('small-seal')
            with ui.element('div').classes('workspace'):
                with ui.card().classes('surface input-card'):
                    self._create_inputs(now)
                with ui.column().classes('reading-column'):
                    with ui.card().classes('surface reading-panel'):
                        with ui.element('div').classes('reading-heading'):
                            with ui.element('div').classes('reading-title'):
                                ui.icon('filter_vintage', size='19px').classes('text-primary')
                                ui.label('三传 · 观象')
                            ui.label('项目九宫法').classes('method-badge')
                        self.empty_state = self._create_empty_state()
                        self.result_area = ui.column().classes('result-area')
                    with ui.element('div').classes('status-line'):
                        ui.icon('radio_button_checked', size='12px')
                        self.status_message = ui.label('准备就绪：填写输入后查看三传。').props('role=status aria-live=polite')
                    self.ai_result_area = ui.column().classes('w-full')
            with ui.element('aside').classes('reflection-strip'):
                with ui.element('div').classes('reflection-quote'):
                    ui.icon('eco')
                    ui.label('以传统为引，以理性为尺。')
                ui.label('解读用于梳理思路，现实决定仍需事实依据。').classes('reflection-note')
            with ui.element('footer').classes('site-footer'):
                with ui.element('div').classes('footer-mark'):
                    ui.label('小六壬 · 三传')
                    ui.element('span').classes('footer-dot')
                    ui.label('传统文化的当代表达')
                ui.label('静观其变 · 从容而行')


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
