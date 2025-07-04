from typing import Dict, Tuple
from .calendar_converter import solar_to_lunar
from .five_elements_utils import analyze_wuxing, get_wuxing

HEAVENLY_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
EARTHLY_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
ZODIAC_ANIMALS = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

def calculate_bazi(year: int, month: int, day: int, hour: int, minute: int) -> Dict[str, str]:
    # 使用简化的八字计算方法
    # 年柱：基于年份计算
    year_stem_index = (year - 4) % 10
    year_branch_index = (year - 4) % 12
    
    # 月柱：基于月份和年份计算
    month_stem_index = (year_stem_index * 2 + month) % 10
    month_branch_index = (month + 1) % 12
    
    # 日柱：基于日期计算（简化版）
    day_stem_index = (year * 5 + month * 6 + day) % 10
    day_branch_index = (year * 5 + month * 6 + day) % 12
    
    # 时柱：基于时辰计算
    hour_branch_index = (hour + 1) // 2 % 12
    hour_stem_index = (day_stem_index * 2 + hour_branch_index) % 10
    
    bazi = {
        "year": f"{HEAVENLY_STEMS[year_stem_index]}{EARTHLY_BRANCHES[year_branch_index]}",
        "month": f"{HEAVENLY_STEMS[month_stem_index]}{EARTHLY_BRANCHES[month_branch_index]}",
        "day": f"{HEAVENLY_STEMS[day_stem_index]}{EARTHLY_BRANCHES[day_branch_index]}",
        "time": f"{HEAVENLY_STEMS[hour_stem_index]}{EARTHLY_BRANCHES[hour_branch_index]}"
    }
    
    return bazi

def get_chinese_year(year: int) -> str:
    stem = HEAVENLY_STEMS[(year - 4) % 10]
    branch = EARTHLY_BRANCHES[(year - 4) % 12]
    animal = ZODIAC_ANIMALS[(year - 4) % 12]
    return f"{stem}{branch}[{animal}]"

def analyze_day_master_strength(bazi: Dict[str, str], gender: str) -> str:
    day_master = bazi['day'][0]
    is_yang = day_master in "甲丙戊庚壬"
    
    if gender == "男":
        if is_yang:
            return "日主阳刚，有利于男性发展"
        else:
            return "日主阴柔，男性可能需要在事业上更加努力"
    else:  # 女性
        if is_yang:
            return "日主阳刚，女性可能在事业上较为顺利，但需要注意家庭平衡"
        else:
            return "日主阴柔，有利于女性的人际关系和家庭和谐"

def analyze_spouse_palace(bazi: Dict[str, str], gender: str) -> str:
    if gender == "男":
        spouse_palace = bazi['day'][1]
        analysis = f"配偶宫在日支：{spouse_palace}，"
    else:
        spouse_palace = bazi['year'][1]
        analysis = f"配偶宫在年柱：{spouse_palace}，"
    
    if spouse_palace in "子午卯酉":
        analysis += "配偶可能性格较为固执但忠诚"
    elif spouse_palace in "寅申巳亥":
        analysis += "配偶可能富有冒险精神和创造力"
    elif spouse_palace in "辰戌丑未":
        analysis += "配偶可能性格温和，注重家庭"
    
    return analysis