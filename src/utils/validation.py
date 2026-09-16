"""Shared input rules for CLI, web, and calculation entry points."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re


def validate_numbers(values) -> list[int]:
    if len(values) != 3:
        raise ValueError('请输入三个数字')
    result = []
    for value in values:
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError('请输入1-999之间的整数') from None
        if not number.is_finite() or number != number.to_integral_value() or not 1 <= number <= 999:
            raise ValueError('请输入1-999之间的整数')
        result.append(int(number))
    return result


def validate_datetime(year, month, day, hour=0, minute=0) -> datetime:
    value = datetime(year, month, day, hour, minute)
    if not 1900 <= value.year <= 2099:
        raise ValueError('日期年份必须在1900-2099之间')
    return value


def parse_datetime(date_text: str, time_text: str = '00:00') -> datetime:
    if not isinstance(date_text, str) or not isinstance(time_text, str):
        raise ValueError('请输入日期和时间')
    try:
        value = datetime.strptime(f'{date_text.strip()} {time_text.strip()}', '%Y-%m-%d %H:%M')
    except ValueError:
        raise ValueError('请输入有效日期（YYYY-MM-DD）和时间（HH:MM）') from None
    return validate_datetime(value.year, value.month, value.day, value.hour, value.minute)


def normalize_gender(value: str) -> str:
    genders = {'M': '男', 'F': '女', '男': '男', '女': '女'}
    try:
        return genders[value.strip().upper()]
    except (KeyError, AttributeError):
        raise ValueError('性别请输入M/F或男/女') from None


def validate_chinese(text: str, *, exact_three=True) -> str:
    chars = re.sub(r'[,，\s]', '', text or '')
    valid_length = len(chars) == 3 if exact_three else 1 <= len(chars) <= 3
    if not valid_length or not all('\u4e00' <= c <= '\u9fff' for c in chars):
        raise ValueError('请输入3个汉字' if exact_three else '请输入1到3个汉字')
    return chars
