import json

class Bagua:
    def __init__(self, name, symbol, nature, direction, family_member, body_part, animal):
        self.name = name
        self.symbol = symbol
        self.nature = nature
        self.direction = direction
        self.family_member = family_member
        self.body_part = body_part
        self.animal = animal

    @classmethod
    def load_bagua(cls):
        with open('data/bagua.json', 'r', encoding='utf-8') as f:
            bagua_data = json.load(f)
        return [cls(**data) for data in bagua_data]

BAGUA = Bagua.load_bagua()