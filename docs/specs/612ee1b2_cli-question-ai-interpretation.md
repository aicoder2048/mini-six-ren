# 计划：非交互 CLI 增加 `--question` / `--model`（可选 AI 解读）

需求来源：本轮任务 prompt（为 `src/cli.py` 的非交互入口增加可选 AI 解读）。
基线：`master`，本次规划时工作树干净；本地已核实 `uv run python -m unittest discover -s tests` = **57 tests OK**。
相关约束：[`docs/specs/interpretation-experience.md`](../docs/specs/interpretation-experience.md)（本地结果先于 AI、失败不清除本地结果、失败以异常交给界面、Prompt 与 2400 token 预算不改）。
历史规格（不覆盖）：[`docs/specs/762559ac_cli-non-interactive-entry.md`](../docs/specs/762559ac_cli-non-interactive-entry.md)。

---

## 1. 目标（可验收行为）

| 调用 | 期望行为 |
|---|---|
| `--numbers 1,2,3` | 与现在**逐字相同**：仅本地三传表、stdout、退出码 0、stderr 为空、不构造 `DivinationAgent` |
| `--numbers 1,2,3 --question "近期求职"` | 先打印本地三传表，再打印 AI 解读；退出码 0 |
| `--numbers 1,2,3 --question "..." --model deepseek:deepseek-flash` | 用指定模型（`SupportedModels` 标识），走同一解读路径 |
| `--question` 缺省模型 | 取 `DivinationAgent.get_available_models()` 返回列表的**第一个** |
| `--question` 且无任何可用模型 | stdout 仍含本地三传；stderr 给出清晰提示；退出码非 0（`3`） |
| `--question` 且 AI 抛异常 | 本地三传已完整输出且不被清除；错误写 stderr；退出码非 0（`3`） |
| `--json --question`（成功） | JSON 在原 4 个键上增加 `question`、`interpretation`；stdout 仍是纯 JSON、stderr 空 |
| `--json --question`（AI 失败） | 原 4 键 + `question` + `interpretation:null` + `error`；stdout 仍是纯 JSON；退出码 `3` |

硬约束：

- **不修改** `src/ai_agent.py`（含 Prompt、`SupportedModels`、`DivinationAgent`）。
- 不改计算层：`HandTechnique.predict`、`format_prediction`、`resolve_numbers` 的映射、`get_relations`/`describe_relation`、历法与笔画字典一律不动。
- 不改 Rich 交互菜单：`select_llm_model`、`xiaoliu_submenu`、`display_divination_result` 保持原样。
- 无 `--question` 时行为与现在完全一致（纯本地、不调用 AI、不读密钥、不构造 Agent）。
- 现有 57 个测试**一行不改**且全绿。
- 新增/修改仅限：`src/cli.py`、`tests/test_cli_noninteractive.py`、`README.md`（+ 本计划文档）。

## 2. 现状核实（供 builder 对齐）

- `src/cli.py` 关键位置：`format_prediction`（表格渲染）、`build_parser`（`--numbers`/`--date`/`--chars` 互斥、`--time`、`--json`）、`resolve_numbers`、`build_json_payload`（4 个键：`input`/`symbols`/`relations`/`relation_descriptions`）、`run_batch`、`main`；模块级已有 `console`、`error_console = Console(stderr=True)`、`EXIT_SUCCESS/EXIT_INPUT_ERROR/EXIT_USAGE_ERROR = 0/1/2`，已 import `json`、`sys`、`Panel`、`Text`。
- 交互菜单 AI 路径（**不得改动，只作复用参照**）：
  `select_llm_model()` 以 `DivinationAgent.get_available_models()` 决定候选与 `SupportedModels.get_display_name(model)` 显示名；`xiaoliu_submenu()` 中为
  `interpretation = DivinationAgent(selected_model).interpret_prediction(result.symbols, question)`，
  失败时 `except Exception as exc: console.print(f'[red]AI解读失败：{exc}[/red]')`，本地结果已先输出、不被清除。
