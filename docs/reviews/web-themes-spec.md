# Web 皮肤/主题：Spec 独立审查

- 日期：2026-09-16。
- 审查者：独立 Spec Agent，未参与实现。
- 规格：`.scratch/web-themes/spec.md`；任务：`.scratch/web-themes/issues/01-themes.md`；验收记录：`docs/reviews/web-themes-acceptance.md`。
- 基线：`9af7aac177f33cdb8de96d95b8ade9d5cd508f26`。
- 范围：`git diff 9af7aac` 中的 `src/web.py`、`src/web.css`、`README.md`；`git ls-files --others --exclude-standard` 列出的 `src/themes/theme.js`、`src/themes/night.css`、`src/themes/ink.css`、`src/themes/neon.css`、`tests/test_web_themes.py` 全文逐行读取。验证在本工作树内完成，未修改实现代码，未提交。

## 结论

阻断问题 0，非阻断问题 3。规格“皮肤清单”与“设计与验收”各条均有对应实现；未发现算法或计算结果变更；页面文案、输入默认值/范围、模型选项、结果内容与状态文案与基线一致。非阻断项分别是：暗色皮肤下指南对话框主按钮为 Quasar 默认“白字配主色底”，对比度不足；节点测试的说明文字宣称覆盖了效果清理逻辑但实际未执行；`web.css` 头部既有规则的修改超出规格表格“不改动既有规则”的字面表述（验收记录已声明为头部换行策略例外）。

## 独立运行的验证

- `uv run python -m unittest discover -s tests -v`：38 项全部通过（原 30 项 + `tests/test_web_themes.py` 8 项，node v26.5.0 可用，脚本逻辑测试未跳过）。
- `uv lock --locked`：通过。`git diff --check`：通过；对未跟踪文件逐个 `git diff --no-index --check /dev/null <file>`：无空白问题。
- NiceGUI 2.20.0 `Client(ui.page('/x'), request=None)` 上下文构造页面：`_head_html` 顺序为 web.css → `MSR_THEME_IDS` 脚本 → theme.js → night.css → ink.css → neon.css，全部位于模板 `<head>` 的 `{{ head_html }}`（`nicegui/templates/index.html:15`）内、`<body>` 之前；`.theme-switcher` 为 `div` 且 `role=group`、`aria-label=切换皮肤`；四个 `button` 均 `type=button`、`data-theme-id`、`aria-pressed`（paper 为 true）与 `title`；每个按钮仅一个 `click` 监听器，`handler` 为 None、`js_handler` 调用 `window.msrTheme.apply("<id>")`；`.hero-title` 带 `data-text="一念起，观三传。"`。
- 遍历 1–6 三数全部 216 种组合：九个符号的五行均落在 `ELEMENT_KEYS`，不会产生 `unknown` 钩子。
- 自写括号感知解析器核对三份主题 CSS：所有规则（含 `@media` 内嵌规则）的每个选择器均以 `html[data-theme="<id>"]` 开头；12 个 `@keyframes` 均带主题前缀，无跨主题重名。
- `grep` 三份主题 CSS 与 `web.css`：无 `http`、`@import`、`@font-face` 或非 `data:` 的 `url()`；`web.css` 不含 `data-element`、`element-wood/fire/earth/metal/water` 或 `data-text`。
- 本地服务（端口 8791，`reload=False`）+ Claude in Chrome，1440 宽：默认加载 `data-theme=paper`、`localStorage` 为空；`apply('night')` 后 `data-theme=night`、存储 `night`、`#msr-stars` 画布存在、`aria-pressed` 同步、指针移动后 `--msr-mx/--msr-my` 写入根元素、`--q-primary` 为 `#e0b755`、输入框底色/文字色改为暗色配置；切到 `ink` 后画布移除、两个变量清空、`--q-primary` 为 `#b8262b`、标题 `writing-mode: vertical-rl`；切到 `neon` 后 `--q-primary` 为 `#22e3ff`、状态行 `::after` 内容为 `▌`、`scrollWidth` 等于视口；`apply('bogus')` 回落 `paper` 并存储 `paper`。`?theme=neon` 重新加载：首屏即为 `neon`、存储 `neon`、仅 neon 按钮 `aria-pressed=true`。
- 键盘：点击“素纸”后按 Tab 焦点移至“星夜”按钮，按 Enter 后 `data-theme=night`、存储与 `aria-pressed` 同步。
- 同源 iframe 模拟 390px 与 320px：四套皮肤 `scrollWidth` 均等于视口宽度，`.swatch-label` 为 `display:none`；390px 下品牌与操作区处于同一行（brand y=22/h=44，actions y=28/h=31）。
- 覆盖 `window.matchMedia` 模拟减少动态效果后切到 `night`：未发起 `requestAnimationFrame`，画布存在且已静态绘制星点，未添加 `msr-theme-fade` 类；恢复后切换会发起动画帧。
- 霓虹皮肤下输入空值提交：错误文案“请输入1-999之间的整数”、颜色 `rgb(255,92,122)`、状态行“未能计算，请检查输入。”；输入 5/2/3 后三张卡片 `data-element` 为 water/earth/earth，角标与徽章颜色按五行分色，折叠面板头部/图标/内容均为亮色；星夜与霓虹下 `.q-menu` 背景分别为 `#151c3a`、`#0b0f1f`，文字为亮色。
- NiceGUI `on()` 实现（`element.py:381-393`，`static/nicegui.js:198-210`）：提供 `js_handler` 时客户端以该函数替代 `emit`，不向服务器发送事件；`ui.colors` 通过 `colors.js` 以内联样式写到 `document.body`，主题 CSS 的 `html[data-theme] body { --q-primary: … !important }` 可覆盖。

