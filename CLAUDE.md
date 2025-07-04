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
- `sxtwl`: 中国传统历法计算库
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
- 使用sxtwl库进行精确的历法计算
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
- 所有数据文件都使用JSON格式存储在data/目录
- 类使用类方法（@classmethod）加载数据
- 数据加载在模块级别完成，避免重复读取

### 错误处理
- 用户输入验证使用专门的验证函数
- 日期格式验证和汉字验证
- 使用rich.console显示错误信息

### AI集成
- 使用OpenAI API进行占卜解读
- 需要设置OPENAI_API_KEY环境变量
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
- 需要OpenAI API密钥才能使用AI解读功能
- 使用.env文件存储敏感信息
- 确保data/目录下的JSON文件完整

### 中文字符处理
- 项目专门处理中文字符和汉字笔画计算
- 使用Unicode范围验证汉字输入
- 支持简体中文显示和输入

### 历法计算
- 使用sxtwl库进行准确的公历农历转换
- 支持闰月计算和时辰转换
- 八字计算基于传统历法规则