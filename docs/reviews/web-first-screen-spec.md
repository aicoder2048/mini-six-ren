# Web 首屏布局调整：Spec 独立审查

- 日期：2026-09-16。
- 审查者：独立 Spec Agent，未参与实现。
- 规格：`.scratch/web-first-screen/spec.md`；任务：`.scratch/web-first-screen/issues/01-first-screen.md`；验收记录：`docs/reviews/web-first-screen-acceptance.md`。
- 基线：`b5d929c`。
- 范围：`git diff b5d929c` 中的 `src/web.py`、`src/web.css`、`src/themes/{ink,night,neon}.css`、`README.md`、`tests/test_interpretation_experience.py`、`tests/test_regressions.py` 逐行阅读；未跟踪文件 `.scratch/web-first-screen/spec.md`、`.scratch/web-first-screen/issues/01-first-screen.md`、`docs/reviews/web-first-screen-acceptance.md` 全文阅读。验证在本工作树内完成，未修改实现代码，未提交，未使用 stash。

## 结论

阻断问题 0，非阻断问题 3。规格"设计与验收"各条均有对应实现并在浏览器中复现：页头 88px（≤900px 为 80px）、主视觉两行且标题与副标题同行基线对齐、表单顺序"输入 → 错误 → 开始占卜 → 状态 → 折叠选填区"、折叠区随 AI 可用性默认展开/收起、文案全部改为"开始占卜"、问题框 56px、冗余提示删除、水墨主视觉横排且竖排规则全部移除、三套皮肤折叠区配色。四套皮肤在 1440×900 视口下主按钮底边 ≤530、空状态底边 ≤804；390px 视口主按钮底边 ≤544、无横向溢出；点击后三张三传卡片在桌面首屏。算法文件无改动，浏览器结果与 `HandTechnique.predict` 一致。三项非阻断问题分别是：星夜/霓虹下折叠区副标题与标题同色（层级丢失）；水墨水印在 901–约 1070px 视口与副标题末尾轻微重叠；水墨折叠区未按规格提供与面板一致的标题色。

## 独立运行的验证

