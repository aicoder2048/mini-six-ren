import os
from dotenv import load_dotenv
import openai
from symbols import SYMBOLS
from rich.table import Table
from rich import box
from openai import OpenAI
import re

class HandTechnique:
    @staticmethod
    def predict(num1, num2, num3, question=None):
        symbols = HandTechnique.__generate_prediction(num1, num2, num3)
        table = HandTechnique.__format_prediction(symbols)
        
        interpretation = None
        if question:
            interpretation = HandTechnique.interpret_prediction(symbols, question)
        
        return table, interpretation

    @staticmethod
    def __calculate_symbol(start_position, steps):
        end_position = (start_position + steps - 1) % 9
        return SYMBOLS[end_position]

    @staticmethod
    def __generate_prediction(num1, num2, num3):
        first_symbol = HandTechnique.__calculate_symbol(0, num1)
        second_symbol = HandTechnique.__calculate_symbol((num1 - 1) % 9, num2)
        third_symbol = HandTechnique.__calculate_symbol((num1 + num2 - 2) % 9, num3)
        return [first_symbol, second_symbol, third_symbol]

    @staticmethod
    def __format_prediction(symbols):
        table = Table(title="小六壬三传占卜", show_header=True, box=box.SIMPLE)
        table.add_column("初传（前期）", style="cyan", justify="center")
        table.add_column("关系", style="red", justify="center")
        table.add_column("中传（中期）", style="green", justify="center")
        table.add_column("关系", style="red", justify="center")
        table.add_column("末传（后期）", style="magenta", justify="center")

        # 添加符号名称
        table.add_row(
            f"【{symbols[0].name}】", "",
            f"【{symbols[1].name}】", "",
            f"【{symbols[2].name}】"
        )
        
        # 添加五行属性
        table.add_row(
            f"（{symbols[0].element.name}）", "",
            f"（{symbols[1].element.name}）", "",
            f"（{symbols[2].element.name}）"
        )
        
        # 添加生克关系
        relations = HandTechnique.__get_relations(symbols)
        
        table.add_row(
            "", f"[bold red]{relations[0]}→[/bold red]",
            "", f"[bold red]{relations[1]}→[/bold red]",
            ""
        )

        return table

    @staticmethod
    def __is_generating(element1, element2):
        return element1.generates == element2.name

    @staticmethod
    def __is_overcoming(element1, element2):
        return element1.overcomes == element2.name
    
    @staticmethod
    def __get_relations(symbols):
        relations = []
        for i in range(2):
            if HandTechnique.__is_generating(symbols[i].element, symbols[i+1].element):
                relation = "生"
            elif HandTechnique.__is_overcoming(symbols[i].element, symbols[i+1].element):
                relation = "克"
            else:
                relation = "无"
            relations.append(relation)
        return relations

    @staticmethod
    def interpret_prediction(symbols, question):
        load_dotenv()
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        prompt = HandTechnique.__generate_interpretation_prompt(symbols, question)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert in Chinese divination, specifically in interpreting 小六壬 (Xiao Liu Ren) results. Provide a concise interpretation in no more than 500 characters."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )

        interpretation = response.choices[0].message.content
        # 移除Markdown格式
        interpretation = re.sub(r'#+ ', '', interpretation)  # 移除标题
        interpretation = re.sub(r'\*\*(.*?)\*\*', r'\1', interpretation)  # 移除粗体
        interpretation = re.sub(r'\*(.*?)\*', r'\1', interpretation)  # 移除斜体
        interpretation = re.sub(r'- ', '', interpretation)  # 移除列表符号

        return interpretation

    @staticmethod
    def __generate_interpretation_prompt(symbols, question):
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

        relations = HandTechnique.__get_relations(symbols)
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
        prompt += "请以中国传统文化的智慧精髓来回答，语言要优雅含蓄，富有哲理，同时也要让现代人容易理解。字数控制在500字以内。"

        # 如果处于debug模式，打印高亮的prompt
        
        # from rich import print as rprint
        # rprint("[bold yellow]Debug: Generated Prompt[/bold yellow]")
        # rprint(f"[cyan]{prompt}[/cyan]")

        return prompt