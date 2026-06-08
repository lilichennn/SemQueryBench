# DAIL-SQL 代码工程说明文档

## 1. 项目概述

DAIL-SQL 是一个高效的 Text-to-SQL 解决方案，通过优化 LLM 提示工程，在 Spider 排行榜上使用 GPT-4 达到了 86.6% 的执行准确率。该方法的核心特点包括：
- 将结构知识编码为 SQL 语句
- 基于骨架相似性选择示例
- 移除跨域知识以提高 token 效率
- 仅需约 1600 tokens/question 在 Spider-dev 上

## 2. 项目结构

```
DAIL-SQL/
├── img/                    # 文档图片资源
├── llm/                    # LLM 交互模块
│   └── chatgpt.py          # ChatGPT 交互实现
├── prompt/                 # 提示构建模块
│   ├── ExampleFormatTemplate.py     # 示例格式模板
│   ├── ExampleSelectorTemplate.py   # 示例选择器模板
│   ├── PromptICLTemplate.py         # ICL 提示模板
│   ├── PromptReprTemplate.py        # 提示表示模板
│   └── prompt_builder.py            # 提示构建器
├── results/                # 实验结果
├── utils/                  # 工具函数
│   ├── datasets/           # 数据集处理
│   │   └── spider.py
│   ├── linking_utils/      # 链接处理工具
│   ├── data_builder.py     # 数据构建器
│   ├── enums.py            # 枚举定义
│   ├── linking_process.py  # 链接处理
│   ├── post_process.py     # 后处理
│   ├── pretrained_embeddings.py  # 预训练嵌入
│   └── utils.py            # 通用工具
├── ask_llm.py              # 调用 LLM 主入口
├── data_preprocess.py      # 数据预处理
├── generate_question.py    # 生成提示主入口
├── nltk_downloader.py      # NLTK 下载器
├── requirements.txt        # 依赖列表
└── README.md               # 项目说明
```

## 3. 核心模块详解

### 3.1 数据处理模块 (utils/data_builder.py)

#### 3.1.1 BasicDataset 类

**功能**：基础数据集类，提供数据加载和处理的核心功能。

**关键方法**：
- `get_databases()`: 加载所有数据库表信息
- `get_tables(db_id)`: 获取指定数据库的表结构
- `get_train_json()`: 获取训练数据的 JSON 格式
- `get_test_json()`: 获取测试数据的 JSON 格式
- `data_pre_process()`: 数据预处理，添加骨架信息和 schema 链接信息

**子类**：
- `SpiderDataset`: Spider 数据集实现
- `RealisticDataset`: 真实数据集实现
- `BirdDataset`: BIRD 数据集实现

### 3.2 提示构建模块 (prompt/prompt_builder.py)

**功能**：根据不同配置创建提示模板。

**关键函数**：
- `prompt_factory(repr_type, k_shot, example_format, selector_type)`: 创建提示类的工厂函数
  - `repr_type`: 提示表示类型（SQL、TEXT 等）
  - `k_shot`: 示例数量
  - `example_format`: 示例格式（仅 SQL、QA 等）
  - `selector_type`: 示例选择器类型（余弦相似度、随机等）

**提示类型层次**：
1. **表示类型 (REPR_TYPE)**：定义提示的整体结构
   - SQLPrompt: 代码表示
   - TextPrompt: 文本表示
   - NumberSignPrompt: OpenAI 演示格式
   - BaselinePrompt: 基础格式
   - InstructionPrompt: Alpaca SFT 格式
   - 以及带外键、带规则、COT 等变体

2. **示例格式 (EXAMPLE_TYPE)**：定义示例的展示方式
   - SqlExampleStyle: 仅显示 SQL
   - QuestionSqlExampleStyle: 显示问题-SQL 对
   - CompleteExampleStyle: 显示完整信息

