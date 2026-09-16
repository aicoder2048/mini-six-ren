# Mini Six Ren 代码库总览与审阅发现

> **修复后对照（2026-09-15）**：下文保留原审阅快照；当前实现与验证结果见本文末尾 §11 和 `docs/specs/review-improvements.md`。
>
> 基于 commit `3e6014e`（分支 `aicoder2048/ui-improvment`）的全量扫描。
> 用途：后续改动时的交叉参考。若代码结构变化，请同步更新本文。
> 相关文档：`docs/specs/review-improvements.md`（正在进行中的修复计划，本文"发现"一节与其 11 条改进项一一对应）。

---

## 1. 一句话概括

**小六壬占卜应用**：用户给三个数字（或日期、或三个汉字），程序在 9 个"宫位"上掐指一算得出三个符号（初传 / 中传 / 末传），再把符号和五行生克关系喂给 LLM，生成一段中文解读。有终端版（`src/cli.py`）和网页版（`src/web.py`）两个入口。

代码量：约 2000 行 Python（`src/` 下 16 个文件）+ `data/` 下 JSON 数据 + 4 万行汉字字典。

---

## 2. 全局结构图

```
             ┌──────────────┐        ┌──────────────┐
             │  src/cli.py  │        │  src/web.py  │   ← 两个入口（终端 / 浏览器），只负责"问用户要输入、展示结果"
             │  rich 终端 UI │        │  NiceGUI 网页 │
             └──────┬───────┘        └──────┬───────┘
                    │                       │
                    ▼                       ▼
            ┌─────────────────────────────────────┐
            │  src/hand_technique.py              │   ← 核心算法：3 个数 → 3 个符号 + 两段生克关系
            │  HandTechnique.predict / predict_async
            └────────┬──────────────────┬─────────┘
                     │                  │
                     ▼                  ▼
            ┌────────────────┐   ┌──────────────────────┐
            │ src/symbols.py │   │  src/ai_agent.py     │   ← 拼 prompt、调 LLM（pydantic-ai），流式返回解读
            │ SYMBOLS（9 个）│   │  DivinationAgent     │
            └───────┬────────┘   └──────────────────────┘
                    ▼
            ┌─────────────────────┐
            │ src/five_elements.py│   ← 五行（金木水火土）及"谁生谁、谁克谁"
            │ FIVE_ELEMENTS       │
            └─────────────────────┘

            ┌──────────────────────────────────────────┐
            │  src/utils/                              │   ← 输入转换 + 八字工具箱
            │  stroke_count.py        汉字 → 笔画数     │      （cli.py 用得多，web.py 只用两个函数）
            │  calendar_converter.py  公历 → 农历        │
            │  bazi_calculator.py     八字四柱           │
            │  five_elements_utils.py 帮扶/克泄耗分析    │
            └──────────────────────────────────────────┘
                              ▼
                data/symbols.json, five_elements.json, hanzi_dictionary.txt ...
```

依赖方向是**自上而下、单向**的：UI → 算法 → 数据/AI。底层模块不知道 UI 的存在，所以 CLI 和 Web 能共用同一套算法。

### 2.1 import 关系（实际生效）

| 模块 | 依赖 |
|---|---|
| `cli.py` | `hand_technique`, `ai_agent`, `five_elements`, `utils.calendar_converter`, `utils.stroke_count`, `utils.bazi_calculator`, `utils.five_elements_utils`, `rich` |
| `web.py` | `hand_technique`, `ai_agent`, `utils.stroke_count`, `utils.calendar_converter`, `nicegui` |
| `hand_technique.py` | `symbols`, `ai_agent`, `rich.table` |
| `symbols.py` | `five_elements` |
| `ai_agent.py` | `pydantic_ai`, `dotenv`, `rich` |
| `utils/bazi_calculator.py` | `.calendar_converter`, `.five_elements_utils` |
| `utils/five_elements_utils.py` | `five_elements` |
| `utils/calendar_converter.py` | `lunardate` |
| `bagua.py`, `celestial_stems_earthly_branches.py` | **无人 import**（见 §7） |

---

## 3. 一次占卜的完整流程（主线）

以 Web 版为例，点"开始占卜"后：

1. **收集输入** — `web.py:_perform_divination` 读当前 tab，把输入转成三个整数 `[num1, num2, num3]`：
   - 数字模式：直接用（Web 允许 1–999，CLI 不限范围）
   - 时间模式：`月`、`日`、`时辰` 各映射成一个数（CLI 与 Web 算法不同，见 §7-5）
   - 汉字模式：`utils/stroke_count.get_stroke_counts` 去 `data/hanzi_dictionary.txt` 里逐行查每个字的笔画