- `uv run python -m unittest discover -s tests -v`：41 项全部通过（含新增 `test_optional_panel_follows_ai_availability_and_button_names_the_action`）。
- `uv lock --locked`：通过。`git diff --check`：通过；三份未跟踪文件逐个 `git diff --no-index --check /dev/null <file>` 与 `grep -nE " +$"`：无行尾空白。
- `git diff b5d929c --stat -- src/hand_technique.py src/utils/ src/symbols.py src/five_elements.py src/ai_agent.py data/`：为空，算法与数据文件未改动；`HandTechnique.predict(1,2,3)` 为 大安/留连/赤口、(比和, 被克)，与浏览器点击"开始占卜"后的卡片一致。
- `grep` 全仓（`src/`、`README.md`、`tests/`、`docs/`）：`form-divider`、`form-section-title`、`optional-label`、`writing-mode`、`vertical-rl`、`text-orientation`、`row-reverse` 零命中；"查看三传"仅残留于规格"问题"段落的历史描述；"开始占卜"出现在 `web.py:164,225,226,336,337`、`README.md:40,107,108` 与两处测试断言。
- NiceGUI 2.20.0 `Client(ui.page('/x'), request=None)` 上下文：`ui.expansion(..., value=True)` 的 `model-value` 为 True；`ui.row().classes('hero-line')` 的类为 `nicegui-row row hero-line`，换行由 `web.css:26` 的 `flex-wrap: wrap` 提供。
- 本地服务两实例（`reload=False`，`host=127.0.0.1`）：8101 以 `env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY` 启动（无模型）；8102 以 `OPENAI_API_KEY=offline-test` 启动（一个模型）。工作树无 `.env`。
- Claude in Chrome：窗口 1440×900 时实际视口仅 1440×779（浏览器 chrome 占位，`resize_window` 无法把视口撑到 900），因此规格所述"1440×900 视口"改用同源 iframe（1440×900）精确复现；390×844、1200×900、1024×768、901×900、820×1180 同法。后台标签页内 CSS 动画停在起始帧，霓虹 `neon-crt` 起始 `scale(.3,.004)` 会把整页压扁，量测前注入 `body{animation:none!important}`，仅影响动画不影响布局。
- 1440×900 视口，8101（无模型）四套皮肤：页头 0–88；主视觉 88–215（水墨 88–229）；眉题 116–133；`.hero-line` 143–189，标题 143–189（36px）与副标题 163–184 同行，`align-items: baseline`，两者间距 18px；主按钮底边 素纸 524 / 星夜 524 / 水墨 530 / 霓虹 516，文案"开始占卜"；状态行"准备就绪：填写输入后开始占卜。"；折叠区收起（`q-expansion-item--collapsed`），副标题"选填 · 留空只看三传，本地无需 AI"；空状态底边 素纸/星夜/霓虹 790、水墨 804，末行提示底边 782/796；`scrollWidth` 等于 1440。
- 1440×900 视口，8102（有模型）素纸：折叠区展开，副标题"选填 · 填写问题后可获得 AI 解读"，展开后底边 847，主按钮底边仍为 524；问题框 `min-height: 56px`；解读方式默认值"OpenAI GPT-5.6"；面板内说明"选择 AI 并填写问题后生成解读；问题留空则只计算三传。"。
- 390×844 视口（8102，四套皮肤）：页头 80px；标题 28px 且副标题换到下一行（标题底 165/183，副标题顶 183/201）；`.hero-aside` 隐藏；主按钮底边 素纸 526 / 星夜 526 / 水墨 544 / 霓虹 518；`document.documentElement.scrollWidth` 与 `body.scrollWidth` 均为 390，所有元素右缘最大值 390；展开后问题框/下拉在 627–805 之间，霓虹输入文字 `#fff` 底 `rgba(7,7,13,.6)`、星夜 `rgb(236,231,217)` 底 `rgba(255,255,255,.043)`、水墨 `#161616` 底 `#fff`。
- 点击"开始占卜"（1440×900，8101）：素纸三张卡片 477–837、水墨 491–867，均在首屏；`.input-snapshot` 为"数字模式 · 起课数字：1、2、3"；关系标题"初传→中传 · 比和""中传→末传 · 被克"；状态"本地三传已完成。选择AI并填写问题，可再次提交获取解读。"；按钮恢复"开始占卜"且可用。
- 水墨 1440 截图：标题横排粗体（`font-weight: 700`），`::after` 为 8px 笔触 SVG 下划线；`.hero::after` 内容「觀」108px、位于 `left: 62%`（x≈740–848），在主视觉带（88–229）内未被裁切；`.hero-aside` 朱印横排、`rotate(-2deg)`、置右（x 1166–1361）；`writing-mode` 全部为 `horizontal-tb`。
- 中间宽度：1200×900、1024×768、901×900 素纸与水墨主按钮底边 515–524、空状态底边 781–798、无横向溢出；820×1180 单列布局主按钮底边 494/512。

## 逐条验证证据

### 设计与验收

