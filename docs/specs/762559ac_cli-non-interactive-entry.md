# 计划：`src/cli.py` 非交互命令行入口（argparse）

需求来源：`docs/specs/feature-proposals.md`「提案 2：CLI 非交互 / 可脚本化调用」（第 50–77 行）。
基线：`master`（本次规划时 HEAD 为 `1a9edd7`）。

## 1. 目标

在保留「不带参数 → 原有 Rich 交互菜单」这一默认行为的前提下，给 CLI 增加可脚本化的参数入口：

| 参数 | 语义 |
|---|---|
| `--numbers 1,2,3` | 三个 1–999 整数，逗号分隔，直接起课 |
| `--date 2026-09-17 --time 14:00` | 北京时间（UTC+8），走共享的 `utils.calendar_converter.date_to_numbers` |
| `--chars 天地人` | 恰好三个汉字，走 `utils.validation.validate_chinese` + `utils.stroke_count.get_stroke_counts` |
| `--json` | 输出结构化 JSON（符号名、五行、关系、方向说明 + 输入快照） |

约束（验收硬条件）：

- 文本模式输出与 `format_prediction` 渲染的内容一致（同一函数渲染，不另写一份文本）。
- 成功退出码 `0`；非法参数（越界数字、错误日期、非汉字、缺 `--time` 等）退出码非 `0`，错误信息清晰且写到 **stderr**。
- `--json` 的 stdout 必须是**纯 JSON 文档**，可直接 `json.loads(stdout)`。
- 不带参数运行仍进入原有交互菜单，现有测试（`tests/test_regressions.py`、`tests/test_interpretation_experience.py`、`tests/test_web_themes.py`）全部保持通过。
- 非交互路径**不构造 `DivinationAgent`、不调用 `select_llm_model`、不发起任何网络请求**，也不 `chdir`、不清屏、不打横幅。

## 2. 现状（已核实）

- `src/cli.py`（512 行）
  - 顶部已 import：`utils.validation` 的 `parse_datetime/normalize_gender/validate_numbers/validate_chinese`、`utils.calendar_converter` 的 `date_to_numbers`（第 1–17 行）。
  - `format_prediction(result)`（第 27–59 行）返回 Rich `Table`，表体含符号名与五行，表体内含 `Prediction.relations` 原值（比和/生/克/被生/被克），表 caption 为两段 `describe_relation(...)` 方向说明。**不要改动它。**
  - `main()`（第 325–338 行）：清屏 → 彩标题 → 主菜单循环，取值为 `get_menu_choice(...)`。
  - 文件末尾：`if __name__ == "__main__": set_current_working_dir(); main()`（第 510–512 行）；`set_current_working_dir()`（第 489–505 行）会 `chdir` 到项目根目录并 `console.print` 一行横幅。
  - 模块级 `console = Console()` 出现两次（约第 25 行、第 323 行）。保留现状即可（避免无关改动），`tests/test_interpretation_experience.py` 会 patch `cli.console` 与 `cli.Console`。
- `src/hand_technique.py`：`HandTechnique.predict(n1, n2, n3) -> Prediction(symbols, relations)`，纯函数，内部复用 `validate_numbers`，不触碰 AI/UI。
- `src/utils/symbol_relations.py`：`describe_relation(first, second, relation)` 给出方向说明（如 `金克木，后传克前传`）。
- `data/symbols.json` 为 **9 个符号**的九宫环：`大安(木) 留连(木) 速喜(火) 赤口(金) 小吉(水) 空亡(土) 病符(土) 桃花(土) 天德(金)`；`predict` 为 `position = (position + n - 1) % 9` 的累加。
- 数据加载路径全部相对模块文件（`Path(__file__).resolve().parents[...]`），因此非交互路径不需要 `chdir`。
- `import cli` 无网络副作用（`ai_agent` 只在实例化 `DivinationAgent` 时才 `load_dotenv`/建 `Agent`）。
- 现有测试均 `sys.path.insert(0, .../src)` 后 `import cli`；新测试沿用同一模式。

已实测的期望值（供测试硬编码，不要用「再跑一遍 `predict`」来生成期望）：

