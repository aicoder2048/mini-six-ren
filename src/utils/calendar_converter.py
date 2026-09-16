"""Calendar conversions; legacy BaZi exports alias their canonical modules."""
from typing import Tuple, Dict, Any
from lunar_python import Lunar, Solar
from .validation import parse_datetime, validate_datetime, normalize_gender
from .bazi_calculator import calculate_bazi, HEAVENLY_STEMS, EARTHLY_BRANCHES, ZODIAC_ANIMALS
from .five_elements_utils import analyze_wuxing, WUXING, DETAILED_WUXING


def solar_to_lunar(year: int, month: int, day: int) -> Tuple[int, int, int, bool]:
    validate_datetime(year, month, day)
    lunar = Solar.fromYmd(year, month, day).getLunar()
    return lunar.getYear(), abs(lunar.getMonth()), lunar.getDay(), lunar.getMonth() < 0


def lunar_to_solar(year: int, month: int, day: int, is_leap: bool = False) -> Tuple[int, int, int]:
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (year, month, day)):
        raise ValueError('农历年、月、日必须为整数')
    if not isinstance(is_leap, bool):
        raise ValueError('是否闰月必须为布尔值')
    if not 1899 <= year <= 2099 or not 1 <= month <= 12 or not 1 <= day <= 30:
        raise ValueError('请输入有效农历日期')
    try:
        solar = Lunar.fromYmd(year, -month if is_leap else month, day).getSolar()
    except Exception as exc:
        raise ValueError('农历日期或闰月不存在') from exc
    result = solar.getYear(), solar.getMonth(), solar.getDay()
    validate_datetime(*result)
    return result


def date_to_numbers(date_text: str, time_text: str) -> list[int]:
    value = parse_datetime(date_text, time_text)
    _, month, day, _ = solar_to_lunar(value.year, value.month, value.day)
    return [month, day, (value.hour + 1) % 24 // 2 + 1]


def format_bazi_output(bazi: Dict[str, str], wuxing_analysis: Dict[str, Any], solar_date: str, solar_time: str, lunar_date: Tuple[int, int, int, bool], gender: str) -> Dict[str, Any]:
    zodiac = ZODIAC_ANIMALS[EARTHLY_BRANCHES.index(bazi['year'][1])]
    day_master = bazi['day'][:2]
    day_wuxing = WUXING[day_master[0]]
    detailed_wuxing = DETAILED_WUXING.get(day_master, f"{day_wuxing}命")
    
    lunar_year, lunar_month, lunar_day, is_leap = lunar_date
    
    basic_info = {
        "basic_info": {
            "sex": normalize_gender(gender),
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
            "wuxing_count": ' '.join([f'{count}个{element}' for element, count in wuxing_analysis['wuxing_count'].items()]),
            "helping_wuxing": ''.join(wuxing_analysis['helping_wuxing']),
            "weakening_wuxing": ''.join(wuxing_analysis['weakening_wuxing']),
            "missing": '五行俱全' if not wuxing_analysis['missing'] else '缺' + ''.join(wuxing_analysis['missing']),
            "missing_impact": '五行俱全，影响不大' if not wuxing_analysis['missing'] else '缺' + ''.join(wuxing_analysis['missing']) + '，可能影响相关方面的发展'
        }
    }
    
    return {**basic_info, **bazi_info, **wuxing_info}
