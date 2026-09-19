# Web 八字测算与流年太岁页面实施计划

## 目标与边界

新增 `/bazi`，由现有头部在「小六壬 / 八字」间双向导航。八字页消费现有共享计算及格式化函数，按基本信息、八字信息、五行分析、命运解析、流年太岁的顺序展示本地报告；支持四种皮肤、北京时间流年选择、独立请求状态和可访问错误提示。不增加 AI 功能。

仅修改 `src/web.py`、`src/web.css`、`src/themes/night.css`、`src/themes/ink.css`、`src/themes/neon.css`、测试和 `README.md`；本计划保存在 `docs/specs/1c150dbf_web-bazi-page.md`。禁止修改 CLI、八字/太岁/历法/五行算法、`src/hand_technique.py`、`src/utils/symbol_relations.py`、`data/`，不实现导出、历史、分享或旧日主分析工具。

已阅读 `CLAUDE.md` 及开发流程。规划基线：`uv run python -m unittest discover -s tests -v` 返回 0，124 项通过。工作树已有未跟踪 `requests/tai-sui-analysis.md`、`requests/web-bazi-page.md`，不修改或纳入本任务提交。

## 当前实现与重要兼容约定

- `create_page()` 每次实例化 `DivinationWebApp`；`main()` 内注册 `/`。新增工厂遵循这一模式，禁止全局控制器或缓存 UI 引用。
- 现有 `DivinationWebApp._add_theme_assets()` 和 `_create_theme_switcher()` 是无状态静态方法，可直接复用，不要为了主题实例化小六壬控制器（会探测 AI 模型）。原页计算、AI、九宫动画和表单交互不变。
- **需求描述与现状有一处差异**：`cli.bazi_calculation` 当前自行拼装展示行，并未调用 `format_bazi_output`；formatter 的 `birth_info` 多生肖、`day_master` 多括号内详细五行信息，`wuxing_info.missing_impact` 是概要而不是 CLI 的详细缺失分析。不得借本任务修正这些既有差异。
- 决策：按用户明确的 formatter 等值验收要求，Web 基础/八字/五行字段以 `format_bazi_output` 原值为准；另外显示 CLI 使用的三个分析函数的完整结果。所谓 CLI/Web 一致指共享计算与分析内容一致，不要求终端装饰、随机报告号或上述既有标签格式字节相同。详细缺失影响放在「命运解析」，formatter 的概要仍保留在「五行分析」，不能拿概要冒充详细分析。
- `format_bazi_output(..., target_year=year)` 内部已调用 `analyze_tai_sui(bazi['year'][1], year)`。使用返回的 `tai_sui_info`，不再重复计算太岁；尤其不能改用出生公历年份取生肖。
- `format_tai_sui_section(result)` 已共享值年将军、资料缺失提示、关系摘要、所有关系的解释和资料说明，Web 直接渲染其行列表，避免第二套解释规则。

## 实施步骤

### 1. 新增独立八字页面控制器与数据接线（`src/web.py`）

新增 `BaziWebApp`，持有自身日期/时间/性别/流年控件、提交按钮、错误标签、状态标签、结果容器和最近一次成功报告。新增 `create_bazi_page()`，每次创建并返回新控制器。不要继承或实例化 `DivinationWebApp` 来获取业务状态。

导入并复用：
- `parse_datetime`、`normalize_gender`（`utils.validation`）；
- `calculate_bazi`、`analyze_day_master_strength`、`analyze_spouse_palace`（`utils.bazi_calculator`）；
- `analyze_wuxing`、`analyze_missing_wuxing`（`utils.five_elements_utils`）；
- `solar_to_lunar`、`format_bazi_output`、`format_tai_sui_section`（`utils.calendar_converter`）。

提交处理顺序：
1. 清空上次错误及报告，清空已保存结果，避免非法重提后仍展示旧报告。
2. 对日期/时间调用 `parse_datetime`，对性别调用 `normalize_gender`。不编写新的日期解析、换日、时区或性别映射。
3. 流年控件使用 `ui.select`，选项为整数 `1900..2099`；确保提交值为非 bool 的整数且在选项范围内，不用 `int(value)` 静默截断小数或强行转换非法值。最终领域范围仍由 formatter 内部太岁函数校验。
4. 按 CLI 顺序调用农历转换、八字、五行及三个分析函数；日期/时间文本用校验后的 datetime 格式化为 `%Y-%m-%d` / `%H:%M` 后传给 formatter，性别传规范化值，显式传所选 `target_year`。
5. 全部计算成功后才提交报告状态并渲染。报告保留 formatter 字典和三个独立分析字符串，渲染函数只读取这些结果及原始四柱/五行统计，不计算命理规则。
6. 校验失败展示 `ValueError` 信息；其他计算或渲染异常也进入错误提示路径，并清除可能的半份报告。`error_message` 使用 `.classes('error-message').props('role=alert')`，状态使用 `role=status aria-live=polite`；失败后可修改输入再次成功提交。

