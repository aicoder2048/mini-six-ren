# Web 实时 AI 解读与结果区直达计划

## 目标与边界

实现 Web 真流式五段解读、结果标题栏 AI 入口、提交后定位及窄屏表单摘要。保持本地三传先展示、失败保留本地结果，以及现有「开始占卜」输入校验和条件调用 AI 的语义。

只修改 `src/ai_agent.py` 的 Web 异步链路、`src/web.py`、`src/web.css`、`src/themes/night.css`、`src/themes/ink.css`、`src/themes/neon.css`、`README.md`、`tests/test_interpretation_experience.py`、`tests/test_regressions.py`。素纸由 `web.css` 实现，无须新增 paper.css。不新增依赖。

不改 `src/hand_technique.py`、`src/utils/symbol_relations.py`、`data/symbols.json`、AI 系统 Prompt、事实 payload、token 预算、CLI 的任何行为、历法/笔画映射、九宫动画算法；不做八字/五行/太岁集成、导出/历史/分享、模型超时或重试。

## 已核实的基础

- 已阅读根目录 `CLAUDE.md`、开发流程及 CLI 非交互规格。规划基线 `c8b3988`；工作树有未跟踪的 `requests/web-stream-and-ai-reach.md`，不得覆盖或随意提交它。本阶段未实现、未运行测试。
- `_stream_interpretation_web` 消费累积 `stream_text()`，但只在结束时返回 `_format_markdown_for_web(full_response)`；Web 当前只显示 spinner。
- `_perform_divination` 同时负责本地计算和 AI；`_display_ai_result` 目前每次清空并重建卡片。`create_page` 已确保每个 Client 独立控制器，必须延续。
- `.workspace` 在 900px（含）以下变单列。当前表单未保存卡片引用，错误/状态均位于表单，收起后必须在 AI 卡片仍看得到生成/失败状态。
- CLI 非交互通过重定向 stdout 调用同步 `interpret_prediction`，不是 Web 异步 API；同步 `_stream_interpretation`/Rich Live 不动。`docs/specs/612ee1b2_cli-question-ai-interpretation.md` 的无进度、纯 JSON、退出码等约束继续有效。
- 测试侦察已由独立子 Agent 完成：现有 NiceGUI Client + unittest/asyncio.Event、FunctionModel 风格可以直接扩展。依赖 `stream_text` 默认 `delta=False`（累积快照），默认短时合并可能掩盖过快的测试片段。

## 1. Web 流式接口（先做）

在 `src/ai_agent.py`：

1. 为 `interpret_prediction_async` 和 `_stream_interpretation_web` 增加可选关键字参数 `on_update=None`，明确类型为接收累计 Markdown 字符串、返回 Awaitable[None] 的异步回调。默认不回调，保留 `await ... -> str`，旧调用仍然有效。
2. 每个 `stream_text()` 快照覆盖 `full_response`，不能使用 `+=`；使用既有 formatter 得到展示快照，顺序 `await on_update(snapshot)`。可显式指定 `delta=False, debounce_by=None` 以不额外合并供应商片段，并按已安装 API 核实参数；修改相应 stub 签名。不要创建未等待的回调任务。
3. 正常结束仍从最后原始累计文本调用同一个 formatter 返回权威全文；不从骨架拼接得到最终结果。回调缺省时最终结果与现状完全相同。
4. 异常按现有规则传播并包装；不返回错误字符串，不吞掉回调异常，不加控制台输出、超时或自动重试。同步 CLI 方法和 formatter 本身不改。

## 2. 稳定 AI 卡片与五段骨架

在 `src/web.py` 给每个控制器保存 AI Markdown、AI 状态标签、结果区按钮等引用。将 `_display_ai_result` 拆分/扩展为「开始生成、更新内容、成功收尾、失败」几个清楚的操作，供两个入口共用。

