#!/usr/bin/env python3
"""
小六壬占卜 Web Interface
Mini Six Ren Divination Web Application using NiceGUI
"""

import os
import sys
import re
import asyncio
from datetime import datetime
from typing import Optional, List

# Add the src directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nicegui import ui, app
from nicegui.events import ValueChangeEventArguments

from hand_technique import HandTechnique
from ai_agent import DivinationAgent, SupportedModels
from utils.stroke_count import get_stroke_counts
from utils.calendar_converter import solar_to_lunar


class DivinationWebApp:
    def __init__(self):
        self.current_model = None
        self.available_models = []
        self.divination_result = None
        self.ai_interpretation = None
        
        # UI element references
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
        
        # Initialize available models
        self._check_available_models()
    
    def _check_available_models(self):
        """Check which AI models are available"""
        self.available_models = DivinationAgent.get_available_models()
        if self.available_models:
            self.current_model = self.available_models[0]
    
    def _validate_numbers(self, num1_str, num2_str, num3_str) -> tuple[bool, str, List[int]]:
        """Validate number inputs"""
        try:
            nums = [int(n) for n in [num1_str, num2_str, num3_str]]
            if all(1 <= n <= 999 for n in nums):
                return True, "", nums
            else:
                return False, "数字必须在1-999之间", []
        except ValueError:
            return False, "请输入有效数字", []
    
    def _validate_chinese(self, text: str) -> tuple[bool, str, List[int]]:
        """Validate Chinese character input"""
        if not text or len(text) < 3:
            return False, "请输入3个汉字", []
        
        # Check if all characters are Chinese
        chinese_chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        if len(chinese_chars) < 3:
            return False, "请输入3个汉字", []
        
        # Get stroke counts for first 3 characters
        first_three = chinese_chars[:3]
        try:
            stroke_counts = get_stroke_counts(first_three)
            if not stroke_counts:
                return False, "无法计算汉字笔画数", []
            return True, "", stroke_counts
        except Exception as e:
            return False, f"笔画计算错误: {str(e)}", []
    
    def _validate_date_time(self, date_str: str, time_str: str) -> tuple[bool, str, List[int]]:
        """Validate date and time input"""
        try:
            if not date_str or not time_str:
                return False, "请选择日期和时间", []
            
            # Parse date and time
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            time_obj = datetime.strptime(time_str, "%H:%M")
            
            # Calculate numbers based on date and time
            month = date_obj.month
            day = date_obj.day
            hour = time_obj.hour
            
            # Convert to 1-9 range
            num1 = (month - 1) % 9 + 1
            num2 = (day - 1) % 9 + 1
            num3 = (hour % 12) // 2 + 1  # Convert to traditional 12-hour periods
            
            return True, "", [num1, num2, num3]
        except ValueError:
            return False, "日期或时间格式错误", []
    
    async def _perform_divination(self):
        """Perform divination based on current input"""
        try:
            # Clear previous results
            self.result_area.clear()
            self.ai_result_area.clear()
            if self.error_message:
                self.error_message.set_text("")
            
            # Force UI update
            await asyncio.sleep(0)
            
            # Get current input values
            current_tab = self.input_tabs.value
            question = self.question_input.value.strip()
            
            if not question:
                self._show_error("请输入您要占卜的问题")
                return
            
            # Validate inputs based on current tab
            if current_tab == "numbers":
                valid, error_msg, numbers = self._validate_numbers(
                    self.number_inputs[0].value,
                    self.number_inputs[1].value,
                    self.number_inputs[2].value
                )
            elif current_tab == "date":
                valid, error_msg, numbers = self._validate_date_time(
                    self.date_input.value,
                    self.time_input.value
                )
            elif current_tab == "chinese":
                valid, error_msg, numbers = self._validate_chinese(
                    self.chinese_input.value
                )
            else:
                self._show_error("请选择输入方式")
                return
            
            if not valid:
                self._show_error(error_msg)
                return
            
            # Show loading with modern design
            self.result_area.clear()
            with self.result_area:
                with ui.card().classes('w-full bento-card rounded-2xl p-12 text-center'):
                    ui.spinner('dots', size='lg').props('color=purple')
                    ui.label('正在连接天地智慧...').classes('text-xl text-gray-300 mt-4')
            
            # Force UI update to show spinner
            await asyncio.sleep(0.1)
            
            # Perform divination
            if not self.current_model:
                self._show_error("请先配置AI模型")
                return
            
            # Get divination result
            table, ai_result = await HandTechnique.predict_async(
                numbers[0], numbers[1], numbers[2], 
                question, self.current_model
            )
            
            # Get the actual symbols for better display
            symbols = HandTechnique._HandTechnique__generate_prediction(numbers[0], numbers[1], numbers[2])
            relations = HandTechnique._HandTechnique__get_relations(symbols)
            
            # Display results
            self._display_results(symbols, relations, ai_result)
            
        except Exception as e:
            self._show_error(f"占卜计算错误: {str(e)}")
    
    def _display_results(self, symbols, relations, ai_result):
        """Display divination results"""
        self.result_area.clear()
        
        with self.result_area:
            # Modern results header
            with ui.card().classes('w-full gradient-purple rounded-3xl shadow-2xl mb-6'):
                with ui.card_section().classes('p-8 text-center'):
                    ui.label('占卜结果').classes('text-4xl font-bold text-white mb-2')
                    ui.label('DIVINATION RESULTS').classes('text-sm tracking-widest text-white opacity-80')
            
            # Three transmissions display with modern cards
            with ui.grid(columns=5).classes('w-full gap-4 mb-6'):
                # First transmission
                with ui.card().classes('col-span-1 bento-card rounded-2xl p-6'):
                    ui.label('初传').classes('text-sm text-gray-400 mb-2')
                    ui.label(symbols[0].name).classes('text-3xl font-bold gradient-text mb-2')
                    ui.label(f'{symbols[0].element.name}行').classes('text-sm text-gray-300')
                    ui.label(symbols[0].direction).classes('text-xs text-gray-400')
                        
                # First relation arrow
                with ui.column().classes('col-span-1 justify-center items-center'):
                    relation_class = 'gradient-cyan' if relations[0] == '生' else 'gradient-amber' if relations[0] == '克' else 'bg-gray-600'
                    with ui.element('div').classes(f'{relation_class} rounded-full p-3'):
                        ui.icon('arrow_forward', size='1.5rem').classes('text-white')
                    ui.label(relations[0]).classes('text-sm text-gray-400 mt-2')
                
                # Second transmission
                with ui.card().classes('col-span-1 bento-card rounded-2xl p-6'):
                    ui.label('中传').classes('text-sm text-gray-400 mb-2')
                    ui.label(symbols[1].name).classes('text-3xl font-bold gradient-text mb-2')
                    ui.label(f'{symbols[1].element.name}行').classes('text-sm text-gray-300')
                    ui.label(symbols[1].direction).classes('text-xs text-gray-400')
                
                # Second relation arrow
                with ui.column().classes('col-span-1 justify-center items-center'):
                    relation_class = 'gradient-cyan' if relations[1] == '生' else 'gradient-amber' if relations[1] == '克' else 'bg-gray-600'
                    with ui.element('div').classes(f'{relation_class} rounded-full p-3'):
                        ui.icon('arrow_forward', size='1.5rem').classes('text-white')
                    ui.label(relations[1]).classes('text-sm text-gray-400 mt-2')
                
                # Third transmission
                with ui.card().classes('col-span-1 bento-card rounded-2xl p-6'):
                    ui.label('末传').classes('text-sm text-gray-400 mb-2')
                    ui.label(symbols[2].name).classes('text-3xl font-bold gradient-text mb-2')
                    ui.label(f'{symbols[2].element.name}行').classes('text-sm text-gray-300')
                    ui.label(symbols[2].direction).classes('text-xs text-gray-400')
                    
            # Detailed symbol information in Bento Grid
            with ui.grid(columns='1 1 1').classes('w-full gap-4 mb-6'):
                for i, symbol in enumerate(symbols):
                    position = ["初传", "中传", "末传"][i]
                    gradient = ['gradient-purple', 'gradient-cyan', 'gradient-amber'][i]
                    
                    with ui.card().classes(f'col-span-1 bento-card rounded-2xl overflow-hidden'):
                        # Gradient header
                        with ui.element('div').classes(f'{gradient} p-4'):
                            ui.label(f'{position} · {symbol.name}').classes('text-xl font-bold text-white')
                        
                        # Content
                        with ui.card_section().classes('p-6'):
                            ui.label(symbol.description).classes('text-gray-300 mb-4')
                            
                            with ui.column().classes('gap-3'):
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon('temple_buddhist', size='1.2rem').classes('text-purple-400')
                                    ui.label(f'神灵: {symbol.deity}').classes('text-sm text-gray-300')
                                
                                ui.label(symbol.deity_description).classes('text-xs text-gray-400 ml-7')
                                
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon('explore', size='1.2rem').classes('text-cyan-400')
                                    ui.label(f'方位: {symbol.direction}').classes('text-sm text-gray-300')
        
        # Display AI interpretation with streaming
        self._display_ai_result(ai_result)
    
    def _display_ai_result(self, ai_result):
        """Display AI interpretation with modern design"""
        if not ai_result:
            return
            
        self.ai_result_area.clear()
        with self.ai_result_area:
            # AI interpretation with gradient accent
            with ui.card().classes('w-full bento-card rounded-2xl overflow-hidden'):
                # Gradient header
                with ui.element('div').classes('gradient-cyan p-6'):
                    with ui.row().classes('items-center gap-3'):
                        ui.icon('psychology', size='2rem').classes('text-white')
                        ui.label('AI 智慧解读').classes('text-2xl font-bold text-white')
                
                # Content with enhanced styling
                with ui.card_section().classes('p-8'):
                    cleaned_result = self._clean_ai_result(ai_result)
                    ui.markdown(cleaned_result).classes('ai-interpretation prose prose-invert max-w-none')
    
    def _clean_ai_result(self, text: str) -> str:
        """Clean and format AI result text for web display"""
        if not text:
            return ""
        
        # The text is already formatted by ai_agent._format_markdown_for_web
        # Just ensure proper spacing and structure
        text = re.sub(r'\n{3,}', '\n\n', text)  # Normalize paragraph spacing
        
        # Add some visual breaks for better readability
        text = re.sub(r'(\d+\. )', r'\n\1', text)  # Add space before numbered items
        
        return text.strip()
    
    def _show_error(self, message: str):
        """Show error message"""
        if self.error_message:
            self.error_message.set_text(message)
            self.error_message.classes('text-red-500 font-bold')
    
    def _on_model_change(self, e: ValueChangeEventArguments):
        """Handle model selection change"""
        for model in self.available_models:
            if SupportedModels.get_display_name(model) == e.value:
                self.current_model = model
                break
    
    def create_ui(self):
        """Create the main UI"""
        # Set up modern gradient color scheme
        ui.colors(primary='#7c3aed', secondary='#06b6d4', accent='#f59e0b', 
                 dark='#1e1b4b', positive='#10b981', negative='#ef4444', 
                 info='#3b82f6', warning='#f59e0b')
        
        # Add custom CSS for gradients and modern styling
        ui.add_css("""
        /* Full page dark background */
        body {
            background-color: #111827 !important;
            color: white !important;
            margin: 0;
            padding: 0;
        }
        .q-page {
            background-color: #111827 !important;
        }
        .gradient-purple {
            background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%);
        }
        .gradient-cyan {
            background: linear-gradient(135deg, #06b6d4 0%, #67e8f9 100%);
        }
        .gradient-amber {
            background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
        }
        .gradient-text {
            background: linear-gradient(135deg, #7c3aed 0%, #06b6d4 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .bento-card {
            backdrop-filter: blur(10px);
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
        }
        .bento-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        }
        .huge-text {
            font-size: 4rem;
            font-weight: 800;
            line-height: 1;
        }
        .medium-text {
            font-size: 2rem;
            font-weight: 600;
        }
        /* Fix input text colors */
        .q-field__native {
            color: white !important;
        }
        .q-field__control {
            color: white !important;
        }
        
        /* Enhanced AI interpretation text styling */
        .ai-interpretation {
            line-height: 1.8 !important;
            font-size: 16px !important;
        }
        
        .ai-interpretation h3 {
            color: #67e8f9 !important;
            font-size: 1.2rem !important;
            font-weight: 600 !important;
            margin: 1.5rem 0 0.8rem 0 !important;
            border-left: 3px solid #06b6d4;
            padding-left: 12px;
        }
        
        .ai-interpretation p {
            margin-bottom: 1.2rem !important;
            text-indent: 2em;
            color: #e5e7eb !important;
        }
        
        .ai-interpretation ul, .ai-interpretation ol {
            margin: 1rem 0 !important;
            padding-left: 1.5rem !important;
        }
        
        .ai-interpretation li {
            margin-bottom: 0.6rem !important;
            color: #e5e7eb !important;
        }
        
        .ai-interpretation strong {
            color: #fbbf24 !important;
            font-weight: 600 !important;
        }
        
        .ai-interpretation blockquote {
            border-left: 3px solid #7c3aed;
            padding-left: 1rem;
            margin: 1rem 0;
            font-style: italic;
            color: #c4b5fd !important;
        }
        """)
        
        # Main container
        with ui.column().classes('w-full min-h-screen bg-gray-900'):
            with ui.column().classes('w-full max-w-6xl mx-auto p-6'):
                # Hero Header with gradient
                with ui.card().classes('w-full gradient-purple text-white rounded-3xl shadow-2xl mb-8'):
                    with ui.card_section().classes('p-12 text-center'):
                        ui.label('小六壬').classes('huge-text mb-2')
                        ui.label('MINI SIX REN DIVINATION').classes('text-sm tracking-widest opacity-80 mb-4')
                        ui.label('古老智慧 · 现代演绎').classes('text-xl font-light')
            
                # Compact usage guide with stats
                with ui.card().classes('w-full bento-card rounded-2xl p-6 mb-6'):
                    with ui.row().classes('w-full items-center gap-8'):
                        # Instructions on the left
                        with ui.column().classes('flex-1'):
                            with ui.row().classes('items-center gap-3 mb-3'):
                                ui.icon('auto_stories', size='2rem').classes('text-purple-300')
                                ui.label('使用指南').classes('text-xl font-semibold text-white')
                            
                            with ui.row().classes('gap-6'):
                                with ui.row().classes('items-center gap-2'):
                                    ui.label('1').classes('text-xl font-bold text-purple-300')
                                    ui.label('选择AI模型').classes('text-sm text-gray-300')
                                
                                with ui.row().classes('items-center gap-2'):
                                    ui.label('2').classes('text-xl font-bold text-cyan-300')
                                    ui.label('输入占卜数据').classes('text-sm text-gray-300')
                                
                                with ui.row().classes('items-center gap-2'):
                                    ui.label('3').classes('text-xl font-bold text-amber-300')
                                    ui.label('描述您的问题').classes('text-sm text-gray-300')
                    
                        # Stats on the right
                        with ui.row().classes('gap-4'):
                            with ui.card().classes('bento-card rounded-xl p-4 gradient-cyan'):
                                ui.label('9').classes('text-3xl font-bold text-white')
                                ui.label('宫位').classes('text-xs text-white opacity-80')
                            
                            with ui.card().classes('bento-card rounded-xl p-4 gradient-amber'):
                                ui.label('3').classes('text-3xl font-bold text-white')
                                ui.label('三传').classes('text-xs text-white opacity-80')
                            
                            with ui.card().classes('bento-card rounded-xl p-4 gradient-purple'):
                                ui.label('∞').classes('text-3xl font-bold text-white')
                                ui.label('智慧').classes('text-xs text-white opacity-80')
            
                # Model selection in a beautiful card
                with ui.card().classes('w-full bento-card rounded-2xl p-6 mb-6'):
                    ui.label('AI模型选择').classes('text-xl font-semibold text-white mb-4')
                    if self.available_models:
                        model_options = [SupportedModels.get_display_name(model) 
                                       for model in self.available_models]
                        self.model_select = ui.select(
                            model_options, 
                            label='',
                            value=model_options[0] if model_options else None,
                            on_change=self._on_model_change
                        ).classes('w-full').props('dark filled')
                    else:
                        with ui.card().classes('w-full bg-red-500/20 border-red-500/50 rounded-xl p-4'):
                            ui.label('⚠️ 未找到可用的AI模型，请检查API密钥配置').classes('text-red-300')
                        return
            
                # Input section with modern tabs
                with ui.card().classes('w-full bento-card rounded-2xl p-6 mb-6'):
                    ui.label('占卜输入').classes('text-xl font-semibold text-white mb-4')
                    
                    with ui.tabs().classes('w-full') as tabs:
                        numbers_tab = ui.tab('numbers', label='数字模式', icon='pin')
                        date_tab = ui.tab('date', label='时间模式', icon='calendar_today') 
                        chinese_tab = ui.tab('chinese', label='汉字模式', icon='translate')
                    
                    with ui.tab_panels(tabs, value='numbers').classes('w-full mt-4'):
                        # Numbers input panel
                        with ui.tab_panel('numbers'):
                            ui.label('请输入三个数字（1-999）').classes('text-gray-300 mb-4')
                            with ui.row().classes('w-full gap-4'):
                                self.number_inputs = []
                                for i, label in enumerate(['初数', '中数', '末数']):
                                    with ui.column().classes('flex-1'):
                                        ui.label(label).classes('text-sm text-gray-400 mb-1')
                                        num_input = ui.number(
                                            label='', 
                                            value=i+1, 
                                            min=1, 
                                            max=999
                                        ).classes('w-full text-white').props('dark filled outlined input-class="text-white"')
                                        self.number_inputs.append(num_input)
                
                        # Date input panel
                        with ui.tab_panel('date'):
                            ui.label('请选择日期和时间').classes('text-gray-300 mb-4')
                            with ui.row().classes('w-full gap-4'):
                                with ui.column().classes('flex-1'):
                                    ui.label('日期').classes('text-sm text-gray-400 mb-1')
                                    self.date_input = ui.date(
                                        value=datetime.now().strftime('%Y-%m-%d')
                                    ).classes('w-full').props('dark filled')
                                with ui.column().classes('flex-1'):
                                    ui.label('时间').classes('text-sm text-gray-400 mb-1')
                                    self.time_input = ui.time(
                                        value=datetime.now().strftime('%H:%M')
                                    ).classes('w-full').props('dark filled')
                
                        # Chinese characters input panel
                        with ui.tab_panel('chinese'):
                            ui.label('请输入3个汉字（将计算笔画数）').classes('text-gray-300 mb-4')
                            self.chinese_input = ui.input(
                                label='',
                                placeholder='例如：川建国、关税战、天行健'
                            ).classes('w-full').props('dark filled outlined')
            
                    self.input_tabs = tabs
                
                # Question input with gradient accent
                with ui.card().classes('w-full bento-card rounded-2xl p-6 mb-6'):
                    with ui.row().classes('items-center gap-3 mb-4'):
                        ui.icon('psychology', size='2rem').classes('text-purple-400')
                        ui.label('您的问题').classes('text-xl font-semibold text-white')
                    
                    self.question_input = ui.textarea(
                        label='',
                        placeholder='请详细描述您要占卜的问题...\n例如：今日运势如何？工作项目能否顺利？感情发展趋势？',
                        validation={'请输入问题': lambda value: len(value.strip()) > 0}
                    ).classes('w-full').props('dark filled autogrow rows=3')
            
                # Error message area
                self.error_message = ui.label('').classes('text-red-400 text-center font-semibold mb-4')
                
                # Divination button with gradient
                def on_divination_click():
                    asyncio.create_task(self._perform_divination())
                
                with ui.element('button').classes(
                    'w-full gradient-purple text-white font-bold py-4 px-8 rounded-2xl '
                    'text-lg shadow-lg hover:shadow-xl transform hover:-translate-y-1 '
                    'transition-all duration-200'
                ).on('click', on_divination_click):
                    with ui.row().classes('justify-center items-center gap-3'):
                        ui.icon('auto_fix_high', size='1.5rem')
                        ui.label('开始占卜')
            
                # Results area
                self.result_area = ui.column().classes('w-full mt-8')
                self.ai_result_area = ui.column().classes('w-full')


def main():
    """Main function to run the web application"""
    # Set working directory to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # Create the application
    web_app = DivinationWebApp()
    
    # Set up the main page with dark theme
    @ui.page('/', dark=True)
    def index():
        web_app.create_ui()
    
    # Configure and run the application
    ui.run(
        title='小六壬占卜 Web版',
        port=8080,
        host='0.0.0.0',
        reload=True,
        favicon='🔮',
        dark=True
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()