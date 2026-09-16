"""Shared relationships used in local results and AI prompts."""


def get_relations(symbols) -> list[str]:
    relations = []
    for first, second in zip(symbols, symbols[1:]):
        if first.element.name == second.element.name:
            relations.append('比和')
        elif first.element.generates == second.element.name:
            relations.append('生')
        elif first.element.overcomes == second.element.name:
            relations.append('克')
        elif second.element.generates == first.element.name:
            relations.append('被生')
        elif second.element.overcomes == first.element.name:
            relations.append('被克')
        else:
            raise ValueError('无法识别五行关系，请检查五行数据')
    return relations


def describe_relation(first, second, relation: str) -> str:
    """Explain direction explicitly; relation names take the left symbol as subject."""
    left, right = first.element.name, second.element.name
    explanations = {
        '比和': f'同属{left}，性质相近',
        '生': f'{left}生{right}，前传生后传',
        '克': f'{left}克{right}，前传克后传',
        '被生': f'{right}生{left}，后传生前传',
        '被克': f'{right}克{left}，后传克前传',
    }
    return explanations[relation]