- 发起调用前创建一次 `.ai-card` 和一个持久的 `ui.markdown`，初值按顺序为：`### 一句话判断`、`### 初传｜起点`、`### 中传｜过程`、`### 末传｜趋势`、`### 行动建议`。卡片标记 busy，显示「正在生成…」及当前问题/模型（问题用 label，不拼 HTML）。
- 增量中对同一 Markdown 实例 `set_content`，不反复 `ai_result_area.clear()`、重建卡片或重绘本地三传。spinner 可以保留作状态装饰，但正文不能等结束才显示。
- 增加一个纯展示投影函数：输入已格式化的累计文本，输出当前文本及尚未抵达的五段骨架标题。对规范顺序输出，已到达章节替换对应占位、未到达章节保留，完整标题不重复。以行首完整标题识别，处理标题/粗体跨片、重复快照；不要丢弃尚未成段的首个非空片段、前言或非标准文本。可以将累计正文保留并补齐未到标题；不要把完整五段骨架简单附加到正文末尾。此投影仅影响生成中展示，不校正模型内容、不注入事实。
- 成功时直接 `set_content(interpretation)`（异步方法的权威返回值），令 `ai_interpretation == markdown.content == _format_markdown_for_web(raw_full_text)`，移除所有骨架辅助内容、busy 状态和生成提示。不强迫缺标题或异常格式输出保留虚构标题；非标准输出同样以原有完整路径结果为准。
- 失败策略明确：清除未完成的 AI 正文/骨架，`ai_interpretation = None`，在 AI 卡片内显示可见失败提示和「本地结果已保留，可重新解读」。不把部分输出当成功。保留原有 `error_message`、`status_message` 更新及 `divination_result`、`result_area`。请求开始前清理旧成功状态，防止失败后旧答案冒充本次答案。
- 状态用 `role=status`/`aria-live=polite`，失败用 alert；避免每个 token 都让读屏器重读全部正文。

## 3. 两个入口共享同一请求流程

新增 `_request_ai_interpretation`（结果区事件）及一个内部 AI 运行 helper；具体命名可调整，但不要让结果区按钮调用整个 `_perform_divination`。

### 原提交入口

- 校验和本地计算顺序不变。成功设置已有输入快照并 `_display_results`；本地成功即允许窄屏摘要收起，无须等待 AI 成功。
- 有选中 AI 且问题 strip 后非空才调用共用 AI helper。无模型或空问题仍只做本地计算，不构造 Agent。
- local-only 成功可以定位 reading-panel；不能滚到空白 AI 区域。

### 结果标题栏入口

- 在 `create_ui` 的 `.reading-heading` 内新增持久按钮，初始文案「生成 AI 解读」。没有本地结果时禁用；本地结果存在时可用；成功后文案「重新解读」。失败后仍可再次生成。
- 点击时读取既有 `question_input.value` 与 `model_select` 所代表的当前模型，不新增第二组输入，不用旧 `question_snapshot` 代替当前问题。保持 `_on_model_change` 与 `current_model` 的一致性，不维护互相竞争的模型来源。
- 使用现有 `divination_result.symbols`，不重新预测、不读取已修改但尚未提交的数字/日期/汉字来替换结果。保留本次本地起课快照；卡片显示实际请求的问题/模型，避免与旧起课问题混淆。
- 模型为 local、无可用模型或问题为空时不发请求，给出具体提示，展开表单及 optional_panel，定位可修改字段。保留本地结果；无凭据时不能出现死路按钮。
- 两个入口共用 `is_running` 防重入和禁用/恢复逻辑，不能由 helper 再拿一次锁导致自己的请求被跳过。推荐最外层各自设置 busy，内部 helper 不重复检查锁，finally 恢复两按钮。未完成时互点也只能产生一个请求。
- 在首次 await 前捕获 result/question/model 快照；生成期间修改输入不会改变当前请求、标签或收尾结果。引用全部是当前 Client 私有。

## 4. 定位与窄屏表单摘要

### 定位

