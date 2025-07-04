from typing import Dict, List, Tuple, Any
from five_elements import FIVE_ELEMENTS

WUXING = {
    '甲': '木', '乙': '木', '丙': '火', '丁': '火', '戊': '土',
    '己': '土', '庚': '金', '辛': '金', '壬': '水', '癸': '水',
    '子': '水', '丑': '土', '寅': '木', '卯': '木', '辰': '土',
    '巳': '火', '午': '火', '未': '土', '申': '金', '酉': '金',
    '戌': '土', '亥': '水'
}

DETAILED_WUXING = {
    "己子": "壁上土", "己丑": "壁上土",
    "己寅": "城墙土", "己卯": "城墙土", 
    "己辰": "大驿土", "己巳": "大驿土",
    "己午": "路旁土", "己未": "路旁土",
    "己申": "大驿土", "己酉": "大驿土",
    "己戌": "平地土", "己亥": "平地土",
}

def build_orders():
    generation_order = []
    overcoming_order = []
    element_dict = {element.name: element for element in FIVE_ELEMENTS}
    
    # 构建相生顺序
    current = FIVE_ELEMENTS[0].name
    for _ in range(len(FIVE_ELEMENTS)):
        generation_order.append(current)
        current = element_dict[current].generates
    
    # 构建相克顺序
    current = FIVE_ELEMENTS[0].name
    for _ in range(len(FIVE_ELEMENTS)):
        overcoming_order.append(current)
        current = element_dict[current].overcomes
    
    return generation_order, overcoming_order

GENERATION_ORDER, OVERCOMING_ORDER = build_orders()

# 添加这个打印语句来检查顺序是否正确
print(f"Generation Order: {GENERATION_ORDER}")
print(f"Overcoming Order: {OVERCOMING_ORDER}")

def get_wuxing(stem_branch: str) -> Tuple[str, str]:
    return WUXING[stem_branch[0]], WUXING[stem_branch[1]]

def analyze_wuxing(bazi: Dict[str, str]) -> Dict[str, Any]:
    wuxing_count = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}
    for pillar in bazi.values():
        wuxing_count[WUXING[pillar[0]]] += 1
        wuxing_count[WUXING[pillar[1]]] += 1
    
    day_wuxing = WUXING[bazi['day'][0]]
    
    wuxing_order = ["木", "火", "土", "金", "水"]
    
    day_index = wuxing_order.index(day_wuxing)
    helping_wuxing = [day_wuxing, wuxing_order[(day_index - 1) % 5]]
    weakening_wuxing = [
        wuxing_order[(day_index + 1) % 5],
        wuxing_order[(day_index + 2) % 5],
        day_wuxing
    ]
    
    missing = [w for w, count in wuxing_count.items() if count == 0]
    
    return {
        "wuxing_count": wuxing_count,
        "helping_wuxing": helping_wuxing,
        "weakening_wuxing": weakening_wuxing,
        "missing": missing
    }

def analyze_missing_wuxing(missing_wuxing: List[str], gender: str) -> str:
    impacts = []
    if "木" in missing_wuxing:
        impacts.append("缺木可能影响决断力和创新能力")
    if "火" in missing_wuxing:
        impacts.append("缺火可能影响人际关系和表现力")
    if "土" in missing_wuxing:
        impacts.append("缺土可能影响稳定性和健康")
    if "金" in missing_wuxing:
        impacts.append("缺金可能影响事业和财运")
    if "水" in missing_wuxing:
        impacts.append("缺水可能影响智慧和灵活性")
    
    return "；".join(impacts) if impacts else "五行俱全，影响不大"

def print_generation_cycle():
    cycle = " -> ".join(GENERATION_ORDER) + f" -> {GENERATION_ORDER[0]}"
    print(f"\n五行相生循环：{cycle}")

def print_overcoming_cycle():
    cycle = " -> ".join(OVERCOMING_ORDER) + f" -> {OVERCOMING_ORDER[0]}"
    print(f"\n五行相克循环：{cycle}")

def get_supporting_elements(day_element: str) -> Tuple[List[str], str]:
    index = GENERATION_ORDER.index(day_element)
    generating_element = GENERATION_ORDER[(index - 1) % len(GENERATION_ORDER)]
    
    elements = [generating_element, day_element]
    description = f"{generating_element}生{day_element}（生我者）\n{day_element}为日主（同我者）"
    
    return elements, description

def get_weakening_elements(day_element: str) -> Tuple[List[str], str]:
    gen_index = GENERATION_ORDER.index(day_element)
    over_index = OVERCOMING_ORDER.index(day_element)
    overcoming_element = OVERCOMING_ORDER[(over_index - 1) % len(OVERCOMING_ORDER)]
    generated_element = GENERATION_ORDER[(gen_index + 1) % len(GENERATION_ORDER)]
    
    elements = [overcoming_element, generated_element, day_element]
    description = (
        f"{overcoming_element}克{day_element}（克我者）\n"
        f"{day_element}生{generated_element}（我生者）\n"
        f"{day_element}耗泄（耗泄者，虽然是同类，但会造成耗损）"
    )
    
    return elements, description

def get_element_details(element_name: str) -> dict:
    element = next(e for e in FIVE_ELEMENTS if e.name == element_name)
    return {
        "名称": element.name,
        "描述": element.description,
        "寓意": element.meanings,
        "促进": element.promotes,
        "禁忌": element.taboos
    }

def print_element_details(element_name: str):
    details = get_element_details(element_name)
    print(f"\n{details['名称']}元素详情：")
    print(f"描述：{details['描述']}")
    
    for category in ['寓意', '促进', '禁忌']:
        print(f"\n{category}：")
        for key, value in details[category].items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for sub_key, sub_value in value.items():
                    print(f"    {sub_key}: {sub_value}")
            else:
                print(f"  {key}: {value}")