| 规格条目 | 实现位置 | 判定 |
|---|---|---|
| 页头最小高度 104→88px，≤900px 为 80px | `web.css:15` `min-height: 88px`；`web.css:150` `min-height: 80px` | 符合；浏览器 1440 高 88、390 高 80 |
| 主视觉两行：眉题一行，标题（28–36px）与副标题同行、基线对齐，窄屏自动换行 | `web.py:298-302` 眉题后新增 `ui.row().classes('hero-line')` 包裹标题与副标题；`web.css:24-29` `.hero` 内边距 48/38→28/26、`.hero-line { align-items: baseline; gap: 18px; flex-wrap: wrap }`、`.hero-title` `clamp(28px, 2.6vw, 36px)`；`web.css:151,175` 窄屏 22/20 与 28px | 符合；1440 为 36px 同行基线对齐，1200 为 31.2px，≤1024 为 28px，390 换行 |
| 表单顺序：起课方式 → 输入 → 错误提示 → 开始占卜 → 状态行 → 折叠选填区 | `web.py:334-349`：`error_message` → `submit_button` → `status_message` → `optional_panel`（`ui.expansion`）内含 `question_input`、`model_select`、本地说明/AI 说明；原 `ui.separator`、"心中所问"标题、`optional-label` 删除 | 符合；浏览器 `.form-card` 子元素顺序 section-heading / tabs / panels / error-message / button / status-message / optional-panel；`test_regressions.py:293-294` 断言两控件父级为折叠区 |
| 配置了 AI 模型时选填区默认展开，否则收起并说明"本地无需 AI" | `web.py:339-340` `caption` 按 `available_models` 二选一，`value=bool(self.available_models)` | 符合；8101 收起 + "选填 · 留空只看三传，本地无需 AI"，8102 展开 + "选填 · 填写问题后可获得 AI 解读"；`test_regressions.py:283-294` 覆盖两种情况 |
| 主按钮文案"开始占卜"，就绪状态同步；处理中"正在计算…/正在解读…"与完成/失败文案不变 | `web.py:336-337` 按钮与就绪文案；`web.py:164` `finally` 恢复"开始占卜"；`web.py:110-111,140-142,151-159` 处理中/完成/失败文案未在 diff 中出现 | 符合；点击后状态与按钮恢复均复现；`test_interpretation_experience.py:130`、`test_regressions.py:292` 断言 |
| 卡片内边距与间距收紧 | `web.css:34` `.form-card` 28→24px、gap 16→14；`web.css:49` `.input-hint` 14→10；`web.css:78-79,90,95` 空状态 27→20、罗盘间距 30→22、阶段引导 36→26、末行 38→26；`web.css:177` ≤600px 22/18→20/16 | 符合 |
| 问题框最小高度 80→56px | `web.css:66` `min-height: 56px`（`web.py:342` 同时 `rows=3→2`，Quasar `autogrow` 渲染为 `rows=1`，实际高度由 CSS 决定） | 符合；浏览器计算值 56px |
| 去掉"选一个方式，从此刻开始。" | `web.py` diff 删除 L310 `helper-text` 标签；浏览器 `.form-card > .helper-text` 不存在 | 符合 |
| 空状态引导文案写明「开始占卜」 | `web.py:225-226` 桌面/手机两版文案；`web.css:88` `.empty-copy` `max-width` 310→400 以容纳加长文案 | 符合 |
| 水墨主视觉横排：粗体标题配笔触下划线，朱印横排置右，水印「觀」缩小到主视觉带内；竖排规则移除 | `ink.css:16-23`：`.hero { overflow: hidden; padding: 30px 0 28px }`、`::after` 108px `left: 62%`、`.hero-title` 700 + `::after` 8px `var(--brush)`、`.hero-aside` 横排 `rotate(-2deg)`；原 L15-24 竖排规则与 L78-82 窄屏回横排规则全部删除；`ink.css:75-79` 仅保留水印隐藏、字距、卡片阴影 | 符合；全仓无 `writing-mode`；见问题 2（中等宽度水印位置） |
| 星夜、霓虹、水墨为折叠区提供与各自面板一致的边框、背景与标题色 | `night.css:61-62` 边框 `var(--line)`、背景 `var(--surface-2)`、标题 `var(--ink)`；`neon.css:46-47` 边框 `var(--line)`、背景 `rgba(7,7,13,.6)`、标题 `#fff`；`ink.css:35` 直角、边框 `var(--ink)`、背景透明，未设标题色；三套皮肤均删除已无元素的 `.form-divider`（neon 同时从等宽字体列表移除 `.optional-label`） | 星夜/霓虹符合，副标题层级见问题 1；水墨标题色见问题 3 |
| 1440×900 视口四套皮肤主按钮与右侧空状态位于首屏 | 见"独立运行的验证"：主按钮底边 516–530，空状态底边 790–804 | 符合 |
| 390px 视口主按钮位于首屏、无横向溢出 | 主按钮底边 518–544；`scrollWidth`=390，元素右缘最大 390 | 符合 |
| 点击后三传结果在桌面首屏可见 | 素纸 477–837、水墨 491–867 | 符合 |
| 现有输入默认值/范围、模型选项、结果内容与 AI 流程不变；`question_input`、`model_select` 仍可由测试直接赋值 | `web.py:320-331` `ui.number(value=i+1, min=1, max=999)`、日期 `min=1900-01-01 max=2099-12-31` 未变；`web.py:343-345` `model_options` 构造与 `on_change=self._on_model_change` 未变；`_perform_divination` 除 L164 文案外无改动，仍读取 `self.question_input.value` 与 `self.current_model`；`_display_results`、`_display_ai_result`、`create_page` 未变 | 符合；`test_regressions.py:236,239,269,307`、`test_interpretation_experience.py:158` 直接赋值通过；算法文件零改动 |