- `DivinationAgent.get_available_models()` 按 `SupportedModels` 定义顺序（`OPENAI_GPT56`, `DEEPSEEK_FLASH`）过滤有 API 密钥者；`interpret_prediction(symbols, question)` 内部用 `asyncio.run` + 流式 `Console()` 打印进度，**返回**格式化后的 markdown 文本（`### ` 标题保留）；密钥缺失时抛 `RuntimeError`。
- **重要事实（已实测）**：以脚本方式运行时 `load_dotenv()` 会按调用方文件位置向上找到项目根 `.env`，本机 `.env` 含真实密钥（实测 `DivinationAgent.get_available_models()` 返回 `[DEEPSEEK_FLASH]`）。因此**任何带 `--question` 的真实调用都会发起付费请求**——测试必须用离线替身，禁止把 `--question` 放进 subprocess 用例。
- 已实测：`contextlib.redirect_stdout(io.StringIO())` 能捕获 `ai_agent` 内部 `Console()`/`Live` 的输出（含进度行与最终帧），外部 stdout 保持干净。

## 3. 接口契约

### 3.1 新增参数（`build_parser`）

```python
parser.add_argument('--question', metavar='求问事项', default=None,
                    help='求问事项；给出时先打印本地三传，再调用 AI 解读（需要配置 API 密钥）')
parser.add_argument('--model', metavar='MODEL', default=None,
                    help='AI 模型标识（openai:gpt-5.6 或 deepseek:deepseek-flash）；缺省取第一个可用模型。'
                         '仅在给出 --question 时生效')
```

- `--question` 与 `--model` 不进入现有互斥组（与 `--json` 一样是正交修饰）。
- 取值先 `strip()`；**空串（或全空白）等价于未给出**（对齐交互菜单「留空跳过 AI」）。
- `--model` 只用 `SupportedModels` 的 `value` 标识，**不**接受显示名。
- `parser.description` 需更新为：「不带参数进入交互菜单；带参数做本地计算，给出 `--question` 时再调用 AI 解读。」

### 3.2 退出码

```
EXIT_SUCCESS = 0
EXIT_INPUT_ERROR = 1     # 值非法（沿用现状）
EXIT_USAGE_ERROR = 2     # 参数组合/取值错误
EXIT_AI_ERROR = 3        # 无可用模型 或 AI 调用失败（新增）
```

### 3.3 `main()` 分流（在现有分支上增补）

顺序（保持现有行为不变）：

1. `parse_args`；
2. `--date` 缺 `--time` / `--time` 无 `--date` → stderr `参数错误…` → `2`（原样）；
3. 三种输入模式全空：
   - 若 `args.as_json or args.question is not None or args.model is not None` →
     stderr `[bold red]参数错误：--json、--question 和 --model 需要与 --numbers、--date 或 --chars 之一一起使用。[/bold red]` → `2`
     （**必须保留 `参数错误` 字样**，现有测试断言该子串；`--json` 单独使用的行为与现在一致）；
   - 否则 `interactive_main()` → `0`（原样）；
4. `args.model is not None` 且不在 `SUPPORTED_MODELS_BY_VALUE` 中 →
   stderr `[bold red]参数错误：--model 只支持 openai:gpt-5.6、deepseek:deepseek-flash。[/bold red]` → `2`
   （沿用仓库既有约定：不用 `parser.error`，避免 `SystemExit` 难以在进程内断言）；
5. `return run_batch(args)`。

`--model` 在**没有** `--question` 时是**受校验但无副作用**的：不调用 AI、不查密钥，输出与现在逐字相同、退出码 0（这是「未给出 `--question` 时行为与现在完全一致」的直接推论；不做成报错，以免破坏该保证）。

### 3.4 文本模式输出（stdout）