可将接线封装为 Web 模块内小函数以便测试，但它只是调用编排，不引入第二份八字实现、不移动或重构共享领域代码。

### 2. 页面结构、导航与交互（`src/web.py`）

- `main()` 在现有 `ui.page('/', dark=False)(create_page)` 旁注册 `ui.page('/bazi', dark=False)(create_bazi_page)`；保留主入口启动模式，不在模块导入时启动服务器。
- 添加无状态导航构建辅助函数，两页头部都调用。使用真实 `/`、`/bazi` 链接，标示当前页 `aria-current=page`；保留原首页品牌、指南和皮肤切换。避免为了共享头部大幅重排首页。
- 八字页沿用 `app-shell`、`site-header`、`header-actions`、`page-main`、`workspace`、`form-card`、`reading-panel`、`site-footer` 等公共外壳，并添加 `bazi-page` 等专属钩子。
- 输入：公历出生日期原生 `type=date min=1900-01-01 max=2099-12-31`；出生时间原生 `type=time`（分钟精度）；性别选项男/女；流年整数选择器。日期默认北京当天、时间默认 `00:00`、性别默认男。流年在每次页面创建时用 `datetime.now(timezone(timedelta(hours=8))).year` 初始化，不能使用服务器本地年份或导入时常量。
- 显示北京时间 UTC+8、1900–2099、午夜换日、不做真太阳时校正的简短输入说明；流年注明「按北京时间公历年」。
- 主按钮「开始测算」。改变流年后点击该按钮更新整份报告；在流年控件旁明确提示此操作，不承诺自动计算。报告自身显示所用流年，避免把尚未提交的选择误认为当前结果。
- 初始只显示填写提示，无报告卡片。无 AI 控件、模型探测或网络调用。
- 始终可见免责声明：原样保留 README 文案「八字后的性格和关系解读仍为原有简化规则；历法计算修正不代表这些解读得到验证。」再明确「日主强弱、配偶宫分析属于上述简化规则，仅供传统文化参考。」

报告固定为五张 `.bazi-section` 卡片，使用标题和稳定 `data-section` 标识，内容用 NiceGUI 文本元素安全渲染：

| 卡片 / 标识 | 内容来源与展示要求 |
| --- | --- |
| 基本信息 / basic | `basic_info.sex`、`solar_date`、`lunar_date`，标签性别、公历生日、农历生日 |
| 八字信息 / pillars | 完整 `bazi_info.birth_info`、`day_master`、`bazi_five_elements`；另用四格清楚标出年柱/月柱/日柱/时柱，直接读 `bazi['year'/'month'/'day'/'time']` |
| 五行分析 / wuxing | 完整 `wuxing_info.wuxing_count`、`missing`、`helping_wuxing`、`weakening_wuxing`、`missing_impact`；最后一项标为「缺失影响概要」。统计另可用徽章呈现，但不能遗漏 0 个元素或重排共享值的含义 |
| 命运解析 / analysis | 日主强弱（CLI 日主旺衰）、配偶宫（CLI 配偶宫位）、详细缺失影响，分别为三个分析函数的返回文本，不截断、不重新解释 |
| 流年太岁 / tai-sui | 逐行展示 `format_tai_sui_section(report['tai_sui_info'])`，包含所选流年、值年将军与说明、关系摘要、全部犯/合关系、组合及数据原文解释、资料说明 |

太岁需正确处理同时多关系、无特殊关系及 `general_status != 'available'` 的资料未收录分支；未收录不等于计算失败，不凭空补将军。不把三合改写为完整命盘成局。

### 3. 四皮肤与响应式（CSS）

在 `src/web.css` 增加 `.page-nav`、`.page-nav-link`、`.bazi-page`、`.bazi-section`、`.bazi-section-title`、`.bazi-field`、`.bazi-pillars`、`.bazi-pillar`、`.bazi-element-badge`、`.bazi-disclaimer` 等布局/样式钩子。

- 素纸以基础 CSS 实现。新报告卡片宽度可收缩，长解释换行；窄屏表单在前、报告在后，四柱由四格转两格，头部导航和主题选择不造成横向溢出。
- 五行徽章同时复用 `element-badge element-{key}` 和 `data-element={key}`，key 来自已有 `ELEMENT_KEYS`；为五种 `[data-element]` 接上已有 `--el-*` 色彩变量，不再定义领域映射。素纸也有清晰可读配色。
- 三个主题 CSS 各追加带 `html[data-theme="night|ink|neon"]` 前缀的新卡片/标题/导航/免责声明规则，使用各自现有 surface、边框、文本及五行变量，避免纸色卡片漏到深色皮肤。
- 每个逗号分隔选择器都带主题前缀，以通过现有作用域测试；新样式不得改变首页三传、九宫或 AI 动画。无需修改 `theme.js`；继续使用其本地主题记忆和效果清理。

