# Web 皮肤/主题 Standards 独立审查

- 日期：2026-09-16
- 基线：`9af7aac`；审查未暂存的待提交改动。审查者未参与实现，未修改实现代码。
- 范围：`git diff 9af7aac` 覆盖的 `src/web.py`、`src/web.css`、`README.md`；逐一完整读取 `git ls-files --others --exclude-standard` 列出的新增文件：`src/themes/theme.js`、`src/themes/night.css`、`src/themes/ink.css`、`src/themes/neon.css`、`tests/test_web_themes.py`、`.scratch/web-themes/spec.md`、`.scratch/web-themes/issues/01-themes.md`、`docs/reviews/web-themes-acceptance.md`。
- 依据：`CLAUDE.md`（开发规约、计算与界面边界、验证、算法变更的独立复核）、`AGENTS.md`、`docs/agents/{workflow,issue-tracker,triage-labels,domain}.md`；通用代码质量（可读性、单一职责、死代码、防御性处理、错误不被吞掉、注入安全、无外部网络请求、每次页面请求独立控制器、测试测行为且确定性）。

## 结论

通过；阻断问题 0，非阻断问题 9。

未发现违反项目规范或会造成缺陷的问题。本次不涉及算法变更（AST 对照证实），无外部网络请求，主题样式严格限定在 `html[data-theme="<id>"]` 之下，星夜效果的启停清理完整，注入到 `<script>`/props 的字符串全部来自模块级常量且经独立核对无逃逸风险。非阻断项集中在规格文档与实现的一致性、测试覆盖声明与实际覆盖的差距、以及若干可选的防御性加固。

## 逐条问题