| 输入 | 起课数字 | 符号 / 五行 | 关系 | 方向说明 |
|---|---|---|---|---|
| `--numbers 1,2,3` | 1,2,3 | 大安(木)、留连(木)、赤口(金) | 比和、被克 | `同属木，性质相近`、`金克木，后传克前传` |
| `--date 2026-09-17 --time 14:00` | 8,7,8（农历八月七日、未时编号 8） | 桃花(土)、小吉(水)、速喜(火) | 克、克 | `土克水，前传克后传`、`水克火，前传克后传` |
| `--chars 天地人` | 4,6,2（字典笔画 天4/地6/人2） | 赤口(金)、天德(金)、大安(木) | 比和、克 | `同属金，性质相近`、`金克木，前传克后传` |

（`describe_relation` 关系名以左传为主语；`--date` 的时辰编号规则为 `(hour + 1) % 24 // 2 + 1`，与交互路径和 Web 完全一致。）

## 3. 接口契约（builder 按此实现，不再自行裁量）

### 3.1 参数解析

用 `argparse`，`prog='cli.py'`：

- 互斥组（`add_mutually_exclusive_group()`）：`--numbers`、`--date`、`--chars`，均为字符串选项。
- `--time`：独立选项，默认 `None`，仅与 `--date` 搭配。
- `--json`：`action='store_true'`，`dest='as_json'`（避免与 `import json` 混淆）。
- 两个入口函数：`build_parser() -> ArgumentParser`、`main(argv=None) -> int`。

### 3.2 分流与退出码

```
EXIT_SUCCESS = 0
EXIT_INPUT_ERROR = 1     # 值非法：越界数字、错误日期时间、非汉字、字典缺字
EXIT_USAGE_ERROR = 2     # 参数组合错误：--date 缺 --time、--time 无 --date、--json 无输入模式
```

`main(argv=None)` 流程：

1. `args = build_parser().parse_args(argv)`（未知参数、`--numbers` 缺值等由 argparse 自己 `SystemExit(2)`，保持默认）。
2. `args.date is not None and args.time is None` → stderr 打印「参数错误：使用 --date 时必须同时提供 --time（格式 HH:MM）。」→ `return 2`。
3. `args.time is not None and args.date is None` → stderr 打印「参数错误：--time 只能与 --date 一起使用。」→ `return 2`。
4. 三种输入模式全为 `None` 且 `args.as_json` → stderr 打印「参数错误：--json 需要与 --numbers、--date 或 --chars 之一一起使用。」→ `return 2`。
5. 三种输入模式全为 `None`（且未给 `--json`）→ `interactive_main()` → `return 0`（原有交互菜单）。
6. 否则 → `return run_batch(args)`。

注意：`parser.error(...)` 会抛 `SystemExit`，不便在进程内测试；上面 2–4 一律用「打印到 stderr + 返回 `2`」实现。

### 3.3 输出与错误流

- 正常结果只写 **stdout**：文本模式 `console.print(format_prediction(prediction))`；JSON 模式 `print(json.dumps(payload, ensure_ascii=False, indent=2))`。
- 文本模式**不额外**回显「本次输入 / 起课数字」（保持「与 `format_prediction` 一致的文本」，并让 stdout 干净；输入快照在 JSON 模式的 `input` 字段里可见）。`format_prediction` 的 caption 已包含两段方向说明。
- 错误只写 **stderr**：新增模块级 `error_console = Console(stderr=True)`，错误信息用 `error_console.print('[bold red]输入错误：{exc}[/bold red]')`。错误路径 stdout 必须为空（这样 `--json` 失败时不会有半截 JSON）。
- 非交互路径不调用 `clear_screen()`、`set_current_working_dir()`、`display_colorful_title()`。

### 3.4 JSON schema

字段与 `Prediction`（`symbols` / `relations`）同名对齐，并要求包含符号名、五行、关系、方向说明：

```json
{
  "input": {"mode": "numbers", "numbers": [1, 2, 3]},
  "symbols": [
    {"name": "大安", "element": "木"},
    {"name": "留连", "element": "木"},
    {"name": "赤口", "element": "金"}
  ],
  "relations": ["比和", "被克"],
  "relation_descriptions": ["同属木，性质相近", "金克木，后传克前传"]
}
```

- `symbols` 顺序 = 初传、中传、末传；`relations` 长度 2，第 i 项为 `symbols[i] → symbols[i+1]`。
- `relation_descriptions[i] = describe_relation(symbols[i], symbols[i+1], relations[i])`。
- `input` 按模式取值：
  - numbers：`{"mode": "numbers", "numbers": [1,2,3]}`（`validate_numbers` 归一化后的整数列表）
  - date：`{"mode": "date", "date": "2026-09-17", "time": "14:00", "numbers": [8,7,8]}`
  - chars：`{"mode": "chars", "chars": "天地人", "numbers": [4,6,2]}`（`chars` 为 `validate_chinese` 去分隔符后的字符串）
