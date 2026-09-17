# Web 首屏布局调整 Standards 独立审查

- 日期：2026-09-16
- 基线：`b5d929c`；审查未暂存的待提交改动。审查者未参与实现，未修改实现代码，未 commit、未 stash。
- 范围：`git diff b5d929c` 覆盖的 `src/web.py`、`src/web.css`、`src/themes/ink.css`、`src/themes/night.css`、`src/themes/neon.css`、`README.md`、`tests/test_interpretation_experience.py`、`tests/test_regressions.py`（`--stat`：8 个文件，+78/−63）；逐一完整读取 `git ls-files --others --exclude-standard` 列出的新增文件：`.scratch/web-first-screen/spec.md`、`.scratch/web-first-screen/issues/01-first-screen.md`、`docs/reviews/web-first-screen-acceptance.md`。
- 依据：`CLAUDE.md`（开发规约、计算与界面边界、验证、算法变更的独立复核）、`AGENTS.md`、`docs/agents/{workflow,issue-tracker,triage-labels,domain}.md`；通用代码质量（可读性、死代码、错误处理不变、每次页面请求独立控制器、测试测行为且确定性）。

## 结论

通过；阻断问题 0，非阻断问题 4。

未发现违反项目规范或会造成缺陷的问题。本次不涉及算法变更（AST 对照证实：`_perform_divination` 仅按钮文案常量不同，三个校验函数、`create_page`、`_on_model_change`、`_check_available_models`、`_display_results` 均 UNCHANGED；`hand_technique`、`utils/`、`data/` 未触及）。移入 `ui.expansion` 的 `question_input`/`model_select` 在折叠态下仍被提交流程正确读取（审查者独立探针证实）。被删除的 `.form-divider`/`.form-section-title`/`.optional-label` 在仓库内无任何残留引用；`ink.css` 无竖排规则残留；三份主题 CSS 的 310 个选择器全部以 `html[data-theme="<id>"]` 开头。文案改动在源码、测试、README 中同步，处理中/完成/失败文案未变。非阻断项为一处规格未披露的附带样式改动、一处测试覆盖建议与两处文档一致性提示。

## 逐条问题

| # | 位置 | 级别 | 问题 | 建议 |
|---|---|---|---|---|
| 1 | `src/themes/night.css:61` | 非阻断 | 为 `.optional-panel` 配色时把既有的 `.culture-panel` 规则合并改写，使结果区"查看传统文化背景"面板在星夜皮肤下新增 `background: var(--surface-2)`（基线只有 `border-color`）。规格 `spec.md:21` 与验收记录只描述"为折叠区提供边框、背景与标题色"，未提及改动结果区既有元素，违背 `workflow.md`"维持单一来源"的精神。视觉上是同一皮肤内两个 expansion 保持一致，改动本身合理。 | 二选一：把 `.culture-panel` 拆回单独规则保持基线外观；或在 `spec.md` 皮肤条目与 `web-first-screen-acceptance.md` 交付段落中补一句"星夜下 `.culture-panel` 同步取 `--surface-2` 背景"。 |
| 2 | `tests/test_regressions.py:283-294` | 非阻断 | 新测试断言了折叠区默认态、按钮文案与两个输入的父级，但未断言表单卡片内的元素顺序（错误提示 → 开始占卜 → 状态行 → 折叠区）。"主按钮紧随输入之后、位于选填区之前"是本次交付的核心，服务端若把折叠区挪回按钮之前，现有测试不会失败。审查者探针已确认当前顺序正确（见验证证据 2）。 | 在同一测试中取 `card = app.submit_button.parent_slot.parent`，对 `card.default_slot.children` 建索引，断言 `error_message < submit_button < status_message < optional_panel`。 |
| 3 | `src/web.py:274-277`、`README.md:106-108` | 非阻断 | 页内"使用指南"步骤为 01 起课 → 02 留下心中所问 → 03 顺着三传阅读，且全程未出现主按钮名；README Web 步骤已改为 1 起课 → 2 开始占卜 → 3 心中所问（可选）。两条路径都可行，但同一产品的两份操作说明顺序不一致，且指南没有告诉首次用户要点哪个按钮。 | 将 02 文案调整为例如"点「开始占卜」即得三传。问题可留空；选择可用的 AI 模型并填写问题后再次提交，才会生成解读。"，或调整步骤顺序与 README 对齐。 |
| 4 | `docs/reviews/web-first-screen-acceptance.md:15` | 非阻断 | 写作"Chrome 1440×900（视口 1445×941）"：视口尺寸大于所述窗口尺寸，读者无法确定 y≈524/847 的坐标是相对哪个高度成立。规格 `spec.md:22` 的验收口径是"1440×900 视口"。主按钮底边 524 在任一口径下都在首屏，结论不受影响，但证据表述应准确。 | 改写为实际测量视口（例如"视口 1445×941，窗口外框 1440×900 折算后仍满足"），或以 900 高度重新截取一次。 |

