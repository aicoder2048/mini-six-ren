import json

class CelestialStem:
    def __init__(self, name, element):
        self.name = name
        self.element = element

class EarthlyBranch:
    def __init__(self, name, element, zodiac):
        self.name = name
        self.element = element
        self.zodiac = zodiac

def load_celestial_stems_earthly_branches():
    with open('data/celestial_stems_earthly_branches.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stems = [CelestialStem(**stem) for stem in data['celestial_stems']]
    branches = [EarthlyBranch(**branch) for branch in data['earthly_branches']]
    
    return stems, branches

CELESTIAL_STEMS, EARTHLY_BRANCHES = load_celestial_stems_earthly_branches()