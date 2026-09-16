# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Mini Six Ren（小六壬）是一个基于Python的中国传统占卜应用，包含了八字测算、小六壬占卜、五行分析等功能。该项目使用了中国传统文化的数据和算法，为用户提供占卜和命理分析服务。

## 开发环境和依赖

### Python依赖管理
- 使用 `uv` 作为Python包管理器
- 安装依赖：`uv sync`
- 添加新依赖：`uv add <package_name>`
- 运行项目：`uv run src/cli.py`

### 核心依赖
- `lunar-python`: 中国传统历法计算库
- `openai`: 用于AI解读功能
- `rich`: 终端UI美化库
- `python-dotenv`: 环境变量管理

## 项目架构

### 主要模块结构
```
src/
├── cli.py              # 主CLI界面和菜单系统
├── bagua.py           # 八卦相关类和数据
├── celestial_stems_earthly_branches.py  # 天干地支
├── five_elements.py   # 五行系统
├── hand_technique.py  # 小六壬占卜核心算法
├── symbols.py         # 占卜符号定义
└── utils/
    ├── bazi_calculator.py      # 八字计算
    ├── calendar_converter.py   # 历法转换
    ├── five_elements_utils.py  # 五行工具函数
    └── stroke_count.py         # 汉字笔画计算
```

### 数据文件结构
```
data/
├── bagua.json                     # 八卦数据
├── celestial_stems_earthly_branches.json  # 天干地支数据
├── five_elements.json             # 五行数据
├── symbols.json                   # 占卜符号数据
├── hanzi_dictionary.txt           # 汉字字典
└── 太岁_*.json                    # 太岁数据文件
```

## 核心功能模块

### 1. 小六壬占卜系统 (hand_technique.py)
- 核心算法：通过三个数字计算符号位置
- 支持三种输入方式：数字、日期、汉字笔画
- 集成OpenAI API进行占卜解读
- 计算五行生克关系

### 2. 八字测算系统 (bazi_calculator.py)
- 使用lunar-python库进行精确的历法计算
- 分析日主强弱、配偶宫位等
- 五行缺失分析和影响评估

### 3. 五行系统 (five_elements.py)
- 完整的五行相生相克关系
- 包含寓意、促进、禁忌等详细信息
- 支持帮扶和克泄耗分析

### 4. CLI界面系统 (cli.py)
- 使用rich库创建美观的终端界面
- 渐变色标题和彩色菜单
- 分层菜单结构和错误处理

## 开发规约

### 数据加载模式
- 领域数据使用JSON格式存储在data/目录；汉字笔画保留现有TXT字典，模块初始化时一次性读取为映射
- 类使用类方法（@classmethod）加载数据
- 数据加载在模块级别完成，避免重复读取
- 路径相对于模块文件定位到项目data目录，不依赖启动工作目录

### 错误处理
- 用户输入验证使用专门的验证函数
- 日期格式验证和汉字验证
- 使用rich.console显示错误信息

### AI集成
- 使用OpenAI API进行占卜解读
- 本地占卜不需要密钥；仅AI解读需要OPENAI_API_KEY或DEEPSEEK_API_KEY
- 使用.env文件管理API密钥

## 常用开发命令

### 运行应用
```bash
uv run src/cli.py
```

### 安装新依赖
```bash
uv add <package_name>
```

### 项目入口
- 主程序入口：`src/cli.py`
- 项目会自动设置工作目录到项目根目录

## 注意事项

### 环境配置
- 本地三传先显示，选用AI且问题非空时再调用；失败不能清除本地结果
- 使用.env文件存储敏感信息
- 确保data/目录下的JSON文件完整

### 中文字符处理
- 项目专门处理中文字符和汉字笔画计算
- 使用Unicode范围验证汉字输入
- 支持简体中文显示和输入

### 历法计算
- 使用lunar-python库进行准确的公历农历转换
- 支持闰月计算和时辰转换
- 八字计算基于传统历法规则

## 计算与界面边界
- `HandTechnique.predict` 返回 `Prediction(symbols, relations)`，不创建Rich表格或AI客户端。
- CLI在`format_prediction`中渲染表格，Web直接渲染结构化结果。
- 每次Web页面请求创建独立`DivinationWebApp`，禁止共享含UI引用的控制器。
- `utils.validation`提供共用校验；`calendar_converter.date_to_numbers`为两种界面提供统一日期输入。
- 八字唯一实现位于`bazi_calculator`；五行分析位于`five_elements_utils`；符号关系位于`symbol_relations`。
- 历法按北京时间UTC+8解释输入，公历范围1900–2099；八字采用lunar-python sect 2（午夜换日），不做真太阳时校正。

## 验证
运行 `uv run python -m unittest discover -s tests -v`。改进规格见 `docs/specs/review-improvements.md`。

## 算法变更的独立复核

涉及算法新增、修改、替换或可能影响结果的重构时，必须由未参与实现的独立 Agent Reviewer 复核；实现者自审和现有测试不能替代。Reviewer 应独立检查参考样例、边界条件、领域约定及新旧行为差异。阻断问题修复后必须复审，复核完成前不得报告算法变更已完成。复核证据、结论和限制需写入规格或审查记录。

详细流程见根目录 `AGENTS.md` 的“算法变更的独立复核”章节；此要求对 Codex 和 Claude Code 均适用。


## Agent skills

### Issue tracker

使用本地 Markdown：`.scratch/<feature>/issues/`，既有spec由功能入口链接。见 `docs/agents/issue-tracker.md`。

### Triage labels

采用五个默认triage标签；执行状态在tracker文档中另行定义。见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文：根目录 `CONTEXT.md` 与 `docs/adr/` 按需创建。见 `docs/agents/domain.md`。

### 开发流程

按规格规划、实现、独立审查并本地提交，具体流程与命令见 `docs/agents/workflow.md`。