- 无 `--question`：`console.print(format_prediction(prediction))` —— 一行不改。
- 有 `--question`：**完全相同的** `console.print(format_prediction(prediction))`，随后
  `console.print(Panel(Text(interpretation), title='AI三传解读', border_style='magenta'))`（与 `display_divination_result` 的 AI 面板标题/配色一致，复用同一 UI 语言）。
  由此得到可测性质：带 `--question` 的 stdout **以**不带时的 stdout 为前缀（本地渲染逐字不变）。
- AI 供应商内部的进度/流式输出（`ai_agent` 里的 `Console()`/`Live`）**不得进入本进程 stdout**：调用时用 `contextlib.redirect_stdout(io.StringIO())` 捕获后丢弃。理由：JSON 模式必须保持纯 JSON；文本模式下若放行流式输出，解读文本会在 stdout 出现两遍（交互路径目前即是如此），对可脚本化入口不可接受。非交互契约里不承诺进度提示。

### 3.5 JSON 模式输出（stdout）

`build_json_payload` 增加**可选**关键字参数，仅在给出 `question` 时追加字段（保证无 `--question` 时 payload 与现在完全相等、键序不变）：

```python
def build_json_payload(prediction, input_summary, question=None, interpretation=None, error=None):
    payload = { ...现有 4 个键... }
    if question is not None:
        payload['question'] = question
        payload['interpretation'] = interpretation
        if error is not None:
            payload['error'] = error
    return payload
```

- 成功：恰好 6 键（4 + `question` + `interpretation`），无 `error`。
- 失败（无可用模型 / AI 异常）：7 键，`interpretation` 为 `None`，`error` 为字符串（`str(exc)` 或固定提示）。
- 一次 `print(json.dumps(..., ensure_ascii=False, indent=2))`，失败时**也**输出该 JSON（本地结果必须在里头），随后返回 `3`。

### 3.6 错误流（stderr）

- AI 阶段任何失败（含无可用模型）统一：
  `error_console.print(f'[bold red]AI解读失败：{ai_error}[/bold red]')` → 返回 `EXIT_AI_ERROR`。
- 无可用模型的提示文案（模块常量，便于测试断言 `模型`）：

```python
NO_MODEL_MESSAGE = (
    '未配置可用的AI模型：请在 .env 中设置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY，'
    '或去掉 --question 仅做本地计算。'
)
```

- 显式 `--model` 但该密钥未配置：不预检，直接交给 `DivinationAgent(...).interpret_prediction`，由 `ai_agent` 抛出的
  `RuntimeError('未设置XXX_API_KEY环境变量，无法使用YYY')` 经 `str(exc)` 呈现到 stderr —— 提示同样清晰，且少一条分支。
- AI 失败时**不**向 stdout 追加任何文字。

## 4. 参考实现（`src/cli.py`）

### 4.1 顶部

新增 `import contextlib`、`import io`（其余不动）；新增：

```python
EXIT_AI_ERROR = 3

NO_MODEL_MESSAGE = (
    '未配置可用的AI模型：请在 .env 中设置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY，'
    '或去掉 --question 仅做本地计算。'
)

SUPPORTED_MODELS_BY_VALUE = {model.value: model for model in SupportedModels}
```

### 4.2 新函数

```python
def resolve_model(requested):
    """返回要使用的 SupportedModels；--model 缺省时取首个可用模型，无可用模型返回 None。"""
    if requested is not None:
        return SUPPORTED_MODELS_BY_VALUE[requested]   # main() 已校验取值
    available = DivinationAgent.get_available_models()
    return available[0] if available else None


def run_ai_interpretation(prediction, question, model):
    """复用交互菜单同一解读路径；AI 内部进度输出不进本进程 stdout。"""
    with contextlib.redirect_stdout(io.StringIO()):
        return DivinationAgent(model).interpret_prediction(prediction.symbols, question)
```

### 4.3 `run_batch` 重写为

