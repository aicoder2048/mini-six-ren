from typing import Dict
from lunar_python import Solar
from .validation import normalize_gender, validate_datetime

HEAVENLY_STEMS = list("甲乙丙丁戊己庚辛壬癸")
EARTHLY_BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")
ZODIAC_ANIMALS = list("鼠牛虎兔龙蛇马羊猴鸡狗猪")


def calculate_bazi(year: int, month: int, day: int, hour: int, minute: int) -> Dict[str, str]:
    """China civil time; solar-term year/month boundaries, midnight day boundary."""
    validate_datetime(year, month, day, hour, minute)
    pillars = Solar.fromYmdHms(year, month, day, hour, minute, 0).getLunar().getEightChar()
    pillars.setSect(2)
    return {"year": pillars.getYear(), "month": pillars.getMonth(),
            "day": pillars.getDay(), "time": pillars.getTime()}

def get_chinese_year(year: int) -> str:
    stem = HEAVENLY_STEMS[(year - 4) % 10]
    branch = EARTHLY_BRANCHES[(year - 4) % 12]
    animal = ZODIAC_ANIMALS[(year - 4) % 12]
    return f"{stem}{branch}[{animal}]"

def analyze_day_master_strength(bazi: Dict[str, str], gender: str) -> str:
    day_master = bazi['day'][0]
    is_yang = day_master in "甲丙戊庚壬"
    
    if normalize_gender(gender) == "男":
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
    if normalize_gender(gender) == "男":
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