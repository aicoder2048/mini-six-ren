from lunardate import LunarDate
from typing import Tuple, Dict, List, Any

HEAVENLY_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
EARTHLY_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
ZODIAC_ANIMALS = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]
WUXING = {
    '甲': '木', '乙': '木', '丙': '火', '丁': '火', '戊': '土',
    '己': '土', '庚': '金', '辛': '金', '壬': '水', '癸': '水',
    '子': '水', '丑': '土', '寅': '木', '卯': '木', '辰': '土',
    '巳': '火', '午': '火', '未': '土', '申': '金', '酉': '金',
    '戌': '土', '亥': '水'
}

DETAILED_WUXING = {
    "己子": "壁上土", "己丑": "壁上土",
    "己寅": "城墙土", "己卯": "城墙土", 
    "己辰": "大驿土", "己巳": "大驿土",
    "己午": "路旁土", "己未": "路旁土",
    "己申": "大驿土", "己酉": "大驿土",
    "己戌": "平地土", "己亥": "平地土",
}

def solar_to_lunar(year: int, month: int, day: int) -> Tuple[int, int, int, bool]:
    lunar_date = LunarDate.fromSolarDate(year, month, day)
    return lunar_date.year, lunar_date.month, lunar_date.day, lunar_date.isLeapMonth

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

def analyze_wuxing(bazi: Dict[str, str]) -> Dict[str, Any]:
    wuxing_count = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}
    for pillar in bazi.values():
        wuxing_count[WUXING[pillar[0]]] += 1
        wuxing_count[WUXING[pillar[1]]] += 1
    
    day_wuxing = WUXING[bazi['day'][0]]
    
    # 定义五行相生顺序
    wuxing_order = ["木", "火", "土", "金", "水"]
    
    # 确定帮扶和克泄耗的五行
    day_index = wuxing_order.index(day_wuxing)
    helping_wuxing = [day_wuxing, wuxing_order[(day_index - 1) % 5]]  # 同我者和生我者
    weakening_wuxing = [
        wuxing_order[(day_index + 1) % 5],  # 我生者
        wuxing_order[(day_index + 2) % 5],  # 克我者
        day_wuxing  # 耗泄者（同类）
    ]
    
    missing = [w for w, count in wuxing_count.items() if count == 0]
    
    return {
        "wuxing_count": wuxing_count,
        "helping_wuxing": helping_wuxing,
        "weakening_wuxing": weakening_wuxing,
        "missing": missing
    }

def format_bazi_output(bazi: Dict[str, str], wuxing_analysis: Dict[str, Any], solar_date: str, solar_time: str, lunar_date: Tuple[int, int, int, bool], gender: str) -> Dict[str, Any]:
    zodiac = ZODIAC_ANIMALS[EARTHLY_BRANCHES.index(bazi['year'][1])]
    day_master = bazi['day'][:2]
    day_wuxing = WUXING[day_master[0]]
    detailed_wuxing = DETAILED_WUXING.get(day_master, f"{day_wuxing}命")
    
    lunar_year, lunar_month, lunar_day, is_leap = lunar_date
    
    basic_info = {
        "basic_info": {
            "sex": {'男' if gender.upper() == 'M' else '女'},
            "solar_date": f"{solar_date} {solar_time}",
            "lunar_date": f"{lunar_year}年{'闰' if is_leap else ''}{lunar_month}月{lunar_day}日"
        }
    }
    
    bazi_info = {
        "bazi_info": {
            "birth_info": f"{bazi['year']}[{zodiac}]年 {bazi['month']}月 {bazi['day']}日 {bazi['time']}时",
            "day_master": f"{day_master[0]}{day_wuxing}命（{detailed_wuxing}）",
            "bazi_five_elements": ' '.join([WUXING[pillar[0]] + WUXING[pillar[1]] for pillar in bazi.values()])
        }
    }
    
    wuxing_info = {
        "wuxing_info": {
            "wuxing_count": {' '.join([f'{count}个{element}' for element, count in wuxing_analysis['wuxing_count'].items()])},
            "helping_wuxing": ''.join(wuxing_analysis['helping_wuxing']),
            "weakening_wuxing": ''.join(wuxing_analysis['weakening_wuxing']),
            "missing": {'五行俱全' if not wuxing_analysis['missing'] else '缺' + ''.join(wuxing_analysis['missing'])},
            "missing_impact": {'五行俱全，影响不大' if not wuxing_analysis['missing'] else '缺' + ''.join(wuxing_analysis['missing']) + '，可能影响相关方面的发展'}
        }
    }
    
    return {**basic_info, **bazi_info, **wuxing_info}
