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
            if all(1 <= n <= 9 for n in nums):
                return True, "", nums
            else:
                return False, "数字必须在1-9之间", []
        except ValueError:
            return False, "请输入有效数字", []
    
    def _validate_chinese(self, text: str) -> tuple[bool, str, List[int]]:
        """Validate Chinese character input"""
        if not text or len(text) < 3:
            return False, "请输入至少3个汉字", []
        
        # Check if all characters are Chinese
        chinese_chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        if len(chinese_chars) < 3:
            return False, "请输入至少3个汉字", []
        
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
            
            # Show loading
            self.result_area.clear()
            with self.result_area:
                spinner = ui.spinner('dots', size='lg', color='primary')
                loading_label = ui.label('正在计算占卜结果...')
            
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
            # Display divination table
            ui.separator().classes('my-4')
            ui.label('占卜结果').classes('text-h5 text-center text-primary')
            ui.separator().classes('my-4')
            
            with ui.card().classes('w-full shadow-lg'):
                with ui.card_section():
                    ui.label('小六壬三传占卜').classes('text-h6 text-center mb-4')
                    
                    # Create divination results grid
                    with ui.grid(columns=5).classes('w-full gap-4'):
                        # Headers
                        ui.label('初传（前期）').classes('text-center font-bold text-primary col-span-1')
                        ui.label('关系').classes('text-center font-bold text-secondary col-span-1')
                        ui.label('中传（中期）').classes('text-center font-bold text-primary col-span-1')
                        ui.label('关系').classes('text-center font-bold text-secondary col-span-1')
                        ui.label('末传（后期）').classes('text-center font-bold text-primary col-span-1')
                        
                        # Display actual symbols
                        with ui.card().classes('p-4 text-center bg-blue-50'):
                            ui.label(f'【{symbols[0].name}】').classes('text-lg font-bold text-blue-700')
                            ui.label(f'({symbols[0].element.name})').classes('text-sm text-gray-600')
                            ui.label(f'{symbols[0].direction}').classes('text-xs text-gray-500')
                        
                        # First relation
                        relation_color = 'text-green-500' if relations[0] == '生' else 'text-red-500' if relations[0] == '克' else 'text-gray-500'
                        ui.label(f'{relations[0]}→').classes(f'text-center text-2xl {relation_color}')
                        
                        with ui.card().classes('p-4 text-center bg-green-50'):
                            ui.label(f'【{symbols[1].name}】').classes('text-lg font-bold text-green-700')
                            ui.label(f'({symbols[1].element.name})').classes('text-sm text-gray-600')
                            ui.label(f'{symbols[1].direction}').classes('text-xs text-gray-500')
                        
                        # Second relation
                        relation_color = 'text-green-500' if relations[1] == '生' else 'text-red-500' if relations[1] == '克' else 'text-gray-500'
                        ui.label(f'{relations[1]}→').classes(f'text-center text-2xl {relation_color}')
                        
                        with ui.card().classes('p-4 text-center bg-purple-50'):
                            ui.label(f'【{symbols[2].name}】').classes('text-lg font-bold text-purple-700')
                            ui.label(f'({symbols[2].element.name})').classes('text-sm text-gray-600')
                            ui.label(f'{symbols[2].direction}').classes('text-xs text-gray-500')
                    
                    # Additional symbol information
                    ui.separator().classes('my-4')
                    ui.label('符号详解').classes('text-subtitle1 font-bold mb-2')
                    
                    with ui.row().classes('w-full gap-4'):
                        for i, symbol in enumerate(symbols):
                            position = ["初传", "中传", "末传"][i]
                            with ui.card().classes('flex-1'):
                                with ui.card_section():
                                    ui.label(f'{position} - {symbol.name}').classes('font-bold text-center')
                                    ui.label(symbol.description).classes('text-sm text-center')
                                    ui.separator().classes('my-2')
                                    ui.label(f'神灵：{symbol.deity}').classes('text-xs')
                                    ui.label(symbol.deity_description).classes('text-xs text-gray-600')
        
        # Display AI interpretation with streaming
        self._display_ai_result(ai_result)
    
    def _display_ai_result(self, ai_result):
        """Display AI interpretation with streaming effect"""
        if not ai_result:
            return
            
        self.ai_result_area.clear()
        with self.ai_result_area:
            ui.separator().classes('my-4')
            ui.label('AI解读').classes('text-h5 text-center text-secondary')
            ui.separator().classes('my-4')
            
            with ui.card().classes('w-full shadow-lg'):
                with ui.card_section():
                    # Display AI result with proper formatting
                    # Clean up the text and display it nicely
                    cleaned_result = self._clean_ai_result(ai_result)
                    ui.markdown(cleaned_result).classes('prose max-w-none')
    
    def _clean_ai_result(self, text: str) -> str:
        """Clean and format AI result text"""
        if not text:
            return ""
        
        # Remove excessive markdown formatting that might not render well
        # Keep basic formatting but clean up
        text = re.sub(r'\*\*\*+', '**', text)  # Reduce multiple asterisks
        text = re.sub(r'#{4,}', '###', text)   # Limit header levels
        
        return text
    
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
        # Set up page styling
        ui.colors(primary='#1976d2', secondary='#26a69a', accent='#9c27b0', 
                 dark='#1d1d1d', positive='#21ba45', negative='#c10015', 
                 info='#31ccec', warning='#f2c037')
        
        # Main container
        with ui.column().classes('w-full max-w-4xl mx-auto p-4'):
            # Header
            with ui.row().classes('w-full justify-center mb-6'):
                ui.label('小六壬占卜 Web版').classes('text-h3 text-center text-primary')
                ui.label('Mini Six Ren Divination').classes('text-h6 text-center text-gray-600')
            
            # Usage instructions
            with ui.expansion('使用说明', icon='help').classes('w-full mb-4'):
                ui.markdown("""
                ### 使用方法
                
                1. **选择AI模型**：从下拉菜单中选择可用的AI模型
                2. **选择输入方式**：
                   - **数字输入**：直接输入3个数字（1-9）
                   - **日期输入**：选择日期和时间，系统自动转换为数字
                   - **汉字输入**：输入汉字，系统计算笔画数
                3. **填写问题**：描述您要占卜的具体问题
                4. **开始占卜**：点击按钮查看结果和AI解读
                
                ### 关于小六壬
                小六壬是中国传统占卜方法，通过三传（初传、中传、末传）来预测事物的发展趋势。
                """).classes('prose max-w-none')
            
            # Model selection
            if self.available_models:
                model_options = [SupportedModels.get_display_name(model) 
                               for model in self.available_models]
                self.model_select = ui.select(
                    model_options, 
                    label='选择AI模型',
                    value=model_options[0] if model_options else None,
                    on_change=self._on_model_change
                ).classes('w-full mb-4')
            else:
                ui.banner('未找到可用的AI模型，请检查API密钥配置', type='warning')
                return
            
            # Input tabs
            with ui.tabs().classes('w-full') as tabs:
                numbers_tab = ui.tab('numbers', label='数字输入')
                date_tab = ui.tab('date', label='日期输入') 
                chinese_tab = ui.tab('chinese', label='汉字输入')
            
            with ui.tab_panels(tabs, value='numbers').classes('w-full'):
                # Numbers input panel
                with ui.tab_panel('numbers'):
                    ui.label('请输入三个数字（1-9）').classes('text-subtitle1 mb-2')
                    with ui.row().classes('w-full'):
                        self.number_inputs = [
                            ui.number(label='第一个数字', value=1, min=1, max=9).classes('flex-1'),
                            ui.number(label='第二个数字', value=2, min=1, max=9).classes('flex-1'),
                            ui.number(label='第三个数字', value=3, min=1, max=9).classes('flex-1')
                        ]
                
                # Date input panel
                with ui.tab_panel('date'):
                    ui.label('请选择日期和时间').classes('text-subtitle1 mb-2')
                    with ui.row().classes('w-full'):
                        self.date_input = ui.date(value=datetime.now().strftime('%Y-%m-%d')).classes('flex-1')
                        self.time_input = ui.time(value=datetime.now().strftime('%H:%M')).classes('flex-1')
                
                # Chinese characters input panel
                with ui.tab_panel('chinese'):
                    ui.label('请输入至少3个汉字（将计算笔画数）').classes('text-subtitle1 mb-2')
                    self.chinese_input = ui.input(
                        label='输入汉字',
                        placeholder='例如：测试运势'
                    ).classes('w-full')
            
            self.input_tabs = tabs
            
            # Question input
            ui.separator().classes('my-4')
            ui.label('请描述您要占卜的问题').classes('text-subtitle1 mb-2')
            self.question_input = ui.textarea(
                label='占卜问题',
                placeholder='例如：今日运势如何？工作是否顺利？'
            ).classes('w-full')
            
            # Error message area
            self.error_message = ui.label('').classes('text-red-500 text-center font-bold')
            
            # Divination button
            def on_divination_click():
                asyncio.create_task(self._perform_divination())
            
            ui.button(
                '开始占卜',
                on_click=on_divination_click,
                color='primary'
            ).classes('w-full mt-4 p-3 text-h6')
            
            # Results area
            ui.separator().classes('my-6')
            self.result_area = ui.column().classes('w-full')
            self.ai_result_area = ui.column().classes('w-full')


def main():
    """Main function to run the web application"""
    # Set working directory to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # Create the application
    web_app = DivinationWebApp()
    
    # Set up the main page
    @ui.page('/')
    def index():
        web_app.create_ui()
    
    # Configure and run the application
    ui.run(
        title='小六壬占卜 Web版',
        port=8080,
        host='0.0.0.0',
        reload=True,
        favicon='🔮'
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()