- 给 `ai_result_area`、表单内容及 reading-panel 保存稳定引用/安全 DOM id。AI 骨架进入 DOM 且摘要收起后，只在每次请求开始定位一次 AI 区域，后续片段不抢滚动位置。
- 使用 NiceGUI `ui.run_javascript` 提交客户端定位：等待 DOM 更新/一帧，再 `scrollIntoView({block: 'start', behavior: reduced ? 'instant' : 'smooth'})`；通过 `window.matchMedia('(prefers-reduced-motion: reduce)').matches` 判断。沿用 CSS reduced-motion 规则。插入脚本的仅限程序生成的元素 id，不插问题文本。
- 定位是非阻塞增强：不要 await 浏览器返回值再开始模型调用，避免无浏览器的 Client 测试挂起。目标不存在安全返回；客户端定位失败不能被包装成模型失败。

### 表单状态

- 在 `.form-card` 中保留一个摘要行和一个 `.form-details` 容器，现有控件移动进后者但不销毁重建；保存 card、details、summary_label、edit_button 引用。
- 初始/校验失败为 expanded；本地成功设置 collapsed 状态类（如 `.has-reading.form-collapsed`）。CSS 只在 `@media (max-width: 900px)` 隐藏 details、显示摘要。桌面始终展示完整表单，跨断点自动正确切换，不用一次性服务端屏幕宽度判断。
- 摘要一行：模式/起课数字（时间或汉字源信息沿用 input_summary），问题短摘要及模型/仅本地；长文本省略，提供可访问的完整文本，固定可见「修改」按钮，不横向溢出。它描述最后成功提交的快照，不伪称未提交输入已重新计算；AI-only 重新解读可刷新问题/模型摘要而不更改起课数字。
- 「修改」展开同一组原控件，保留所有值/当前 tab/模型和已有三传，维护 aria-expanded/aria-controls，定位表单；下一次成功提交再次收起。AI 失败不撤销本地成功收起状态，失败信息必须在可见 AI 卡片中。
- 原错误/状态在 details 中可保留，但校验失败必须展开；AI 的运行/错误状态在结果区亦可见。不要为一行摘要丢失输入或把全页三传长内容强行压进一个视口。

## 5. 样式与文档

- `src/web.css`：增加结果区 AI 按钮、摘要/修改按钮、表单 details、AI busy/error 状态的布局与素纸配色；header 可换行、点击区足够大、focus-visible/disabled 状态清晰；摘要 flex 子项 min-width:0、ellipsis，修改按钮不收缩；AI 区域适当 scroll-margin-top。
- `night.css`、`ink.css`、`neon.css`：分别补充新控件/摘要/失败状态，复用现有主题变量和视觉风格（金色深空、朱文墨线、荧光边框）；不要让浅色默认背景泄漏到深色皮肤。新骨架标题沿用 `.ai-interpretation h3`。适配主题的 specificity 与 600px 规则，确保后加载主题不覆盖隐藏/展开契约。
- README 替换「再等待完整解读，生成期间显示等待状态」：本地先显示、五段骨架随生成实时填充、可在结果区生成/重新解读、移动端成功后摘要收起并可修改；保留密钥与本地模式说明。使用指南第 03 项同步提示结果区入口。

## 6. 离线测试计划

优先写失败测试，再实现。扩展既有文件，不新建联网测试设施。

### tests/test_interpretation_experience.py

1. Agent 流式接口：离线 context manager/stream stub 按累积快照提供多个片段，暂停于 Event；首个及第二个快照在结束前收到回调，有无回调返回值严格相等；捕获 stdout/stderr 证明 Web 无终端进度。至少一份包含多重星号、四级标题、多空行/列表的 fixture 验证 formatter 一致性。
2. Web 真更新：用真实 Agent + 可控离线 stream（或 FunctionModel + Event）运行 `_perform_divination`，流未放行前断言五标题骨架、本地结果已存在；逐次放行断言 Markdown.content 已包含新增正文、task 未完成、同一 Markdown id 未变、result_area 未重建。结束断言内容和权威全文逐字相等，无占位残留。
3. 投影边界：空片段、首个不完整标题、跨片标题和粗体、重复累计快照、一次返回完整内容、缺标题/额外文本；规范五标题不重复，最终不丢字、不拼重复正文。期望值使用独立字面量，不只调用实现生成期望。
4. 保留 PromptContracts（仅单标题的现有 FunctionModel）并确认同步/异步最终结果、Prompt、max_tokens 不变。
5. 新入口：通过已注册的按钮事件回调触发（不只检查按钮文字），确认取当前 question/model、复用当前 symbols，`HandTechnique.predict` 未再次调用；改问题/模型后重新解读使用新值。初始禁用、缺问题/模型展开提示、忙碌互斥一并覆盖。
6. 记录 run_javascript：开始一次定位 AI，后续快照无重复调用；验证 reduced-motion 分支和安全元素定位。无浏览器测试不等待 JS 回执。