- 顶层不新增其它键；不加时间戳、不加日志、不加 AI 字段。

## 4. 实施步骤

### 步骤 1：`src/cli.py`

只做「新增解析/分流 + 抽取交互主体」，不改任何计算、渲染、菜单函数。

1. 顶部新增 `import argparse`、`import json`、`import sys`（`re/os/random/datetime` 等保持不动）。
2. 在模块级 `console` 附近新增：

   ```python
   EXIT_SUCCESS = 0
   EXIT_INPUT_ERROR = 1
   EXIT_USAGE_ERROR = 2

   error_console = Console(stderr=True)
   ```

3. 新增 `build_parser()`：按 §3.1 定义三个互斥输入选项、`--time`、`--json`；`description` 写明「不带参数进入交互菜单，带参数只做本地起课、不调用 AI」。
4. 新增 `resolve_numbers(args) -> tuple[list[int], dict]`（非法输入抛 `ValueError`，由调用方转换退出码）：

   ```python
   def resolve_numbers(args):
       if args.numbers is not None:
           numbers = validate_numbers(args.numbers.split(','))
           return numbers, {'mode': 'numbers', 'numbers': numbers}
       if args.date is not None:
           numbers = date_to_numbers(args.date, args.time)
           return numbers, {'mode': 'date', 'date': args.date, 'time': args.time, 'numbers': numbers}
       chars = validate_chinese(args.chars)
       numbers = get_stroke_counts(chars)
       return numbers, {'mode': 'chars', 'chars': chars, 'numbers': numbers}
   ```

   （`--numbers` 只按 ASCII 逗号切分，与交互路径 `numbers_input.split(',')` 保持一致；`validate_numbers`/`validate_chinese` 会自行报错。）

5. 新增 `build_json_payload(prediction, input_summary) -> dict`，按 §3.4 组装；方向说明用 `describe_relation`，长度按 `len(prediction.relations)` 生成。
6. 新增 `run_batch(args) -> int`：

   ```python
   def run_batch(args):
       try:
           numbers, input_summary = resolve_numbers(args)
           prediction = HandTechnique.predict(*numbers)
       except ValueError as exc:
           error_console.print(f'[bold red]输入错误：{exc}[/bold red]')
           return EXIT_INPUT_ERROR
       if args.as_json:
           print(json.dumps(build_json_payload(prediction, input_summary), ensure_ascii=False, indent=2))
       else:
           console.print(format_prediction(prediction))
       return EXIT_SUCCESS
   ```

7. 把现有 `main()` 的函数体原样搬进新的 `interactive_main()`，并在其**最开头**保留 `set_current_working_dir()`（顺序与今天一致：`set_current_working_dir()` → `clear_screen()` → `display_colorful_title()` → 菜单循环），函数体不加其它改动。
8. 新写 `main(argv=None) -> int` 实现 §3.2 的分流；`--json` 模式不触发交互分支。
9. 文件末尾改为：

   ```python
   if __name__ == "__main__":
       sys.exit(main())
   ```

   （`set_current_working_dir()` 已移入 `interactive_main()`，因此 `--numbers ...` 这类调用不再 `chdir`、不打印横幅。）

保持这些公共名字不变：`console`、`Console`、`format_prediction`、`display_divination_result`、`xiaoliu_submenu`、`tools_submenu`、`bazi_calculation`、`stroke_count_calculation`、`main`、`HandTechnique`、`describe_relation`（现有测试的 patch 目标）。

### 步骤 2：`tests/test_cli_noninteractive.py`（新增）

文件头沿用现有风格：`sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))`，`import cli`，`import unittest`。

辅助手段：
- 捕获输出用 `contextlib.redirect_stdout(io.StringIO())` / `redirect_stderr(io.StringIO())` —— 模块级 `console = Console()` 在写入时动态解析 `sys.stdout`，`redirect_stdout` 对文本与 JSON 两条路径都有效（已实测：非终端宽度 80，caption 不折行）。
- 需要交互分流的用例一律 `patch('cli.interactive_main', Mock())`，**不要**真的进入菜单循环（`get_menu_choice` 返回 `'q'` 时会 `exit()`，直接调用会挂住或误退出）。

用例（每条都是可独立验收的行为，不依赖实现自身的输出作为期望）：

