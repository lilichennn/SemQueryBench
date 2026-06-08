# OpenSearch-SQL 代码工程说明文档

## 1. 项目概述

OpenSearch-SQL 是一个先进的 Text-to-SQL 框架，通过多 Agent 系统实现从自然语言到 SQL 查询的转换。该框架在 BIRD 基准测试上取得了第一名的成绩，采用了结构化 CoT 方法和 Alignment 技术来提升性能。

**核心功能**：
- 数据库模式处理和管理
- 自然语言查询分析和理解
- SQL 查询生成和优化
- 多模型集成和调用
- 结果评估和分析

**技术亮点**：
- 模块化 Pipeline 架构
- 结构化 Few-shot 学习
- Self-taught CoT 方法
- Alignment 技术缓解模型幻觉
- 支持多种先进的 LLM 模型

## 2. 目录结构

```
OpenSearch-SQL-main/
├── Bird/                  # 数据集目录
│   ├── fewshot/           # Few-shot 示例
│   ├── bird_dev.json      # DAIL-SQL 数据
│   └── correct_fewshot2.json # 校正的 few-shot 数据
├── image/                 # 图片资源
├── run/                   # 运行脚本
│   ├── run_main.sh        # 主运行脚本
│   └── run_preprocess.sh  # 数据预处理脚本
├── src/                   # 源代码
│   ├── database_process/  # 数据库处理模块
│   ├── llm/               # 语言模型模块
│   ├── pipeline/          # 处理管道模块
│   ├── runner/            # 任务运行模块
│   └── main.py            # 主入口文件
├── .gitignore             # Git 忽略文件
├── LICENSE                # 许可证
├── readme.md              # 英文说明文档
├── readme_zh.md           # 中文说明文档
└── requirements.txt       # 依赖文件
```

## 3. 核心模块说明

### 3.1 数据库处理模块 (`src/database_process/`)

**功能**：处理数据库模式信息，生成 few-shot 示例，准备查询相关数据。

**核心文件**：
- `data_preprocess.py`：数据预处理，提取数据库模式信息
- `generate_question.py`：生成结构化的 few-shot 示例
- `make_emb.py`：生成表和字段的嵌入向量
- `prepare_train_queries.py`：准备训练查询数据

**关键功能**：
- 提取表结构、字段信息和外键关系
- 生成结构化的 few-shot 示例，扩展为 Query-CoT-SQL Pair 形式
- 为表和字段生成嵌入向量，用于相似度计算
- 准备训练数据，优化模型输入

### 3.2 语言模型模块 (`src/llm/`)

**功能**：集成和调用各种预训练语言模型，处理模型输出。

**核心文件**：
- `model.py`：模型定义和调用
- `prompts.py`：提示模板定义
- `db_conclusion.py`：数据库结论生成
- `all_prompt.py`：所有提示模板的集合

**关键功能**：
- 支持多种预训练语言模型（GPT、DeepSeek、Qwen、Gemini）
- 统一的模型调用接口
- 结构化的提示模板设计
- 模型输出处理和解析
- API 调用管理和错误处理

### 3.3 处理管道模块 (`src/pipeline/`)

**功能**：定义和实现处理管道的各个节点，处理从自然语言到 SQL 的转换过程。

**核心文件**：
- `workflow_builder.py`：管道构建器
- `pipeline_manager.py`：管道管理器
- `generate_db_schema.py`：生成数据库模式
- `extract_col_value.py`：提取列值信息
- `extract_query_noun.py`：提取查询中的名词
- `column_retrieve_and_other_info.py`：检索相关列和其他信息
- `candidate_generate.py`：生成 SQL 候选
- `align_correct.py`：对齐和纠正生成的 SQL
- `vote.py`：对多个候选进行投票选择
- `evaluation.py`：评估生成结果
- `utils.py`：工具函数

**关键功能**：
- 模块化的管道设计
- 每个节点负责特定的处理任务
- 节点间的数据传递和状态管理
- SQL 生成和优化
- 结果评估和分析

### 3.4 任务运行模块 (`src/runner/`)

**功能**：管理任务执行，协调各个模块的工作。

**核心文件**：
- `run_manager.py`：任务运行管理器
- `task.py`：任务定义
- `database_manager.py`：数据库管理器
- `logger.py`：日志管理器
- `statistics_manager.py`：统计管理器
- `execution.py`：执行管理
- `check_and_correct.py`：检查和纠正
- `column_retrieve.py`：列检索
- `column_update.py`：列更新
- `extract.py`：信息提取

**关键功能**：
- 任务初始化和管理
- 并行任务执行
- 数据库连接和管理
- 日志记录和统计
- 结果生成和保存
- 检查点管理和恢复