### tests/test_regressions.py

1. 扩展 AI failure/duplicate click：首包前失败、已输出后失败、两入口互点、失败后显式重试；本地对象及子树保留、失败可见、`ai_interpretation is None`、两按钮 finally 恢复。
2. 摘要状态：初始展开→本地成功折叠标记/正确摘要→修改展开且输入保留→再次成功收起；校验失败展开；AI 失败保持本地成功状态。检查窄屏 media rule 和桌面默认规则，长问题不丢完整可访问内容。
3. 两个 Client 并行输出/折叠/修改相互独立，不能全局保存 UI 引用。
4. 保留数字/日期/汉字输入、无密钥、local/空问题跳过 AI 的现有断言。既有 `failing_ai(*args)` 需兼容新增 `on_update` 关键字，否则 TypeError 会伪装测试成功/导致 Event 永不到达；AsyncMock 不会自行回调，流式测试必须实际触发。
5. 若因包裹 details 改变控件层级，只调整原有直接 parent 检查到正确容器，不删行为断言。若测试仅调用 `_on_model_change` 而未改 select，补全真实控件值与事件的一致模拟，保留 local 不调用 AI 的契约。

所有 AI 测试禁用真实模型请求（`ALLOW_MODEL_REQUESTS=False`），patch `load_dotenv`/可用模型并使用 FunctionModel 或完整 stub。假密钥不代表网络隔离；不得执行可能读取真实 .env 的在线 `--question` 命令。测试中的 wait_for 仅是测试死锁防护，不是新增模型超时。

## 7. 验证、审查和交付

建议顺序：接口/投影测试 → 流式 AI 卡片 → 共用流程及结果按钮 → 摘要和定位 → 四皮肤/README → 回归及审查。

命令（按退出状态判断，不扫描输出文字猜失败）：

```bash
uv run python -m unittest discover -s tests -p 'test_interpretation_experience.py' -v
uv run python -m unittest discover -s tests -p 'test_regressions.py' -v
uv run python -m unittest discover -s tests -p 'test_cli_noninteractive.py' -v
uv run python -m unittest discover -s tests -v
uv lock --locked
git diff --check
```

浏览器人工/可用离线浏览器工具验收：四皮肤 × 桌面与 375px/900px/901px；用慢速离线替身，确认首片出现、骨架填充、结尾一致、没有每片重新滚动；开启 reduced motion 验证立即定位；摘要修改、跨断点、长文本、键盘聚焦、失败卡片及两入口恢复。服务端 Client 测试只能证明组件状态，不能代替实际滚动/响应式布局；无法运行浏览器须记录限制，不声称已验证。

按 `docs/agents/workflow.md` 委派独立 Standards/Spec 审查。虽然不改领域算法，新展示标题识别属于文本解析逻辑，保守执行 `AGENTS.md` 的独立 Reviewer 要求：让未实现的 Reviewer 按本规格独立构造分片/边界参考，比较流式最终结果与旧 formatter；核对无领域/CLI/Prompt 变化，记录范围、命令、证据、结论、未解决项和覆盖限制，阻断修复后复审。独立复核未完成不能称完成。

最终交付必须给出全套测试结果、离线增量与最终一致性证据、结果按钮/摘要测试、四皮肤浏览器验证情况及独立复核结论。只纳入本任务文件，不触碰用户未跟踪需求文件。
