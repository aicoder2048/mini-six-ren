# Web 九宫环可视化

## 变更概览

Web 起课结果现在会显示九宫旋转路径：九个符号按 `data/symbols.json` 的 `order` 排序，`大安` 位于正上方，其余节点顺时针排列。结果环会标出起算点、初／中／末传各自经过的宫位、三个落点及五行颜色，并在落点摘要中显示 `finger_position` 和 `bagua`。原有三传结果卡片、关系说明和 AI 区域仍保留。

## 实现位置

- `src/web.py`
  - 新增 `PalaceWalk`、`PalaceSegment` 和 `build_palace_walk()`。它按“本宫算第 1 数”生成每段访问序列、访问次数、落点、移动步数、整圈数和余步；路径从上一段落点继续，落点逻辑与 `HandTechnique.predict` 对齐。
  - `DivinationWebApp` 保存经过输入模式转换并验证后的 `number_snapshot`，结果渲染只使用这个快照。九宫环组件包含固定九节点、起算标记、三段经过槽、重复落点徽标、三段落点摘要和两条有方向的关系行。
  - 空状态也渲染静态九宫环，但不显示虚构的经过、落点或关系。原有异步提交、防重入和 AI 失败保留本地结果的流程仍在原位置运行。
- `src/web.css`
  - 提供九宫环、节点、访问标记、落点、摘要、关系行和响应式布局；大数字通过访问次数聚合而非创建逐步节点，手机布局下摘要可改为单列。
  - 增加素纸主题五行变量、窄屏调整，以及 `prefers-reduced-motion: reduce` 下九宫环动画和过渡禁用规则。
- `src/themes/night.css`、`src/themes/ink.css`、`src/themes/neon.css`
  - 分别为九宫环节点、摘要、关系和五行元素提供主题化颜色与边框，选择器限定在各自主题根节点下。
- `tests/test_web_palace_ring.py`
  - 覆盖九宫顺序、独立计数样例、跨边界、整圈与 999 输入、与 `HandTechnique.predict` 的落点一致性、三种输入模式快照、重复落点、AI 失败、页面隔离、原始 `finger_position`／`bagua` 字段和四主题／减弱动画 CSS 钩子。
- `docs/specs/d8b3217d_nine-palace-visualization.md`
  - 记录了布局、计数、可访问性、响应式、兼容行为和验证要求。

差异中没有修改 `data/`、`src/hand_technique.py`、关系计算或 AI prompt；`data/symbols.json` 的字段仅被读取。另有 `adws/adw_sssf_config/sssf.config.yaml` 的 agent 模型配置调整，与九宫 UI 渲染无关。

## 使用与验证

启动 Web 页面：

```bash
uv run src/web.py
```

在页面中提交数字、时间或汉字起课即可看到九宫环；可通过主题切换检查素纸、星夜、水墨和霓虹样式。修改输入框不会改变已显示的环，重新提交才会替换路径。

自动化验证：

```bash
uv run python -m unittest discover -s tests -v
```

本次运行结果为 `Ran 92 tests ... OK`。差异中未包含独立 Reviewer 记录或浏览器尺寸／主题的人工视觉验收记录；上述命令验证了模型、页面结构、兼容行为及 CSS 钩子，但不替代实际手机宽度和四主题的浏览器检查。
