# OpenSearch-SQL 模型使用说明文档

## 1. 支持的模型

OpenSearch-SQL 框架支持多种预训练语言模型，包括：

| 模型类型 | 支持的变体 | 适用场景 |
|---------|-----------|---------|
| GPT     | gpt-4, gpt-4o, gpt-3.5-turbo | 通用场景，性能优秀 |
| DeepSeek | deepseek-coder | 代码生成，SQL优化 |
| Qwen    | qwen-max, qwen-max-longcontext | 长上下文处理 |
| Gemini  | gemini-pro | 多模态处理 |
| 自定义SFT | 基于DeepSeek的微调模型 | 特定领域优化 |

## 2. 模型配置

### 2.1 API 密钥配置

在 `src/llm/model.py` 文件中配置相应模型的 API 密钥：

#### GPT 模型配置
```python
# 在 gpt_req 类的 get_ans 方法中设置
url = "https://api.openai.com/v1/chat/completions"
key = "YOUR_OPENAI_API_KEY"
```

#### DeepSeek 模型配置
```python
# 在 deep_seek 类的 __init__ 方法中设置
headers = {
    "Content-Type": "application/json",
    "Authorization": "YOUR_DEEPSEEK_API_KEY"
}
```

#### Qwen 模型配置
```python
# 在 qwenmax 类的 __init__ 方法中设置
dashscope.api_key = "YOUR_DASHSCOPE_API_KEY"
```

### 2.2 模型参数配置

在运行配置文件中设置模型参数：

| 参数 | 描述 | 默认值 | 建议值 |
|------|------|--------|--------|
| engine | 模型引擎 | - | gpt-4o |
| temperature | 生成温度 | 0.0 | 0.0-0.3 |
| n | 生成候选数量 | 1 | 3-5 |
| single | 是否单候选 | true | 根据需要调整 |
| return_question | 是否返回问题 | false | false |

## 3. 模型调用方式

### 3.1 命令行调用

使用 `run_main.sh` 脚本运行框架：

```bash
# 基本调用
sh run/run_main.sh

# 自定义参数调用
python src/main.py \
    --data_mode dev \
    --db_root_path /path/to/data \
    --pipeline_nodes generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation \
    --pipeline_setup '{"model_para": {"node_name": "gpt_req", "config": {"engine": "gpt-4o", "temperature": 0.0, "n": 3, "single": "false", "return_question": "false"}}}'
```

### 3.2 编程式调用

可以在 Python 代码中直接调用框架：

```python
from runner.run_manager import RunManager
import argparse

# 解析参数
args_parser = argparse.ArgumentParser()
args_parser.add_argument('--data_mode', type=str, default='dev')
args_parser.add_argument('--db_root_path', type=str, default='/path/to/data')
args_parser.add_argument('--pipeline_nodes', type=str, default='generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation')
args_parser.add_argument('--pipeline_setup', type=str, default='{"model_para": {"node_name": "gpt_req", "config": {"engine": "gpt-4o", "temperature": 0.0, "n": 3, "single": "false", "return_question": "false"}}}')
args = args_parser.parse_args()

# 运行框架
run_manager = RunManager(args)
run_manager.initialize_tasks(0, 10, dataset)  # 处理前10个查询
run_manager.run_tasks()
run_manager.generate_sql_files()
```

## 4. 输入输出格式

### 4.1 输入格式

框架接受 JSON 格式的查询数据，每个查询包含以下字段：

```json
{
  "question_id": 0,
  "db_id": "academic",
  "question": "What is the average publication year of papers written by authors from Stanford?",
  "evidence": "Paper table has columns: id, title, year, venue. Author table has columns: id, name, affiliation. PaperAuthor table has columns: paper_id, author_id.",
  "raw_question": "What is the average publication year of papers written by authors from Stanford?"
}
```

### 4.2 输出格式

框架生成的 SQL 查询会保存为 JSON 格式，包含以下信息：