## 4. 关键结构体和函数

### 4.1 核心结构体

#### `RunManager` 类 (`src/runner/run_manager.py`)

**功能**：管理任务执行，协调各个模块的工作。

**关键属性**：
- `args`：运行参数
- `result_directory`：结果目录
- `statistics_manager`：统计管理器
- `tasks`：任务列表
- `total_number_of_tasks`：总任务数
- `processed_tasks`：已处理任务数

**关键方法**：
- `initialize_tasks(start, end, dataset)`：初始化任务
- `run_tasks()`：运行任务
- `worker(task)`：处理单个任务
- `load_checkpoint(db_id, question_id)`：加载检查点
- `generate_sql_files()`：生成 SQL 文件

#### `Task` 类 (`src/runner/task.py`)

**功能**：定义任务，存储任务相关信息。

**关键属性**：
- `db_id`：数据库 ID
- `question_id`：问题 ID
- `question`：问题文本
- `evidence`：证据信息
- `raw_question`：原始问题

#### `DatabaseManager` 类 (`src/runner/database_manager.py`)

**功能**：管理数据库连接和模式信息。

**关键属性**：
- `db_mode`：数据库模式
- `db_root_path`：数据库根路径
- `db_id`：数据库 ID
- `db_schema`：数据库模式
- `db_fewshot_path`：few-shot 数据路径

**关键方法**：
- `get_db_schema()`：获取数据库模式
- `_set_paths()`：设置路径
- `get_tables()`：获取表信息

#### `PipelineManager` 类 (`src/pipeline/pipeline_manager.py`)

**功能**：管理处理管道的设置和参数。

**关键属性**：
- `pipeline_setup`：管道设置

**关键方法**：
- `get_model_para()`：获取模型参数
- `get_node_para(node_name)`：获取节点参数

#### `WorkflowBuilder` 类 (`src/pipeline/workflow_builder.py`)

**功能**：构建处理管道。

**关键属性**：
- `workflow`：工作流对象

**关键方法**：
- `build(pipeline_nodes)`：构建工作流
- `_add_nodes(nodes)`：添加节点
- `_add_edges(edges)`：添加边

### 4.2 核心函数

#### `build_pipeline(pipeline_nodes)` (`src/pipeline/workflow_builder.py`)

**功能**：构建和编译处理管道。

**参数**：
- `pipeline_nodes`：管道节点字符串，用 '+' 分隔

**返回值**：
- 编译后的工作流应用

#### `candidate_generate(task, execution_history)` (`src/pipeline/candidate_generate.py`)

**功能**：生成 SQL 候选。

**参数**：
- `task`：任务对象
- `execution_history`：执行历史

**返回值**：
- 包含生成的 SQL 和相关信息的字典

#### `align_correct(task, execution_history)` (`src/pipeline/align_correct.py`)

**功能**：对齐和纠正生成的 SQL。

**参数**：
- `task`：任务对象
- `execution_history`：执行历史

**返回值**：
- 包含纠正后的 SQL 和相关信息的字典

#### `vote(task, execution_history)` (`src/pipeline/vote.py`)

**功能**：对多个 SQL 候选进行投票选择。

**参数**：
- `task`：任务对象
- `execution_history`：执行历史

**返回值**：
- 包含投票结果和相关信息的字典

#### `evaluation(task, execution_history)` (`src/pipeline/evaluation.py`)

**功能**：评估生成的 SQL 结果。

**参数**：
- `task`：任务对象
- `execution_history`：执行历史

**返回值**：
- 包含评估结果和相关信息的字典

#### `model_chose(node_name, engine)` (`src/llm/model.py`)

**功能**：选择和初始化模型。

**参数**：
- `node_name`：节点名称
- `engine`：模型引擎

**返回值**：
- 初始化的模型对象

#### `get_sql(chat_model, prompt, temperature, return_question=False, n=1, single=True)` (`src/runner/check_and_correct.py`)

**功能**：获取 SQL 查询。

**参数**：
- `chat_model`：聊天模型
- `prompt`：提示文本
- `temperature`：生成温度
- `return_question`：是否返回问题
- `n`：生成候选数量
- `single`：是否单候选

**返回值**：
- 生成的 SQL 和相关信息

#### `main(args)` (`src/main.py`)

**功能**：主函数，运行处理管道。

**参数**：
- `args`：运行参数

**流程**：
1. 加载数据集
2. 初始化运行管理器
3. 初始化任务
4. 运行任务
5. 生成 SQL 文件

## 5. 工作流程

OpenSearch-SQL 框架的工作流程如下：