## 逐条验证证据

### 默认皮肤保持不变

| 规格条目 | 实现位置 | 判定 |
|---|---|---|
| `paper` 使用现有暖白纸感与朱砂主色，`web.css` 不改动既有规则 | `git diff 9af7aac -- src/web.css`：既有规则改动仅 `.site-header` 增 `flex-wrap: wrap`（L15）、`.brand` 增 `flex-wrap: nowrap`（L16）、`.header-actions` 增 `flex-wrap: nowrap; margin-left: auto`（L21）、≤900px 新增 `.header-actions { gap: 12px }`（L150）、≤600px 新增 `.site-header { gap: 12px }`（L167，原继承 20px）、减少动态效果规则增加 `animation-iteration-count: 1 !important`（L189）；其余新增均为 `.theme-*`/`.swatch-*`/`html.msr-theme-fade` 规则（L127-138、L168-171） | 符合验收记录声明的“切换控件样式、头部换行策略、reduced-motion 迭代次数”例外；见问题 3 |
| 页面结构只新增切换控件与属性钩子 | `web.py` diff：新增 `Theme` 注册表（L31-46）、`_add_theme_assets`（L235-243）、`_create_theme_switcher`（L245-256）、`create_ui` 中 L262 注入与 L284 放置控件、hero 标题改用常量并加 `data-text`（L26、L291）、三传卡片/徽章钩子（L174-181）；文案、`ui.number(value=i+1, min=1, max=999)`、日期 `min=1900-01-01 max=2099-12-31`、`model_options`、结果与状态文案均无改动；`_perform_divination`、验证函数、`create_page` 未变 | 符合；无算法变更 |

### 皮肤清单