### README 与验收记录

- `README.md:40` 新增首屏说明；`README.md:106-108` 步骤改为"选择起课方式 → 开始占卜 → 心中所问 · 解读方式（可选）"，与实现顺序和折叠区默认态一致；步骤 4/5 未变。
- 验收记录"41 项通过""lock/diff --check 通过""四套皮肤主按钮底边 y≈524""选填区展开底边 y≈847，主按钮位置不变""390px 主按钮底边 y≈526–544、`scrollWidth` 等于视口""点击后三张卡片在首屏""水墨横排、水印在带内、朱印置右"均由本审查独立复现，数值一致（霓虹主按钮底边 516 略低于记录的 ≈524，属去除 CRT 动画后的正常差异）。
- 验收记录称视口 1445×941；本机 Chrome 在 1440×900 窗口下视口为 779px，此时主按钮（524）仍在首屏，空状态末行提示（766–782）贴近折叠线。规格以"视口"为准，判定不受影响，但实际 900px 高的窗口余量很小。

## 问题列表

1. 非阻断 · 低 — `src/themes/neon.css:47`、`src/themes/night.css:62`：`html[data-theme] .optional-panel .q-item__label` 的特异性 (0,3,1) 同时命中副标题 `.q-item__label--caption`，覆盖了 `web.css:64` 的 `var(--muted)`；浏览器计算值霓虹标题/副标题均为 `#fff`，星夜均为 `rgb(236,231,217)`，副标题失去弱化层级（素纸与水墨保持 muted）。建议在两套皮肤追加 `.optional-panel .q-item__label--caption { color: var(--muted) }`。
2. 非阻断 · 低 — `src/themes/ink.css:17`：水印 `left: 62%` 在 901–约 1070px 视口下与副标题末尾重叠（901px：水印 x≈497–605，副标题右缘 602；1024px：573–681 vs 602；1200px 起不重叠）。5% 不透明度，仅视觉层面。建议在 `@media (max-width: 1199px)` 内右移（如 `left: 72%`）或缩小字号。
3. 非阻断 · 低 — `src/themes/ink.css:35`：规格要求水墨为折叠区提供"与面板一致的…标题色"，当前仅覆盖边框与背景，标题沿用 `web.css:63` 的 `#4c493f`（600），与水墨面板标题 `var(--ink)`（`#161616`，700）不一致；白底上可读，仅为规格字面偏差。建议补 `.optional-panel .q-item__label { color: var(--ink) }`。

## 覆盖限制

- 浏览器验证使用 Chrome 自动化标签页且处于后台：CSS 动画停在起始帧，量测时注入 `body{animation:none!important}` 去除霓虹 CRT 起始缩放；折叠区展开/收起过渡、水墨盖印等运动过程未观察。
- 1440×900 与 390×844 视口均通过同源 iframe 复现（本机窗口最大只能得到 779px 视口）；未在实体手机、Safari、Firefox 验证。
- 有模型状态通过 `OPENAI_API_KEY=offline-test` 的第二实例观察；未调用真实 AI 服务，AI 等待/解读/失败文案仅按代码差异（未改动）与既有单元测试核对。
- 未做辅助技术朗读测试；折叠区头部的键盘可达性依赖 Quasar `QExpansionItem` 默认行为，规格未要求，未单独验证。

## 复查

