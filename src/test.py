"""Small manual prediction example; automated tests live in tests/."""
from hand_technique import HandTechnique

if __name__ == '__main__':
    prediction = HandTechnique.predict(3, 5, 8)
    print([symbol.name for symbol in prediction.symbols], prediction.relations)