| # | 位置 | 级别 | 问题 | 建议 |
|---|---|---|---|---|
| 1 | `.scratch/web-themes/spec.md:11`、`:29` | 非阻断 | 规格写明"`web.css` 不改动既有规则""只追加切换控件样式"，但实现修改了既有规则：`src/web.css:15` `.site-header` 加 `flex-wrap: wrap`，`:16` `.brand` 加 `flex-wrap: nowrap`，`:20` `.header-actions` 加 `flex-wrap: nowrap; margin-left: auto`，`:167` ≤600px 下 `.site-header` gap 由 20px 改为 12px，`:189` 减少动态效果规则新增 `animation-iteration-count: 1`。这些改动合理且已在 `docs/reviews/web-themes-acceptance.md:9,19` 披露，但规格本身未更新，违背 `workflow.md` "维持单一来源"。 | 更新 `spec.md` 皮肤清单与计划第 1 条，明确允许的头部换行策略与减少动态效果补丁。 |
| 2 | `tests/test_web_themes.py:79`、`:93` | 非阻断 | 类文档声称验证"清理逻辑"，但桩环境 `document.body: null` 使 `effects[id].start()` 永不执行，星夜画布/监听器/CSS 变量/rAF 的启停从未被测试覆盖；该部分只有人工浏览器验收（acceptance 第 15 条）与本次审查者独立桩测试作为证据。 | 增加带 `body`/`createElement`/`addEventListener` 计数桩的用例：`apply('night')` 后断言画布 1 个、`resize`/`pointermove`/`visibilitychange` 各 1 个；`apply('paper')` 后全部归零且 `--msr-mx/--msr-my` 被移除。审查者的桩脚本可直接复用（见验证证据）。 |
| 3 | `tests/test_web_themes.py:110-117` | 非阻断 | node 桩脚本写入源码树 `tests/_theme_harness.js` 再删除；进程被中断时会在仓库留下未跟踪文件，并行运行会互相覆盖。 | 改用 `tempfile.NamedTemporaryFile(suffix='.js')`，或通过 `subprocess.run(['node', '-'], input=HARNESS)` 从 stdin 执行。 |
| 4 | `tests/test_web_themes.py:36-39` | 非阻断 | `test_theme_script_is_valid_javascript` 只做子串断言（含 `window.msrTheme`、不含 `</script>`），并未验证 JS 语法；名称与行为不符（`CLAUDE.md` "Clear test names describing scenario"）。 | 改名为 `test_theme_script_exposes_api_and_is_safe_to_inline`，或在 node 可用时补 `node --check`。 |
| 5 | `src/themes/theme.js:51` | 非阻断 | `draw()` 在每颗星的循环内调用 `reducedMotion()`（即 `window.matchMedia`），最多 260 次/帧、约 1.5 万次/秒；且 rAF 循环启动后不监听 `matchMedia` 的 `change` 事件，用户在页面打开期间开启系统"减少动态效果"时，流星仍会继续生成。 | 把 `const still = reducedMotion()` 提到 `draw()` 开头一次求值；可选：`matchMedia(...).addEventListener('change', onVisibility)` 复用现有暂停/恢复逻辑。 |
| 6 | `src/web.py:238-240`、`:252`、`:256`、`:291` | 非阻断 | 注入点依赖"常量必然安全"的隐含不变量：`json.dumps(..., ensure_ascii=False)` 与 `theme.js` 原文直接拼进 `<script>`；`theme.id` 未加引号进入 `props()` 与 CSS 属性选择器；`title="..."`、`data-text="..."` 若常量含 `"` 会破坏 NiceGUI props 解析；`ui.html(theme.label, tag='span')` 以原始 HTML 渲染纯文本。当前四个 id 均为 `[a-z]+`、文案不含引号，测试也断言了 `theme.js` 不含 `</script>`，故无实际缺陷。 | 按 fail-fast 原则在模块加载时断言 `all(re.fullmatch(r'[a-z]+', t.id) for t in THEMES)`；`ui.html` 处改用 `html.escape(theme.label)` 或保留默认 `ensure_ascii=True`。 |
| 7 | `src/web.py:240-243` | 非阻断 | 每次页面请求从磁盘读取 `theme.js` 与三份主题 CSS（连同基线已有的 `web.css` 共 5 次文件读取）。与基线 `ui.add_css(Path)` 的既有模式一致，且 `reload=True` 开发模式下便于改样式即生效，但与 `CLAUDE.md` "数据加载在模块级别完成，避免重复读取" 的精神有出入。 | 可接受现状；若后续关注性能，可在模块级缓存文件内容或改为 `add_head_html(..., shared=True)` 一次注入（静态内容，不含 UI 引用，不违反独立控制器要求）。 |
| 8 | `tests/test_web_themes.py:22-34`、`:48`、`:58` | 非阻断 | CSS 作用域测试按行解析并跳过 `@keyframes`，不校验关键帧名是否带 `<id>-` 前缀（关键帧名是全局的，目前 12 个均已命名空间化）；页面测试依赖 NiceGUI 私有属性 `client._head_html`、`_event_listeners`（已在注释中说明）。 | 补一条断言：`re.findall(r'@keyframes ([\w-]+)', css)` 全部以 `f'{theme.id}-'` 开头。私有属性依赖可接受，升级 NiceGUI 时留意。 |
| 9 | `src/web.css:169`、`src/web.py:251-256` | 非阻断 | ≤600px 时 `.swatch-label { display: none }`，按钮的可访问名称退化为 `title` 属性；`title` 可用但依赖浏览器/读屏器的回退规则。`theme.js:145-148` 的 `MutationObserver` 若 `.theme-swatch` 在 `DOMContentLoaded` 时已存在则永不触发也永不断开（当前 Vue 延迟挂载，不会发生）。 | 给按钮显式加 `aria-label="{theme.label}"`；观察前先 `querySelector` 一次即可提前断开。均为可选加固。 |

## 验证证据

### 可运行验证（审查者独立运行）

- `uv run python -m unittest discover -s tests -v`：38 项全部通过（原 30 项 + `tests/test_web_themes.py` 8 项，含 node 桩用例；本机 node v26.5.0），运行后 `tests/` 无残留 `_theme_harness.js`。
- `uv lock --locked`：通过（Resolved 108 packages）；`pyproject.toml`、`uv.lock` 无改动，未引入新依赖。
- `git diff --check 9af7aac`：通过；对全部新增文件 `git diff --check --no-index /dev/null <file>`：无空白问题。
- `uv run python -m py_compile src/web.py tests/test_web_themes.py`、`node --check src/themes/theme.js`：通过。

### 特别检查

