# Web 首屏布局调整验收

- 日期：2026-09-16
- 规格：`.scratch/web-first-screen/spec.md`；任务：`.scratch/web-first-screen/issues/01-first-screen.md`
- 基线：`b5d929c`，开始时工作树干净。

## 交付

页头 104→88px；主视觉压缩为两行（眉题；标题与副标题同行，`.hero-line`）。表单改为"输入 → 开始占卜 → 状态 → 折叠选填区（心中所问 · 解读方式）"，选填区在有可用 AI 模型时默认展开、否则收起；问题框最小高度 56px，卡片留白收紧，移除冗余提示。按钮与就绪文案改为"开始占卜"，空状态引导写明按钮名。水墨皮肤主视觉改横排（粗体标题 + 笔触下划线、横排朱印、缩小的「觀」水印），移除竖排规则；三套皮肤为 `.optional-panel` 提供配色。

## 验证证据

- `uv run python -m unittest discover -s tests -v`：41 项通过（新增 `test_optional_panel_follows_ai_availability_and_button_names_the_action`；`test_result_exposes_input_snapshot_and_complete_relations` 的按钮文案断言更新为"开始占卜"）。
- `uv lock --locked`、`git diff --check`：通过。
- Chrome 窗口按 1440×900 设置（工具实测视口 1445×941）：四套皮肤主按钮底边 y≈524，右侧空状态整体在首屏；以 `OPENAI_API_KEY=offline-test` 启动的第二实例中选填区默认展开，底边 y≈847，主按钮位置不变；点击"开始占卜"后三传三张卡片在首屏可见。
- 同源 iframe 390px：素纸/水墨/星夜主按钮底边 y≈526–544，`scrollWidth` 等于视口；霓虹/水墨/星夜展开选填区后输入框、下拉与说明文字配色正常。
- 水墨 1440：标题横排带笔触下划线，「觀」水印位于主视觉带内不被裁切，朱印横排置右。

## 独立审查

- [Standards](web-first-screen-standards.md)：通过，0 阻断、4 非阻断；修复后复查通过（复查中新发现的水墨折叠区副标题同色问题已补 caption 规则修复）。
- [Spec](web-first-screen-spec.md)：通过，0 阻断、3 非阻断；修复后复查通过。
- 两位审查者均以 AST/diff 对照确认计算、输入解析、模型调用行为未变；本次没有算法变更。

## 审查后修正

星夜文化面板恢复只改边框；星夜/霓虹/水墨折叠区标题与副标题分层；水墨水印右移并在 ≤1100px 隐藏；页内指南三步改为「选择起课方式 → 点开始占卜 → 心中所问（选填）」；测试补充主按钮先于折叠区的顺序断言。

## 限制

浏览器验收仅 Chrome；未验证 Safari、Firefox 与实体手机。AI 展开态通过假密钥的本地实例观察，未调用真实 AI 服务。本次不涉及算法变更。
