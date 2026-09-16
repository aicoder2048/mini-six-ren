# 三传体验改进验收记录

日期：2026-09-15。基线：`f69f4f809a6ee874e34fcb66d55aa87ce7a942ef`；原始工作树干净。规格：[三传算法、解读与使用体验](../specs/interpretation-experience.md)。

## 交付与验证

- 九宫起课符号保持；五行关系完整区分生、克、被生、被克、比和，CLI/Web/Prompt均说明方向。
- Prompt固定“一句话判断→三传→行动建议”；每传要求依据、白话、建议。问题以独立JSON数据传入；中性化符号释义，趋势含条件。CLI/Web共用2400 tokens预算。
- Web输入流程简化，桌面三列、手机单列；输入快照、起课数字、状态反馈、折叠文化背景可用。
- CLI补齐输入摘要及日期规则；80列真实Panel保留完整方向说明。
- AI失败抛出异常由界面展示，不会作为普通解读显示；本地结果保留，提交按钮恢复。

## 自动化

| 命令 | 最终结果 |
|---|---|
| `uv run python -m unittest discover -s tests -v` | 30项通过；23项既有回归+7项新增验收 |
| `uv run python scripts/audit_interpretation_algorithm.py` | 25格、5,832组基线对照、2,187次周期、60项非法输入、729组Prompt事实通过 |
| `uv lock --locked` | 108个包的锁文件一致，无依赖变更 |
| `git diff --check` | 通过 |

实施采用行为测试先失败后修复：完整关系、AI请求契约、Web快照/真实供应商失败、CLI起课摘要；真实80列Panel回归补充独立审查发现的截断问题。AI请求使用PydanticAI FunctionModel离线替身，未请求在线模型。

## 独立审查

- [算法](interpretation-algorithm-review.md)：通过；范围、独立样例及限制见该报告。最终CLI摘要与布局修复未修改算法或输入映射，最后再次运行独立脚本通过。
- [Standards](interpretation-standards-review.md)：初审无阻断；共用预算的非阻断建议已采纳，复审未解决0项。
- [Spec](interpretation-spec-review.md)：初审2项P2（CLI摘要遗漏、80列长关系截断）；修复后原Reviewer复审通过，未解决0项，范围扩张0项。

## 浏览器验收

使用ego-browser访问绑定127.0.0.1:8091的本地服务，禁用可用模型列表，避免意外AI请求。验证实际NiceGUI页面，不仅检查HTTP响应。

- 1280px：三列各约346.7px；页面scrollWidth=innerWidth=1280。
- 375px：三传单列311px；页面scrollWidth=innerWidth=375；卡片clientWidth=scrollWidth、clientHeight=scrollHeight，无内部裁切。
- 数字1、2、3：大安/留连/赤口，比和与被克（金克木）。
- 日期2026-09-15 12:00：显示UTC+8和起课数字8、5、7，结果桃花/速喜/天德。
- 汉字中国人：显示原文与字典笔画4、8、2，结果赤口/留连/速喜。
- 小数1.5：显示整数错误，无新结果，按钮可用；改回1后清除错误并呈现三传。
- 展开文化背景后显示全部神灵说明与方位，仍无横向溢出。
- 截图：使用CDP完整页面截图实际检查桌面与手机的输入/结果/展开详情；临时截图位于 `/tmp/mini-six-ren-desktop.png` 和 `/tmp/mini-six-ren-mobile.png`，不作为持久仓库资产。原生日期控件的自动化填充需按ISO值派发input/change事件；不据此声称所有手机平台的日期选择器已验证。

## 限制与兼容性

- 未进行在线模型盲评；输入契约和规则不能保证模型固定格式、字数、抗注入或实际文案质量。
- 关系字符串返回值发生有意变化：旧“无”细分三类；`Prediction`结构及三传符号不变。AI公共调用失败由返回错误字符串改为抛出RuntimeError，现有CLI/Web已捕获。
- 浏览器视觉验收为Chromium桌面与375px模拟手机，不覆盖所有设备、浏览器、屏幕阅读器；等待/失败/多客户端由真实NiceGUI客户端和离线供应商测试覆盖。
- 八字叙事、旧日主工具、笔画标准、六宫策略属于范围外；本轮没有证明占卜的现实预测效力。

本轮按规格→本地tickets→实现/测试→独立复核与修复→验收→当前分支本地提交推进；不包含远程push或部署。