1. **默认皮肤 `paper` 保持不变**：`git diff 9af7aac -- src/web.css` 共五处改动。(a) 新增 `.theme-switcher`/`.theme-swatch`/`.swatch-*`/`html.msr-theme-fade` 规则，只匹配新元素或仅在切换 500ms 内生效的类；(b) `.site-header` 可换行、`.brand` 与 `.header-actions` 不换行并 `margin-left: auto`，在头部内容单行放得下时无视觉差异，仅在窄屏挤压时改变换行方式；(c) ≤900px `.header-actions` gap、≤600px `.site-header` gap 20→12px 及色样缩小，属窄屏容纳切换控件的排布调整；(d) 减少动态效果规则增加 `animation-iteration-count: 1`，只在系统偏好开启时生效。未改动任何既有配色、字号、卡片或结果区规则；`data-element`/`element-<key>` 钩子在 `web.css` 中没有对应规则（`grep` 确认），默认皮肤外观不受影响。上述 (b)(c)(d) 即任务说明中允许的"头部换行策略与 reduced-motion 迭代次数"，但规格文档未同步（问题 1）。
2. **主题 CSS 作用域**：逐行阅读三份主题文件，所有选择器均以 `html[data-theme="night"|"ink"|"neon"]` 开头，包括 `@media (max-width: 900px)` 块内的规则（`ink.css:75-83`）与 `::selection`、`body::before/::after`、Quasar 弹层规则；12 个 `@keyframes` 名称全部带 `night-`/`ink-`/`neon-` 前缀且只被同主题规则引用。`test_theme_stylesheets_only_target_their_own_skin` 亦通过。主题变量通过 `html[data-theme]`（特异性 0,1,1）覆盖 `:root`（0,1,0），不需要 `!important`；`--q-primary` 等在 `body` 上覆盖，作用域同样受限。
3. **`theme.js` 效果启停与偏好遵守**：审查者独立编写 node DOM 桩（含 `body`、`createElement`、window/document 监听器计数、rAF 计数、`style.setProperty` 记录），执行 `apply('night')` → 指针移动 → 两帧 → 隐藏/显示 → `apply('ink')` → `apply('night')` → `apply('paper')`。结果：启动后画布 1 个、`resize`/`pointermove` 各 1、`visibilitychange` 1、`--msr-mx/--msr-my` 已写入、rAF 在运行；页面隐藏时 `cancelAnimationFrame` 被调用且无待执行帧，显示后恢复；切走后画布 0、三个监听器全部移除、CSS 变量全部移除、rAF 已取消；再次启停结果一致。`prefers-reduced-motion: reduce` 模式下：不启动 rAF、不生成流星、`resize()` 仅静态绘制一次、不添加 `msr-theme-fade` 类。`readInitial`/`apply` 对 URL 参数与 `localStorage` 值均以 `IDS.includes` 白名单校验，非法值回落默认且不写入存储（加载时）；`localStorage` 读写均有 try/catch。
4. **`_add_theme_assets` 注入安全**：用真实 NiceGUI `Client` 构建页面并检查 `_head_html`：顺序为 `web.css` `<style>` → 常量 `<script>` → `theme.js` `<script>` → night/ink/neon `<style>`；`window.MSR_THEME_IDS` 出现在 `theme.js` 之前；`theme.js` 段内无 `</script>`，三份 CSS 无 `</style>`、`<!--`；无 `@import`、`http(s)://`、`fetch`、`<link`、`@font-face`（`ink.css` 中的 `xmlns` 位于 data URI 内，不发起请求）。NiceGUI 模板将 `head_html` 置于 `<head>` 内 Quasar CSS 之后（`templates/index.html:15`），故内联脚本在首屏绘制前同步执行、主题 CSS 在 Quasar 之后参与层叠。`props()` 解析结果核对：`title`、`aria-label`、`data-text` 含 `·`、中文与 `。` 均正确解析；`js_handler` 以 JSON 传输后在客户端 `eval`，`json.dumps(theme.id)` 生成的双引号字符串安全。
5. **无算法变更**：以 `ast.dump` 对照基线与当前 `src/web.py`：`_perform_divination`、`_validate_numbers`、`_validate_chinese`、`_validate_date_time`、`create_page`、`main`、`_display_ai_result`、`_display_empty_state`、`_show_error`、`_on_model_change`、`_check_available_models`、`__init__` 全部 UNCHANGED；仅 `_display_results`（新增 `data-element` prop 与 `element-<key>` class）与 `create_ui`（注入资源、切换控件、`data-text`）CHANGED，新增 `_add_theme_assets`、`_create_theme_switcher`。`git diff 9af7aac --stat` 只涉及 `README.md`、`src/web.css`、`src/web.py`，`hand_technique`、`utils/*`、数据文件均未触及。`ELEMENT_KEYS` 经枚举 1–6 三数全组合的预测结果核对，覆盖木火土金水全部五行，`'unknown'` 回退不可达但保持防御。因此不触发 `AGENTS.md` 的独立算法复核要求。

