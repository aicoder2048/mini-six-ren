from hand_technique import HandTechnique
from ai_agent import DivinationAgent, SupportedModels
from five_elements import FIVE_ELEMENTS
from utils.calendar_converter import solar_to_lunar, lunar_to_solar, date_to_numbers
from utils.stroke_count import get_stroke_counts, format_stroke_count_output
from utils.bazi_calculator import calculate_bazi, analyze_day_master_strength, analyze_spouse_palace, get_chinese_year
from utils.five_elements_utils import analyze_wuxing, analyze_missing_wuxing, get_wuxing, print_generation_cycle, print_overcoming_cycle, get_supporting_elements, get_weakening_elements
from rich import box
from rich.panel import Panel
from rich.console import Console
from rich.text import Text
from rich.prompt import Prompt
from rich.style import Style
from rich.table import Table 
from utils.validation import parse_datetime, normalize_gender, validate_numbers, validate_chinese
from datetime import datetime 
import random
import os
import re

console = Console()

def format_prediction(result):
    symbols = result.symbols
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
    relations = result.relations

    table.add_row(
        "", f"[bold red]{relations[0]}→[/bold red]",
        "", f"[bold red]{relations[1]}→[/bold red]",
        ""
    )

    return table


def create_gradient_text(text, start_color=(100, 100, 255), end_color=(255, 100, 100)):
    gradient_text = Text(text, style="bold")
    for i in range(len(text)):
        r = start_color[0] + (end_color[0] - start_color[0]) * i // len(text)
        g = start_color[1] + (end_color[1] - start_color[1]) * i // len(text)
        b = start_color[2] + (end_color[2] - start_color[2]) * i // len(text)
        gradient_text.stylize(f"rgb({r},{g},{b})", i, i+1)
    return gradient_text

def display_menu(items, title, level=1):
    menu_items = []
    for i, item in enumerate(items, 1):
        color = f"rgb({random.randint(150,255)},{random.randint(150,255)},{random.randint(150,255)})"
        menu_items.append(f"[{color}]{i}. {item}[/{color}]")
    
    # Add a separator
    menu_items.append("─" * 30)
    
    if level > 1:
        menu_items.append("[yellow]h. 返回主菜单[/yellow]")
    menu_items.append("[red]q. 退出程序[/red]")
    
    gradient_title = create_gradient_text(title)
    menu_panel = Panel(
        "\n".join(menu_items),
        title=gradient_title,
        title_align="center",
        border_style="bold",
        box=box.DOUBLE_EDGE,
        expand=False,
        padding=(1, 2),
        width=min(80, console.width - 4)
    )
    console.print(menu_panel)

def get_menu_choice(options, level=1):
    choices = [str(i) for i in range(1, len(options) + 1)]
    if level > 1:
        choices.append('h')
    choices.append('q')
    
    while True:
        choice = Prompt.ask("请输入选项", choices=choices)
        if choice == 'q':
            console.print("感谢使用小六壬占卜系统，再见！")
            exit()
        elif choice == 'h' and level > 1:
            return 'home'
        elif choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice)
        else:
            console.print("[bold red]无效选项，请重新输入。[/bold red]")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_colorful_title():
    title = Text("欢迎使用小六壬占卜系统！", style="bold")
    for i in range(len(title)):
        title.stylize(f"color({random.randint(16, 231)})", i, i+1)
    console.print(Panel(title, border_style="bold", box=box.DOUBLE))

def solar_to_lunar_conversion():
    date_str = Prompt.ask("[bold cyan]请输入公历日期（格式：YYYY-MM-DD）[/bold cyan]")
    
    try:
        date_value = parse_datetime(date_str)
        year, month, day = date_value.year, date_value.month, date_value.day
        lunar_year, lunar_month, lunar_day, is_leap = solar_to_lunar(year, month, day)
        
        console.print(f"\n[bold green]公历日期：[/bold green]{year}年{month}月{day}日")
        console.print(f"[bold green]农历日期：[/bold green]{lunar_year}年{'闰' if is_leap else ''}{lunar_month}月{lunar_day}日")
    except ValueError:
        console.print("[bold red]输入格式错误，请确保输入正确的日期格式（YYYY-MM-DD）。[/bold red]")
