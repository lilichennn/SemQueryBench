# DAIL-SQL 使用步骤指南

## 1. 环境设置

### 1.1 安装依赖

**输入**：
- Python 3.8+ 环境
- 网络连接（用于下载依赖和模型）

**操作**：
```bash
# 创建虚拟环境
conda create -n DAIL-SQL python=3.8
conda activate DAIL-SQL

# 安装依赖
python -m pip install --upgrade pip
pip install -r requirements.txt

# 下载 NLTK 数据
python nltk_downloader.py
```

**输出**：
- 安装好所有依赖的 Python 环境
- 下载完成的 NLTK 数据

### 1.2 配置 Stanford CoreNLP

**输入**：
- Stanford CoreNLP 安装包

**操作**：
```bash
# 下载 Stanford CoreNLP
wget http://nlp.stanford.edu/software/stanford-corenlp-full-2018-10-05.zip

# 解压到 third_party 目录
mkdir -p third_party
unzip stanford-corenlp-full-2018-10-05.zip -d third_party/

# 启动 CoreNLP 服务器
cd third_party/stanford-corenlp-full-2018-10-05
nohup java -mx4g -cp "*" edu.stanford.nlp.pipeline.StanfordCoreNLPServer &
cd ../../
```

**输出**：
- 运行中的 Stanford CoreNLP 服务器

## 2. 数据准备

### 2.1 下载数据集

**输入**：
- Spider 数据集下载链接

**操作**：
```bash
# 创建数据集目录
mkdir -p dataset/spider

# 下载 Spider 数据集（需要手动访问链接下载）
# 链接：https://yale-lily.github.io/spider

# 解压数据集到指定目录
unzip spider.zip -d dataset/spider/
```

**输出**：
- 解压后的 Spider 数据集，包括：
  - `train_spider_and_others.json`：训练数据
  - `dev.json`：开发数据
  - `tables.json`：表结构信息
  - `database/`：数据库文件

### 2.2 数据集结构

**Spider 数据集结构**：
```
dataset/spider/
├── train_spider_and_others.json  # 训练数据
├── dev.json                      # 开发数据
├── dev_gold.sql                  # 开发数据黄金答案
├── tables.json                   # 表结构信息
└── database/                     # 数据库文件
    ├── album/                    # 示例数据库
    │   ├── album.sqlite         # SQLite 数据库文件
    │   └── schema.sql           # 数据库 schema
    └── ...                       # 其他数据库
```

## 3. 数据预处理

### 3.1 运行预处理脚本

**输入**：
- 原始 Spider 数据集
- 运行中的 Stanford CoreNLP 服务器

**操作**：
```bash
python data_preprocess.py
```

**输出**：
- `dataset/spider/enc/train_schema-linking.jsonl`：训练数据的 schema 链接信息
- `dataset/spider/enc/test_schema-linking.jsonl`：测试数据的 schema 链接信息

### 3.2 预处理过程详解

**数据转换流程**：
1. **读取原始数据**：从 `train_spider_and_others.json` 和 `dev.json` 读取数据
2. **Schema 解析**：解析 `tables.json` 获取数据库表结构
3. **实体链接**：使用 Stanford CoreNLP 进行实体识别和链接
4. **问题模式提取**：提取问题的模式信息
5. **保存结果**：将处理后的信息保存为 JSONL 格式

**中间数据**：
- 实体链接结果：将问题中的实体与数据库表/列关联
- 问题模式：提取问题的结构化表示，用于后续示例选择

## 4. 提示生成

### 4.1 基本提示生成

**输入**：
- 预处理后的数据集
- 配置参数（提示类型、示例数量、选择策略等）

**操作**：
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

**输出**：
- `dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-150_ANS-4096/questions.json`：生成的提示文件

### 4.2 提示生成过程详解

**数据转换流程**：
1. **加载数据**：加载预处理后的数据集和 schema 链接信息
2. **选择示例**：根据选择策略（如 EUCDISQUESTIONMASK）从训练集中选择相关示例
3. **格式化提示**：根据提示类型（如 SQL）和示例格式（如 QA）格式化提示
4. **计算 token 成本**：估算提示的 token 数量和成本
5. **保存提示**：将生成的提示保存为 JSON 格式

**中间数据**：
- 示例选择结果：选择的相关示例列表
- 提示模板：根据配置生成的提示模板
- Token 成本估算：每个提示的 token 数量和成本

