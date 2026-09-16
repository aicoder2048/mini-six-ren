"""Local prediction model, independent of AI and UI frameworks."""
from dataclasses import dataclass
from symbols import SYMBOLS, Symbol
from utils.symbol_relations import get_relations
from utils.validation import validate_numbers


@dataclass(frozen=True)
class Prediction:
    symbols: tuple[Symbol, ...]
    relations: tuple[str, ...]


class HandTechnique:
    @staticmethod
    def predict(num1, num2, num3) -> Prediction:
        numbers = validate_numbers([num1, num2, num3])
        position = 0
        symbols = []
        for number in numbers:
            position = (position + number - 1) % len(SYMBOLS)
            symbols.append(SYMBOLS[position])
        return Prediction(tuple(symbols), tuple(get_relations(symbols)))