1. **数据预处理**：
   - 处理数据库模式信息
   - 生成 few-shot 示例
   - 准备查询相关数据

2. **任务初始化**：
   - 加载数据集
   - 为每个查询创建任务
   - 设置运行环境和参数

3. **管道构建**：
   - 根据配置构建处理管道
   - 初始化各个节点
   - 设置节点间的连接

4. **任务执行**：
   - 逐个处理任务
   - 执行管道的各个节点
   - 生成 SQL 候选

5. **结果处理**：
   - 对齐和纠正生成的 SQL
   - 对多个候选进行投票选择
   - 评估生成结果

6. **结果生成**：
   - 生成 SQL 文件
   - 统计评估结果
   - 保存运行日志

### 5.1 详细处理流程

1. **生成数据库模式**：
   - 提取表结构、字段信息和外键关系
   - 构建数据库模式表示

2. **提取列值信息**：
   - 分析查询，提取相关列
   - 识别列值和约束条件

3. **提取查询中的名词**：
   - 分析查询文本
   - 提取关键名词和实体

4. **检索相关列和其他信息**：
   - 根据提取的信息检索相关列
   - 收集其他必要信息，如外键关系

5. **生成 SQL 候选**：
   - 使用 LLM 生成多个 SQL 候选
   - 应用结构化 CoT 方法

6. **对齐和纠正生成的 SQL**：
   - 对齐 Agent 输入输出
   - 纠正语法错误和逻辑问题
   - 确保 SQL 符合数据库模式

7. **对多个候选进行投票选择**：
   - 应用 Self-Consistency 方法
   - 对多个候选进行投票
   - 选择最佳 SQL 查询

8. **评估生成结果**：
   - 评估 SQL 语法正确性
   - 评估执行结果准确性
   - 计算各种评估指标

## 6. 技术栈

| 类别 | 技术/库 | 用途 | 来源 |
|------|---------|------|------|
| **编程语言** | Python 3.8+ | 主要开发语言 | `requirements.txt` |
| **Web 框架** | - | - | - |
| **数据库** | SQLite | 示例数据库 | `src/pipeline/candidate_generate.py` |
| **机器学习** | - | - | - |
| **LLM 集成** | OpenAI API, DeepSeek API, DashScope API | 模型调用 | `src/llm/model.py` |
| **工具库** | pandas, tqdm, logging, json, argparse | 数据处理和工具 | `requirements.txt` |
| **工作流** | langgraph | 管道构建 | `src/pipeline/workflow_builder.py` |
| **网络** | requests | API 调用 | `src/llm/model.py` |
| **文件系统** | pathlib, os | 路径管理 | 多个文件 |

## 7. 依赖关系

### 7.1 核心依赖

| 依赖 | 版本 | 用途 | 来源 |
|------|------|------|------|
| pandas | - | 数据处理 | `requirements.txt` |
| tqdm | - | 进度显示 | `requirements.txt` |
| requests | - | API 调用 | `requirements.txt` |
| langgraph | - | 管道构建 | `src/pipeline/workflow_builder.py` |
| dashscope | - | Qwen 模型调用 | `src/llm/model.py` |
| torch | - | 自定义模型支持 | `src/llm/model.py` |
| transformers | - | 自定义模型支持 | `src/llm/model.py` |

### 7.2 模块依赖关系

```
main.py → run_manager.py → workflow_builder.py → pipeline nodes
       → database_manager.py → database_process modules
       → logger.py → statistics_manager.py

pipeline nodes → llm/model.py → prompts.py
              → database_manager.py
              → utils.py

llm/model.py → prompts.py
             → db_conclusion.py

database_process modules → pandas, json, os
```

## 8. 配置和部署

### 8.1 配置文件

OpenSearch-SQL 框架使用命令行参数进行配置，主要参数包括：

| 参数 | 描述 | 必需 | 默认值 |
|------|------|------|--------|
| `--data_mode` | 数据模式 | 是 | - |
| `--db_root_path` | 数据库根路径 | 是 | - |
| `--pipeline_nodes` | 管道节点配置 | 是 | - |
| `--pipeline_setup` | 管道设置（JSON 格式） | 是 | - |
| `--use_checkpoint` | 使用检查点 | 否 | False |
| `--checkpoint_nodes` | 检查点节点配置 | 否 | - |
| `--checkpoint_dir` | 检查点目录 | 否 | - |
| `--log_level` | 日志级别 | 否 | warning |
| `--start` | 开始任务索引 | 否 | 0 |
| `--end` | 结束任务索引 | 否 | 1 |

### 8.2 部署步骤   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

1. **环境搭建**：
   - 安装 Python 3.8+
   - 安装依赖：`pip install -r requirements.txt`

