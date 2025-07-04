import json
from typing import List, Dict, Any

class FiveElement:
    def __init__(self, name: str, properties: Dict[str, Any]):
        self.name = name
        self.description = properties['description']
        self.heavenly_stems = properties['heavenly_stems']
        self.earthly_branches = properties['earthly_branches']
        self.trigrams = properties['trigrams']
        self.directions = properties['directions']
        self.meanings = properties['meanings']
        self.promotes = properties['promotes']
        self.taboos = properties['taboos']
        self.generates = properties['generates']
        self.overcomes = properties['overcomes']

    @classmethod
    def load_five_elements(cls) -> List['FiveElement']:
        with open('data/five_elements.json', 'r', encoding='utf-8') as f:
            elements_data = json.load(f)
        return [cls(data['name'], data) for data in elements_data]

FIVE_ELEMENTS = FiveElement.load_five_elements()