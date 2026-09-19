# 流年太岁：独立 Standards 审查

- 日期：2026-09-19。
- 身份：独立 Standards Reviewer（Codex），未参与本次实现；本次只审查并写入本记录，未修改实现、测试、数据、任务输入或规格，未暂存或提交。
- 基线：`fa8e83c1eeaff60415e89488bc59acb5c6535aa3`；审查时 HEAD 与基线一致。
- 结论：**Standards 轴通过，无阻断问题**。有一项非阻断测试增强建议。本结论不代替另一个独立 Reviewer 的 Spec／算法审查，也不单独宣布功能 Done。

## 范围与依据

已阅读根目录 `CLAUDE.md`、`AGENTS.md`、`docs/specs/457fdccf_annual-tai-sui.md`、`docs/agents/workflow.md`。按未暂存工作树方式检查 `git diff HEAD`，并通过 `git ls-files --others --exclude-standard` 逐一读取任务新增文件：

- `src/utils/tai_sui.py`（完整文件）。
- `tests/test_tai_sui.py`（完整文件）。
- `tests/fixtures/tai_sui_bazi_baseline.json`（完整文件）。
- 已跟踪变更：`src/cli.py`、`src/utils/calendar_converter.py`；审查期间其他工作上下文追加了规格第 7 节，本 Reviewer 随后读取了该差异，属于允许的实施记录范围。

`requests/tai-sui-analysis.md` 识别为原有输入，未修改或纳入交付操作。未修改任何太岁 JSON、Web UI、AI prompt、小六壬、符号关系、日主历史映射、八字核心或依赖文件。未启动额外算法 Reviewer：本任务已明确另有独立 Spec／算法 Reviewer。

## 检查结果

| 检查项 | 证据与判断 |
| --- | --- |
| 一次加载、相对路径、类方法 | `tai_sui.py:20–35,95`：两个加载入口均为 `@classmethod`；默认目录基于 `__file__`；模块底部一次构建缓存。独立监测先后导入太岁模块、历法模块、CLI，12 份文件各读取一次；随后遍历 12 个出生支分析，无新增读取。现有子进程测试还覆盖非项目目录导入。 |
| 不吞文件、点名异常 | 预期文件由既有地支／生肖常量生成，额外 glob 文件也进入加载；缺文件不能被 glob 遗漏。读取、编码、JSON、依赖结构错误包装为 `TaiSuiDataError` 并使用 `raise ... from exc`；重复支记录点名第二个路径。无 `except: continue`。独立补测损坏的额外文件被拒绝且保留 JSON 异常链。 |
| 结构校验 | 校验单键顶层、记录对象、年份列表及条目、同支干支年标签、神煞两个字符串、两类关系容器、关系对象／列表、非空有效地支列表、组合／解释字符串及可选类型。拒绝重复年份与重复支文件。未擅加六十甲子阴阳合法性校正；允许稀疏年份和缺省可选类别。 |
| 缓存隔离 | 命中关系深复制；返回列表及字典按次创建，将军及说明为不可变字符串。已有测试实际修改结果内层数组和解释后再次调用，确认不污染缓存。 |
| 可维护性与最小范围 | 加载、分析和展示边界清楚；类别顺序为声明常量，未手写地支关系表；CLI 复用分析与展示助手，只追加一节。未引入依赖、命令模式、年份交互、额外框架或无关清理。 |
| 接口兼容性 | `format_bazi_output` 保留六个位置参数，年份是新增仅关键字参数；三个旧键的构造未改。CLI 仍从既有 `bazi['year'][1]` 取出生支，保留旧报告编号、标题渲染、分隔线和异常处理。固定夹具经真实基线独立验证，详见下文。 |
| 测试质量 | 使用 unittest、mock、临时目录，无新依赖。覆盖加载形状、实际不可读模拟、编码／JSON／结构损坏、缓存、返回隔离、固定关系期望、稀疏年份、输入边界、真正按时区转换的年界替身、显式年份不读时钟及 CLI 捕获。没有修改旧测试期望。展示断言仍可增强，见 S-01。 |

## 验证证据