| 皮肤 / 条目 | 实现位置 | 判定 |
|---|---|---|
| 星夜 · 深空渐变底 | `night.css:3` body 双径向渐变 + `#0b1020` | 已实现 |
| 星夜 · 鎏金强调色 | `night.css:2` `--accent:#e0b755`、L14 渐变标题、L33 提交按钮 | 已实现 |
| 星夜 · 毛玻璃卡片 | `night.css:19` `backdrop-filter: blur(14px)` 作用于表单卡、阅读区、AI 卡、指南对话框 | 已实现 |
| 星夜 · 五行分色徽章 | `night.css:54-58` `.element-badge.element-<key>`；卡片顶边 L48-52 | 已实现 |
| 星夜 · 缓慢转动的星盘 | `night.css:38` `.compass::before` `night-spin 90s linear infinite` | 已实现 |
| 星夜 · Canvas 星空闪烁与流星 | `theme.js:22-110`：`seed/draw/frame`，流星每 5–12s 一颗（L72） | 已实现 |
| 星夜 · 随指针移动的提灯光晕 | `theme.js:87-91` `pointermove` 写 `--msr-mx/--msr-my`；`night.css:6` `body::before` 径向渐变 | 已实现 |
| 星夜 · 三传卡片交错浮现 | `night.css:44-46` `night-rise` 延迟 0/.12/.24s | 已实现 |
| 水墨 · 宣纸白与墨黑 | `ink.css:2-3` `--paper:#f8f7f2`、`--ink:#161616`、SVG 噪点纹理（data URI） | 已实现 |
| 水墨 · 桌面竖排标题 | `ink.css:18-22` `writing-mode: vertical-rl`；≤900px 回横排（L75-81） | 已实现，浏览器 1440 宽核对为 `vertical-rl` |
| 水墨 · 笔触分隔 | `ink.css:2` `--brush` SVG；L55 卡片顶部笔触；L61 符号名下划笔触 | 已实现 |
| 水墨 · 朱文印章徽章 | `ink.css:28` 朱红描边、旋转 -3°；品牌印 L9；`hero-aside` 印章框 L23 | 已实现 |
| 水墨 · 墨晕背景 | `ink.css:5` `body::before` 双径向墨晕 + `ink-wash` | 已实现 |
| 水墨 · 圆相空状态 | `ink.css:45-50` conic-gradient + mask 画未合口的墨环 | 已实现 |
| 水墨 · 印章盖印入场 | `ink.css:28,73` `ink-stamp`（起始 `scale(1.3)`，与验收记录“已改为不超出视口”一致） | 已实现 |
| 水墨 · 三传墨晕显现 | `ink.css:54,56-57,74` `ink-bloom` 延迟 0/.18/.36s | 已实现 |
| 水墨 · 悬停时符号名下划墨线 | `ink.css:60-62` `::after` `scaleX(0→1)` | 已实现，静态 `transform` 为 `matrix(0,0,0,1,0,0)` |
| 霓虹 · 深黑底、青/品红荧光 | `neon.css:2-3` `--paper:#07070d`、`--accent:#22e3ff`、`--magenta:#ff3ea5` | 已实现 |
| 霓虹 · 网格地面 | `neon.css:3` 36px 双向线性渐变网格铺满页面 | 已实现（为平铺网格，非透视地面；属合理诠释） |
| 霓虹 · 扫描线 | `neon.css:5` `body::after` 固定定位 3px 重复渐变 + 暗角 | 已实现 |
| 霓虹 · HUD 角标 | `neon.css:62-64` 卡片 `::before/::after` 角括；L33-34 标题 `[ ]`；L18 `//`；L72 `>` | 已实现 |
| 霓虹 · 五行荧光分色 | `neon.css:66-70` 角标、L76-80 徽章 | 已实现，浏览器核对 water/earth 颜色 |
| 霓虹 · 切换时 CRT 开机动画 | `neon.css:3,94` body `neon-crt .8s … 1`，`scale(.3,.004)` 起始（与验收记录一致） | 已实现 |
| 霓虹 · 标题悬停故障字效 | `neon.css:20-24,95-96` 依赖 `data-text`，`web.py:291` 提供 | 已实现 |
| 霓虹 · 卡片悬停扫描光带 | `neon.css:65,99` `neon-scan` | 已实现 |
| 霓虹 · 状态行闪烁光标 | `neon.css:51,97` `.status-message::after` `▌` + `neon-blink` | 已实现 |

### 设计与验收