```python
def run_batch(args):
    """非交互起课：本地计算必先完成；给出 --question 时才调用 AI。"""
    try:
        numbers, input_summary = resolve_numbers(args)
        prediction = HandTechnique.predict(*numbers)
    except ValueError as exc:
        error_console.print(f'[bold red]输入错误：{exc}[/bold red]')
        return EXIT_INPUT_ERROR

    question = (args.question or '').strip() or None
    interpretation = None
    ai_error = None
    if question is not None:
        model = resolve_model(args.model)
        if model is None:
            ai_error = NO_MODEL_MESSAGE
        else:
            try:
                interpretation = run_ai_interpretation(prediction, question, model)
            except Exception as exc:
                ai_error = str(exc)

    if args.as_json:
        print(json.dumps(
            build_json_payload(prediction, input_summary,
                               question=question, interpretation=interpretation, error=ai_error),
            ensure_ascii=False, indent=2))
    else:
        console.print(format_prediction(prediction))
        if interpretation is not None:
            console.print(Panel(Text(interpretation), title='AI三传解读', border_style='magenta'))

    if ai_error is not None:
        error_console.print(f'[bold red]AI解读失败：{ai_error}[/bold red]')
        return EXIT_AI_ERROR
    return EXIT_SUCCESS
```

注意：`question is None` 时**不调用** `resolve_model`，因此 `get_available_models()` 与 `DivinationAgent` 都不会被触碰（无 `--question` = 零 AI 副作用）。

### 4.4 保持不变的公共名字

`console`、`error_console`、`Console`、`Prompt`、`format_prediction`、`display_divination_result`、`select_llm_model`、`xiaoliu_submenu`、`tools_submenu`、`bazi_calculation`、`stroke_count_calculation`、`main`、`HandTechnique`、`describe_relation` —— 现有测试的 patch 目标，禁止重命名/删除。

## 5. 测试计划（`tests/test_cli_noninteractive.py` 追加，现有 16 个用例不动）

**安全前提（必须遵守）**：所有 `--question` 用例都在进程内、并 patch 整个 `cli.DivinationAgent`（含 `get_available_models`），使真实付费请求在结构上不可能发生；**不新增任何带 `--question` 的 subprocess 用例**（`.env` 里有真实密钥）。subprocess 只用于「不进入 AI 阶段」的用法/取值错误。

新增辅助（模块级）：

```python
from ai_agent import SupportedModels   # 只读复用，不修改 ai_agent.py

def offline_agent(models=(SupportedModels.DEEPSEEK_FLASH,), interpretation='【离线替身解读】', error=None):
    """离线 AI 替身：patch cli.DivinationAgent 用，绝不发起网络请求。"""
    agent = Mock()
    agent.get_available_models.return_value = list(models)
    if error is not None:
        agent.return_value.interpret_prediction.side_effect = error
    else:
        agent.return_value.interpret_prediction.return_value = interpretation
    return agent
```

`run_cli`（现有辅助）与 `redirect_stdout/redirect_stderr` 继续沿用。

新测试类 `NonInteractiveQuestion(unittest.TestCase)`：

