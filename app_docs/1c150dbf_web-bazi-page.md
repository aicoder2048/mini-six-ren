# Web 八字测算页与流年太岁

## 变更概览

新增 NiceGUI `/bazi` 页面，并在现有首页头部加入「小六壬 / 八字」双向导航。页面由独立的 `BaziWebApp` 控制器负责每次请求的输入、错误和报告状态；不共享首页控制器，也不引入 AI。八字、五行、日主/配偶宫分析、日期/性别校验和太岁报告均复用现有共享函数，八字算法与 CLI 未改动。

报告按固定顺序显示五张卡片：

1. **基本信息**：性别、公历生日、农历生日。
2. **八字信息**：生辰八字、命主五行、八字五行，以及年/月/日/时四柱。
3. **五行分析**：五行数量、缺失、帮扶、克泄耗和缺失影响概要；五行徽章带有 `data-element` 及既有元素颜色钩子。
4. **命运解析**：日主强弱、配偶宫、详细缺失影响。
5. **流年太岁**：所选年份的值年将军和资料说明、犯/合太岁关系及原始解释，或「无特殊关系」。

出生日期使用原生 `date` 控件并限制在 `1900-01-01` 至 `2099-12-31`，时间使用原生 `time` 控件；流年选择器默认当前北京时间年份，改年后需再次点击「开始测算」。失败时清空旧报告并通过 `role=alert` 展示错误，成功后提供状态提示。页面始终显示关于简化规则、日主强弱和配偶宫的免责声明。

## 主要文件

- `src/web.py`：新增导航、`BaziWebApp`、`create_bazi_page()` 和 `/bazi` 路由；首页仅增加导航入口。
- `src/web.css`：八字卡片、四柱网格、五行徽章、免责声明、导航和窄屏布局样式。
- `src/themes/night.css`、`src/themes/ink.css`、`src/themes/neon.css`：为星夜、水墨、霓虹皮肤增加八字卡片、导航、免责声明和五行颜色规则；素纸样式在 `src/web.css` 中提供。
- `tests/test_web_bazi.py`：覆盖共享函数结果渲染、太岁关系、边界和非法输入、失败清理、请求隔离、流年重算、北京时间跨年默认值、导航、路由注册、主题资源和无 AI 调用。
- `tests/test_web_themes.py`：验证基础样式钩子及三套主题的作用域和五行颜色钩子。
- `README.md`：补充 `/bazi` 地址、输入方式、报告内容、四种皮肤和本地计算/简化规则说明。
- `docs/specs/1c150dbf_web-bazi-page.md`：记录实现范围、兼容约定、验收结果和未完成的独立审查/视觉验收限制。

## 使用与验证

启动 Web 后访问 `http://localhost:8080/bazi`，填写公历出生日期、出生时间和性别，选择流年并点击「开始测算」。页面头部可返回 `/` 小六壬页面；流年变更不会自动刷新，需重新提交。

变更记录中的验证结果均为通过：

```bash
uv run python -m unittest discover -s tests -p 'test_web_bazi.py' -v
uv run python -m unittest discover -s tests -p 'test_web_themes.py' -v
uv run python -m unittest discover -s tests -p 'test_regressions.py' -v
uv run python -m unittest discover -s tests -v
uv lock --locked
git diff --check
```

记录的结果分别为 11、11、28、136 项测试通过，锁文件无变更，差异检查通过；HTTP 冒烟检查也记录为 `/` 和 `/bazi` 均返回 200。规格同时明确：当前环境没有独立 Agent Reviewer，因此独立审查尚未完成；未执行真实浏览器视觉验收，HTTP/NiceGUI 元素树检查不能替代桌面和约 375px 窄屏的实际检查。
