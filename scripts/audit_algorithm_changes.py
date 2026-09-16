"""Independent review checks; run from project root with uv run python <this file>.

Consolidated from the review's executed heredocs. No project files are changed.
Baseline: 3e6014e. Upstream references:
https://raw.githubusercontent.com/6tail/lunar-python/master/test/EightCharTest.py
"""
import ast
import calendar
import io
import random
import subprocess
import sys
from datetime import date, datetime, timedelta
from itertools import product
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd() / 'src'))
from hand_technique import HandTechnique
from symbols import SYMBOLS
from utils.stroke_count import STROKE_COUNTS
from utils.symbol_relations import get_relations
from utils.bazi_calculator import calculate_bazi, analyze_day_master_strength, analyze_spouse_palace
from utils.calendar_converter import solar_to_lunar, lunar_to_solar, date_to_numbers
from lunar_python import Solar, LunarYear

source = subprocess.check_output(['git', 'show', '3e6014e:src/hand_technique.py'], text=True)
tree = ast.parse(source)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
keep = {'__calculate_symbol', '__generate_prediction', '__is_generating', '__is_overcoming', '__get_relations'}
cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in keep]
namespace = {'SYMBOLS': SYMBOLS}
exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), 'baseline', 'exec'), namespace)
old = namespace['HandTechnique']
rng = random.Random(420)
cases = list(product(range(1, 10), repeat=3)) + [tuple(rng.randint(1, 999) for _ in range(3)) for _ in range(10000)]
for i in range(3):
    for value in range(1, 1000):
        values = [999, 999, 999]
        values[i] = value
        cases.append(tuple(values))
for values in cases:
    result = HandTechnique.predict(*values)
    expected = old._HandTechnique__generate_prediction(*values)
    assert result.symbols == tuple(expected), values
    assert result.relations == tuple(old._HandTechnique__get_relations(expected)), values
print('Baseline nine-position comparison:', len(cases), 'cases pass', flush=True)
for symbols in product(SYMBOLS, repeat=3):
    assert get_relations(symbols) == old._HandTechnique__get_relations(symbols)
print('All 729 symbol triples relationships: pass', flush=True)

expected = {}
duplicates = 0
for line in Path('data/hanzi_dictionary.txt').read_text().splitlines():
    parts = line.strip().split()
    if len(parts) >= 2 and parts[0] not in expected:
        expected[parts[0]] = int(parts[1][7:9])
    elif len(parts) >= 2:
        duplicates += 1
assert expected == STROKE_COUNTS
print('Dictionary first-match equivalence:', len(expected), 'keys;', duplicates, 'duplicates; range', min(expected.values()), max(expected.values()), flush=True)

for fn in [analyze_day_master_strength, analyze_spouse_palace]:
    for stem in '甲乙丙丁戊己庚辛壬癸':
        bazi = {'day': stem + '子', 'year': '甲寅'}
        assert len({fn(bazi, g) for g in ['M', 'm', '男', ' m ']}) == 1
        assert len({fn(bazi, g) for g in ['F', 'f', '女', ' f ']}) == 1
        assert fn(bazi, 'M') != fn(bazi, 'F')
        for invalid in ['', 'X', None, 1]:
            try:
                fn(bazi, invalid)
            except ValueError:
                pass
            else:
                raise AssertionError((fn, invalid))
print('Gender aliases/rejection, two helpers and all stems: pass', flush=True)

count = 0
for year in range(1900, 2100):
    for month in range(1, 13):
        for day in [1, calendar.monthrange(year, month)[1]]:
            solar = (year, month, day)
            assert lunar_to_solar(*solar_to_lunar(*solar)) == solar, solar
            pillar = calculate_bazi(year, month, day, 23, 59)['day']
            offset = (date(year, month, day) - date(2005, 12, 23)).days
            assert pillar == '甲乙丙丁戊己庚辛壬癸'[(7 + offset) % 10] + '子丑寅卯辰巳午未申酉戌亥'[(5 + offset) % 12], (solar, pillar)
            count += 1