### 项目规范对照

- 计算与界面边界：`create_page` 仍为每次请求创建独立 `DivinationWebApp`；`THEMES` 为模块级不可变纯数据（`frozen=True`，仅字符串），不含 UI 引用；`_add_theme_assets` 使用 `shared=False` 的 per-client head 注入。
- 路径定位：`THEME_DIR = Path(__file__).with_name('themes')`，不依赖启动工作目录。
- 错误处理：资源文件缺失时 `read_text` 直接抛出异常，未被吞掉。
- 语言与文档：新增规格、ticket、验收记录与代码注释均为简体中文；ticket 含 `Status: in-review`、`Blocked by`、规格链接、验收条件与 `## Comments`，符合 `issue-tracker.md`；`README.md` 的皮肤表、URL 参数说明与目录树与实现一致。
- 测试：新增测试测行为（注册表、注入内容、切换按钮无服务端 handler、五行钩子、URL/存储优先级与回落），mock 掉模型探测，不依赖网络；node 缺席时按 `skipUnless` 跳过，结果确定。

## 限制与未解决项

- 本审查未在真实浏览器中做视觉、键盘与读屏器验收，浏览器证据以 `docs/reviews/web-themes-acceptance.md` 为准；未验证 Safari/Firefox（`background-attachment: fixed`、`backdrop-filter`、`mask` 的降级表现）。
- 星夜效果的启停清理由审查者的 node 桩独立证实，但项目测试套件本身未覆盖（问题 2）；`prefers-reduced-motion` 的运行时切换（问题 5）未在实际系统层面验证。
- `docs/reviews/web-themes-acceptance.md:24` 链接的 `web-themes-spec.md` 尚待 Spec 轴审查者产出，本报告不覆盖规格符合性（如各皮肤交互效果是否齐全）。
- 上述 9 项均为非阻断，可在本次提交或后续任务中处理；不阻碍将 ticket 置为 `resolved`。

## 复查

- 日期：2026-09-16（首轮报告同日）；复查者与首轮相同，仍未修改实现代码、未 commit、未 stash。
- 复查对象：修复后的 `src/web.py`、`src/themes/theme.js`、`src/themes/{night,ink,neon}.css`、`tests/test_web_themes.py`、`.scratch/web-themes/spec.md`、`docs/reviews/web-themes-acceptance.md`。`src/web.css`、`README.md` 相对基线的 diff 与首轮一致（+22/−4、+13/−1），未再改动。

### 逐项核对