```json
{
  "node_type": "candidate_generate",
  "rewrite_question": "What is the average publication year of papers written by authors from Stanford?",
  "SQL": "SELECT AVG(p.year) FROM Paper p JOIN PaperAuthor pa ON p.id = pa.paper_id JOIN Author a ON pa.author_id = a.id WHERE a.affiliation = 'Stanford'"
}
```

## 5. 模型选择指南

### 5.1 根据任务类型选择

| 任务类型 | 推荐模型 | 理由 |
|---------|---------|------|
| 简单查询 | gpt-3.5-turbo | 成本低，响应快 |
| 复杂查询 | gpt-4o, qwen-max | 推理能力强，上下文理解好 |
| 长上下文 | qwen-max-longcontext | 支持更长的输入上下文 |
| 代码优化 | deepseek-coder | 代码生成能力优秀 |

### 5.2 根据性能需求选择

| 性能需求 | 推荐模型 | 配置建议 |
|---------|---------|---------|
| 高精度 | gpt-4o | temperature=0.0, n=5 |
| 高速度 | gpt-3.5-turbo, deepseek-coder | temperature=0.1, n=3 |
| 平衡 | qwen-max | temperature=0.2, n=4 |

## 6. 批量处理

### 6.1 批量处理配置

```bash
# 处理多个查询
python src/main.py \
    --data_mode dev \
    --db_root_path /path/to/data \
    --pipeline_nodes generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation \
    --pipeline_setup '{"model_para": {"node_name": "gpt_req", "config": {"engine": "gpt-4o", "temperature": 0.0, "n": 3, "single": "false", "return_question": "false"}}}' \
    --start 0 \
    --end 100  # 处理前100个查询
```

### 6.2 并行处理

框架支持多进程并行处理，可在 `src/runner/run_manager.py` 中修改 `NUM_WORKERS` 参数：

```python
NUM_WORKERS = 3  # 设置为 CPU 核心数的一半左右
```

## 7. 结果评估与分析

### 7.1 评估指标

框架会自动评估生成的 SQL 查询，使用以下指标：

- **执行准确率 (EX)**：SQL 是否能正确执行并返回正确结果
- **逻辑形式准确率 (LF)**：SQL 结构是否正确
- **部分准确率 (PA)**：SQL 部分结构是否正确

### 7.2 结果分析

生成的结果保存在 `results` 目录中，可使用以下命令查看：

```bash
# 查看生成的 SQL 文件
ls results/{data_mode}/{pipeline_nodes}/{dataset_name}/{run_time}/-*.json

# 查看统计信息
cat results/{data_mode}/{pipeline_nodes}/{dataset_name}/{run_time}/statistics.json
```

## 8. 常见问题与解决方案

### 8.1 API 调用失败

**问题**：模型 API 调用失败，返回错误信息。

**解决方案**：
1. 检查 API 密钥是否正确配置
2. 检查网络连接是否正常
3. 检查模型是否支持当前的请求频率
4. 调整请求参数，减少每次请求的内容长度

### 8.2 生成的 SQL 语法错误

**问题**：生成的 SQL 查询存在语法错误。

**解决方案**：
1. 增加 `n` 参数值，生成更多候选
2. 调整 `temperature` 参数，平衡创造力和准确性
3. 确保提供了足够的 few-shot 示例
4. 检查数据库模式信息是否正确

### 8.3 性能问题

**问题**：处理速度慢，资源消耗高。

**解决方案**：
1. 使用更快的模型，如 gpt-3.5-turbo
2. 减少 `n` 参数值，生成 fewer 候选
3. 启用并行处理，增加 `NUM_WORKERS`
4. 使用较小的 few-shot 示例集

### 8.4 内存不足

**问题**：处理大型数据库时内存不足。

**解决方案**：
1. 分批处理查询，减少 `--end` 参数值
2. 使用长上下文模型，如 qwen-max-longcontext
3. 优化数据库模式表示，减少内存使用