## 验证证据

### 可运行验证（审查者独立运行）

- `uv run python -m unittest discover -s tests -v`：41 项全部通过（与验收记录一致：新增 `test_optional_panel_follows_ai_availability_and_button_names_the_action`，`test_result_exposes_input_snapshot_and_complete_relations` 文案断言更新）。全套第二次运行仍 41 项通过；两个改动测试单独连续运行 3 次均通过，结果确定。
- `uv lock --locked`：通过（Resolved 108 packages）；`pyproject.toml`、`uv.lock` 无改动，未引入新依赖。NiceGUI 2.20.0 的 `ui.expansion` 签名含 `caption`、`icon`、`value` 关键字，用法合法。
- `git diff --check b5d929c`：通过；三个新增文件以 `git diff --check --no-index /dev/null <file>` 检查：无空白问题，均以换行结尾。
- `uv run python -m py_compile src/web.py tests/test_regressions.py tests/test_interpretation_experience.py`：通过。
- 编码与换行：11 个涉及文件均为 UTF-8（`web.css` 基线与当前均为纯 ASCII），无 CR。

### 特别检查

1. **无算法变更**：以 `ast.dump` 逐函数对照 `git show b5d929c:src/web.py` 与当前文件。`_validate_numbers`、`_validate_chinese`、`_validate_date_time`、`create_page`、`main`、`_on_model_change`、`_check_available_models`、`_display_results`、`_display_ai_result`、`_show_error`、`_add_theme_assets`、`_create_theme_switcher`、`Theme.__post_init__` 及模块级 `THEMES`/`DEFAULT_THEME`/`ELEMENT_KEYS`/`HERO_TITLE`/`THEME_DIR` 全部 UNCHANGED。CHANGED 的三处：`_perform_divination` 在把 `'查看三传'`/`'开始占卜'` 归一化后 AST 完全相同（唯一差异是 `finally` 中的 `set_text` 常量）；`__init__` 仅新增 `self.optional_panel = None`；`create_ui` 与 `_display_empty_state` 为布局与文案改动。`git diff b5d929c --name-only` 仅 8 个文件，`src/hand_technique.py`、`src/utils/`、`src/ai_agent.py`、`src/cli.py`、`data/` 无差异。模型选项构建（`model_options`、`ui.select(...)`、本地提示/AI 提示分支）经 `git diff -w` 核对为纯缩进移动，未改一字。因此不触发 `AGENTS.md` 的独立算法复核要求。
2. **折叠区内输入仍参与提交流程**：审查者用真实 NiceGUI `Client` 独立探针：(a) 配置 AI 时把 `optional_panel.value` 手动置为 `False` 后填写问题并提交，`interpret_prediction_async` 收到的第二个参数即该问题，`question_snapshot`、`ai_interpretation` 正确，提交后按钮文案回到"开始占卜"；随后经 `_on_model_change(value='local')` 再提交，AI 调用次数保持 1。(b) 未配置 AI 时折叠区默认收起、`model_select.value == 'local'` 且选项只有本地一项，填写问题后提交，`question_snapshot` 仍被捕获，本地三传正常生成。(c) 两种可用性下 `caption` 分别为"选填 · 留空只看三传，本地无需 AI"/"选填 · 填写问题后可获得 AI 解读"，`icon='edit_note'`，`value` 分别为 False/True。表单卡片子元素顺序：section-heading、input-tabs、input-panels、error-message、submit-button、status-message、optional-panel；`hero-line` 为 `nicegui-row` 且只含 `hero-title`（props 保留 `role=heading aria-level=1 data-text`）与 `hero-description`；主题切换按钮仍为 4 个。
3. **主题 CSS 作用域**：独立脚本去注释、展开 `@media`、剔除 `@keyframes` 后逐个选择器检查：night 87、ink 89、neon 134 个选择器全部以 `html[data-theme="<id>"]` 开头；12 个 `@keyframes` 名均带主题前缀；无 `</style`、`<!--`、`@import`、外部 `http(s)://`、`fetch`、`<link`、`@font-face`。项目测试 `test_theme_stylesheets_only_target_their_own_skin` 亦通过。本次 diff 未新增 `!important`。
4. **`ink.css` 无竖排残留**：`writing-mode`、`vertical-rl`、`text-orientation`、`row-reverse`、`border-right: 2px`、`padding-right: 10px` 均无命中；≤900px 媒体块只剩水印隐藏、标题字距与卡片阴影三条。新用到的 `var(--brush)` 在 `ink.css:2` 基线即已定义（`transmission-card`、`symbol-name` 沿用同一变量）。
5. **死代码**：`form-divider`、`form-section-title`、`optional-label` 在 `*.py/*.css/*.js/*.md/*.html` 中零命中（`neon.css` 的 mono 字体清单已同步移除 `.optional-label`）。`web.css` 新增的 `.hero-line`、`.optional-panel*` 规则均有对应元素；`.question-field`、`.local-note`、`.desktop-copy/.mobile-copy` 仍被使用且 ≤900px 切换规则保留。
6. **文案一致性**：`查看三传` 在仓库内仅剩 `.scratch/web-first-screen/spec.md:10` 的问题陈述（合理保留）；源码按钮初值、`finally` 复位值、就绪状态文案、空状态引导、两处测试断言、README 特性列表与步骤均为"开始占卜"。处理中文案"正在计算…"/"正在计算本地三传…"/"正在解读…"/"本地三传已完成，正在等待 … 解读…"及完成、失败文案逐行核对未变。`docs/specs/*.md`、`specs/codebase-overview.md` 无过期引用。

