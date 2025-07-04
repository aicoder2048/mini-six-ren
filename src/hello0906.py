from datetime import date
from rich import print
from rich.console import Console
from rich.text import Text

console = Console()

name = Text("我是邹致远")
name.stylize("bold magenta")
console.print(name)

today = date.today()
date_text = Text(f"今天的日期是: {today.strftime('%Y年%m月%d日')}")
date_text.stylize("cyan")
console.print(date_text)