| 规格条目 | 实现位置 | 判定 |
|---|---|---|
| 切换控件：色样 + 名称按钮、`role=group`、`aria-label`、`aria-pressed`、键盘可操作、窄屏只显示色样 | `web.py:248-256`；`web.css:127-137`（`.swatch-dot`/`.swatch-label`）、L171 ≤600px 隐藏文字；`:focus-visible` L130；原生 `<button>` 支持 Enter/Space | 符合，浏览器键盘与 390/320px 核对通过；窄屏可访问名称由 `title` 提供 |
| 切换完全在浏览器端：`html[data-theme]` + 主题 CSS，不经服务器、不刷新 | `web.py:253` `js_handler`，`theme.js:122-138` `apply` 改写 `root.dataset.theme`；NiceGUI 在有 `js_handler` 时不 `emit` | 符合 |
| 选择写入 `localStorage`，再次访问保持；`?theme=<id>` 可指定并记忆；无效值回落默认 | `theme.js:12-19` `readInitial`（URL 优先并 `persist:true`，其次存储），L123 无效回落 `DEFAULT`，L131 写入 | 符合，节点测试与浏览器均核对 |
| head 内联脚本在首屏绘制前应用已保存皮肤 | `web.py:239-240` 以 `add_head_html` 内联；`theme.js:140-141` 立即写 `data-theme`；主题 `<style>` 同在 head | 符合 |
| 主题 CSS 只匹配自身 `html[data-theme="<id>"]` | 三份 CSS 全部规则前缀核对（测试 + 括号感知解析）；keyframes 名称带前缀 | 符合 |
| 暗色皮肤覆盖 Quasar 输入框、下拉菜单、对话框、折叠面板与 `--q-primary` | night：L3、L27-30、L19（`.guide-dialog`）、L66-68；neon：L3、L40-45、L29、L91-93 | 符合；但对话框内 `开始探索` 按钮未覆盖，见问题 1 |
| 主题 JS 效果只在激活时启动、切走时完整清理（画布、监听器、CSS 变量） | `theme.js:132-136` 仅对 `effects[id]` 启停；`stop()` L98-108 取消 rAF、移除 resize/pointermove/visibilitychange、移除画布、清除变量 | 符合，浏览器核对画布与变量已清理 |
| 遵守 `prefers-reduced-motion` | `theme.js:10,42,51,86,94,125`：不启动帧循环、静态绘制、无淡入类；`web.css:189` 将所有 CSS 动画压到一次迭代 | 符合，以 `matchMedia` 覆盖方式核对 |
| 页面隐藏时暂停动画 | `theme.js:92-96` `visibilitychange` 取消/恢复 rAF | 符合（代码路径） |
| 三传卡片与五行徽章带 `data-element` / `element-<key>`，默认皮肤不使用 | `web.py:174-181`；`web.css` 无相关选择器 | 符合 |
| 所有皮肤下输入方式、模型选择、指南对话框、空状态、结果、文化背景、AI 解读与错误/等待状态可读可用；桌面与手机不产生水平溢出 | 浏览器核对霓虹错误态、结果、折叠面板，星夜/霓虹下拉菜单；四皮肤 390/320px 无溢出 | 基本符合；指南对话框主按钮对比度见问题 1；AI 等待/解读状态仅按 CSS 规则核对（无密钥） |
| 不引入外部字体、图片或脚本网络请求；每次页面请求仍创建独立 `DivinationWebApp` | 主题资源全部内联/data URI；`neon.css:2` `--mono` 仅为字体族回退名，无 `@font-face`；`create_page` 未变，主题方法为 `@staticmethod` 无共享状态 | 符合 |

### 计划与验收记录