### 项目规范对照

- 计算与界面边界：`create_page` 仍为每次请求创建独立 `DivinationWebApp`；`optional_panel` 作为实例属性保存，与其他控件一致，无模块级 UI 引用。
- 错误处理：`_show_error`、`_perform_divination` 的 try/except/finally 结构未变，AI 失败仍保留本地结果并以异常文本提示。
- 语言与文档：新增规格、ticket、验收记录与代码注释均为简体中文；ticket 含 `Status: in-review`、`Blocked by`、规格链接、交付行为、验收条件与 `## Comments`，符合 `issue-tracker.md`；规格位于 `.scratch/<feature>/spec.md` 作为功能入口，符合约定。
- 测试：新测试沿用既有 `Client(ui.page(...), request=None)` + `patch('web.DivinationAgent.get_available_models')` 模式，mock 掉模型探测，不依赖网络与环境变量；`parent_slot` 为 NiceGUI `Element` 的公开属性。
- 依赖与工具：未新增依赖、未引入新工具；`uv` 命令链完整可用。

## 限制与未解决项

- 本审查未在真实浏览器中做视觉、首屏高度、横向溢出与读屏器验收；浏览器证据以 `docs/reviews/web-first-screen-acceptance.md` 为准（仅 Chrome，未验证 Safari/Firefox 与实体手机）。审查者的探针只证实服务端元素树的顺序与状态。
- `docs/reviews/web-first-screen-acceptance.md:22` 链接的 `web-first-screen-spec.md` 尚待 Spec 轴审查者产出，本报告不覆盖规格符合性（例如各皮肤折叠区"标题色"是否齐全、水印位置等视觉要求）。
- 上述 4 项均为非阻断，可在本次提交或后续任务中处理；不阻碍将 ticket 置为 `resolved`。