print('Gregorian month endpoints:', count, 'roundtrips and anchored day cycles pass', flush=True)
for invalid in [(1899, 12, 31), (2100, 1, 1), (1900, 2, 29), (2099, 2, 29)]:
    try:
        solar_to_lunar(*invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(invalid)

references = [
    ((1939, 8, 5, 16, 0), ('己卯', '辛未', '甲戌', '壬申')),
    ((1999, 7, 21, 16, 0), ('己卯', '辛未', '甲戌', '壬申')),
    ((1901, 1, 1, 12, 0), ('庚子', '戊子', '己卯', '庚午')),
    ((1960, 12, 17, 12, 0), ('庚子', '戊子', '己卯', '庚午')),
    ((2023, 2, 24, 23, 0), ('癸卯', '甲寅', '癸丑', '甲子')),
    ((1900, 1, 29, 16, 0), ('己亥', '丁丑', '壬寅', '戊申')),
]
for args, expected in references:
    assert tuple(calculate_bazi(*args).values()) == expected, args
print('Six additional upstream reference fixtures: pass', flush=True)

for year in [1900, 1950, 2000, 2024, 2099]:
    terms = Solar.fromYmd(year, 7, 1).getLunar().getJieQiTable()
    for term in ['小寒', '立春', '惊蛰', '清明', '立夏', '芒种', '小暑', '立秋', '白露', '寒露', '立冬', '大雪']:
        instant = datetime.strptime(terms[term].toYmdHms(), '%Y-%m-%d %H:%M:%S')
        after = instant.replace(second=0) + (timedelta(minutes=1) if instant.second else timedelta())
        before = after - timedelta(minutes=1)
        def bazi_at(value):
            return calculate_bazi(value.year, value.month, value.day, value.hour, value.minute)
        first, second = bazi_at(before), bazi_at(after)
        assert first['month'] != second['month'], (term, instant, first, second)
        assert (first['year'] != second['year']) == (term == '立春'), (term, instant, first, second)
print('60 solar-term boundaries, bracketing minutes: pass', flush=True)

leaps = invalids = valid = 0
for year in range(1900, 2100):
    lunar_year = LunarYear.fromYear(year)
    for month in range(1, 13):
        for leap in [False, True]:
            lunar_month = lunar_year.getMonth(-month if leap else month)
            if lunar_month is None:
                try:
                    lunar_to_solar(year, month, 1, leap)
                except ValueError:
                    invalids += 1
                else:
                    raise AssertionError((year, month, leap))
            else:
                for day in [1, lunar_month.getDayCount()]:
                    try:
                        solar = lunar_to_solar(year, month, day, leap)
                    except ValueError:
                        # The last lunar months of 2099 extend beyond Gregorian 2099.
                        assert year == 2099
                        continue
                    assert solar_to_lunar(*solar) == (year, month, day, leap), (year, month, day, leap)
                    valid += 1
                if lunar_month.getDayCount() == 29:
                    try:
                        lunar_to_solar(year, month, 30, leap)
                    except ValueError:
                        invalids += 1
                    else:
                        raise AssertionError((year, month, 30, leap))
                leaps += leap
print('All lunar month endpoints:', valid, 'roundtrips;', invalids, 'invalids rejected;', leaps, 'leap months', flush=True)

for args in [(2024, 1, 1.5, False), (2024, 1.5, 1, False), (2024.0, 1, 1, False), (2024, True, True, False), (2023, 2, 1, 'false'), (2024, None, 1, False), (2024, 1, 1, 1)]:
    try:
        lunar_to_solar(*args)
    except ValueError:
        pass
    else:
        raise AssertionError(args)
print('Seven independent invalid lunar input checks: pass', flush=True)

import cli
from web import DivinationWebApp
app = DivinationWebApp.__new__(DivinationWebApp)
for date_text, time_text, reference in [
    ('1900-01-01', '00:00', [12, 1, 1]),
    ('2023-03-22', '23:59', [2, 1, 1]),
    ('2024-02-10', '01:00', [1, 1, 2]),
    ('2099-12-31', '22:59', None),
]:
    actual = date_to_numbers(date_text, time_text)
    if reference is not None:
        assert actual == reference
    assert app._validate_date_time(date_text, time_text) == (True, '', actual)
    with patch('cli.get_menu_choice', side_effect=[2, 'home']), patch('cli.Prompt.ask', side_effect=[date_text, time_text]), patch('cli.DivinationAgent.get_available_models', return_value=[]), patch('cli.HandTechnique.predict', wraps=cli.HandTechnique.predict) as predict, patch('cli.display_divination_result'), patch('cli.console', cli.Console(file=io.StringIO())):
        cli.xiaoliu_submenu()
        predict.assert_called_once_with(*actual)
    print(date_text, time_text, actual, 'CLI handler/Web conversion parity', flush=True)