1. `test_question_prints_local_table_then_interpretation`：`--numbers 1,2,3 --question 近期求职`（离线替身）→ `code == 0`；stdout 同时含 `大安` 与 `【离线替身解读】`；`stdout.index('大安') < stdout.index('【离线替身解读】')`；stderr 为空。
2. `test_interpretation_receives_symbols_and_question`：断言 `instance.interpret_prediction.call_args[0][0]` 的符号名依次为 `大安/留连/赤口`（按领域规则手写字面量），`call_args[0][1] == '近期求职'`。
3. `test_default_model_is_first_available`：`get_available_models` 返回 `[DEEPSEEK_FLASH, OPENAI_GPT56]` → 断言 `cli.DivinationAgent` 以 `SupportedModels.DEEPSEEK_FLASH` 调用（列表首个，不是枚举首个）。
4. `test_explicit_model_is_used`：`--model deepseek:deepseek-flash --question x` → 构造参数为 `SupportedModels.DEEPSEEK_FLASH`；再断言 `get_available_models` 未被调用（给出 `--model` 时不做可用性探测）。
5. `test_model_without_question_stays_local_only`：`--numbers 1,2,3 --model deepseek:deepseek-flash` → `code == 0`、stdout 与 `--numbers 1,2,3` 的 stdout **完全相等**、`agent_mock.assert_not_called()`。
6. `test_invalid_model_exits_usage_error`：`--numbers 1,2,3 --model not-a-model` → `code == 2`、stdout 为空、stderr 含 `参数错误` 与 `--model`。
7. `test_question_without_input_mode_exits_usage_error`：`['--question','近期求职']` → `code == 2`、stdout 为空、stderr 含 `参数错误`、`DivinationAgent` 未被构造；`['--model','deepseek:deepseek-flash']` 同断言。
8. `test_blank_question_stays_local_only`：`--numbers 1,2,3 --question '   '` → `code == 0`、stdout 与不带 `--question` 时完全相等、替身未被构造；再断言 `--json --question '  '` 的 payload 与现有 4 键字面量**相等**（不多 `question`/`interpretation`）。
9. `test_no_available_model_with_question_exits_three`：替身 `models=[]` → `code == 3`；stdout 仍含 `大安`（本地三传保留）；stderr 含 `模型`；`agent_mock.assert_not_called()`（没有可用模型时不得构造客户端）。
10. `test_no_available_model_json_payload`：`--json --question x`，`models=[]` → `code == 3`；`json.loads(stdout)` 成功；`payload['interpretation'] is None`；`payload['error']` 非空；`payload['question'] == 'x'`；`[s['name'] for s in payload['symbols']] == ['大安','留连','赤口']`、`payload['relations'] == ['比和','被克']`。
11. `test_ai_failure_keeps_local_result_text`：替身 `error=RuntimeError('provider down')` → `code == 3`；stdout 含本地表格片段（`大安`、`金克木，后传克前传`）且不含替身解读文本；stderr 含 `AI解读失败` 与 `provider down`。
12. `test_ai_failure_keeps_local_result_json`：同上加 `--json` → `code == 3`；`json.loads(stdout)` 成功；`interpretation is None`、`error` 含 `provider down`；`relations`/`relation_descriptions` 与无 AI 时相同（证明确实未被清除）。
13. `test_json_with_question_success_adds_two_fields`：`--json --question 近期求职` → `code == 0`；`set(payload) == {'input','symbols','relations','relation_descriptions','question','interpretation'}`；`payload['interpretation'] == '【离线替身解读】'`；`payload['question'] == '近期求职'`；stderr 为空。
14. `test_ai_progress_output_never_reaches_stdout`：替身 `interpret_prediction` 先 `print('PROGRESS-CHATTER')` 再返回解读文本（模拟 `ai_agent` 的流式打印）→ JSON 模式：`json.loads(stdout)` 成功且 `'PROGRESS-CHATTER' not in stdout`；文本模式：`'PROGRESS-CHATTER' not in stdout` 且 `stdout.count('【离线替身解读】') == 1`（解读只出现一次）。
15. `test_question_stdout_keeps_local_prefix`：分别捕获不带 `--question` 与带 `--question`（离线替身成功）的 stdout，断言后者 `startswith` 前者（本地渲染逐字不变）。
16. `NonInteractiveSubprocess` 追加两条**安全**用例（不进入 AI 分支）：
    - `--numbers 1,2,3 --model not-a-model` → `returncode == 2`，stdout 为空，stderr 含 `参数错误`；
    - `--question 近期求职`（无输入模式）→ `returncode == 2`，stdout 为空。
    并在类注释里写明：`--question` + 输入模式的端到端调用会使用 `.env` 真实密钥，故只做进程内替身验证。

期望结果：现有 57 个用例保持不改动、全绿；新增后总数约 73。

## 6. `README.md` 改动（「CLI 非交互 / 脚本调用」小节，约第 226–260 行）

