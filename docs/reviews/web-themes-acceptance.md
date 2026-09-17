# Web 皮肤/主题验收

- 日期：2026-09-16
- 规格：`.scratch/web-themes/spec.md`；任务：`.scratch/web-themes/issues/01-themes.md`
- 基线：`9af7aac`，开始时工作树干净。

## 交付

保留现有暖白纸感界面为默认皮肤 `paper`，新增 `night`（星夜）、`ink`（水墨）、`neon`（霓虹）三套皮肤。头部提供 `role=group` 的色样切换控件；切换只在浏览器端改写 `html[data-theme]`，写入 `localStorage`，`?theme=<id>` 可指定并记忆，head 内联脚本在首屏绘制前应用已保存皮肤。主题样式各自独立于 `src/themes/<id>.css`，只匹配自身属性选择器；`src/web.css` 既有规则未改，仅追加切换控件样式、头部换行策略与减少动态效果下的 `animation-iteration-count`。星夜的星空画布、流星与指针光晕由 `src/themes/theme.js` 在激活时启动、切走时清理；水墨与霓虹的效果全部为 CSS。三传卡片与五行徽章新增 `data-element` / `element-<key>` 钩子，默认皮肤不使用。

## 验证证据

- `uv run python -m unittest discover -s tests -v`：40 项通过（原 30 项 + `tests/test_web_themes.py` 10 项：注册表完整性与常量校验、主题 CSS 与关键帧仅匹配自身皮肤、页面注入与纯客户端切换按钮、五行钩子、`theme.js` 在 node 桩环境下的读取/回落/持久化与星夜效果启停清理）。
- `uv lock --locked`、`git diff --check`：通过。
- 本地服务 `uv run python src/web.py`，使用 Claude in Chrome 在 1440×1000 下逐皮肤验收：默认皮肤与基线一致；星夜显示星空画布、鎏金标题、星盘与五行分色卡片，切走后画布与 `--msr-mx/--msr-my` 变量被清理；水墨显示竖排标题、朱印、笔触顶边、圆相空状态与水印，悬停划出墨线；霓虹显示网格、扫描线、HUD 角标、雷达空状态、标题悬停故障字效与卡片扫描光带。
- 切换后 `localStorage` 为所选 id，`aria-pressed` 同步；`?theme=neon` 重载后生效并记忆；无效值回落默认。
- 三套皮肤下指南对话框、模型下拉菜单、折叠面板的背景与文字色已按主题覆盖（通过计算样式与截图核对）。
- 同源 iframe 模拟 390px 与 320px 视口：四套皮肤加载期间与结果展示后 `scrollWidth` 均等于视口宽度；头部在 390px 单行显示，320px 优雅换为两行。1024px 下水墨竖排主视觉正常。
- 修正记录：切换控件曾使 390px 头部品牌行断开，已改为品牌/操作区各自不换行、整体可换行并缩小窄屏色样；水墨印章入场 `scale(1.6)` 与霓虹 CRT `scaleX(1.25)` 曾造成加载期间短暂横向溢出，已改为不超出视口的动画。
- 审查后修正：三套皮肤覆盖指南对话框按钮配色以保证对比度（计算样式核对：星夜金底 `#1a1408` 字、霓虹青底 `#07070d` 字、水墨黑底纸白字，默认不变）；`theme.js` 缓存媒体查询并响应 reduced-motion 变化、观察者兜底断开；`Theme` 常量导入时校验 id 与文案；色样按钮加 `aria-label`；测试桩改为真正启停效果并写入临时目录。

## 独立审查

- [Standards](web-themes-standards.md)：通过，0 阻断、9 非阻断；非阻断项已按报告修复并复查。
- [Spec](web-themes-spec.md)：通过，0 阻断、3 非阻断；非阻断项已按报告修复并复查。
- 两位审查者均以 AST/diff 对照确认计算、输入解析、模型调用行为未变；本次没有算法变更。

## 限制

浏览器验收使用 Chrome；未验证 Safari、Firefox 与实体手机。`backdrop-filter`、`overflow`/`mask` 等属性在旧浏览器可能降级为无模糊或实心样式，不影响可读性。减少动态效果偏好通过代码路径检查，未在系统层面实际切换验证。自动化标签页处于后台时 Chrome 不派发 `requestAnimationFrame`，Vue 过渡会暂停，这是环境现象而非页面缺陷。本次不涉及算法变更，未调用真实 AI 服务。
