def getbihua(char: str) -> int:
    dictionary_path = 'data/hanzi_dictionary.txt'
    
    with open(dictionary_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == char:
                # The stroke count is the 8th and 9th characters of the second part
                return int(parts[1][7:9])
    
    # If the character is not found in the dictionary
    return -1

def get_stroke_counts(chars: str) -> list[int]:
    """
    获取最多3个中文字符的笔画数。

    参数:
    chars (str): 输入的中文字符串，最多3个字符

    返回:
    list[int]: 每个字符的笔画数列表

    示例:
    >>> get_stroke_counts("你好")
    [7, 8]
    >>> get_stroke_counts("中国人")
    [4, 8, 2]
    >>> get_stroke_counts("一")
    [1]
    """
    if len(chars) > 3:
        chars = chars[:3]
    
    stroke_counts = []
    for char in chars:
        stroke_count = getbihua(char)
        stroke_counts.append(stroke_count)
    
    return stroke_counts


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