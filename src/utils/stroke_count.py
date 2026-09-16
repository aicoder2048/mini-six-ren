from pathlib import Path
from .validation import validate_chinese


def _load_strokes() -> dict[str, int]:
    path = Path(__file__).resolve().parents[2] / 'data' / 'hanzi_dictionary.txt'
    strokes = {}
    with path.open(encoding='utf-8') as source:
        for line in source:
            parts = line.split()
            if len(parts) >= 2:
                strokes.setdefault(parts[0], int(parts[1][7:9]))
    return strokes


STROKE_COUNTS = _load_strokes()


def getbihua(char: str) -> int:
    try:
        return STROKE_COUNTS[char]
    except KeyError:
        raise ValueError(f'字典中没有汉字「{char}」的笔画数') from None


def get_stroke_counts(chars: str) -> list[int]:
    return [getbihua(char) for char in validate_chinese(chars, exact_three=False)]


def format_stroke_count_output(chars: str, stroke_counts: list[int]) -> str:
    """
    格式化笔画数输出。

    参数:
    chars (str): 输入的中文字符串
    stroke_counts (list[int]): 笔画数列表

    返回:
    str: 格式化的输出字符串

    示例:
    >>> format_stroke_count_output("你好", [7, 8])
    '笔画数：\n  你: 7画\n  好: 8画\n总笔画数：15画'
    """
    output = "笔画数：\n"
    for char, count in zip(chars, stroke_counts):
        output += f"  {char}: {count}画\n"
    output += f"总笔画数：{sum(stroke_counts)}画"
    return output