## 复查

- 日期：2026-09-16（首轮报告同日）；复查者与首轮相同，仍未修改实现代码、未 commit、未 stash。
- 复查对象：修复后的 `src/themes/night.css`、`src/themes/neon.css`、`src/themes/ink.css`、`src/web.py`、`tests/test_regressions.py`、`docs/reviews/web-first-screen-acceptance.md`，以及按 Spec 意见追加的主题改动。`src/web.css`、`README.md`、`tests/test_interpretation_experience.py` 相对基线的 diff 与首轮一致（+22/−21、+3/−2、+1/−1），未再改动。新增未跟踪文件 `docs/reviews/web-first-screen-spec.md`（Spec 轴报告）不在本轴范围。

### 逐项核对

| 首轮 # | 修复说明 | 核对结果 | 是否引入新问题 |
|---|---|---|---|
| 1 星夜 `.culture-panel` 附带改动 | `.culture-panel` 恢复只改边框色；`.optional-panel` 单独一条带背景；新增 caption 规则保持 muted | **已解决**。`night.css:61` 与基线逐字相同（`border-color: var(--line)`）；`:62` `.optional-panel` 独立规则；`:63` 标题 `var(--ink)`；`:64` `.q-item__label--caption { color: var(--muted) }`。标题与 caption 规则特异性相同（0,3,1），caption 规则声明在后，副标题正确取 muted。 | 无。 |
| 2 测试未断言元素顺序 | 新测试补充 `siblings.index(submit_button) < siblings.index(optional_panel)` | **已解决**。`tests/test_regressions.py:295-296` 以 `submit_button.parent_slot.children` 建索引断言。复查者做反向验证：在同一 slot 中交换两元素位置后该断言变为 False，说明断言能捕获"折叠区挪回按钮之前"的回归。单独连跑 3 次通过。 | 无。 |
| 3 页内指南与 README 顺序不一致 | 三步改为 起课 → 点「开始占卜」顺着三传阅读 → 心中所问（选填） | **已解决**。`web.py:275-277` 步骤顺序、按钮名与 README `:106-108` 一致；步骤 02 保留了原 03 的三传阅读要点与文化背景提示，步骤 03 写明折叠区名称与"再次点「开始占卜」"，无信息丢失。 | 无功能问题。残留（非阻断，可读性）：`:277` 文案对折叠区名用 ASCII 双引号 `"心中所问 · 解读方式"`，而同一行按钮名用「」；`ui.label` 文本经 Vue 以文本节点渲染，不进入 props/HTML，无注入风险。另 README `:108` 写"（可选）"，页内指南与折叠区 caption 写"（选填）/选填"，措辞不统一，可顺手对齐。 |
| 4 验收记录视口口径 | 改为"窗口按 1440×900 设置（工具实测视口 1445×941）" | **已解决**。`web-first-screen-acceptance.md:15` 已按此表述，读者可知坐标相对的是实测视口高度 941。 | 无。 |
| Spec 意见：neon/night 副标题 muted | 两套皮肤各加 `.optional-panel .q-item__label--caption { color: var(--muted) }` | **无标准问题**。`neon.css:46-48`、`night.css:62-64` 三条规则均以 `html[data-theme="<id>"]` 开头，caption 规则紧随标题规则之后，层叠顺序正确。 | 无。 |
| Spec 意见：ink 标题色、水印位置与隐藏断点 | `ink.css:36` 新增 `.optional-panel .q-item__label { color: var(--ink) }`；`:17` 水印 `left: 68%`；新增 `@media (max-width: 1100px)` 隐藏水印 | **部分符合，引入一个新的非阻断问题**（见下）。作用域检查：ink 90 个选择器全部带前缀，两个媒体块内规则亦然；≤900px 块只剩标题字距与卡片阴影，无竖排残留。 | **新增非阻断 #5**：`ink.css:36` 的标题色规则同样命中副标题。Quasar `QItemLabel` 在 `caption` 模式下输出 `class="q-item__label q-item__label--caption text-caption"`（`nicegui/static/quasar.umd.prod.js` 中 `QItemLabel` 的 class 计算已核对），因此 `html[data-theme="ink"] .optional-panel .q-item__label`（特异性 0,3,1）会覆盖 `web.css:64` 的 `.optional-panel .q-item__label--caption { color: var(--muted) }`（0,2,0），水墨皮肤下副标题"选填 · …"将与标题同为 `#161616`，而非 muted `#6a6a66`。这正是 night/neon 本轮通过补 caption 规则规避的情况，ink 漏补。建议在 `:36` 之后追加 `html[data-theme="ink"] .optional-panel .q-item__label--caption { color: var(--muted); }`，或把 `:36` 选择器收窄为 `.q-item__label:not(.q-item__label--caption)`。 |

