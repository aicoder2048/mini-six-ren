import os
from dataclasses import dataclass
from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
import re
import asyncio
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from enum import Enum
from typing import Optional


class SupportedModels(Enum):
    """支持的LLM模型枚举"""
    OPENAI_GPT4O = "openai:gpt-4o"
    DEEPSEEK_CHAT = "deepseek:deepseek-chat"
    
    @classmethod
    def get_display_name(cls, model):
        """获取模型的显示名称"""
        names = {
            cls.OPENAI_GPT4O: "OpenAI GPT-4o",
            cls.DEEPSEEK_CHAT: "DeepSeek Chat"
        }
        return names.get(model, model.value)
    
    @classmethod
    def get_api_key_name(cls, model):
        """获取模型对应的API密钥环境变量名"""
        keys = {
            cls.OPENAI_GPT4O: "OPENAI_API_KEY",
            cls.DEEPSEEK_CHAT: "DEEPSEEK_API_KEY"
        }
        return keys.get(model, "")


@dataclass
class DivinationDeps:
    """占卜AI依赖数据类"""
    api_key: str
    model_type: SupportedModels


class DivinationAgent:
    """小六壬占卜AI解读代理"""
    
    def __init__(self, model_type: SupportedModels = SupportedModels.OPENAI_GPT4O):
        load_dotenv()
        self.model_type = model_type
        self.agent = Agent(
            model_type.value,
            deps_type=DivinationDeps,
            system_prompt=self._get_system_prompt()
        )
    
    @classmethod
    def get_available_models(cls) -> list[SupportedModels]:
        """获取当前环境中可用的模型列表"""
        load_dotenv()
        available = []
        
        for model in SupportedModels:
            api_key_name = SupportedModels.get_api_key_name(model)
            if os.getenv(api_key_name):
                available.append(model)
        
        return available
    
    @classmethod
    def is_model_available(cls, model: SupportedModels) -> bool:
        """检查指定模型是否可用（API密钥是否设置）"""
        load_dotenv()
        api_key_name = SupportedModels.get_api_key_name(model)
        return bool(os.getenv(api_key_name))
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return (
            "你是一位精通小六壬占卜的大师，具有深厚的传统文化功底。你的职责是：\n"
            "1. 仔细理解求问者的具体问题和关切\n"
            "2. 深入分析三传符号的含义和五行关系\n"
            "3. 将占卜结果与求问事项紧密结合，提供针对性解读\n"
            "4. 避免泛泛而谈，要针对具体问题给出具体指导\n"
            "5. 语言要优雅含蓄，富有哲理，但让现代人容易理解\n\n"
            "格式要求：\n"
            "- 使用清晰的段落结构，每段专注一个要点\n"
            "- 用 ### 标题区分不同主题（如：卦象分析、时间发展、建议指导等）\n"
            "- 重要内容使用 **粗体** 强调\n"
            "- 具体建议可用列表形式呈现\n"
            "请始终围绕求问者的具体问题进行解读，字数控制在1000字以内。"
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
        api_key_name = SupportedModels.get_api_key_name(self.model_type)
        api_key = os.getenv(api_key_name)
        
        if not api_key:
            model_name = SupportedModels.get_display_name(self.model_type)
            return f"错误：未设置{api_key_name}环境变量，无法使用{model_name}"
        
        deps = DivinationDeps(api_key=api_key, model_type=self.model_type)
        prompt = self._generate_interpretation_prompt(symbols, question)
        
        try:
            # 使用同步方式运行异步流式响应
            return asyncio.run(self._stream_interpretation(prompt, deps))
            
        except Exception as e:
            model_name = SupportedModels.get_display_name(self.model_type)
            return f"{model_name}解读出错：{str(e)}"
    
    async def interpret_prediction_async(self, symbols, question: str) -> str:
        """
        异步版本的AI解读方法，用于Web界面
        
        Args:
            symbols: 三传符号列表
            question: 用户问题
            
        Returns:
            str: AI解读结果
        """
        api_key_name = SupportedModels.get_api_key_name(self.model_type)
        api_key = os.getenv(api_key_name)
        
        if not api_key:
            model_name = SupportedModels.get_display_name(self.model_type)
            return f"错误：未设置{api_key_name}环境变量，无法使用{model_name}"
        
        deps = DivinationDeps(api_key=api_key, model_type=self.model_type)
        prompt = self._generate_interpretation_prompt(symbols, question)
        
        try:
            # 直接调用异步流式响应方法
            return await self._stream_interpretation_web(prompt, deps)
            
        except Exception as e:
            model_name = SupportedModels.get_display_name(self.model_type)
            return f"{model_name}解读出错：{str(e)}"
    
    async def _stream_interpretation(self, prompt: str, deps: DivinationDeps) -> str:
        """异步流式处理AI解读"""
        console = Console()
        full_response = ""
        
        # 显示开始提示
        model_name = SupportedModels.get_display_name(self.model_type)
        console.print(f"\n[bold cyan]正在使用{model_name}生成AI解读...[/bold cyan]")
        
        try:
            async with self.agent.run_stream(
                prompt, 
                deps=deps,
                model_settings={'max_tokens': 1000}
            ) as result:
                console.print(f"[bold cyan]{model_name}解读结果：[/bold cyan]")
                
                # 使用简单的打印方式避免Live冲突
                async for message in result.stream_text():
                    full_response = message
                    # 清屏并显示当前内容
                    console.clear()
                    console.print(f"[bold cyan]{model_name}解读结果：[/bold cyan]")
                    console.print(self._clean_markdown(full_response))
                
                console.print("\n[bold green]解读完成！[/bold green]")
                
        except Exception as e:
            console.print(f"\n[bold red]{model_name}解读失败：{str(e)}[/bold red]")
            raise
        
        return self._format_markdown_for_web(full_response)
    
    async def _stream_interpretation_web(self, prompt: str, deps: DivinationDeps) -> str:
        """异步流式处理AI解读 - Web版本（无控制台输出）"""
        full_response = ""
        
        try:
            async with self.agent.run_stream(
                prompt, 
                deps=deps,
                model_settings={'max_tokens': 1000}
            ) as result:
                async for message in result.stream_text():
                    full_response = message
                
        except Exception:
            raise
        
        return self._format_markdown_for_web(full_response)
    
    def _clean_markdown(self, text: str) -> str:
        """清理Markdown格式 - CLI版本"""
        # 移除Markdown格式用于CLI显示
        text = re.sub(r'#+ ', '', text)  # 移除标题
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 移除粗体
        text = re.sub(r'\*(.*?)\*', r'\1', text)  # 移除斜体
        text = re.sub(r'- ', '', text)  # 移除列表符号
        return text
    
    def _format_markdown_for_web(self, text: str) -> str:
        """为Web界面格式化Markdown - 保留结构"""
        if not text:
            return ""
        
        # 清理过度的markdown格式但保留结构
        text = re.sub(r'#{4,}', '###', text)  # 限制标题级别最多到h3
        text = re.sub(r'\*\*\*+', '**', text)  # 减少多重星号
        
        # 确保段落分隔
        text = re.sub(r'\n{3,}', '\n\n', text)  # 标准化段落间距
        
        # 优化列表格式
        text = re.sub(r'^(\d+\.)\s*', r'\1 ', text, flags=re.MULTILINE)  # 标准化有序列表
        text = re.sub(r'^[-*]\s*', r'- ', text, flags=re.MULTILINE)  # 标准化无序列表
        
        # 确保每个主要部分前有适当间距
        text = re.sub(r'(###[^\n]+)', r'\n\1', text)
        
        return text.strip()
    
    def _generate_interpretation_prompt(self, symbols, question: str) -> str:
        """生成解读提示词"""
        prompt = f"【重要】求问事项：{question}\n"
        prompt += "请您务必围绕此具体问题进行解读，避免泛泛而谈。\n\n"
        
        prompt += "=== 三传占卜结果 ===\n"

        for i, symbol in enumerate(symbols):
            position = ["初传（前期）", "中传（中期）", "末传（后期）"][i]
            prompt += f"\n{position}：\n"
            prompt += f"• 符号：{symbol.name}\n"
            prompt += f"• 描述：{symbol.description}\n"
            prompt += f"• 解释：{symbol.interpretation}\n"
            prompt += f"• 五行：{symbol.element.name}\n"
            prompt += f"• 方位：{symbol.direction}\n"
            prompt += f"• 神灵：{symbol.deity} - {symbol.deity_description}\n"

        # 添加明确的五行属性和生克关系
        prompt += "\n=== 五行生克关系 ===\n"
        prompt += f"初传五行：{symbols[0].element.name}\n"
        prompt += f"中传五行：{symbols[1].element.name}\n"
        prompt += f"末传五行：{symbols[2].element.name}\n\n"

        relations = self._get_relations(symbols)
        prompt += f"初传→中传：{relations[0]}（{symbols[0].element.name}{'生' if relations[0] == '生' else '克' if relations[0] == '克' else '与'}{symbols[1].element.name}）\n"
        prompt += f"中传→末传：{relations[1]}（{symbols[1].element.name}{'生' if relations[1] == '生' else '克' if relations[1] == '克' else '与'}{symbols[2].element.name}）\n\n"

        prompt += "=== 解读要求 ===\n"
        prompt += f"请紧密结合求问事项「{question}」，进行以下分析：\n\n"
        prompt += f"1. **针对性分析**：这三传结果对于「{question}」这个具体问题意味着什么？请直接回应求问者的关切。\n\n"
        prompt += "2. **时间发展脉络**：\n"
        prompt += f"   - 初传（当前/近期）：{symbols[0].name}对此事的影响\n"
        prompt += f"   - 中传（中期发展）：{symbols[1].name}如何推动事态变化\n"
        prompt += f"   - 末传（最终结果）：{symbols[2].name}预示的最终走向\n\n"
        
        if relations[0] != '无' or relations[1] != '无':
            prompt += "3. **五行影响机制**：结合求问事项，解释五行生克如何具体影响这件事的发展：\n"
            if relations[0] != '无':
                prompt += f"   - {symbols[0].element.name}{relations[0]}{symbols[1].element.name}：对此事态发展的推动/阻碍作用\n"
            if relations[1] != '无':
                prompt += f"   - {symbols[1].element.name}{relations[1]}{symbols[2].element.name}：对最终结果的影响机制\n"
        else:
            prompt += "3. **符号启示**：三传间无明显五行生克，请重点分析各符号本身对此问题的指导意义。\n"
        
        prompt += "\n4. **具体建议**：基于以上分析，针对这个具体问题给出实用的行动指导和注意事项。\n\n"
        prompt += "5. **关键提示**：如有特别需要注意的时间、方位、或神灵护佑，请一并说明。\n\n"
        
        prompt += "【重要提醒】请始终围绕求问事项进行解读，将抽象的占卜符号与具体问题紧密结合，给出有针对性的指导。"

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