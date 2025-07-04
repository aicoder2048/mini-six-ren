import os
from dataclasses import dataclass
from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
import re
import asyncio
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live


@dataclass
class DivinationDeps:
    """占卜AI依赖数据类"""
    openai_api_key: str


class DivinationAgent:
    """小六壬占卜AI解读代理"""
    
    def __init__(self):
        load_dotenv()
        self.agent = Agent(
            'openai:gpt-4o',
            deps_type=DivinationDeps,
            system_prompt=self._get_system_prompt()
        )
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return (
            "You are an expert in Chinese divination, specifically in interpreting "
            "小六壬 (Xiao Liu Ren) results. Provide a concise interpretation in Chinese. "
            "Your response should be professional, culturally appropriate, and limited to 1000 characters."
        )
    
    def interpret_prediction(self, symbols, question: str) -> str:
        """
        使用PydanticAI解读小六壬占卜结果
        
        Args:
            symbols: 三传符号列表
            question: 用户问题
            
        Returns:
            str: AI解读结果
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "错误：未设置OPENAI_API_KEY环境变量"
        
        deps = DivinationDeps(openai_api_key=api_key)
        prompt = self._generate_interpretation_prompt(symbols, question)
        
        try:
            # 使用同步方式运行异步流式响应
            return asyncio.run(self._stream_interpretation(prompt, deps))
            
        except Exception as e:
            return f"AI解读出错：{str(e)}"
    
    async def _stream_interpretation(self, prompt: str, deps: DivinationDeps) -> str:
        """异步流式处理AI解读"""
        console = Console()
        full_response = ""
        
        # 显示开始提示
        console.print("\n[bold cyan]正在生成AI解读...[/bold cyan]")
        
        try:
            async with self.agent.run_stream(
                prompt, 
                deps=deps,
                model_settings={'max_tokens': 1000}
            ) as result:
                console.print("[bold cyan]AI解读结果：[/bold cyan]")
                
                # 使用简单的打印方式避免Live冲突
                async for message in result.stream_text():
                    full_response = message
                    # 清屏并显示当前内容
                    console.clear()
                    console.print("[bold cyan]AI解读结果：[/bold cyan]")
                    console.print(self._clean_markdown(full_response))
                
                console.print("\n[bold green]解读完成！[/bold green]")
                
        except Exception as e:
            console.print(f"\n[bold red]解读失败：{str(e)}[/bold red]")
            raise
        
        return self._clean_markdown(full_response)
    
    def _clean_markdown(self, text: str) -> str:
        """清理Markdown格式"""
        # 移除Markdown格式
        text = re.sub(r'#+ ', '', text)  # 移除标题
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 移除粗体
        text = re.sub(r'\*(.*?)\*', r'\1', text)  # 移除斜体
        text = re.sub(r'- ', '', text)  # 移除列表符号
        return text
    
    def _generate_interpretation_prompt(self, symbols, question: str) -> str:
        """生成解读提示词"""
        prompt = f"尊敬的小六壬大师，请为以下问题进行占卜解读：'{question}'\n\n"
        prompt += "三传结果如下：\n\n"

        for i, symbol in enumerate(symbols):
            position = ["初传（前期）", "中传（中期）", "末传（后期）"][i]
            prompt += f"{position}:\n"
            prompt += f"符号: {symbol.name}\n"
            prompt += f"描述: {symbol.description}\n"
            prompt += f"解释: {symbol.interpretation}\n"
            prompt += f"五行: {symbol.element.name}\n"
            prompt += f"方位: {symbol.direction}\n"
            prompt += f"神灵: {symbol.deity} - {symbol.deity_description}\n\n"

        # 添加明确的五行属性和生克关系
        prompt += "三传五行属性及关系：\n"
        prompt += f"初传五行：{symbols[0].element.name}\n"
        prompt += f"中传五行：{symbols[1].element.name}\n"
        prompt += f"末传五行：{symbols[2].element.name}\n"

        relations = self._get_relations(symbols)
        prompt += f"初传{'【生】' if relations[0] == '生' else '【克】' if relations[0] == '克' else '和'}中传{'五行没有生或克的关系' if relations[0] == '无' else ''}\n"
        prompt += f"中传{'【生】' if relations[1] == '生' else '【克】' if relations[1] == '克' else '和'}末传{'五行没有生或克的关系' if relations[1] == '无' else ''}\n\n"

        prompt += "请您运用您渊博的小六壬知识，对这三个符号进行全面而深入的解读：\n"
        prompt += "1. 请分析三传之间的关系，解释它们如何相互影响和演变。\n"
        prompt += "2. 结合问题的具体内容，阐述这些符号对求问者当前处境的启示。\n"
        if relations[0] != '无' or relations[1] != '无':
            prompt += "3. 请结合求问的事情和三传的符号，详细解释以下五行生克关系如何影响事态的发展：\n"
            if relations[0] != '无':
                prompt += f"   - 初传{relations[0]}中传的影响\n"
            if relations[1] != '无':
                prompt += f"   - 中传{relations[1]}末传的影响\n"
        else:
            prompt += "3. 三传之间没有五行的生克关系，请仅分析符号本身的含义及其对求问事项的影响，不要讨论或臆测任何五行相关的影响。\n"
        prompt += "4. 基于您的解读，请提供具体的建议或化解之策，指导求问者如何趋吉避凶。\n"
        prompt += "5. 如果有任何需要特别注意的方位、时间或相关神灵，请一并点明。\n\n"
        prompt += "请以中国传统文化的智慧精髓来回答，语言要优雅含蓄，富有哲理，同时也要让现代人容易理解。字数控制在1000字以内。"

        return prompt
    
    def _is_generating(self, element1, element2):
        """判断五行相生关系"""
        return element1.generates == element2.name

    def _is_overcoming(self, element1, element2):
        """判断五行相克关系"""
        return element1.overcomes == element2.name
    
    def _get_relations(self, symbols):
        """获取三传之间的五行关系"""
        relations = []
        for i in range(2):
            if self._is_generating(symbols[i].element, symbols[i+1].element):
                relation = "生"
            elif self._is_overcoming(symbols[i].element, symbols[i+1].element):
                relation = "克"
            else:
                relation = "无"
            relations.append(relation)
        return relations