1. 交互保留：`patch('cli.interactive_main')` → `cli.main([])` 返回 `0` 且 mock 被调用一次；`cli.main(['--numbers','1,2,3'])` 返回 `0` 且 mock 未被调用。
2. 非交互不碰 AI：`patch` 掉 `cli.interactive_main`、`cli.DivinationAgent`、`cli.select_llm_model`、`cli.get_menu_choice`、`cli.Prompt.ask`，对三种模式各跑一次，断言全部 mock 未被调用（`DivinationAgent` 的 mock 构造即失败也可）。
3. 数字文本输出：`main(['--numbers','1,2,3']) == 0`；stdout 同时包含 `大安`、`留连`、`赤口`、（木）、（金）、`比和`、`被克`、`同属木，性质相近`、`金克木，后传克前传`。
4. `--json` 数字结构：`main(['--numbers','1,2,3','--json']) == 0`，`json.loads(stdout)` 等于 §3.4 的完整字典（逐字段 `assertEqual`，含 `input.mode == 'numbers'`、`relations == ['比和','被克']`）。
5. `--json` stdout 纯净：整个 stdout 能被 `json.loads` 解析一次成功（证明没有横幅/菜单/提示混入），且 stdout 中不含 `欢迎使用`。
6. 日期走共享换算：`main(['--date','2026-09-17','--time','14:00','--json'])`，`payload['input'] == {'mode':'date','date':'2026-09-17','time':'14:00','numbers':[8,7,8]}`，`[s['name'] for s in payload['symbols']] == ['桃花','小吉','速喜']`（字面量，来自农历八月七日 + 未时编号规则）。
7. 汉字走笔画字典：`main(['--chars','天地人','--json'])`，`input['numbers'] == [4,6,2]`，符号名为 `['赤口','天德','大安']`；再断言 `--chars 天,地,人` 得到相同 payload（`validate_chinese` 去分隔符）。
8. 非法数字 → `1`：分别覆盖 `0,2,3`、`1000,2,3`、`1,2`、`1,2,3,4`、`1.5,2,3`、`a,2,3`；断言返回值 `== 1`、stderr 含 `输入错误`、stdout 为空。额外一条：`['--numbers=-1,2,3']` → `1`（`=` 形式让 argparse 把负号当值；空格形式 `--numbers -1,2,3` 由 argparse 退出 `2`，属可接受行为，不必测）。
9. 非法日期 → `1`：`2026-02-30 12:00`、`1899-01-01 12:00`、`2026/09/17 12:00`、`2026-09-17 25:00`。
10. 非法汉字 → `1`：`abc`、`天地`、`天地人四`。
11. 参数组合 → `2`：`['--date','2026-09-17']`、`['--time','14:00']`、`['--json']`；断言 stderr 有说明、stdout 为空。
12. 真实进程退出码（subprocess，`cwd` = 项目根，`env=os.environ | {'PYTHONIOENCODING': 'utf-8'}`，`text=True, encoding='utf-8'`，命令 `[sys.executable, 'src/cli.py', ...]`）：
    - `--numbers 1,2,3 --json` → `returncode == 0`，`json.loads(stdout)` 成功；
    - `--numbers 0,2,3` → `returncode == 1`，stdout 为空，stderr 含 `1-999`；
    - `--chars abc` → `returncode == 1`；
    - `--date 2026-09-17` → `returncode == 2`。
13. 不改动现有测试文件；`tests/test_regressions.py` 中 `cli.xiaoliu_submenu`/`cli.console`/`cli.HandTechnique.predict` 的 patch 目标必须继续有效（步骤 1 已要求保留）。

### 步骤 3：`README.md`

在「使用示例 → 小六壬占卜示例 → CLI版本示例」（现第 204 行附近，交互示例代码块之后）新增一段 `#### CLI 非交互 / 脚本调用`，内容：

- 四条命令示例（`--numbers`、`--date --time`、`--chars`、`--numbers --json`）。
- 一段说明：不带参数仍进入原有交互菜单；非交互路径只做本地计算，不调用 AI、不发起网络请求；错误信息输出到 stderr 且退出码非 0（`1` 输入非法、`2` 参数组合错误）；`--time` 必须与 `--date` 一起；`--json` 的 stdout 只有 JSON。
- 一段 `--numbers 1,2,3 --json` 的示例输出（即 §3.4 的 JSON）。
- 在「运行应用 → CLI版本（命令行界面）」（现第 64–69 行）的代码块里补一行 `# 非交互：uv run src/cli.py --numbers 1,2,3 --json`，并指向上面的小节。

只在 README 补充，不新建文档。

## 5. 验证

