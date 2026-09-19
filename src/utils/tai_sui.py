"""Annual Tai Sui analysis, faithfully sourced from the project's JSON records."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from .bazi_calculator import (
    EARTHLY_BRANCHES, HEAVENLY_STEMS, ZODIAC_ANIMALS, get_chinese_year,
)

FAN_TYPES = ('值太岁', '冲太岁', '刑太岁', '害太岁', '破太岁')
HE_TYPES = ('六合太岁', '三合太岁', '相生太岁', '得助太岁')
BEIJING_TIME = timezone(timedelta(hours=8))


class TaiSuiDataError(RuntimeError):
    """A named Tai Sui file could not be read or has an invalid structure."""


class TaiSuiData:
    @classmethod
    def load_all(cls, data_dir: Path | None = None) -> dict:
        directory = Path(data_dir) if data_dir is not None else Path(__file__).resolve().parents[2] / 'data'
        expected = [directory / f'太岁_{branch}{animal}.json'
                    for branch, animal in zip(EARTHLY_BRANCHES, ZODIAC_ANIMALS)]
        records = {}
        for path in expected + sorted(set(directory.glob('太岁_*.json')) - set(expected)):
            branch, record = cls.load_file(path)
            if branch in records:
                raise TaiSuiDataError(f'{path}: 重复地支记录 {branch}')
            records[branch] = record
        return records

    @classmethod
    def load_file(cls, path: Path) -> tuple[str, dict]:
        path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
            label = path.stem.removeprefix('太岁_')
            if not label or label[0] not in EARTHLY_BRANCHES:
                raise ValueError('文件名缺少有效地支')
            branch = label[0]
            zodiac_label = branch + ZODIAC_ANIMALS[EARTHLY_BRANCHES.index(branch)]
            if not isinstance(raw, dict) or len(raw) != 1 or next(iter(raw)) not in ('太岁', zodiac_label):
                raise ValueError('顶层必须为太岁或对应生肖键')
            record = next(iter(raw.values()))
            if not isinstance(record, dict) or not isinstance(record['年份'], list):
                raise ValueError('年份必须为列表')
            years = {}
            for entry in record['年份']:
                if not isinstance(entry, dict):
                    raise ValueError('年份条目必须为对象')
                year, general = entry['年'], entry['神煞']
                if (not isinstance(year, str) or len(year) != 3
                        or year[0] not in HEAVENLY_STEMS or year[1:] != branch + '年'):
                    raise ValueError('年标签必须为同地支的干支年')
                if year in years:
                    raise ValueError(f'重复年份 {year}')
                if not isinstance(general, list) or len(general) != 2 or not all(isinstance(s, str) for s in general):
                    raise ValueError('神煞必须为将军及说明两个字符串')
                years[year] = general
            normalized = {'source_file': path.name, '年份': years}
            for group in ('犯太岁', '合太岁'):
                if not isinstance(record[group], dict):
                    raise ValueError(f'{group}必须为对象')
                normalized[group] = {}
                for kind, entries in record[group].items():
                    if isinstance(entries, dict):
                        entries = [entries]
                    if not isinstance(entries, list):
                        raise ValueError(f'{group}/{kind}必须为对象或列表')
                    relations = []
                    for entry in entries:
                        if not isinstance(entry, dict):
                            raise ValueError(f'{kind}条目必须为对象')
                        branches = entry['地支']
                        if (not isinstance(branches, list) or not branches
                                or not all(isinstance(b, str) and b in EARTHLY_BRANCHES for b in branches)):
                            raise ValueError(f'{kind}地支必须为非空有效地支列表')
                        if not all(isinstance(entry[key], str) for key in ('组合', '解释')):
                            raise ValueError(f'{kind}组合和解释必须为字符串')
                        if '类型' in entry and not isinstance(entry['类型'], str):
                            raise ValueError(f'{kind}类型必须为字符串')
                        relations.append({
                            'relation_type': kind, 'subtype': entry.get('类型'),
                            'combination': entry['组合'], 'branches': branches,
                            'explanation': entry['解释'],
                        })
                    normalized[group][kind] = relations
            return branch, normalized
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
            raise TaiSuiDataError(f'{path}: 太岁数据读取失败：{exc}') from exc


TAI_SUI_DATA = TaiSuiData.load_all()


def analyze_tai_sui(birth_year_branch: str, target_year: int | None = None) -> dict:
    """Use the birth pillar's branch and a Beijing civil-year label (not Li Chun)."""
    if not isinstance(birth_year_branch, str) or birth_year_branch not in EARTHLY_BRANCHES:
        raise ValueError('出生年支必须为单个有效地支')
    if target_year is None:
        target_year = datetime.now(BEIJING_TIME).year
    if isinstance(target_year, bool) or not isinstance(target_year, int) or not 1900 <= target_year <= 2099:
        raise ValueError('流年必须为1900–2099的整数公历年份')
    chinese_year = get_chinese_year(target_year)
    branch = chinese_year[1]
    record = TAI_SUI_DATA[branch]
    general = record['年份'].get(chinese_year[:2] + '年')

    def matching(group, kinds):
        matches = []
        for kind in kinds:
            for relation in record[group].get(kind, []):
                branches = set(relation['branches'])
                if birth_year_branch == branch:
                    matched = kind in ('值太岁', '刑太岁') and branches == {branch}
                else:
                    matched = {birth_year_branch, branch} <= branches
                if matched:
                    matches.append(deepcopy(relation))
        return matches

    fan = matching('犯太岁', FAN_TYPES)
    he = matching('合太岁', HE_TYPES)
    return {
        'target_year': target_year, 'chinese_year': chinese_year,
        'target_year_branch': branch, 'birth_year_branch': birth_year_branch,
        'source_file': record['source_file'],
        'general': general[0] if general else None,
        'general_description': general[1] if general else None,
        'general_status': 'available' if general else 'missing',
        'fan_tai_sui': fan, 'he_tai_sui': he,
        'summary': '、'.join(name for name, entries in (('犯太岁', fan), ('合太岁', he)) if entries) or '无特殊关系',
    }
