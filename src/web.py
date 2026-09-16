#!/usr/bin/env python3
"""小六壬占卜 Web Interface，使用 NiceGUI 展示本地三传和可选AI解读。"""

import os
import sys
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from hand_technique import HandTechnique
from ai_agent import DivinationAgent, SupportedModels
from utils.stroke_count import get_stroke_counts
from utils.calendar_converter import date_to_numbers
from utils.validation import validate_numbers, validate_chinese
from utils.symbol_relations import describe_relation


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
                        ui.spinner('dots').props('color=cyan')
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
            ui.label('三传结果').classes('text-2xl font-bold')
            ui.label(self.input_summary).classes('text-sm text-slate-300 break-words w-full')
            if self.question_snapshot:
                ui.label(f'本次问题：{self.question_snapshot}').classes('text-sm text-slate-300 break-words w-full')
            ui.label('项目九宫法 · 三传表示观察阶段，不对应确定期限。').classes('text-sm text-slate-400')
            with ui.element('div').classes('transmission-grid'):
                for i, (symbol, (stage, hint)) in enumerate(zip(symbols, stages)):
                    with ui.card().classes('surface transmission-card'):
                        ui.label(stage).classes('text-cyan-200 font-semibold')
                        ui.label(hint).classes('text-xs text-slate-300')
                        with ui.row().classes('items-center gap-3'):
                            ui.label(symbol.name).classes('text-3xl font-bold text-white')
                            ui.badge(f'五行 · {symbol.element.name}').props('outline color=cyan')
                        ui.label(symbol.description).classes('font-medium text-slate-200')
                        ui.label(symbol.interpretation).classes('leading-relaxed text-slate-300')
                        if i < 2:
                            with ui.column().classes('relation-block'):
                                ui.label(f'{("初传→中传", "中传→末传")[i]} · {relations[i]}').classes('text-amber-200 font-medium')
                                ui.label(describe_relation(symbol, symbols[i + 1], relations[i])).classes('text-sm text-slate-200')
            ui.label('生：生助；克：制约；比和：同类。被生、被克以箭头左侧的传为主语，不能只凭生克判定吉凶。').classes('text-sm text-slate-300')
            with ui.expansion('查看传统文化背景', icon='auto_stories').classes('w-full surface'):
                for symbol, (stage, _) in zip(symbols, stages):
                    ui.label(f'{stage} · {symbol.name} · 方位：{symbol.direction} · 神灵：{symbol.deity}').classes('font-medium')
                    ui.label(symbol.deity_description).classes('text-sm text-slate-300 mb-3')
                ui.label('方位与神灵是传统文化象征，不代表现实效果。').classes('text-sm text-slate-400')
        self._display_ai_result(ai_result)

    def _display_ai_result(self, ai_result):
        if not ai_result:
            return
        self.ai_result_area.clear()
        with self.ai_result_area:
            with ui.card().classes('w-full surface p-5 md:p-8'):
                ui.label('AI 三传解读').classes('text-xl font-bold text-cyan-200')
                ui.markdown(ai_result).classes('ai-interpretation w-full')

    def _show_error(self, message: str):
        self.error_message.set_text(message)
        self.status_message.set_text('解读失败，本地结果仍可查看。' if self.divination_result is not None else '未能计算，请检查输入。')

    def _on_model_change(self, e: ValueChangeEventArguments):
        self.current_model = next((model for model in self.available_models if model.value == e.value), None)

    def create_ui(self):
        now = datetime.now(timezone(timedelta(hours=8)))
        ui.colors(primary='#a78bfa', secondary='#67e8f9', negative='#fca5a5')
        ui.add_css('''
            body, .q-page { background: #101827; color: #f1f5f9; }
            .page-shell { width: 100%; max-width: 1120px; margin: auto; padding: 24px; gap: 24px; }
            .surface { background: #1c2739; border: 1px solid #3b4961; border-radius: 16px; }
            .transmission-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; width: 100%; }
            .transmission-card { padding: 24px; min-width: 0; overflow-wrap: anywhere; }
            .relation-block { margin-top: auto; padding-top: 16px; border-top: 1px solid #475569; width: 100%; }
            .input-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; width: 100%; }
            .date-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; width: 100%; }
            .q-tab-panels { background: transparent; }
            .q-tab-panel { padding: 16px 0 0; }
            .q-field { min-width: 0; }
            .ai-interpretation { line-height: 1.85; font-size: 16px; overflow-wrap: anywhere; }
            .ai-interpretation h3 { color: #a5f3fc; font-size: 1.15rem; margin: 24px 0 12px; }
            .ai-interpretation strong { color: #fde68a; }
            .ai-interpretation p { margin-bottom: 16px; }
            .ai-interpretation ul, .ai-interpretation ol { padding-left: 24px; }
            .q-btn:focus-visible, .q-item:focus-visible { outline: 2px solid #67e8f9; outline-offset: 3px; }
            @media (max-width: 700px) {
                .page-shell { padding: 16px; gap: 16px; }
                .transmission-grid, .date-grid { grid-template-columns: minmax(0, 1fr); }
                .transmission-card { padding: 20px; }
            }
        ''')
        with ui.column().classes('page-shell'):
            with ui.row().classes('w-full items-center justify-between gap-4'):
                with ui.column().classes('gap-2'):
                    ui.label('小六壬 · 三传').classes('text-3xl font-bold')
                    ui.label('看清起点、过程与趋势，让传统术语更容易理解。').classes('text-slate-300')
                ui.badge('项目九宫法').props('outline color=cyan')

            with ui.card().classes('w-full surface p-5 md:p-6'):
                ui.label('1 · 选择起课方式').classes('text-lg font-semibold')
                ui.label('三种方式任选一种；无需AI也能查看完整三传。').classes('text-sm text-slate-300')
                with ui.tabs().classes('w-full').props('align=left') as tabs:
                    ui.tab('numbers', label='数字', icon='pin')
                    ui.tab('date', label='时间', icon='calendar_today')
                    ui.tab('chinese', label='汉字', icon='translate')
                with ui.tab_panels(tabs, value='numbers').classes('w-full'):
                    with ui.tab_panel('numbers'):
                        ui.label('输入三个1–999的整数').classes('text-sm text-slate-300 mb-3')
                        with ui.element('div').classes('input-grid'):
                            self.number_inputs = [
                                ui.number(label=label, value=i + 1, min=1, max=999, step=1).classes('w-full').props('dark outlined')
                                for i, label in enumerate(('初数', '中数', '末数'))
                            ]
                    with ui.tab_panel('date'):
                        with ui.element('div').classes('date-grid'):
                            self.date_input = ui.input('公历日期', value=now.strftime('%Y-%m-%d')).classes('w-full').props('type=date dark outlined min=1900-01-01 max=2099-12-31')
                            self.time_input = ui.input('北京时间', value=now.strftime('%H:%M')).classes('w-full').props('type=time dark outlined')
                        ui.label('按北京时间 UTC+8，取农历月、日、时辰；闰月沿用同名月份，23点按当日农历日取数。').classes('text-sm text-slate-300 mt-3')
                    with ui.tab_panel('chinese'):
                        self.chinese_input = ui.input('三个汉字', placeholder='例如：天行健、中国人').classes('w-full').props('dark outlined')
                        ui.label('按内置字典笔画取数，支持逗号或空格分隔。').classes('text-sm text-slate-300 mt-3')
                self.input_tabs = tabs

            with ui.card().classes('w-full surface p-5 md:p-6'):
                ui.label('2 · 解读方式（可选）').classes('text-lg font-semibold')
                model_options = {'local': '仅本地计算（不使用AI）'}
                model_options.update({model.value: SupportedModels.get_display_name(model) for model in self.available_models})
                self.model_select = ui.select(model_options, label='解读方式', value=self.current_model.value if self.current_model else 'local', on_change=self._on_model_change).classes('w-full').props('dark outlined')
                self.question_input = ui.textarea('想了解的具体问题', placeholder='例如：准备换工作，接下来应先做好哪些准备？').classes('w-full').props('dark outlined autogrow rows=2')
                ui.label('选择AI且填写问题时才请求解读；问题留空或选择本地模式均只计算三传。').classes('text-sm text-slate-300')
                if not self.available_models:
                    ui.label('当前为本地模式，无需API密钥。').classes('text-sm text-cyan-200')

            self.error_message = ui.label('').classes('text-red-300 w-full break-words').props('role=alert')
            self.submit_button = ui.button('查看三传', icon='auto_awesome', on_click=self._perform_divination).classes('w-full py-3 text-lg').props('no-caps')
            self.status_message = ui.label('准备就绪：填写输入后查看三传。').classes('text-sm text-slate-300').props('role=status aria-live=polite')
            self.result_area = ui.column().classes('w-full gap-4')
            self.ai_result_area = ui.column().classes('w-full')
            ui.label('传统文化探索 · 解读用于梳理思路，现实决定仍需事实依据。').classes('text-xs text-slate-400')


def create_page():
    """Each page owns its controller and every callback's widget references."""
    web_app = DivinationWebApp()
    web_app.create_ui()
    return web_app


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    ui.page('/', dark=True)(create_page)
    ui.run(title='小六壬 · 三传', port=8080, host='0.0.0.0', reload=True, favicon='🔮', dark=True)


if __name__ in {'__main__', '__mp_main__'}:
    main()