所有结果以工具返回的进程退出码为准，不以输出含 `OK` 作为唯一依据。

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `uv run python -m unittest discover -s tests -p 'test_tai_sui.py' -v` | 2 | 默认 `/home/zou/.cache/uv` 只读，无法取得缓存锁，测试尚未执行。 |
| `uv run python -m unittest discover -s tests -v` | 2 | 同上，环境限制。 |
| `uv lock --locked` | 2 | 同上，环境限制。 |
| `UV_CACHE_DIR=/tmp/tai-sui-standards-uv uv run python -m unittest discover -s tests -p 'test_tai_sui.py' -v` | 0 | 16 项通过。 |
| `UV_CACHE_DIR=/tmp/tai-sui-standards-uv uv run python -m unittest discover -s tests -v` | 0 | 124 项通过，包含原 CLI、历法、AI 与 Web 测试。 |
| `UV_CACHE_DIR=/tmp/tai-sui-standards-uv uv lock --locked` | 0 | `Resolved 108 packages`，无依赖文件差异。 |
| `git diff --check` | 0 | 无空白错误。 |
| `UV_CACHE_DIR=/tmp/tai-sui-standards-uv uv run python - <<'PY' … PY`：独立基线夹具核验 | 0 | 下述三组旧字典与完整 CLI 输出均完全一致。 |
| 同形式 Python stdin 检查：读取计数、结构错误、额外坏文件 | 0 | 12 文件各读一次；10 个额外结构反例均点名文件并保留异常链；额外损坏文件未被忽略。 |

独立基线核验方法：通过 `subprocess.run(['git', 'archive', baseline], check=True, capture_output=True)` 获取指定提交，解压至 `TemporaryDirectory`；使用当前 uv 环境的 `sys.executable` 在该目录运行独立子进程，`sys.path` 指向该基线的 `src`，调用其 `calculate_bazi`、`analyze_wuxing`、`solar_to_lunar`、`format_bazi_output` 和 `cli.bazi_calculation`。读取本次夹具并断言其 `baseline` 字段；固定 `random.randint=1234`、`Console(width=100, color_system=None)` 和 Prompt 输入，逐一断言旧字典与完整 CLI 文本等值。检查以下三组：

- `1990-06-15 12:30 M`。
- `1988-09-20 23:15 F`。
- `2023-01-15 00:00 F`（立春前）。

该验证未使用新增分析函数或当前实现生成旧输出，排除了“新增夹具只与新代码互相证明”的问题。当前测试另对每个样例注入 2023／2028 年，移除新增节后与已核实夹具逐字比较。

独立结构补测方法：在导入前包装 `Path.read_text`，仅计数 `太岁_` 文件；依次导入三个入口，再执行 12 次分析。临时复制卯文件，依次设置记录为 null、年份条目为 null、年标签为 bool，以及地支字段为 `None`、`False`、`0`、`{}`、`['卯', None]`、`['卯', []]`、`['卯', '卯兔']`，均断言专用异常、实际路径和非空 `__cause__`。随后复制全部 12 份文件，并新增内容为 `{` 的 `太岁_额外损坏.json`，断言 `load_all` 拒绝且原因是 `JSONDecodeError`。所有变体仅在自动清理的临时目录中构造。

## 发现与建议

### S-01：展示测试可补独立固定行期望（P3，非阻断）

- 位置：`tests/test_tai_sui.py:209–224,254–259`。
- 现状：行测试检查解释、类别和组合的存在；CLI 新节精确期望则调用同一个 `format_tai_sui_section` 生成。若展示助手遗漏 `subtype` 或重排行，CLI 和期望会同步变化，现有测试可能漏报。已有断言也未直接检查将军姓名本身。
- 建议：为至少一个带自刑子类型的样例写固定 `list[tuple[str, str]]` 期望，直接检查姓名、子类型及行顺序；CLI 共用助手的集成断言可以保留。
- 严重程度依据：目前实现明确追加了将军姓名和子类型，并按规定顺序遍历，未发现实际展示错误；这是后续回归保护的弱点，不构成本次合入阻断。

## 审查快照与限制

本结论对应以下 SHA-256；后续若发生代码变化，应针对受影响内容重新审查：

```text
4fc1d05d4870fcfe2a095473c05bf2a5f782fa3f677f94fff95edab5de7ebd2c  src/cli.py
fea4c4697435b641e67399f1a53065b82eec813d64ba0c177b9f64a77114b7c6  src/utils/calendar_converter.py
fc7acac9b8003fda10f03ba9f440c0a91f4a3fc8ed51cf88f0a152d4ea9e20de  src/utils/tai_sui.py
0f296fbddbfff01ff717a09bff7b562c1c740e9393622081f46635d3bf019fe0  tests/test_tai_sui.py
84c571c8fa4cdd93c0f55b14ab91abbcfe9d0d2f1d572e2e8f11ae0edb533aa6  tests/fixtures/tai_sui_bazi_baseline.json
```

未进行完整领域算法交叉推导、全部年份组合穷举或民俗资料考据；这些不属于本次 Standards 轴。仅确认对项目资料的工程处理方式，不为民俗真实性背书。既有资料不一致与缺项不作修订，三合组关系不等于完整命盘成局。模块导入时坏数据会使导入失败，符合规格明确要求的严格加载，不记为本次兼容性缺陷。无未解决阻断项，也没有发生修复后复审；Spec／算法轴结论应查阅另一个独立 Reviewer 的实际记录。