1. 示例代码块追加：

```bash
# 可选 AI 解读：先打印本地三传，再输出解读（需在 .env 配置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY）
uv run src/cli.py --numbers 1,2,3 --question "近期求职"

# 指定模型（取值为 SupportedModels 标识；缺省用第一个可用模型）
uv run src/cli.py --numbers 1,2,3 --question "近期求职" --model deepseek:deepseek-flash

# AI 解读同时保留结构化输出；失败时 interpretation 为 null 并给出 error
uv run src/cli.py --numbers 1,2,3 --question "近期求职" --json
```

2. 说明列表：把现有那条「非交互路径只做本地计算，不调用 AI、不发起任何网络请求。」**改为**：

- 不带 `--question` 时非交互路径只做本地计算，不调用 AI、不发起任何网络请求（行为与之前逐字相同）。
- 给出 `--question` 时，先完整打印本地三传，再调用 AI 解读并输出；解读复用交互菜单同一路径（同一 Prompt、同一 2400 token 预算）。
- `--model` 取值为 `SupportedModels` 的模型标识（`openai:gpt-5.6`、`deepseek:deepseek-flash`）；缺省取 `DivinationAgent.get_available_models()` 的第一个可用模型；未给出 `--question` 时 `--model` 不影响输出。
- `--question` 空白，或未与 `--numbers/--date/--chars` 一起使用，分别等价于「不使用 AI」与参数错误。
- 退出码表：`0` 成功；`1` 输入值非法；`2` 参数组合/取值错误；`3` 无可用模型或 AI 调用失败。
- AI 失败时本地三传仍完整输出、不被清除，错误写 stderr；`--json` 失败时 stdout 仍是纯 JSON（`interpretation: null`，另有 `error` 字符串）。
- 解读生成期间不打印流式进度，stdout 只保留最终结果（便于管道/重定向）；文本模式下解读只出现一次。

3. 「运行应用 → CLI版本」代码块追加一行 `# 非交互 + AI 解读：uv run src/cli.py --numbers 1,2,3 --question "近期求职"`，指回该小节。

## 7. 验证

```bash
# 全套测试（验收命令，含现有 57 个用例）
uv run python -m unittest discover -s tests -v

# 本地行为逐字不变（关键回归）
uv run src/cli.py --numbers 1,2,3
uv run src/cli.py --numbers 1,2,3 --json | python -c 'import json,sys; json.load(sys.stdin)'

# 用法/取值错误（不触碰 AI，安全）
uv run src/cli.py --numbers 1,2,3 --model not-a-model; echo "exit=$?"   # 2
uv run src/cli.py --question "近期求职"; echo "exit=$?"                  # 2

# AI 路径的离线替身冒烟（禁止直接跑真实 --question：.env 有真实密钥会付费）
uv run python -c "
import sys, json; sys.path.insert(0, 'src')
from unittest.mock import Mock, patch
import cli
from ai_agent import SupportedModels
agent = Mock(); agent.get_available_models.return_value = [SupportedModels.DEEPSEEK_FLASH]
agent.return_value.interpret_prediction.return_value = '### 一句话判断\n离线替身解读示例'
with patch('cli.DivinationAgent', agent):
    print('ok-question exit=', cli.main(['--numbers','1,2,3','--question','近期求职']))
    print('json exit=', cli.main(['--numbers','1,2,3','--question','近期求职','--json']))
agent.return_value.interpret_prediction.side_effect = RuntimeError('provider down')
with patch('cli.DivinationAgent', agent):
    print('fail exit=', cli.main(['--numbers','1,2,3','--question','近期求职']))  # 3
with patch('cli.DivinationAgent', Mock(get_available_models=Mock(return_value=[]))):
    print('no-model exit=', cli.main(['--numbers','1,2,3','--question','近期求职']))  # 3
"

# 仓库级检查
uv lock --locked
git diff --check
```