### 4. 自动化验收（新增 `tests/test_web_bazi.py`，扩充 `tests/test_web_themes.py`）

遵循现有 `unittest.IsolatedAsyncioTestCase`、`nicegui.Client(ui.page(...), request=None)` 模式，不需要真实服务器或在线 AI。以真实 client 元素树/文本/props 验证实际渲染，不只断言控制器字典。

1. **固定报告等值**：例如出生 `1990-01-01 10:30`、男、流年 `2023`。测试中直接从共享模块独立调用完整 pipeline 取得期望值（不调用被测 Web 接线函数作为 oracle）。断言五卡片顺序、formatter 各字段真实出现在对应卡片、四柱、三个分析结果以及所有太岁展示行；同时测试女的规范化输入。
2. **太岁分支**：用固定出生日期构造多条犯太岁关系、合太岁、无特殊关系和将军资料未收录样例，参照 `tests/test_tai_sui.py` 的已有固定资料。对每条解释逐字断言，不只检查「流年太岁」标题。可分别测试真实端到端与以共享 `analyze_tai_sui` 结果传入纯渲染入口的分支覆盖。
3. **错误与恢复**：不存在的日期（如 `2023-02-29`）、越界出生日期、空日期/时间、`24:00`、无效/空性别，以及非法/越界流年。校验服务器端也拒绝绕过浏览器约束的值。断言 `role=alert` 非空、报告状态为空且结果容器没有报告；先成功再失败亦如此，修正后恢复成功并清空 alert。
4. **请求隔离**：两个独立 Client 分别调用 `create_bazi_page()`，控件、报告、错误容器均非同一对象。一个提交/改变年份/失败，不影响另一个的值、报告或错误；不能只比较两个手工实例。
5. **流年选择**：同一出生输入先提交 2023 再提交 2024；太岁值等于各自 formatter 输出且实际卡片变化，其余报告内容保持相同。mock `web.datetime` 的北京跨年时刻，验证当前年份默认值及使用 UTC+8（不要依赖测试当天）。
6. **入口和原生控件**：日期、时间 props 与范围、男女选项、1900–2099 流年选项、初始空状态、免责声明；两页真实导航目标与 active 属性。patch `ui.page` / `ui.run`（必要时 `os.chdir`）执行 `main()`，确认两路由注册到正确工厂且不启动服务器。
7. **主题与无 AI**：八字页 head 注入四皮肤资产/切换器，徽章 `data-element` 完整。扩充主题测试验证基础 CSS 和每个主题的新钩子及作用域；已有皮肤测试必须不变绿。patch 模型探测/AI 构造为遇调用即失败，确保八字创建与提交无需 AI。
8. **首页回归**：保留原 `tests/test_regressions.py` 断言，不因八字新增而放宽；原首页输入、AI、页面隔离仍运行原路径。

### 5. README 与收尾

在 README「Web版本」/「Web版本使用」补充 `http://localhost:8080/bazi`、头部双向导航、出生日期/时间/性别、北京时间流年默认及换年后再次测算、五节报告、四皮肤、纯本地无需 AI 密钥和简化规则限制。避免把现有小六壬 AI 使用说明误写为八字也支持 AI。

验证命令：

```bash
uv run python -m unittest discover -s tests -p 'test_web_bazi.py' -v
uv run python -m unittest discover -s tests -p 'test_web_themes.py' -v
uv run python -m unittest discover -s tests -p 'test_regressions.py' -v
uv run python -m unittest discover -s tests -v
uv lock --locked
git diff --check
```

启动 `uv run src/web.py`，人工检查 `/` 与 `/bazi` 双向导航、四皮肤、桌面及约 375px 窄屏、长太岁解释、多次提交与非法输入后的清空恢复；结果卡片/表单/原生日期时间在深浅主题均清晰。记录执行命令和退出码；仅 DOM 测试不能声称已完成浏览器视觉验收。

## 审查与完成条件

按项目流程安排未参与实现的 Standards / Spec 独立审查，检查复用调用、formatter 差异处理、全字段 DOM 呈现、导航/主题无首页回归及输入接线边界。领域函数不应发生 diff；不要顺手修正既有五行、纳音、强弱或配偶宫规则。新输入接线亦需独立检查日期/性别/年份映射；如实现扩大为可能影响计算结果的解析、映射或算法变更，必须遵守 `AGENTS.md` 独立算法 Reviewer 要求，构造独立参考与边界验证、保存证据，修复阻断项后复审，不得只凭本计划中的共享输出等值测试宣布算法正确。

完成以全套测试退出 0、上述需求均验证、README 更新、独立审查结论及覆盖限制已记录为准。若有既有算法问题仅记录，不越界修改；如无浏览器或 Reviewer 能力，明确标为尚未验证而非已完成。
