# 流年太岁分析

## 变更概览

八字报告现在会根据目标公历年的流年太岁资料，生成结构化的「犯太岁／合太岁」分析，并在 CLI 报告中追加「流年太岁」章节。实现直接读取项目内 12 份 `data/太岁_*.json`，不修改原始数据；数据缺失和稀疏年份会被明确保留，而不是借用其他年份资料。

## 实现位置与行为

- `src/utils/tai_sui.py` 新增 `TaiSuiData`、`TaiSuiDataError` 和 `analyze_tai_sui`。
  - 模块导入时按相对模块文件的路径一次加载全部太岁 JSON，兼容四个使用生肖名顶层键的文件及其余使用「太岁」顶层键的文件，并将对象/列表关系统一为列表。
  - 对文件读取、JSON、字段结构、年份、地支和关系条目执行校验；失败会抛出包含文件路径的 `TaiSuiDataError`，并保留原始异常原因。
  - `analyze_tai_sui(birth_year_branch, target_year=None)` 使用八字年柱地支。省略年份时按 UTC+8 的当前公历年；显式年份限制为 1900–2099 的整数。
  - 流年干支由现有 `get_chinese_year` 取得，并在对应流年文件中精确查找将军资料。申猴、酉鸡的未收录年份返回 `general_status='missing'` 及空将军信息，但关系分析仍继续。
  - 犯太岁和合太岁关系均从数据中的地支数组匹配，保留所有同时命中的条目、子类型、组合和解释；结果包含 `summary`，无命中时为「无特殊关系」。返回关系使用深拷贝，避免调用方修改模块缓存。
- `src/utils/calendar_converter.py` 扩展 `format_bazi_output`：保留原六个位置参数和原三个输出区块，增加仅关键字的 `target_year` 与 `tai_sui_info`。新增 `format_tai_sui_section`，负责将结构化结果渲染为带流年、值年太岁、关系摘要、逐条解释和资料说明的行，并对缺失将军显示明确提示。
- `src/cli.py` 在现有「命运解析」后，以 `bazi['year'][1]` 调用分析并追加「流年太岁」章节，沿用原 Rich 标题和键值行样式。没有加入 Web UI 或 AI prompt。

## 测试与兼容性

`tests/test_tai_sui.py` 覆盖：两种顶层数据形状、12 支归一化、短年份列表、缺失/不可读/损坏文件、模块缓存和返回隔离；值太岁、自刑、冲与破、六合、无关系、犯合同时命中、间接关系排除、多关系保留；申猴/酉鸡缺少年份；北京时间年界；输入校验；格式化和 CLI 展示。`tests/fixtures/tai_sui_bazi_baseline.json` 保存三组旧八字格式化及 CLI 基线。

测试记录显示新增测试 16 项、全套测试 124 项通过。基线比较确认 `basic_info`、`bazi_info`、`wuxing_info` 及 CLI 原有内容未改变，CLI 仅在原报告末尾的分隔线前追加新章节；八字核心和小六壬相关文件未改动。

可用以下命令验证（如默认 uv 缓存不可写，将缓存目录放到可写位置）：

```bash
UV_CACHE_DIR=/tmp/tai-sui-uv uv run python -m unittest discover -s tests -v
UV_CACHE_DIR=/tmp/tai-sui-uv uv run python -m unittest discover -s tests -p 'test_tai_sui.py' -v
UV_CACHE_DIR=/tmp/tai-sui-uv uv lock --locked
git diff --check
```

## 规格与独立复核

- `docs/specs/457fdccf_annual-tai-sui.md` 记录数据缺失策略、关系匹配规则、输出契约、测试计划、实施记录和验收范围。
- `docs/reviews/457fdccf_annual-tai-sui-review.md` 记录独立 Spec/算法复核：Reviewer 直接读取原始 JSON，独立构造参考结果，覆盖 1900–2099 年与 12 个出生支的 2,400 组组合、北京时间年界、短列表、同时关系，并以 Git 基线比较 9 组旧八字/CLI 输出；结论为通过、无阻断项。
- `docs/reviews/457fdccf_annual-tai-sui-standards.md` 记录独立 Standards 复核：确认一次加载、严格报错、缓存隔离、接口兼容和回归验证；结论为通过，无阻断项，仅提出固定展示行期望的非阻断建议 S-01。

复核限制也已记录：结论证明的是对项目 JSON 资料和既定规则的忠实映射，不是对民俗资料真实性的考据；原数据的不一致及申猴/酉鸡的缺项未被修订，三合条目不代表完整命盘成局。