### 4.3 提示文件结构

**questions.json 结构**：
```json
{
  "args": {...},  // 生成提示时使用的参数
  "costs": {...}, // token 成本估算
  "questions": [
    {
      "prompt": "...",  // 完整的提示文本
      "prompt_tokens": 1500,  // 提示的 token 数量
      "db_id": "album",  // 数据库 ID
      "question": "..."  // 原始问题
    },
    // 更多问题
  ]
}
```

## 5. 调用 LLM 生成 SQL

### 5.1 基本调用

**输入**：
- 生成的提示文件
- OpenAI API 密钥
- 选择的 LLM 模型

**操作**：
```bash
python ask_llm.py \
--openai_api_key YOUR_API_KEY \
--model gpt-4 \
--question dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-150_ANS-4096
```

**输出**：
- `dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-150_ANS-4096/RESULTS_MODEL-gpt-4.txt`：生成的 SQL 查询

### 5.2 自一致性投票调用

**输入**：
- 生成的提示文件
- OpenAI API 密钥
- 选择的 LLM 模型
- 数据库目录

**操作**：
```bash
python ask_llm.py \
--openai_api_key YOUR_API_KEY \
--model gpt-4 \
--question dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-150_ANS-4096 \
--n 5 \
--db_dir ./dataset/spider/database \
--temperature 1.0
```

**输出**：
- `dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-150_ANS-4096/RESULTS_MODEL-gpt-4.txt`：通过自一致性投票选择的最佳 SQL 查询

### 5.3 LLM 调用过程详解

**数据转换流程**：
1. **加载提示**：从 `questions.json` 加载生成的提示
2. **调用 LLM API**：根据模型类型调用相应的 OpenAI API
3. **处理响应**：解析 LLM 返回的响应，提取 SQL 查询
4. **后处理**：去除重复内容，格式化 SQL
5. **自一致性投票**（可选）：
   - 生成多个 SQL 查询
   - 执行每个查询获取结果
   - 选择返回结果相同的查询作为最终结果
6. **保存结果**：将生成的 SQL 保存为文本文件

**中间数据**：
- LLM 原始响应：包含生成的 SQL 和 token 使用信息
- 多个候选 SQL：自一致性投票时生成的多个候选查询
- 执行结果：每个候选 SQL 的执行结果

**生成的 SQL 文件格式**：
```sql
SELECT name FROM album WHERE year > 2000;
SELECT COUNT(*) FROM artist WHERE country = 'USA';
-- 更多 SQL 查询
```

## 6. 结果评估

### 6.1 使用 Spider 官方评估工具

**输入**：
- 生成的 SQL 查询文件
- 黄金答案文件
- 数据库目录

**操作**：
```bash
# 克隆 Spider 评估工具
git clone https://github.com/taoyds/test-suite-sql-eval.git
cd test-suite-sql-eval

# 安装依赖
pip install -r requirements.txt

# 运行评估
python evaluation.py \
--gold ./dataset/spider/dev_gold.sql \
--pred ../DAIL-SQL/dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-150_ANS-4096/RESULTS_MODEL-gpt-4.txt \
--db ../DAIL-SQL/dataset/spider/database \
--table ../DAIL-SQL/dataset/spider/tables.json \
--etype execution
```

**输出**：
- 评估结果，包括：
  - EX (Execution Accuracy)：执行准确率
  - EM (Exact Match)：精确匹配率
  - 详细的错误分析

### 6.2 评估指标说明

- **EX (Execution Accuracy)**：执行准确率，指生成的 SQL 与黄金答案在执行结果上一致的比例
- **EM (Exact Match)**：精确匹配率，指生成的 SQL 与黄金答案完全相同的比例
- **其他指标**：根据评估工具的不同，还可能包括组件准确率、逻辑形式准确率等

## 7. 高级配置与定制

### 7.1 提示类型选择

DAIL-SQL 支持多种提示类型，可通过 `--prompt_repr` 参数选择：

| 提示类型 | 描述 |
|---------|------|
| SQL | 代码表示提示 |
| TEXT | 文本表示提示 |
| NUMBERSIGN | OpenAI 演示格式 |
| BASELINE | 基础格式 |
| INSTRUCTION | Alpaca SFT 格式 |
| SQLWFK | 带外键的 SQL 格式 |
| SQLWRULE | 带规则的 SQL 格式 |
| SQLCOT | 带思维链的 SQL 格式 |