### 复查验证

- `uv run python -m unittest discover -s tests -v`：41 项全部通过；新测试单独连跑 3 次通过。
- `uv lock --locked`：通过（Resolved 108 packages）；`git diff --check b5d929c`：通过；5 个未跟踪文件 `--no-index` 空白检查：全部干净；`py_compile`：通过。
- AST 对照基线：仍只有 `__init__`（新增 `optional_panel`）、`_perform_divination`（仅按钮文案常量）、`_display_empty_state`、`create_ui`（本轮新增指南文案改动）为 CHANGED；三个校验函数、`create_page`、`_on_model_change` 等 UNCHANGED；不涉及算法变更。
- 主题 CSS 独立扫描：night 88、ink 90、neon 135 个选择器全部以 `html[data-theme="<id>"]` 开头，12 个 `@keyframes` 均带前缀，无外部资源或注入字符。
- 死代码与文案：`form-divider`/`form-section-title`/`optional-label` 在源码、样式、测试、README 中零命中（仅审查报告提及）；`查看三传` 仅剩规格问题陈述。
- 独立探针复跑：折叠态下 `question_input`/`model_select` 仍参与提交流程（AI 收到问题、切回 local 后跳过 AI、无 AI 时快照仍捕获）；表单卡片顺序 错误提示 → 开始占卜 → 状态行 → 折叠区；主题切换按钮 4 个。

### 复查结论

**通过；阻断问题 0，非阻断问题 1（新增）+ 2 项残留提示（不要求本次处理）：**

1. **新增 #5** `src/themes/ink.css:36`：标题色规则连带覆盖副标题，水墨皮肤折叠区 caption 失去 muted 层级；补一条 caption 规则即可（night/neon 已有同样写法可照抄）。视觉层级问题，不影响功能与计算，非阻断。
2. 残留：`src/web.py:277` 折叠区名使用 ASCII 双引号而按钮名用「」；README"（可选）"与页内"（选填）"措辞不一。
3. `docs/reviews/web-first-screen-spec.md` 为 Spec 轴报告，本轴未审。

首轮 4 项非阻断全部已解决；按 Spec 意见追加的 night/neon 改动无标准问题；ink 改动引入 1 项新的非阻断视觉问题。修复未引入功能、边界、错误处理或测试确定性方面的问题，不阻碍将 ticket 置为 `resolved`。