3. **示例选择器 (SELECTOR_TYPE)**：定义如何选择示例
   - CosineSimilarExampleSelector: 基于余弦相似度
   - RandomExampleSelector: 随机选择
   - EuclideanDistanceExampleSelector: 基于欧氏距离
   - EuclideanDistanceQuestionMaskSelector: 基于掩码问题相似度
   - EuclideanDistanceMaskPreSkeletonSimilarThresholdSelector: 基于掩码和骨架相似度

### 3.3 LLM 交互模块 (llm/chatgpt.py)

**功能**：处理与 OpenAI API 的交互。

**关键函数**：
- `init_chatgpt(api_key, org_id, model)`: 初始化 OpenAI API
- `ask_completion(model, batch, temperature)`: 调用 Completion API
- `ask_chat(model, messages, temperature, n)`: 调用 Chat API
- `ask_llm(model, batch, temperature, n)`: 统一的 LLM 调用入口，处理重试逻辑

### 3.4 主程序入口

#### 3.4.1 generate_question.py

**功能**：生成用于 LLM 的提示。

**工作流程**：
1. 加载数据
2. 创建提示模板
3. 为每个问题生成格式化提示
4. 计算 token 成本
5. 保存生成的提示

**关键参数**：
- `--data_type`: 数据集类型（spider, realistic, bird）
- `--split`: 数据分割（train, test）
- `--k_shot`: 示例数量
- `--prompt_repr`: 提示表示类型
- `--example_type`: 示例格式
- `--selector_type`: 示例选择器类型

#### 3.4.2 ask_llm.py

**功能**：调用 LLM 生成 SQL 查询。

**工作流程**：
1. 加载生成的提示
2. 初始化 OpenAI API
3. 批量调用 LLM
4. 处理 LLM 返回结果
5. 保存生成的 SQL 查询

**关键参数**：
- `--openai_api_key`: OpenAI API 密钥
- `--model`: LLM 模型（gpt-3.5-turbo, gpt-4 等）
- `--temperature`: 生成温度
- `--n`: 自一致性投票数量

## 4. 核心枚举类型 (utils/enums.py)

### 4.1 REPR_TYPE

定义提示的表示类型：
- `CODE_REPRESENTATION`: SQL 代码表示
- `TEXT_REPRESENTATION`: 文本表示
- `OPENAI_DEMOSTRATION`: # 格式演示
- `BASIC`: 基础格式
- `ALPACA_SFT`: 指令格式
- 以及带外键 (WFK)、带规则 (WRULE)、COT 等变体

### 4.2 EXAMPLE_TYPE

定义示例的格式类型：
- `ONLY_SQL`: 仅显示 SQL
- `QA`: 问题-SQL 对
- `COMPLETE`: 完整信息
- `QAWRULE`: 带规则的问题-SQL 对

### 4.3 SELECTOR_TYPE

定义示例选择器类型：
- `COS_SIMILAR`: 余弦相似度
- `RANDOM`: 随机选择
- `EUC_DISTANCE`: 欧氏距离
- `EUC_DISTANCE_QUESTION_MASK`: 掩码问题欧氏距离
- `EUC_DISTANCE_MASK_PRE_SKELETON_SIMILARITY_THRESHOLD`: 掩码和骨架相似度

### 4.4 LLM

定义支持的 LLM 模型：
- `TEXT_DAVINCI_003`: OpenAI Text Davinci 003
- `GPT_35_TURBO`: GPT-3.5 Turbo
- `GPT_4`: GPT-4
- 以及各种变体

## 5. 工作流程

### 5.1 数据预处理

```bash
python data_preprocess.py
```

该步骤处理原始数据，生成 schema 链接信息，为后续提示生成做准备。

### 5.2 提示生成

```bash
python generate_question.py \
--data_type spider \
--split test \
--tokenizer gpt-3.5-turbo \
--max_seq_len 4096 \
--prompt_repr SQL \
--k_shot 9 \
--example_type QA \
--selector_type EUCDISQUESTIONMASK
```

该步骤根据配置生成提示，包括：
1. 选择示例
2. 格式化提示
3. 计算 token 成本
4. 保存提示