预期：测试全绿；上面四个替身调用的退出码依次为 `0 / 0 / 3 / 3`，且 `no-model` 那次 stdout 仍打印本地三传、stderr 有提示。

## 8. 不做的事（Out of scope）

- 不修改 `src/ai_agent.py`、Prompt 文本、`INTERPRETATION_MAX_TOKENS`、`SupportedModels` 成员与显示名。
- 不实现流式/实时输出、进度条、`--question` 的 stdin 输入、`--question-file`、历史记录、日志、`--model` 的显示名别名。
- 不改 Rich 交互菜单（`xiaoliu_submenu`/`select_llm_model`/`display_divination_result`）、Web 界面、其它子菜单。
- 不改计算与映射：`HandTechnique.predict`、`get_relations`/`describe_relation`、`validate_*`、`date_to_numbers`、`get_stroke_counts`。
- 不新增/升级依赖（不用 `openai`、`pytest` 等；仅用标准库 `contextlib`/`io`）。
- 不改动现有 57 个测试；不改 `docs/specs/interpretation-experience.md` 等既有规格（只新增本计划文档）。

## 9. 风险与注意点

- **真实付费请求**：`.env` 含真实密钥，脚本方式运行会经 `load_dotenv()` 读到。任何带 `--question` 的自动化验证都必须用替身；不要写 `--question` 的 subprocess 用例，也不要手工直接跑真实 `--question`。
- **JSON 纯净性**：`interpretation` 之外，`ai_agent` 的进度/流式打印必须被 `redirect_stdout` 捕获丢弃；这一条有测试 14 兜底。若将来 `ai_agent` 改为向 stderr 打印，JSON 仍纯净，但文本模式的 stdout 也仍只含表格 + 面板。
- **Rich 宽度**：断言只用短子串（`大安`、`金克木`、替身文案），不要断言整行宽度或 ANSI；测试沿用 `redirect_stdout`（非终端宽度 80）。
- **`build_json_payload` 兼容**：新增参数必须带默认值且仅在有 `question` 时加键，否则 `test_numbers_json_structure` 的整字典相等断言会失败。
- **`--json` 单独使用**：`test_usage_errors_exit_with_code_two` 断言 stderr 含 `参数错误`；新合并分支的文案必须保留该子串。
- **`--model` 无 `--question`**：定为「受校验、无副作用」，不要顺手改成报错或警告（会破坏「与现在完全一致」）。
- **`question.strip()`**：空串/全空白等价于未给出；JSON payload 不得出现 `question` 键。
- **`asyncio.run`**：`interpret_prediction` 在同步 CLI 中运行安全；失败一律 `except Exception`（含 `RuntimeError`）→ `EXIT_AI_ERROR`，不把错误文本当解读。
- **公共符号**：重构 `main`/`run_batch` 时保留第 4.4 节列出的所有名字（现有测试 patch 目标）。

## 10. 复核要求说明

本次变更是**入口参数与输出契约的新增**，并复用既有 AI 调用路径：不改公式、历法/时区/换日规则、输入映射、笔画字典、关系计算与 Prompt 事实。按 `AGENTS.md`「算法变更的独立复核」的判定，**不构成算法变更，不需要独立算法 Reviewer**。

边界：若实施过程中不得不同意改动 `ai_agent.py`、Prompt、`HandTechnique.predict`、`get_relations`/`describe_relation`、`validate_*`、`date_to_numbers`、`get_stroke_counts` 或 `symbols.json` 中任何一项，即升级为算法/规格变更：必须先停下，按 `AGENTS.md` 委派未参与实现的独立 Agent Reviewer 复核后再报告完成；本计划不授权这类改动。

建议的独立复核内容（供流程中的 Spec/Standards Reviewer）：用离线替身独立验证 8 条验收行为、退出码 `0/1/2/3` 语义、`--json` 纯净性与失败时本地结果完整保留，并确认无 `--question` 时输出与基线逐字相同（可用 `git stash` + 基线 `cli.py` 对比 stdout 字节）。