2. **数据准备**：
   - 下载 BIRD 数据集
   - 运行数据预处理脚本：`sh run/run_preprocess.sh`

3. **模型配置**：
   - 在 `src/llm/model.py` 中配置 API 密钥
   - 调整模型参数

4. **运行框架**：
   - 使用 `run_main.sh` 脚本运行：`sh run/run_main.sh`
   - 或使用命令行参数自定义运行：`python src/main.py --data_mode dev --db_root_path /path/to/data --pipeline_nodes ... --pipeline_setup ...`

## 9. 扩展和定制指南

### 9.1 添加新的模型

1. 在 `src/llm/model.py` 中创建新的模型类
2. 更新 `model_chose` 函数以支持新模型
3. 在配置中指定使用新模型

### 9.2 添加新的管道节点

1. 在 `src/pipeline/` 目录下创建新的节点文件
2. 实现节点函数，使用 `@node_decorator` 装饰器
3. 在 `workflow_builder.py` 中注册新节点
4. 更新运行配置，包含新节点

### 9.3 定制提示模板

1. 在 `src/llm/prompts.py` 中添加新的提示模板
2. 在使用提示模板的地方引用新模板
3. 调整模板内容以适应特定任务

### 9.4 扩展评估指标

1. 在 `src/pipeline/evaluation.py` 中添加新的评估指标
2. 更新评估函数以计算新指标
3. 在统计管理器中添加新指标的处理

## 10. 调试和故障排除

### 10.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| API 调用失败 | API 密钥错误或网络问题 | 检查 API 密钥和网络连接 |
| SQL 语法错误 | 模型生成错误或数据库模式不匹配 | 增加 few-shot 示例，调整模型参数 |
| 内存不足 | 处理大型数据库或过多查询 | 分批处理，增加内存 |
| 性能问题 | 模型选择不当或参数配置不合理 | 选择合适的模型，优化参数配置 |
| 结果不准确 | 缺少相关信息或模型理解错误 | 提供更详细的数据库模式，增加 few-shot 示例 |

### 10.2 调试技巧

1. **启用详细日志**：
   - 设置 `--log_level info` 参数
   - 查看 `results/{run_time}/logs/` 目录下的日志文件

2. **检查中间结果**：
   - 查看 `results/{run_time}/{question_id}_{db_id}.json` 文件
   - 分析管道各个节点的输出

3. **使用检查点**：
   - 启用 `--use_checkpoint` 参数
   - 设置 `--checkpoint_nodes` 和 `--checkpoint_dir` 参数
   - 从失败的节点重新开始处理

4. **单步调试**：
   - 设置 `--start` 和 `--end` 参数，只处理单个查询
   - 在代码中添加断点或打印语句

## 11. 性能优化

### 11.1 模型优化

- **选择合适的模型**：根据任务复杂度选择合适的模型
- **调整模型参数**：优化 temperature、n 等参数
- **使用批量处理**：减少 API 调用次数
- **缓存模型响应**：避免重复计算

### 11.2 系统优化

- **启用并行处理**：增加 `NUM_WORKERS` 参数
- **优化内存使用**：分批处理查询，减少内存占用
- **使用 SSD 存储**：提高 I/O 速度
- **优化数据库访问**：减少数据库查询次数，使用缓存

### 11.3 代码优化

- **减少冗余计算**：优化重复计算的部分
- **使用更高效的数据结构**：选择合适的数据结构
- **并行化处理**：使用多线程或多进程
- **优化 I/O 操作**：减少文件读写次数，使用批量操作

## 12. 总结

OpenSearch-SQL 是一个功能强大、结构清晰的 Text-to-SQL 框架，通过模块化设计和先进的技术实现了从自然语言到 SQL 查询的高效转换。该框架的核心优势在于：

1. **模块化 Pipeline 架构**：灵活可扩展，易于定制和扩展
2. **多模型集成**：支持多种先进的预训练语言模型
3. **结构化 CoT 方法**：提升模型推理能力
4. **Alignment 技术**：缓解模型幻觉问题
5. **自动化评估**：提供全面的评估指标和分析

通过详细了解和使用这个框架，开发者可以构建更智能、更准确的 Text-to-SQL 系统，为用户提供更自然、更高效的数据库查询体验。

**适用场景**：
- 学术研究和 benchmark 测试
- 生产环境中的智能查询系统
- 教育和教学演示
- 数据库管理工具的智能助手

**未来发展方向**：
- 集成更多先进的语言模型
- 优化处理管道，提高效率
- 扩展到更多数据库类型和查询场景
- 开发更智能的错误处理和修复机制
- 提供更友好的用户界面和 API