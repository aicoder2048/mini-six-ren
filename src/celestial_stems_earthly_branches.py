import json
from pathlib import Path


class CelestialStem:
    def __init__(self, name, element):
        self.name = name
        self.element = element

    @classmethod
    def load(cls, records):
        return [cls(**record) for record in records]


class EarthlyBranch:
    def __init__(self, name, element, zodiac):
        self.name = name
        self.element = element
        self.zodiac = zodiac

    @classmethod
    def load(cls, records):
        return [cls(**record) for record in records]


with (Path(__file__).resolve().parent.parent / 'data' / 'celestial_stems_earthly_branches.json').open(encoding='utf-8') as source:
    _data = json.load(source)
CELESTIAL_STEMS = CelestialStem.load(_data['celestial_stems'])
EARTHLY_BRANCHES = EarthlyBranch.load(_data['earthly_branches'])
