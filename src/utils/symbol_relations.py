"""Shared relationships used in local results and AI prompts."""


def get_relations(symbols) -> list[str]:
    relations = []
    for first, second in zip(symbols, symbols[1:]):
        if first.element.generates == second.element.name:
            relations.append('生')
        elif first.element.overcomes == second.element.name:
            relations.append('克')
        else:
            relations.append('无')
    return relations