def lunar_to_solar_conversion():
    date_str = Prompt.ask('[bold cyan]请输入农历日期（YYYY-MM-DD）[/bold cyan]')
    leap = Prompt.ask('是否闰月', choices=['y', 'n'], default='n') == 'y'
    try:
        year, month, day = map(int, date_str.split('-'))
        year, month, day = lunar_to_solar(year, month, day, leap)
        console.print(f'[bold green]公历日期：{year:04d}-{month:02d}-{day:02d}[/bold green]')
    except ValueError as exc:
        console.print(f'[red]日期输入错误：{exc}[/red]')


def bazi_calculation():
    date_str = Prompt.ask("[bold cyan]请输入公历日（格式：YYYY-MM-DD）[/bold cyan]")
    time_str = Prompt.ask("[bold cyan]请输入北京时间（UTC+8，格式：HH:MM）[/bold cyan]")
    gender = Prompt.ask("[bold cyan]请输入性别（M/F）[/bold cyan]")
    
    try:
        time_value = parse_datetime(date_str, time_str)
        year, month, day = time_value.year, time_value.month, time_value.day
        hour, minute = time_value.hour, time_value.minute
        gender = normalize_gender(gender)
        
        lunar_date = solar_to_lunar(year, month, day)
        bazi = calculate_bazi(year, month, day, hour, minute)
        wuxing_analysis = analyze_wuxing(bazi)
        
        report_id = random.randint(1000, 9999)
        console.print(Panel(Text(f"命主-{report_id}的生辰八字解析报告", style="bold magenta"), box=box.DOUBLE))
        console.print("─" * 80)
        
        day_master_analysis = analyze_day_master_strength(bazi, gender)
        spouse_palace_analysis = analyze_spouse_palace(bazi, gender)
        missing_impact = analyze_missing_wuxing(wuxing_analysis['missing'], gender)
        
        sections = [
            ("基本信息", [
                ("性别", gender),
                ("公历生日", f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"),
                ("农历生日", f"{lunar_date[0]}年{'闰' if lunar_date[3] else ''}{lunar_date[1]}月{lunar_date[2]}日")
            ]),
            ("八字信息", [
                ("生辰八字", f"{bazi['year']}年 {bazi['month']}月 {bazi['day']}日 {bazi['time']}时"),
                ("命主五行", f"{bazi['day'][0]}{get_wuxing(bazi['day'])[0]}命"),
                ("八字五行", ' '.join([f"{get_wuxing(bazi[p])[0]}{get_wuxing(bazi[p])[1]}" for p in ['year', 'month', 'day', 'time']]))
            ]),
            ("五行分析", [
                ("五行个", ' '.join([f"{count}个{element}" for element, count in wuxing_analysis['wuxing_count'].items()])),
                ("帮扶日主", ''.join(wuxing_analysis['helping_wuxing'])),
                ("克泄耗日主", ''.join(wuxing_analysis['weakening_wuxing'])),
                ("五行是否所缺", '五行俱全' if not wuxing_analysis['missing'] else f"缺{''.join(wuxing_analysis['missing'])}"),
                ("五行缺失影响", missing_impact)
            ]),
            ("命运解析", [
                ("日主旺衰", day_master_analysis),
                ("配偶宫位", spouse_palace_analysis)
            ])
        ]
        
        for title, items in sections:
            console.print(f"\n[bold cyan]{title}：[/bold cyan]")
            for key, value in items:
                console.print(f"  {key}：{value}")
        
        console.print("\n" + "─" * 80)
        
    except ValueError as e:
        console.print(f"[bold red]输入格式错误：{str(e)}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]发生错误：{str(e)}[/bold red]")

def stroke_count_calculation():
    """
    计算用户输入的中文字符的笔画数并显示结果。
    """
    chars = Prompt.ask("[bold cyan]请输入1到3个中文字符[/bold cyan]")
    try:
        chars = validate_chinese(chars, exact_three=False)
        stroke_counts = get_stroke_counts(chars)
        output = format_stroke_count_output(chars, stroke_counts)
        console.print(f"\n[bold green]笔画数计算结果：[/bold green]")
        console.print(output)
    except Exception as e:
        console.print(f"[bold red]计算笔画数时出错：{str(e)}[/bold red]")

def print_five_elements_info():
    console = Console()
    
    # 获取控制台宽度
    console_width = console.width

    console.print(Panel.fit("[bold magenta]五行信息[/bold magenta]", border_style="bold", box=box.DOUBLE))

    # 正确的五行相生顺序
    generation_order = ["木", "火", "土", "金", "水"]
    generation_cycle = " -> ".join(generation_order) + " -> 木"
    
    # 正确的五行相克顺序
    overcoming_order = ["金", "木", "土", "水", "火"]
    overcoming_cycle = " -> ".join(overcoming_order) + " -> 金"
    
    console.print(Panel(f"[cyan]五行相生循环：[/cyan]\n{generation_cycle}\n\n[cyan]五行相克循环：[/cyan]\n{overcoming_cycle}", 
                        title="五行循环", border_style="bold", expand=False, width=console_width))

    # 创建五行信息表格
    table = Table(title="五行详细信息", box=box.ROUNDED, show_header=True, header_style="bold magenta", width=console_width)
    table.add_column("五行", style="cyan", no_wrap=True)
    table.add_column("描述", style="green")
    table.add_column("天干", style="yellow")
    table.add_column("地支", style="blue")
    table.add_column("八卦", style="magenta")
    table.add_column("方位", style="red")

    # 按照正确的相生顺序排列五行元素
    sorted_elements = sorted(FIVE_ELEMENTS, key=lambda e: generation_order.index(e.name))

    for element in sorted_elements:
        table.add_row(
            element.name,
            element.description,
            ", ".join(element.heavenly_stems),
            ", ".join(element.earthly_branches),
            ", ".join(element.trigrams),
            ", ".join(element.directions)
        )

    console.print(table)

    # 打印每个五行的寓意、促进和禁忌
    for element in sorted_elements:
        meanings_table = Table(show_header=False, box=box.SIMPLE, width=console_width - 4)  # -4 for panel borders
        meanings_table.add_column("类别", style="yellow")
        meanings_table.add_column("含义", style="cyan")
        meanings_table.add_column("促进", style="green")
        meanings_table.add_column("禁忌", style="red")

        for key in element.meanings.keys():
            if isinstance(element.meanings[key], dict):
                sub_table = Table(show_header=False, box=None)
                sub_table.add_column("子类别", style="yellow")
                sub_table.add_column("子含义", style="cyan")
                sub_table.add_column("子促进", style="green")
                sub_table.add_column("子禁忌", style="red")
                for sub_key in element.meanings[key].keys():
                    sub_table.add_row(
                        sub_key,
                        element.meanings[key][sub_key],
                        element.promotes[key][sub_key] if key in element.promotes and sub_key in element.promotes[key] else "",
                        element.taboos[key][sub_key] if key in element.taboos and sub_key in element.taboos[key] else ""
                    )
                meanings_table.add_row(key, sub_table, "", "")
            else:
                meanings_table.add_row(
                    key,
                    element.meanings[key],
                    element.promotes[key] if key in element.promotes else "",
                    element.taboos[key] if key in element.taboos else ""
                )

        console.print(Panel(meanings_table, title=f"[bold cyan]{element.name}的寓意、促进和禁忌[/bold cyan]", 
                            border_style="bold", expand=False, width=console_width))

        # 打印帮扶和克泄耗信息
        supporting_elements, supporting_description = get_supporting_elements(element.name)
        weakening_elements, weakening_description = get_weakening_elements(element.name)

        support_weaken_table = Table(show_header=False, box=box.SIMPLE, width=console_width - 4)
        support_weaken_table.add_column("类别", style="yellow")
        support_weaken_table.add_column("元素", style="cyan")
        support_weaken_table.add_column("描述", style="green")

        support_weaken_table.add_row("帮扶元素", ", ".join(supporting_elements), supporting_description)
        support_weaken_table.add_row("克泄耗元素", ", ".join(weakening_elements), weakening_description)

        console.print(Panel(support_weaken_table, title=f"[bold cyan]{element.name}的帮扶和克泄耗元素[/bold cyan]", 
                            border_style="bold", expand=False, width=console_width))

        console.print("\n")  # 添加空行，分隔不同元素的信息

def analyze_day_master():
    date_str = Prompt.ask("[bold cyan]请输入公历日期（格式：YYYY-MM-DD）[/bold cyan]")
    
    try:
        date_value = parse_datetime(date_str)
        year, month, day = date_value.year, date_value.month, date_value.day
        lunar_year, lunar_month, lunar_day, _ = solar_to_lunar(year, month, day)
        
        console.print(Panel.fit(
            f"[bold green]公历日期：[/bold green]{year}年{month}月{day}日\n"
            f"[bold green]农历日期：[/bold green]{lunar_year}年{lunar_month}月{lunar_day}日",
            title="日期信息", border_style="bold", box=box.ROUNDED
        ))
        
        # 这里假设我们使用农历月份作为日主的五行
        # 实际应用中，您可能需要根据具体的八字计算规则来确定日主
        day_master = FIVE_ELEMENTS[(lunar_month - 1) % 5].name
        
        console.print(Panel(f"[bold cyan]日主五行：[/bold cyan]{day_master}", 
                            title="日主", border_style="bold", expand=False))
        
        supporting_elements, supporting_description = get_supporting_elements(day_master)
        weakening_elements, weakening_description = get_weakening_elements(day_master)
        
        support_panel = Panel(
            f"[bold green]元素：[/bold green]{', '.join(supporting_elements)}\n\n"
            f"[bold green]描述：[/bold green]\n{supporting_description}",
            title="帮扶日主的五行", border_style="bold", expand=False
        )
        
        weaken_panel = Panel(
            f"[bold red]元素：[/bold red]{', '.join(weakening_elements)}\n\n"
            f"[bold red]描述：[/bold red]\n{weakening_description}",
            title="克泄耗日主的五行", border_style="bold", expand=False
        )
        
        console.print(support_panel)
        console.print(weaken_panel)
        
    except ValueError:
        console.print(Panel("[bold red]输入格式错误，请确保输入正确的日期格式（YYYY-MM-DD）。[/bold red]", 
                            title="错误", border_style="bold red"))

def tools_submenu():
    while True:
        console.print("\n")
        display_menu(["笔画数计算", "公历转农历", "五行信息", "日主五行分析", "农历转公历"], "工具子菜单", level=2)
        sub_choice = get_menu_choice(["笔画数计算", "公历转农历", "五行信息", "日主五行分析", "农历转公历"], level=2)
        if sub_choice == 'home':
            break
        elif sub_choice == 1:
            stroke_count_calculation()
        elif sub_choice == 2:
            solar_to_lunar_conversion()
        elif sub_choice == 3:
            print_five_elements_info()
        elif sub_choice == 4:
            analyze_day_master()
        elif sub_choice == 5:
            lunar_to_solar_conversion()

def display_divination_result(table, interpretation):
    console = Console()
    
    # 设置表格宽度为控制台宽度
    console_width = console.width
    table.width = console_width
    
    # 显示占卜结果表格，修改标题
    console.print(Panel(table, title="求问占卜", expand=False, width=console_width))
    
    if interpretation:
        # 创建一个文本对象来显示解释
        interpretation_text = Text(interpretation, style="cyan")
        
        # 显示解释面板，宽度与表格相同
        console.print(Panel(interpretation_text, title="大师解读", border_style="magenta", expand=True, width=console_width))

console = Console()

def validate_chinese_chars(chars_input):
    try:
        return True, list(validate_chinese(chars_input))
    except ValueError as exc:
        return False, str(exc)

def main():
    clear_screen()
    display_colorful_title()
    
    while True:
        console.print("\n")
        display_menu(["小六壬占卜", "八字测算", "工具"], "主菜单")
        
        choice = get_menu_choice(["小六壬占卜", "八字测算", "工具"])
        if choice == 1:
            xiaoliu_submenu()
        elif choice == 2:
            bazi_calculation()
        elif choice == 3:
            tools_submenu()

def select_llm_model():
    available_models = DivinationAgent.get_available_models()
    if not available_models:
        console.print('[cyan]本地模式：无需API密钥，仍可计算三传和五行关系。[/cyan]')
        return None
    model_names = ['仅本地计算（不使用AI）'] + [SupportedModels.get_display_name(model) for model in available_models]
    display_menu(model_names, '请选择解读方式')
    choice = get_menu_choice(model_names)
    return None if choice == 1 else available_models[choice - 2]

def xiaoliu_submenu():
    while True:
        console.print("\n")
        display_menu(["输入三个数字", "输入公历日期", "输入三个汉字"], "小六壬占卜", level=2)
        sub_choice = get_menu_choice(["输入三个数字", "输入公历日期", "输入三个汉字"], level=2)
        if sub_choice == 'home':
            return
        
        # 选择LLM模型
        selected_model = select_llm_model()
        if sub_choice == 1:
            while True:
                numbers_input = Prompt.ask(
                    "[bold cyan]输入三个数字（逗号间隔）[/bold cyan]",
                    default="1,2,3"
                )
                try:
                    num1, num2, num3 = validate_numbers(numbers_input.split(','))
                    break
                except ValueError:
                    console.print("[bold red]请输入三个用逗号分隔的1-999整数。[/bold red]")
        elif sub_choice == 2:
            while True:
                date_input = Prompt.ask("[bold cyan]输入公历日期（格式：YYYY-MM-DD）[/bold cyan]")
                time_input = Prompt.ask("[bold cyan]输入北京时间（UTC+8，格式：HH:MM）[/bold cyan]")
                try:
                    num1, num2, num3 = date_to_numbers(date_input, time_input)
                    break
                except ValueError:
                    console.print("[bold red]日期或时间格式错误，请重新输入。[/bold red]")
        elif sub_choice == 3:
            while True:
                chars_input = Prompt.ask("[bold cyan]输入三个汉字（逗号间隔）[/bold cyan]")
                is_valid, result = validate_chinese_chars(chars_input)
                if is_valid:
                    chars = result
                    try:
                        stroke_counts = get_stroke_counts(''.join(chars))
                        num1, num2, num3 = stroke_counts
                        break
                    except Exception as e:
                        console.print(f"[bold red]计算笔画数时出错：{str(e)}[/bold red]")
                else:
                    console.print(f"[bold red]{result}[/bold red]")
                    console.print("[bold red]请重新输入三个汉字，用逗号分隔。[/bold red]")

        result = HandTechnique.predict(num1, num2, num3)
        display_divination_result(format_prediction(result), None)
        if selected_model is not None:
            question = Prompt.ask('[bold cyan]请描述求问事项（留空跳过AI）[/bold cyan]', default='').strip()
            if question:
                try:
                    interpretation = DivinationAgent(selected_model).interpret_prediction(result.symbols, question)
                    console.print(Panel(Text(interpretation), title='大师解读'))
                except Exception as exc:
                    console.print(f'[red]AI解读失败：{exc}[/red]')


def set_current_working_dir():
    import os
    import sys

    # 获取当前脚本的绝对路径
    current_script_path = os.path.abspath(__file__)
    
    # 获取项目根目录（当前工作目录是 src 的父目录）
    project_root = os.path.dirname(os.path.dirname(current_script_path))
    
    # 将项目根目录添加到 Python 路径
    sys.path.insert(0, project_root)
    
    # 切换当前工作目录到项目根目录
    os.chdir(project_root)
    
    console.print(f"[bold green]当前工作目录已设置为：[/bold green]{project_root}")


if __name__ == "__main__":
    set_current_working_dir()
    main()