2. **掐指算符号** — `hand_technique.py:__generate_prediction`，见 §4
3. **算生克关系** — `__get_relations` 比较相邻两个符号的五行：`element1.generates == element2.name` → "生"，`overcomes` → "克"，否则"无"
4. **调 AI** — `ai_agent.py:_generate_interpretation_prompt` 把三个符号的名字、描述、神灵、方位、五行关系和用户问题拼成一大段 prompt，`agent.run_stream` 流式拿回 Markdown 文本，`_format_markdown_for_web` 做轻度清洗
5. **渲染** — `web.py:_display_results` 用 NiceGUI 画三张卡片 + 箭头 + 详情表格，`_display_ai_result` 用 `ui.markdown` 显示解读

CLI 版流程完全一样，只是第 1 步用 `rich.Prompt` 问用户，第 5 步用 `rich.Table` 打印（由 `HandTechnique.__format_prediction` 生成）；AI 流式输出时 CLI 会 `console.clear()` 逐帧重绘（`ai_agent.py:_stream_interpretation`）。

---

## 4. 核心算法：`hand_technique.py`

`data/symbols.json` 定义了 9 个符号（注意：传统小六壬是 6 个，本项目是 9 宫扩展版），按 `order` 排成一圈：

```
大安(木) → 留连(木) → 速喜(火) → 赤口(金) → 小吉(水) → 空亡(土) → 病符(土) → 桃花(土) → 天德(金) → 回到大安
 idx 0      idx 1      idx 2      idx 3      idx 4      idx 5      idx 6      idx 7      idx 8
```

每个 `Symbol` 还带：`description`、`interpretation`、`bagua`、`direction`（方位）、`deity` / `deity_description`（神灵）、`finger_position`（手指位置）、`element`（直接引用 `FiveElement` 对象）。

`__calculate_symbol(start, steps)` 就是"从 start 位置开始，往前数 steps 格，落在哪"：

```python
normalized = steps % 9 or 9              # 大于 9 的数先取模，0 当 9
end = (start + normalized - 1) % 9       # 数格子，第 1 格是自己所在位置
return SYMBOLS[end]
```

三传是**接力**的（`__generate_prediction`）：

```python
first  = __calculate_symbol(0, num1)
second = __calculate_symbol((num1 - 1) % 9, num2)            # 从第一传落点起数
third  = __calculate_symbol((num1 + num2 - 2) % 9, num3)     # 从第二传落点起数
```

实测：

```
(1, 2, 3)    -> 大安(木), 留连(木), 赤口(金)   关系: 无, 无
(3, 5, 8)    -> 速喜(火), 病符(土), 小吉(水)   关系: 生, 克   (火生土, 土克水)
(10, 20, 30) -> 与 (1,2,3) 相同，因为 mod 9
```

公开 API：

- `HandTechnique.predict(num1, num2, num3, question=None, model_type=...)` → `(rich.Table, interpretation_str | None)`，同步，CLI 用
- `HandTechnique.predict_async(...)` → 同上，async，Web 用
- 其余方法均为双下划线私有（`__generate_prediction`、`__get_relations`、`__format_prediction` 等）

---

## 5. 各模块职责速查

| 文件 | 干什么 | 谁在用 |
|---|---|---|
| `five_elements.py` | 从 `data/five_elements.json` 加载 5 个 `FiveElement`（含 `generates` / `overcomes`，以及 `meanings` / `promotes` / `taboos` 按"健康、权力地位、财富、事业工作、人际关系"分类）。模块级 `FIVE_ELEMENTS` | `symbols.py`、`cli.py`、`five_elements_utils.py` |
| `symbols.py` | 加载 9 个 `Symbol`，`element` 字段指向 `FiveElement` 对象。模块级 `SYMBOLS`。**唯一用 `Path(__file__)` 定位数据文件的模块** | `hand_technique.py` |
| `hand_technique.py` | 算符号、算关系、造 rich 表格、调 AI | 两个 UI |
| `ai_agent.py` | `SupportedModels` 枚举（`openai:gpt-5.6`、`deepseek:deepseek-flash`）；`DivinationAgent` 用 pydantic-ai `Agent` 封装。`get_available_models()` 靠 `.env` 里有无对应 API key 判断可用性。system prompt 要求输出 `###` 标题 + `**粗体**` + 列表，≤1000 字 | `hand_technique.py`、两个 UI（模型选择） |
| `utils/calendar_converter.py` | `solar_to_lunar` 用 `lunardate`；另含一份 `calculate_bazi` / `analyze_wuxing` / `format_bazi_output`（重复，见 §7-2） | 两个 UI（只用 `solar_to_lunar`） |
| `utils/stroke_count.py` | `getbihua(char)` 逐行扫字典，取第二列第 8–9 位为笔画数；找不到返回 `-1` | 两个 UI |
| `utils/bazi_calculator.py` | `calculate_bazi`（简化公式）、`get_chinese_year`、`analyze_day_master_strength`、`analyze_spouse_palace` | 仅 CLI "八字测算" |
| `utils/five_elements_utils.py` | `analyze_wuxing`（五行计数、帮扶/克泄耗）、`analyze_missing_wuxing`、`get_supporting_elements` / `get_weakening_elements`、`GENERATION_ORDER` / `OVERCOMING_ORDER`（从 `FIVE_ELEMENTS` 推导） | 仅 CLI |