| 首轮 # | 修复说明 | 核对结果 | 是否引入新问题 |
|---|---|---|---|
| 1 规格与实现不一致 | `spec.md` 同步 `web.css` 实际改动范围 | **部分解决**。`spec.md:11` 皮肤清单已写明"仅追加切换控件样式、头部换行策略（`.site-header`/`.brand`/`.header-actions`）及减少动态效果下的动画迭代次数限制"，与实现一致；但 `spec.md:29` 计划第 1 条仍为"`web.css` 只追加切换控件样式"，与第 11 行自相矛盾。 | 无；残留为文档措辞，非阻断。 |
| 2 效果启停无测试覆盖 | 桩提供 body/canvas/监听器记录；新增 `test_night_effect_starts_on_activation_and_cleans_up_on_switch` | **已解决**。`tests/test_web_themes.py:95-131` 的桩记录 window/document 监听器、`bodyChildren`、`styleVars`；`:163-172` 断言激活后画布 1、`resize`/`pointermove`/`visibilitychange` 各 1、`--msr-mx/--msr-my` 存在，切走后全部归零；`:143-149` 另断言存储为 `night` 时加载即启动效果。独立运行通过。 | 无。残留：桩的 `matchMedia` 返回对象无 `addEventListener`，新增的 reduced-motion 运行时切换路径（见 #5）未被项目测试覆盖，仅由复查者桩脚本证实；非阻断。 |
| 3 桩文件写入源码树 | 改为 `tempfile.TemporaryDirectory` | **已解决**。`:135-141`；运行后 `tests/` 无残留文件。 | 无。`:132` 显式 `process.exit(0)` 并注释原因（`theme.js` 的 15 秒兜底定时器），合理。 |
| 4 测试名不副实 | 改名为 `test_theme_script_is_safe_to_inline_and_exposes_runtime` | **已解决**。`:45-48`，名称与断言内容一致。 | 无。 |
| 5 `matchMedia` 每星调用、运行时不响应 | 缓存 `motionQuery`；监听 `change`；stop 时移除 | **已解决**。`theme.js:10-11` 缓存 `MediaQueryList`，`reducedMotion()` 退化为属性读取；`:98-103` 注册 `change` 处理：取消 rAF、清空流星、reduced 时静态绘制一次、否则在页面可见时重启；`:111` stop 时移除。复查者用可切换 `matches` 的桩独立验证：开启后 rAF 取消且无待执行帧、静态重绘 1 次；关闭后 rAF 恢复；页面隐藏时切换不启动 rAF；切走后 `change` 监听器数为 0、画布/监听器/CSS 变量全部清理。`typeof addEventListener === 'function'` 守卫使旧 Safari（仅 `addListener`）静默降级为不响应运行时切换，可接受。 | 无。 |
| 6 注入点隐含不变量 | `Theme.__post_init__` 校验 id 与文案 | **已解决**。`web.py:38-43` 导入时拒绝不匹配 `[a-z][a-z0-9-]*` 的 id 及含 `"` 的 label/description；`tests:23-27` 覆盖大写、空格、双引号四种反例。 | 无。残留（非阻断）：校验未涵盖 `ui.html(theme.label)` 关心的 `<`/`&`，也未涵盖写入 `data-text="..."` 的 `HERO_TITLE`；当前常量均安全。 |
| 7 每请求读取静态文件 | 保持现状 | **接受**，与基线模式一致，首轮即为可选项。 | — |
| 8 关键帧前缀未校验；私有属性 | 新增 `@keyframes` 前缀断言；私有属性保持 | **已解决**（`tests:37-38`，独立扫描 12 个关键帧均带主题前缀）；私有属性依赖接受，无公开替代。 | 无。 |
| 9 窄屏可访问名称；观察者不断开 | 色样按钮加 `aria-label`；观察者 15 秒兜底断开 | **已解决**。真实 NiceGUI `Client` 解析结果：四个按钮均含 `aria-label` 为皮肤名（`tests:67` 亦断言）；`theme.js:153-157` 找到按钮即断开并清除定时器，否则 15 秒后断开，复查者桩验证 `disconnect` 被调用 1 次。 | 无。可读性提示：`:154` 回调闭包引用了 `:157` 才声明的 `const giveUp`，因 `MutationObserver` 回调以微任务派发，不会触发 TDZ，但先声明再观察更直白；非阻断。 |
| 新增 5（Spec 轴意见） | 三套皮肤增加 `.guide-dialog .q-btn--unelevated` 覆盖 | **无标准问题**。`night.css:35`、`ink.css:40`、`neon.css:51` 均以 `html[data-theme="<id>"]` 开头，独立扫描无未加前缀选择器；`!important` 用法与既有 `.submit-button` 覆盖一致（Quasar 的 `bg-primary` 本身带 `!important`）。默认皮肤无对应规则，外观不变。 | 无。 |

### 复查验证

- `uv run python -m unittest discover -s tests -v`：40 项全部通过（原 30 项 + `test_web_themes.py` 10 项，含 node 桩 4 项）；与 `docs/reviews/web-themes-acceptance.md:13` 一致。
- `uv lock --locked`：通过；`git diff --check 9af7aac` 与全部未跟踪文件的 `--no-index` 空白检查：通过；`py_compile`、`node --check`：通过。
- AST 对照基线：`_perform_divination`、三个校验函数、`create_page`、`main` 等 12 个函数仍 UNCHANGED；新增仅 `Theme.__post_init__`、`_add_theme_assets`、`_create_theme_switcher`；仍不涉及算法变更。
- 主题资源再次 grep：无 `</script>`、`</style>`、`<!--`、`@import`、`http(s)://`、`fetch`、`<link`、`@font-face`。

### 复查结论

**通过；阻断问题 0，非阻断问题 3（均为残留提示，不要求本次处理）：**

1. `.scratch/web-themes/spec.md:29` 计划第 1 条措辞未与第 11 行同步。
2. 项目测试未覆盖 reduced-motion 运行时切换路径（复查者桩已独立证实行为正确）。
3. `Theme.__post_init__` 未涵盖 `<`/`&` 与 `HERO_TITLE`；`theme.js:154/157` 的 `giveUp` 先用后声明仅为可读性提示。

首轮 9 项非阻断中 7 项已解决、1 项部分解决（#1）、1 项按约定保持现状（#7）；修复未引入新问题，不阻碍将 ticket 置为 `resolved`。
