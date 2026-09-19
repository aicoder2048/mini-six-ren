# Web 实时 AI 解读与结果区入口

## 变更概览

Web 端现在会真正消费 AI 流式输出：生成开始即显示固定的五段骨架（「一句话判断 / 初传｜起点 / 中传｜过程 / 末传｜趋势 / 行动建议」），随后在同一个 Markdown 组件中逐步填充；生成结束时以 AI 返回的完整格式化文本作为最终内容。CLI 的同步/非交互输出路径没有改动。

结果区标题新增「生成 AI 解读 / 重新解读」按钮。它复用当前问题和模型选择，并使用已经完成的本地三传，不会因按钮点击重新计算起课。请求开始时 AI 卡片会滚入视口，支持平滑滚动，并在 `prefers-reduced-motion` 下立即定位。AI 失败时清除未完成的 AI 正文、显示失败状态和重试提示，同时保留本地三传。

在不超过 900px 的窄屏上，本地起课成功后表单改为一行输入摘要；「修改」会展开原有控件，输入值和已显示的三传继续保留。桌面仍显示完整表单。

## 代码位置

- `src/ai_agent.py`：`interpret_prediction_async` 与 `_stream_interpretation_web` 增加异步 `on_update` 回调；按累计快照调用 Web 更新，关闭供应商片段合并（`delta=False, debounce_by=None`），最终仍返回完整格式化结果。
- `src/web.py`：增加流式五段投影、持久 AI 卡片/Markdown/状态引用、共享 AI 请求流程、结果区按钮、滚动脚本、窄屏表单摘要及「修改」逻辑。运行状态和输入快照按 Client 保存；本地结果树不会被 AI 增量更新重建。
- `src/web.css`：结果区按钮、AI 忙碌/失败状态、摘要省略、焦点样式、滚动边距和 900px 以下的折叠规则；默认素纸皮肤的样式在此提供。
- `src/themes/night.css`、`src/themes/ink.css`、`src/themes/neon.css`：分别为星夜、水墨、霓虹皮肤补充新按钮、摘要和 AI 状态的配色/边框表现。
- `README.md`：更新 Web 行为说明和 Web 使用步骤，说明骨架实时填充、结果区入口及窄屏摘要。
- `tests/test_interpretation_experience.py`：覆盖离线流式 Agent 回调顺序与静默性、稳定 AI 卡片的增量更新、结果区入口复用当前问题/模型/本地结果，以及投影边界。
- `tests/test_regressions.py`：覆盖表单摘要与修改、校验失败展开、缺少 AI 配置、部分输出后失败及显式重试、双 Client 隔离等回归场景；AI 均使用离线替身。
- `tests/test_web_palace_ring.py`：更新失败 AI stub，使其兼容新增的回调关键字参数。
- `docs/specs/f6285cb4_web-stream-ai-reach.md`：记录本次 Web 流式解读、结果区入口、窄屏摘要、样式和离线验证范围。

## 使用与验证

启动 Web：

```bash
uv run src/web.py
```

完成一次起课后，在表单中填写问题并选择 AI；可以继续使用「开始占卜」，也可以直接在右侧结果标题点击「生成 AI 解读」。应先看到五段骨架，再看到正文逐片增长；成功后按钮变为「重新解读」。窄屏起课成功后检查摘要和「修改」，切换四种皮肤检查按钮与状态样式。

运行完整离线测试：

```bash
uv run python -m unittest discover -s tests -v
```

新增测试通过 `ALLOW_MODEL_REQUESTS=False`、FunctionModel 或本地 stub 隔离在线 AI，并检查最终 Markdown 与非流式完整格式化结果一致；因此验证不会发起真实模型请求。