### 5.1 CLI 独有功能

CLI 比 Web 多一整块：

- **八字测算**（`bazi_calculation`）：公历 → 农历、四柱、日主五行、五行计数、缺失影响、日主旺衰、配偶宫
- **工具子菜单**（`tools_submenu`）：笔画数计算、公历转农历、五行信息（大表格）、日主五行分析

Web 版目前只做了小六壬占卜这一条主线。

### 5.2 两个入口的实现风格

- `cli.py`：过程式。`main()` 循环显示菜单 → 进子菜单 → 调对应函数。启动时 `set_current_working_dir()` 把 cwd 切到项目根，因为大多数模块用相对路径 `'data/xxx.json'` 读文件。`display_menu` 每次随机生成菜单颜色。
- `web.py`：一个 `DivinationWebApp` 类持有所有 UI 元素引用；`create_ui()` 建页面（含大段内联 CSS：`.gradient-purple/cyan/amber`、`.bento-card` 毛玻璃、`.ai-interpretation` 排版），`_perform_divination()` 是 async 事件处理。`ui.run(port=8080, host='0.0.0.0', reload=True, dark=True)`。**整个进程只有一个 `DivinationWebApp` 实例**，所有浏览器客户端共享（见 §7-9）。

---

## 6. 数据文件

| 文件 | 状态 | 说明 |
|---|---|---|
| `data/symbols.json` | ✅ 使用中 | 9 个符号，字段见 §4 |
| `data/five_elements.json` | ✅ 使用中 | 5 个五行，含天干、地支、八卦、方位、寓意/促进/禁忌 |
| `data/hanzi_dictionary.txt` | ✅ 使用中 | 40754 行，格式 ` 字 编码1 编码2`，笔画在第二列 `[7:9]` |
| `data/bagua.json` | ⚠️ 内容为 `[]` | 对应 `bagua.py` 无人 import |
| `data/celestial_stems_earthly_branches.json` | ⚠️ 两个数组均为空 | 对应 `celestial_stems_earthly_branches.py` 无人 import |
| `data/太岁_*.json`（12 个） | ⚠️ 无代码引用 | 十二生肖太岁信息，结构完整但未接入 |

其他非代码文件：

- `prd.md`：一份"高级信息展示与交互专家"的 prompt 模板，Web 版 Bento Grid / 三色渐变 / 毛玻璃视觉风格来源于此，与代码无直接关系
- `ai_docs/nicegui/*`、`ai_docs/pydanticai/*`：框架参考文档，供 AI 辅助开发时查阅
- `main.py`：`uv init` 生成的占位符（`print("Hello from mini-six-ren!")`），不是真正入口
- `src/test.py`：5 行临时脚本，手写了一个生克判断，不是测试

---

## 7. 审阅发现（已知问题 / 粗糙处）

编号与 `docs/specs/review-improvements.md` 的改进项交叉引用标注为 `[RI-n]`。

1. **死代码 / 空数据** `[RI-8]`
   `bagua.py`、`celestial_stems_earthly_branches.py` 没有任何模块 import；对应 JSON 为空。12 个 `太岁_*.json` 无代码引用。`main.py` 是占位符。

2. **重复实现** `[RI-9]`
   - `calculate_bazi` 同时存在于 `utils/calendar_converter.py:27` 和 `utils/bazi_calculator.py:9`
   - `analyze_wuxing` 同时存在于 `utils/calendar_converter.py:57` 和 `utils/five_elements_utils.py:47`
   - `WUXING` / `DETAILED_WUXING` 字典在两个文件里各一份
   - `cli.py:4` 和 `cli.py:7-8` 先后 import 同名函数，**后者覆盖前者**，实际生效的是 `bazi_calculator` / `five_elements_utils` 版本

