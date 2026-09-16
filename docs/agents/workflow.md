# 按规格推进开发

适用流程：规格 → 计划 → 实现与测试 → 审查与修复 → 本地提交。

## 1. 规格与计划

用户提供已有spec时直接以它为依据；需要整理新需求时显式使用 `to-spec`。
使用 `to-tickets` 拆分可独立演示和验收的完整功能，明确依赖和验收条件，写入本地tracker。
新范围或实质性计划选择应与用户确认；已经明确授权的范围和偏好不重复征求确认。
现有规格通过功能目录的 `spec.md` 链接，维持单一来源。

## 2. 实现与反馈

用户授权实施后使用 `implement`。按阻塞关系执行任务，优先在现有接口边界用 `tdd` 验证有意义的行为。
修复bug先复现，再修改；先跑相关测试，完成后跑全套测试。本项目没有配置独立类型检查器，不将语法检查声称为类型检查。

记录实现开始时的Git基线及原有工作树改动，提交时只纳入本任务文件。

## 3. 审查与修复

使用 `code-review` 的两个独立Agent分别审查 Standards 和 Spec；按两个轴保留报告。

- 已提交分支：比较基线与当前HEAD的相关提交。
- 待提交改动：使用 `git diff --cached <baseline>`，确保新增文件也已纳入；不能仅用三点diff审查空的提交差异。
- 若未暂存，审查 `git diff <baseline>` 并逐一读取 `git ls-files --others --exclude-standard` 列出的任务新增文件。
- 算法变更另须遵循 `AGENTS.md` 的独立Reviewer要求。既有复核覆盖的算法未变时可复用其证据；新算法修正需要复审。
- 修复阻断问题后由相应Reviewer复查。保留合理的非阻断建议及不在范围内的问题，不为了清空报告擅自扩张任务。

## 4. 验证、记录与提交

```bash
uv run python -m unittest discover -s tests -v
uv lock --locked
git diff --check
```

涉及当前算法时还可运行 `uv run python scripts/audit_algorithm_changes.py`；它对照固定基线 `3e6014e`，不是适用于任意未来算法变化的通用正确性证明。

通过验收后将ticket置为 `resolved`，在审查记录中保存验证命令、结果、剩余问题及限制。
`implement` 的完成步骤是在当前分支进行本地commit；提交前检查暂存文件清单，报告commit hash。若范围里没有授权远程操作，不自动push、创建远程Issue或发布。

示例请求：

> 使用 to-tickets 将 specs/某项需求.md 拆成计划；确认范围后使用 implement，执行测试、双轴代码审查及必要的独立算法复核，最后commit到当前分支。
