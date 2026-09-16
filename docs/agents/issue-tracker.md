# Issue tracker：本地 Markdown

本项目已选择本地文件跟踪需求和任务，不向远程平台发布 Issue。

## 文件与规格

- 每个功能对应 `.scratch/<feature-slug>/`。
- 功能入口为 `.scratch/<feature-slug>/spec.md`。新规格可写在此处；若已有 `specs/` 或 `docs/specs/` 规格，此入口只链接唯一权威文档，不复制第二份规格。
- 每张实施 ticket 单独保存为 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从01按依赖顺序编号。
- 每张 ticket 包含交付行为、`Blocked by`、`Status` 和可验证的验收条件。
- `.scratch/` 在本项目中是需要提交到Git的任务记录目录，不存放密钥、日志或临时实验产物。

## 状态与依赖

- 初始 triage 状态采用 `triage-labels.md` 的五个标准角色。
- 执行状态另外支持 `in-progress`、`in-review`、`resolved`。测试及所需审查通过后才能设为 `resolved`。
- 只有 `Blocked by` 指向的任务全部为 `resolved`，后续任务才可开始；无依赖任务可直接执行。
- 当前 `review-improvements` 的tickets是对已经授权并实施的改进补建的验收记录，不代表此前已经按这些tickets逐项提交。
- 评论追加到ticket末尾的 `## Comments`，保留决策与验证记录。

## 技能操作映射

- “publish to the issue tracker”：在上述本地目录创建或更新文件。
- “fetch ticket/spec”：读取用户提供路径及关联文档。
- “apply label”：更新ticket的 `Status`。
- 默认不关闭或修改父级需求，除非用户要求。
- Wayfinder如需启用：使用 `.scratch/<effort>/map.md` 保存决策地图，子ticket仍放入 `issues/`；认领用 `claimed`，回答完成用 `resolved`，阻塞关系写入 `Blocked by`。