3. **生克判断写了三遍** `[RI-9]`
   `hand_technique.py:__is_generating/__is_overcoming/__get_relations`、`ai_agent.py:_is_generating/_is_overcoming/_get_relations`、`src/test.py` 各一套，逻辑相同。

4. **Web 直接访问 name-mangled 私有方法** `[RI-10]`
   `web.py:207-208` 用 `HandTechnique._HandTechnique__generate_prediction` / `__get_relations` 绕过双下划线私有。根因：`predict_async` 返回的是 rich `Table`，对 Web 无用，Web 需要原始 `symbols` 和 `relations`。

5. **CLI 与 Web 的"时间模式"算法不一致** `[RI-3]`
   - CLI（`cli.py:404-407`）：先转农历，`num1=农历月`，`num2=农历日`，`num3=(hour+1)%24//2+1`
   - Web（`web.py:96-98`）：直接用公历，`num1=(month-1)%9+1`，`num2=(day-1)%9+1`，`num3=(hour%12)//2+1`
   同一日期两边会得出不同的三传。

6. **模块级 debug print** `[RI-9]`
   `utils/five_elements_utils.py:41-42` 每次 CLI 启动都会打印 `Generation Order: ...` / `Overcoming Order: ...`。

7. **八字算法是简化版** `[RI-2]`
   `calculate_bazi` 的日柱用 `(year*5 + month*6 + day) % 10` 线性公式，不是真实干支纪日；月柱 `(month+1)%12` 未考虑节气。README 说明是因 `sxtwl` 在 ARM64 装不上才换成 `lunardate` 的折中。`pyproject.toml` 已新增 `lunar-python>=1.4,<2` 依赖（尚未被任何模块 import），是正在进行的替换。

8. **笔画查不到返回 -1 仍继续占卜** `[RI-7]`
   `stroke_count.getbihua` 对生僻字返回 `-1`，`get_stroke_counts` 不检查，CLI/Web 都会拿 `-1` 去算符号。另外每查一个字都全量扫描 4 万行字典。

9. **Web 单例共享状态** `[RI-1]`
   `web.py:main()` 只建一个 `DivinationWebApp`，`@ui.page('/')` 每次调用 `create_ui()` 会覆盖 `self.number_inputs` 等引用。两个浏览器同时打开时，后打开的页面会"抢走"前一个页面的元素引用，前一个页面点击占卜会操作错误的元素。

10. **AI 是硬依赖** `[RI-5]`
    Web 版没有 API key 时 `create_ui()` 直接 `return`，连输入区都不渲染；CLI 版 `select_llm_model()` 返回 `None` 时直接退回主菜单。本地符号计算本身不需要 AI。

11. **输入校验分散且宽松** `[RI-7]`
    CLI 数字不限范围、Web 限 1–999；`ui.number` 允许小数，`int()` 会静默截断；性别只认 `M/F`（`analyze_day_master_strength` 比较的是 `"男"`，但 CLI 传入的是原始 `M/F`，导致男性输入走女性分支）。工作树里已出现 `src/utils/validation.py`（未提交）在收敛这些规则。

12. **数据文件路径依赖 cwd** `[RI-8]`
    除 `symbols.py` 外，所有加载器都用相对路径 `'data/...'`，必须先 `os.chdir(project_root)`。`cli.py` 和 `web.py` 各自在启动时切目录；测试或从其他目录 import 会失败。

13. **README 示例与实际输出不符**
    README "CLI版本示例" 里 `1,2,3` 的末传写的是 `速喜`，实际算出来是 `赤口`（见 §4 实测）。

---

## 8. 改 UI 时的落点

分支名是 `ui-improvment`。若只改视觉：

- 页面骨架与 CSS：`web.py:create_ui()`（约 `web.py:300-560`）
- 三传结果卡片与详情表：`web.py:_display_results()`
- AI 解读区：`web.py:_display_ai_result()` + CSS 中 `.ai-interpretation` 段
- CLI 表格样式：`hand_technique.py:__format_prediction()`、`cli.py:display_divination_result()`

底层算法（`hand_technique.py` 私有方法、`symbols.py`、`five_elements.py`）不需要碰。

---

## 9. 运行与验证

