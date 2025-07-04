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

def load_symbols():
    data_path = Path(__file__).parent.parent / 'data' / 'symbols.json'
    with open(data_path, 'r', encoding='utf-8') as f:
        symbols_data = json.load(f)
    
    return [Symbol(**data) for data in symbols_data]

SYMBOLS = load_symbols()