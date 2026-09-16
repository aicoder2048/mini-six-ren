import json
from pathlib import Path
from five_elements import FiveElement, FIVE_ELEMENTS

class Symbol:
    def __init__(self, name, description, interpretation, bagua, direction, element, deity, deity_description, finger_position, order):
        self.name = name
        self.description = description
        self.interpretation = interpretation
        self.bagua = bagua
        self.direction = direction
        self.element = next((e for e in FIVE_ELEMENTS if e.name == element), None)
        self.deity = deity
        self.deity_description = deity_description
        self.finger_position = finger_position
        self.order = order

    @classmethod
    def load_symbols(cls):
        data_path = Path(__file__).resolve().parent.parent / 'data' / 'symbols.json'
        with data_path.open(encoding='utf-8') as source:
            return [cls(**data) for data in json.load(source)]


SYMBOLS = Symbol.load_symbols()