## 9. 高级使用技巧

### 9.1 自定义提示模板

可以在 `src/llm/prompts.py` 中自定义提示模板，优化模型输出：

```python
class db_check_prompts:
    def __init__(self):
        self.new_prompt = """
        /* Some SQL examples are provided based on similar problems: */
        {fewshot}

        #Values in Database:
        {key_col_des}

        #Database name: {db} 
        {column}

        #Forigen keys:
        {foreign_keys}

        #Question: {question}
        #Evidence: {evidence}
        #Order: {q_order}

        Please generate the SQL query based on the above information.
        """
```

### 9.2 模型集成

可以集成自定义的模型实现，步骤如下：

1. 在 `src/llm/model.py` 中创建新的模型类
2. 更新 `model_chose` 函数以支持新模型
3. 在配置中指定使用新模型

### 9.3 性能优化

**提示工程优化**：
- 提供更结构化的 few-shot 示例
- 使用 SQL-Like 中间语言
- 明确指定输出格式要求

**参数优化**：
- 对于复杂查询，使用较低的 `temperature` 和较大的 `n`
- 对于简单查询，使用较高的 `temperature` 和较小的 `n`

**系统优化**：
- 使用 SSD 存储数据，提高 I/O 速度
- 确保有足够的内存，避免频繁换页
- 使用稳定的网络连接，减少 API 调用延迟

## 10. 示例使用场景

### 10.1 学术研究

**场景**：研究 Text-to-SQL 模型的性能。

**配置**：
- 模型：gpt-4o
- 参数：temperature=0.0, n=5
- Pipeline：完整 pipeline

**使用方法**：
```bash
python src/main.py \
    --data_mode test \
    --db_root_path /path/to/bird \
    --pipeline_nodes generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation \
    --pipeline_setup '{"model_para": {"node_name": "gpt_req", "config": {"engine": "gpt-4o", "temperature": 0.0, "n": 5, "single": "false", "return_question": "false"}}}'
```

### 10.2 生产环境

**场景**：在生产环境中处理用户查询。

**配置**：
- 模型：gpt-3.5-turbo 或 deepseek-coder
- 参数：temperature=0.1, n=3
- Pipeline：简化 pipeline，减少处理步骤

**使用方法**：
```bash
python src/main.py \
    --data_mode prod \
    --db_root_path /path/to/prod/data \
    --pipeline_nodes generate_db_schema+column_retrieve_and_other_info+candidate_generate+align_correct \
    --pipeline_setup '{"model_para": {"node_name": "gpt_req", "config": {"engine": "gpt-3.5-turbo", "temperature": 0.1, "n": 3, "single": "false", "return_question": "false"}}}'
```

### 10.3 教育目的

**场景**：用于教学，展示 Text-to-SQL 转换过程。

**配置**：
- 模型：qwen-max
- 参数：temperature=0.2, n=1
- Pipeline：完整 pipeline，启用详细日志

**使用方法**：
```bash
python src/main.py \
    --data_mode dev \
    --db_root_path /path/to/teaching/data \
    --pipeline_nodes generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation \
    --pipeline_setup '{"model_para": {"node_name": "qwenmax", "config": {"engine": "qwen-max", "temperature": 0.2, "n": 1, "single": "true", "return_question": "true"}}}' \
    --log_level info
```

## 11. 总结

OpenSearch-SQL 框架提供了一种灵活、高效的 Text-to-SQL 解决方案，支持多种预训练语言模型。通过合理配置模型参数和使用方法，可以在不同场景下获得优秀的性能。

**核心优势**：
- 支持多种先进的预训练语言模型
- 模块化设计，易于扩展和定制
- 自动化评估和分析
- 支持批量和并行处理
- 不需要额外的模型训练

**适用场景**：
- 学术研究和 benchmark 测试
- 生产环境中的智能查询系统
- 教育和教学演示
- 数据库管理工具的智能助手