- 计划第 3 条“单元测试覆盖注册表完整性、切换控件渲染、注入内容与五行钩子”：`tests/test_web_themes.py` L15-39（注册表、CSS 作用域、脚本合法性）、L42-74（注入与纯客户端按钮、五行钩子）均存在并通过；节点桩测试 L77-136 覆盖读取顺序、URL 记忆、无效回落与 `apply` 持久化。
- 验收记录声称的修正均能在代码中找到：品牌/操作区各自 `nowrap`、整体 `wrap`、窄屏缩小色样（`web.css:15-16,21,167-171`）；印章 `scale(1.3)`、CRT `scale(.3,.004)`（`ink.css:73`、`neon.css:94`）。
- 验收记录“38 项通过”“lock/diff --check 通过”“切走后画布与变量被清理”“`?theme=neon` 生效并记忆”“无效值回落”“390/320px 无溢出，390px 头部单行”均由本审查独立复现。
- README 新增的皮肤说明、`?theme=` 参数、`localStorage`、减少动态效果描述与实现一致。

## 问题列表

1. 非阻断 · 中 — `src/themes/night.css:19`、`src/themes/neon.css:29`（指南对话框覆盖处）：对话框内 `开始探索` 按钮沿用 Quasar `unelevated` 默认 `bg-primary text-white`，星夜为白字配 `#e0b755`（对比度 1.90:1），霓虹为白字配 `#22e3ff`（1.56:1，且被扫描线遮罩再削弱），低于可读阈值；规格要求所有皮肤下指南对话框可读可用。建议仿照 `.submit-button` 的处理，为 `html[data-theme="night"] .guide-dialog .q-btn--unelevated` 与 `neon` 对应规则设深色文字（如 `#1a1408` / `#07070d`）或改用描边样式。
2. 非阻断 · 低 — `tests/test_web_themes.py:79`：`ThemeScriptLogic` 说明文字称验证“清理逻辑”，但桩环境 `document.body: null`（L93）使 `apply` 永不调用 `effects[id].start()/stop()`，画布、监听器与 CSS 变量的清理仅由浏览器验收覆盖。建议修正说明，或在桩中提供最小 `body`/`canvas` 与 `getContext` 桩以断言 `start/stop` 的副作用。
3. 非阻断 · 低 — `.scratch/web-themes/spec.md` 皮肤清单“`web.css` 不改动既有规则”与 `src/web.css:15,16,21,167` 对既有规则的修改不一致；验收记录已把“头部换行策略”列为允许例外，且这些改动对默认皮肤只影响头部换行与 ≤600px 头部间距（20px→12px）。建议在规格中补记这一例外，使规格、验收与实现表述一致。

## 覆盖限制

- 浏览器验证使用 Chrome 自动化标签页，且标签页处于后台：`requestAnimationFrame` 与 Vue 过渡不派发、CSS 动画停在起始帧，因此流星、CRT 开机、盖印/墨晕入场、扫描光带与故障字效仅按代码与伪元素计算样式核对，未观察到运动过程；对话框需手动移除过渡类后截图。
- 减少动态效果通过覆盖 `window.matchMedia` 模拟，未在系统层面切换；页面隐藏暂停按代码路径检查。
- 无 AI 密钥，AI 等待与解读卡片在各皮肤下的呈现仅按 CSS 规则核对；未调用真实 AI 服务。
- 默认皮肤“与基线一致”依据 `web.css` 差异的静态分析与 390/320px 头部几何核对，未做像素级截图比对。
- 未验证 Safari、Firefox 与实体手机；未做辅助技术朗读测试。

## 复查

- 日期：2026-09-16（同日复查）。复查对象为针对上述 3 项非阻断问题及 Standards 审查意见的修复；仍未修改实现代码，未提交。
- 重新运行：`uv run python -m unittest discover -s tests -v` 40 项通过（新增 `test_theme_constants_reject_values_unsafe_for_markup`、`test_night_effect_starts_on_activation_and_cleans_up_on_switch`）；`uv lock --locked` 通过；`git diff --check` 及未跟踪文件逐个空白检查通过。
- 括号感知解析重新核对三份主题 CSS：所有规则仍只匹配自身 `html[data-theme="<id>"]`，12 个 keyframes 名称均带主题前缀；无外部字体/图片/脚本引用；`README.md` 相对基线的改动未变。

### 逐项结论

