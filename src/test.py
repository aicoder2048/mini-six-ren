def __is_generating(element1, element2):
    generating_cycle = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    return generating_cycle[element1] == element2

relation = "生" if __is_generating("木", "金") else "克"
print(relation)