```bash
# 全套测试（验收命令）
uv run python -m unittest discover -s tests -v

# 手工冒烟：成功路径
uv run src/cli.py --numbers 1,2,3
uv run src/cli.py --numbers 1,2,3 --json
uv run src/cli.py --date 2026-09-17 --time 14:00 --json
uv run src/cli.py --chars 天地人 --json

# 手工冒烟：失败路径，退出码应为 1 / 1 / 1 / 2
uv run src/cli.py --numbers 0,2,3; echo "exit=$?"
uv run src/cli.py --date 2026-02-30 --time 12:00; echo "exit=$?"
uv run src/cli.py --chars abc; echo "exit=$?"
uv run src/cli.py --date 2026-09-17; echo "exit=$?"

# stdout 必须是纯 JSON
uv run src/cli.py --numbers 1,2,3 --json | python -c 'import json,sys; json.load(sys.stdin)'

# 不带参数仍进入交互菜单（人工确认后按 q 退出）
uv run src/cli.py

# 仓库级检查
uv lock --locked
git diff --check
```

预期：`--numbers 1,2,3` 文本含 `大安/留连/赤口/比和/被克`；`--json` 输出可被 `json.loads` 解析且字段与 §3.4 一致；全部测试绿。

## 6. 不做的事（Out of scope）

- 日志、历史记录、配置文件、`--version`、`--verbose`。
- AI 解读、任何网络请求、`.env` 读取（非交互路径）。
- 替换/改动 Rich 交互菜单、`format_prediction`、`xiaoliu_submenu` 的分支逻辑与显示。
- Web 界面、可复现链接（提案 3）、复制/导出（提案 1）。
- 计算层改动：`HandTechnique.predict`、`get_relations`/`describe_relation`、`validate_*`、`date_to_numbers`、笔画字典一律不改。

## 7. 风险与注意点

- **Rich 与重定向**：非终端下 `Console()` 宽度 80，caption 两行不折行（已实测 `同属木，性质相近`、`金克木，后传克前传` 完整出现）。测试断言用短子串（符号名、五行、`比和`/`被克`、`同属木`、`金克木`），不要断言整行宽度或颜色转义。不要用 `Console(force_terminal=True)` 的捕获结果做断言（会带 ANSI）。
- **不要 `chdir`**：非交互路径跳过 `set_current_working_dir()`；数据加载已按模块绝对路径定位（`stroke_count`/`symbols`/`five_elements`），从任意 cwd 调用都可用。
- **不要进入菜单**：任何进程内测试都必须 patch `cli.interactive_main`；真实进入菜单会阻塞（`Prompt.ask`）或触发 `exit()`。
- **argparse 的默认退出**：未知选项、`--numbers` 缺值、`--numbers -1,2,3`（负号被当选项）会由 argparse 直接 `SystemExit(2)`，这是可接受的非零退出；只有 §3.2 的第 2–4 条走我们自己的 `return 2`。
- **编码**：subprocess 测试显式传 `PYTHONIOENCODING=utf-8` 与 `encoding='utf-8'`，避免非 UTF-8 locale 下中文表头乱码导致断言抖动。
- **公共符号名**：现有两个测试文件 patch 了 `cli.console`、`cli.Console`、`cli.Prompt.ask`、`cli.get_menu_choice`、`cli.HandTechnique.predict`、`cli.calculate_bazi`、`cli.DivinationAgent.get_available_models`、`cli.display_divination_result`，重构 `main` 时不得重命名或删除这些名字。

## 8. 复核要求说明

本次变更是**入口与输出格式**的新增，不改任何计算公式、历法/时区规则、笔画字典、输入到数字的映射或 AI Prompt 事实：`date_to_numbers`、`validate_*`、`get_stroke_counts`、`HandTechnique.predict`、`get_relations`、`describe_relation` 全部按原样复用。因此按 `docs/specs/feature-proposals.md` 第 5 行的结论，不触发 `AGENTS.md` 的独立算法复核。

边界：若实施过程中不得不同意改动上述任一计算/映射函数（例如为了「顺手」调整 `date_to_numbers` 的返回），则该改动属算法变更，必须先停下、委派未参与实现的独立 Agent Reviewer 按 `AGENTS.md` 复核后才能报告完成；本次计划不授权这类改动。

测试设计上「独立期望」体现在：日期/汉字模式的期望数字（农历八月七日、未时编号 8、天4地6人2）与符号名列表都是按领域规则手工列出并硬编码在测试里的字面量，不是用 `predict` 反推。