```bash
uv sync
uv run src/cli.py          # 终端版
uv run src/web.py          # 网页版，http://localhost:8080
uv run python -m unittest discover -s tests -v   # 回归测试（tests/ 目录为进行中的未提交工作）
```

AI 功能需要 `.env` 中至少一个：`OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY`。

---

## 10. 工作树中进行中的变更（2026-09-15 快照，未提交）

写本文时，另一处会话正按 `docs/specs/review-improvements.md` 重构，工作树已与 HEAD 有较大差异。§1–§9 描述的是 **HEAD `3e6014e`** 的状态；下面列出已观察到的偏移，供对照：

| 变化 | 对应 §7 发现 |
|---|---|
| 新增 `src/utils/symbol_relations.py`：`get_relations(symbols)` 成为唯一的生克判断实现，`ai_agent.py` / `hand_technique.py` 改为 import 它 | 7-3 |
| 新增 `src/utils/validation.py`：`validate_numbers`（1–999 整数，拒绝小数/布尔）、`parse_datetime` / `validate_datetime`（1900–2099）、`normalize_gender`（M/F/男/女 → 男/女）、`validate_chinese` | 7-11 |
| `hand_technique.py` 重写：`HandTechnique.predict(num1, num2, num3) -> Prediction`（dataclass，含 `.symbols` / `.relations`），不再返回 rich Table、不再内部调 AI；`format_prediction(result)` 移到 `cli.py` | 7-4 |
| `utils/calendar_converter.py` 改用 `lunar_python`（`Lunar` / `Solar`）；新增 `lunar_to_solar(year, month, day, is_leap)` 和 `date_to_numbers(date_text, time_text)`（CLI/Web 共用的日期→三数转换）；重复的 `calculate_bazi` / `analyze_wuxing` 改为从 `bazi_calculator` / `five_elements_utils` 转 import | 7-2, 7-5, 7-7 |
| `cli.py` 新增 `lunar_to_solar_conversion()`（农历转公历，含闰月选项）；八字输入提示改为"北京时间（UTC+8）" | RI-6 |
| `pyproject.toml` 新增 `lunar-python>=1.4,<2` | 7-7 |
| 新增 `tests/test_regressions.py`（unittest；覆盖日柱跨月、性别分支、Web 日期模式、小数拒绝、无凭据下 UI 仍渲染） | RI-11 |
| `bagua.py`、`celestial_stems_earthly_branches.py`、`five_elements.py`、`symbols.py`、`stroke_count.py` 亦有改动（推测为路径改用 `Path(__file__)` 与字典预加载，未逐一核对） | 7-1, 7-8, 7-12 |

这些变更落地并提交后，应回头修订 §2.1、§4 公开 API、§5 表格与 §7 发现列表。


## 11. 修复后对照（2026-09-15，当前工作树）

保留 §1–§10 作为审阅基线；其中旧接口、依赖及“正在进行”描述不再代表当前实现。

- `HandTechnique.predict(a,b,c)` 只返回 `Prediction(symbols, relations)`，九宫算法保留。CLI在 `format_prediction` 渲染，Web直接用结构化结果；AI由两个入口按需调用。
- `web.create_page()` 为每次页面访问创建独立控制器。重复提交在任务结束前被忽略；先显示本地结果，再请求AI，失败保留结果。
- CLI/Web均支持无凭据本地模式；有模型时也可明确选择“仅本地计算”。未填写问题不会请求AI。
- `calendar_converter` 使用 `lunar-python` 双向转换；`bazi_calculator` 使用 EightChar sect 2。`lunardate` 依赖已移除。两种界面共享 `date_to_numbers`，采用农历月、日和十二时辰。
- 时间按北京时间UTC+8解释；日柱午夜换日，年/月按节气划分；公历范围1900–2099，不进行真太阳时校正。
- `validation` 集中校验数字、日期时间、汉字和性别。`stroke_count` 从模块路径一次性加载字典，找不到汉字时抛出输入错误。
- 领域数据由类方法加载，文件定位不依赖工作目录；八字/五行/生克关系重复实现已合并。`src/test.py` 保留为调用正式预测API的手动示例。
- README中的 `(1,2,3)` 示例已与实际九宫计算一致。空八卦/干支数据和未接入太岁文件保留；本次未扩展这些功能。
- `tests/test_regressions.py` 覆盖历法参考值和边界、双向转换、CLI实际处理函数、两个NiceGUI客户端和AI异常。验证命令：`uv run python -m unittest discover -s tests -v`。本地Web HTTP启动检查返回200；未调用真实AI服务。