1. 问题 1（对话框按钮对比度）— 已解决。`night.css:35`、`neon.css:51`、`ink.css:40` 新增 `.guide-dialog .q-btn--unelevated` 覆盖，特异性 (0,3,1) 高于 Quasar `.text-white`/`.bg-primary`，`!important` 生效。本地服务（8792）打开指南对话框并逐皮肤读取计算样式：星夜 `#1a1408` 字配金色渐变 `#f1d48a→#d4a843`，对比度 12.66–8.26:1；霓虹 `#07070d` 字配 `#22e3ff`，12.92:1；水墨 `#f8f7f2` 字配 `#161616`，16.87:1；默认皮肤保持白字配 `#a34432`（6.12:1，未受影响）。截图放大核对霓虹与星夜按钮文字清晰可读。
2. 问题 2（节点桩未执行效果启停）— 已解决。`tests/test_web_themes.py:91-133` 桩现提供 `body.appendChild`、`createElement→canvas`、`getContext` 代理、窗口/文档监听器登记与根元素样式变量记录；`test_night_effect_starts_on_activation_and_cleans_up_on_switch` 断言激活星夜后画布 1 个、`resize/pointermove/visibilitychange` 各 1 个、`--msr-mx/--msr-my` 已写入，切走后三者归零/清空；`test_stored_theme_applies_before_paint_and_starts_its_effect` 断言存储为 night 时加载即启动画布。桩文件改写入 `tempfile.TemporaryDirectory()`，不再落在 `tests/`。说明文字与实际覆盖一致。
3. 问题 3（规格与 `web.css` 改动不一致）— 已解决。`.scratch/web-themes/spec.md:11` 皮肤清单已补记例外：切换控件样式、头部换行策略（`.site-header`/`.brand`/`.header-actions` 的换行与窄屏间距）与减少动态效果下的动画迭代次数限制，与 `git diff 9af7aac -- src/web.css` 的实际改动一致。残留一处措辞：同文件“计划”第 1 条（L29）仍写“`web.css` 只追加切换控件样式”，属历史计划文本，与已补记的例外略有出入，不影响验收判定，可顺手改为与皮肤清单一致。

### 随 Standards 意见的附带改动核对（无新增规格偏差）

- `theme.js:10-11` 在脚本加载时缓存 `matchMedia('(prefers-reduced-motion: reduce)')`，`reducedMotion()` 读取其实时 `matches`；`start()` L98-103 注册 `change` 监听，切换偏好时取消帧循环、清空流星并按新偏好静态绘制或重新启动；`stop()` L111 同步移除。节点桩的 `matchMedia` 不含 `addEventListener`，脚本以 `typeof` 守卫，桩测试不受影响；浏览器中重新核对切到星夜后画布与指针变量写入、切回素纸后画布移除、变量清空、`aria-pressed` 与 `localStorage` 同步。
- `theme.js:153-157` MutationObserver 增加 15 秒兜底断开；桩脚本以 `process.exit(0)` 结束以免等待定时器。
- `web.py:39-44` `Theme.__post_init__` 校验 id 为 `[a-z][a-z0-9-]*`、文案不含双引号，四个注册主题均通过；测试覆盖四种非法值。
- `web.py:260` 色样按钮新增 `aria-label="<皮肤名>"`，浏览器核对为 素纸/星夜/水墨/霓虹；与 `title`（名称 · 描述）并存，窄屏隐藏文字后可访问名称仍明确。`test_page_injects_assets_and_client_side_switcher:67` 已断言。
- `test_theme_stylesheets_only_target_their_own_skin:37-38` 新增 keyframes 前缀断言。
- 以上改动未触及文案、输入默认值/范围、模型选项、结果与状态文案、算法或 `create_page`；每次页面请求仍创建独立 `DivinationWebApp`。

### 复查结论

3 项非阻断问题均已解决，未发现新的规格偏差或行为回归；阻断问题 0。仅余问题 3 的历史计划文本措辞（`spec.md:29`）可选修订。复查覆盖限制同主报告：浏览器标签页处于后台，动画运动过程仍按代码核对；未在系统层面切换减少动态效果偏好验证 `change` 监听。