- 日期：2026-09-16（同日复查）。复查对象为针对上述 3 项非阻断问题及 Standards 审查意见的修复；仍未修改实现代码，未提交，未使用 stash。复查期间实现者仍在并发修改（`ink.css` 副标题规则在首次量测后追加），以下结论以最终文件状态为准，并在追加后重新量测。
- 重新运行：`uv run python -m unittest discover -s tests -v` 41 项通过；`uv lock --locked` 通过；`git diff --check` 及未跟踪文件逐个空白检查通过。括号感知解析重新核对三份主题 CSS：所有规则（含 `@media` 内）均以 `html[data-theme="<id>"]` 开头。
- 本地服务 8103（无模型）/ 8104（`OPENAI_API_KEY=offline-test`）/ 8105（无模型，追加规则后复测）+ Claude in Chrome，同源 iframe 1440×900 与 1440/1280/1200/1101/1100/1024/901 宽度逐一量测；用毕已关闭标签页与实例。

### 逐项结论

1. 问题 1（星夜/霓虹副标题层级）— 已解决。`night.css:64`、`neon.css:48` 新增 `.optional-panel .q-item__label--caption { color: var(--muted) }`，特异性 (0,3,1) 与标题规则相同且位于其后。计算样式：星夜标题 `rgb(236,231,217)`（`--ink`）/ 副标题 `rgb(166,169,188)`（`--muted`）；霓虹标题 `#fff` / 副标题 `rgb(127,163,179)`（`--muted`）。
2. 问题 2（水墨水印与副标题重叠）— 已解决。`ink.css:17` 水印改为 `left: 68%`，`ink.css:77-79` 新增 `@media (max-width: 1100px)` 隐藏；原 ≤900px 媒体块仅保留字距与卡片阴影。量测：1440 水印 x≈896–1004（副标题右缘 714、朱印左缘 1166）、1280 为 799–907（660 / 1038）、1200 为 745–853（644 / 958）、1101 为 683–791（607 / 875），均不与副标题或朱印重叠；1100、1024、901 水印 `display: none`。1440 主按钮底边 530、空状态底边 804，首屏结论不变。
3. 问题 3（水墨折叠区标题色）— 已解决。`ink.css:36` 新增 `.optional-panel .q-item__label { color: var(--ink) }`，标题计算值 `rgb(22,22,22)` 与 `.panel-title` 一致。首次量测时该规则同样命中副标题（`rgb(22,22,22)`，重现问题 1 的层级丢失）；实现者随后追加 `ink.css:37` `.q-item__label--caption { color: var(--muted) }`，复测副标题为 `rgb(106,106,102)`（`--muted`），层级恢复。四套皮肤最终为：标题 素纸 `#4c493f` / 星夜 `--ink` / 水墨 `--ink` / 霓虹 `#fff`，副标题均为各自 `--muted`。

### 随 Standards 意见的附带改动核对（无新增规格偏差）

- `night.css:61` `.culture-panel` 恢复为只改边框；点击"开始占卜"后计算样式背景 `rgba(0,0,0,0)`、边框 `rgba(224,183,85,.2)`，与基线一致；`.optional-panel` 仍为 `--surface-2` 背景（`night.css:62`）。
- `web.py:275-277` 页内指南三步改为"01 · 选择起课方式 / 02 · 点「开始占卜」/ 03 · 心中所问（选填）"，浏览器打开对话框核对文案与 `README.md:106-108` 步骤顺序一致；对话框按钮"开始探索"未变。全仓无"查看三传"残留。
- `tests/test_regressions.py:295-296` 新增顺序断言：主按钮在 `parent_slot.children` 中的索引小于折叠区，两种模型状态均通过。
- 验收记录视口表述改为"Chrome 窗口按 1440×900 设置（工具实测视口 1445×941）"，与本审查"窗口尺寸不等于视口"的观察一致。
- 以上改动未触及输入默认值/范围、模型选项、结果与状态文案、`_perform_divination` 或算法文件；`README.md`、`web.css` 相对基线的差异与主报告审查时相同。

### 复查结论

3 项非阻断问题均已解决，Standards 相关附带改动未引入新的规格偏差或行为回归；阻断问题 0。复查覆盖限制同主报告：后台标签页动画停在起始帧、视口通过 iframe 复现、未调用真实 AI、未测 Safari/Firefox/实体手机。