### 7.2 示例选择策略

可通过 `--selector_type` 参数选择不同的示例选择策略：

| 选择策略 | 描述 |
|---------|------|
| COSSIMILAR | 基于余弦相似度 |
| RANDOM | 随机选择 |
| EUCDISTANCE | 基于欧氏距离 |
| EUCDISQUESTIONMASK | 基于掩码问题欧氏距离 |
| EUCDISMASKPRESKLSIMTHR | 基于掩码和骨架相似度阈值 |

### 7.3 示例格式

可通过 `--example_type` 参数选择不同的示例格式：

| 示例格式 | 描述 |
|---------|------|
| ONLYSQL | 仅显示 SQL |
| QA | 显示问题-SQL 对 |
| COMPLETE | 显示完整信息 |
| QAWRULE | 带规则的问题-SQL 对 |

## 8. 完整工作流示例

### 8.1 端到端运行示例

**完整命令序列**：
```bash
# 1. 环境设置
conda create -n DAIL-SQL python=3.8
conda activate DAIL-SQL
pip install -r requirements.txt
python nltk_downloader.py

# 2. 启动 CoreNLP 服务器
mkdir -p third_party
unzip stanford-corenlp-full-2018-10-05.zip -d third_party/
cd third_party/stanford-corenlp-full-2018-10-05
nohup java -mx4g -cp "*" edu.stanford.nlp.pipeline.StanfordCoreNLPServer &
cd ../../

# 3. 数据预处理
python data_preprocess.py

# 4. 提示生成
python generate_question.py --data_type spider --split test --tokenizer gpt-3.5-turbo --max_seq_len 4096 --prompt_repr SQL --k_shot 9 --example_type QA --selector_type EUCDISQUESTIONMASK

# 5. 调用 LLM
python ask_llm.py --openai_api_key YOUR_API_KEY --model gpt-4 --question dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-150_ANS-4096

# 6. 评估结果
git clone https://github.com/taoyds/test-suite-sql-eval.git
cd test-suite-sql-eval
pip install -r requirements.txt
python evaluation.py --gold ../DAIL-SQL/dataset/spider/dev_gold.sql --pred ../DAIL-SQL/dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-150_ANS-4096/RESULTS_MODEL-gpt-4.txt --db ../DAIL-SQL/dataset/spider/database --table ../DAIL-SQL/dataset/spider/tables.json --etype execution
```

### 8.2 使用脚本批量运行

**操作**：
```bash
# 使用提供的脚本运行
bash run_dail_sql_mini.sh YOUR_API_KEY
```

**脚本内容详解**：
1. 检查 API 密钥
2. 运行数据预处理
3. 生成提示
4. 调用 LLM
5. 保存结果

## 9. 常见问题与解决方案

### 9.1 CoreNLP 服务器连接失败

**问题**：`data_preprocess.py` 运行时提示无法连接到 CoreNLP 服务器

**解决方案**：
1. 确保 CoreNLP 服务器正在运行
2. 检查服务器端口是否正确（默认 9000）
3. 检查防火墙设置，确保端口可访问

### 9.2 API 调用失败

**问题**：`ask_llm.py` 运行时提示 API 调用失败

**解决方案**：
1. 检查 API 密钥是否正确
2. 检查网络连接
3. 检查模型名称是否正确
4. 检查提示长度是否超过模型的最大 token 限制

### 9.3 生成的 SQL 质量差

**解决方案**：
1. 尝试不同的提示类型
2. 调整示例数量（k_shot）
3. 尝试不同的示例选择策略
4. 调整温度参数（temperature）
5. 使用自一致性投票（增加 n 参数）

## 10. 总结

DAIL-SQL 是一个高效的 Text-to-SQL 解决方案，通过优化提示工程和示例选择，在 LLM 上取得了优异的成绩。其完整工作流程包括：

1. **环境设置**：安装依赖，启动 CoreNLP 服务器
2. **数据准备**：下载并解压 Spider 数据集
3. **数据预处理**：生成 schema 链接信息
4. **提示生成**：根据配置生成高质量提示
5. **LLM 调用**：调用 OpenAI API 生成 SQL
6. **结果评估**：使用 Spider 官方工具评估生成的 SQL

通过调整不同的配置参数，可以根据具体需求优化模型性能。DAIL-SQL 的设计具有良好的扩展性，可以轻松添加新的提示类型、示例选择器和支持新的 LLM 模型。