### 5.3 调用 LLM

```bash
python ask_llm.py \
--openai_api_key [your_api_key] \
--model gpt-4 \
--question [prompt_dir]
```

该步骤调用 LLM 生成 SQL 查询，包括：
1. 加载提示
2. 调用 OpenAI API
3. 处理返回结果
4. 保存生成的 SQL

### 5.4 自一致性投票

```bash
python ask_llm.py \
--openai_api_key [your_api_key] \
--model gpt-4 \
--question [prompt_dir] \
--n 5 \
--db_dir ./dataset/spider/database \
--temperature 1.0
```

该步骤生成多个 SQL 查询并进行投票，提高结果准确性。

## 6. 关键算法

### 6.1 SQL 骨架提取

```python
def sql2skeleton(query, schema):
    # 将 SQL 查询转换为骨架，保留结构信息，移除具体值
    # 例如：SELECT name FROM users WHERE age > 18 → SELECT [COL] FROM [TABLE] WHERE [COL] > [VALUE]
```

### 6.2 示例选择算法

DAIL-SQL 的核心是基于骨架相似性的示例选择：
1. 计算问题的嵌入
2. 计算 SQL 骨架的嵌入
3. 结合两者的相似性选择最相关的示例
4. 移除跨域知识以提高 token 效率

### 6.3 自一致性投票

1. 生成多个 SQL 查询（n>1）
2. 执行每个查询并获取结果
3. 选择返回结果相同的查询作为最终结果

## 7. 性能优化

1. **Token 效率**：移除跨域知识，仅保留相关信息
2. **示例选择**：基于骨架相似性选择最相关的示例
3. **批量处理**：支持批量调用 LLM，提高效率
4. **重试机制**：处理 API 调用失败的情况
5. **成本估算**：预先计算 token 成本，帮助用户选择合适的配置

## 8. 实验结果

DAIL-SQL 在 Spider 数据集上取得了优异的成绩：

| 方法 | Dev EM | Dev EX | Test EM | Test EX |
|------|--------|--------|---------|---------|
| DAIL-SQL+GPT-4 | 70.0 | 83.1 | 66.5 | 86.2 |
| DAIL-SQL+GPT-4+Self-consistency | 68.7 | 83.6 | 66.0 | 86.6 |

其中：
- EM (Exact Match)：精确匹配率
- EX (Execution Accuracy)：执行准确率

## 9. 扩展与定制

### 9.1 添加新的提示类型

1. 在 `PromptReprTemplate.py` 中创建新的提示类
2. 在 `prompt_builder.py` 的 `get_repr_cls` 函数中添加映射
3. 在 `enums.py` 的 `REPR_TYPE` 中添加枚举值

### 9.2 添加新的示例选择器

1. 在 `ExampleSelectorTemplate.py` 中创建新的选择器类
2. 在 `prompt_builder.py` 的 `get_example_selector` 函数中添加映射
3. 在 `enums.py` 的 `SELECTOR_TYPE` 中添加枚举值

### 9.3 支持新的 LLM

1. 在 `llm/` 目录下创建新的 LLM 交互文件
2. 在 `ask_llm.py` 中添加新模型的支持
3. 在 `enums.py` 的 `LLM` 中添加枚举值

## 10. 总结

DAIL-SQL 是一个高效、高性能的 Text-to-SQL 解决方案，通过优化提示工程和示例选择，在 LLM 上取得了优异的成绩。其核心优势包括：

1. **高效的提示设计**：编码结构知识，提高 LLM 的理解能力
2. **智能的示例选择**：基于骨架相似性选择最相关的示例
3. **优化的 token 效率**：移除冗余信息，降低成本
4. **自一致性投票**：提高结果准确性
5. **灵活的架构**：支持多种提示类型、示例格式和选择器

该项目为 Text-to-SQL 任务提供了一个强大的框架，可以根据不同的需求进行定制和扩展。