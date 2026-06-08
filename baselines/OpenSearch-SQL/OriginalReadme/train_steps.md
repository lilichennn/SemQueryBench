# OpenSearch-SQL 训练步骤文档

## 1. 环境搭建

### 1.1 系统要求
- Python 3.8+
- 足够的内存和磁盘空间（至少10GB）
- 网络连接（用于下载依赖和调用LLM API）

### 1.2 依赖安装
```bash
# 克隆代码仓库
git clone <repository_url>
cd OpenSearch-SQL-main

# 安装依赖
pip install -r requirements.txt
```

## 2. 数据预处理

OpenSearch-SQL 框架不需要额外的模型训练，但需要进行数据预处理来准备 few-shot 示例和数据库模式信息。

### 2.1 准备数据集

1. **下载 BIRD 数据集**
   - 从 [BIRD 官方网站](https://bird-bench.github.io/) 下载完整数据集
   - 解压到指定目录，例如：`.\n2sqlre\data\BIRD`

2. **准备 DAIL-SQL 数据**
   - 我们采用 [DAIL-SQL](https://github.com/BeachWang/DAIL-SQL) 方法生成 few-shot 示例
   - 项目已提供 `Bird/bird_dev.json` 文件，可直接使用

### 2.2 生成 Few-shot 示例

```bash
# 运行数据预处理脚本
sh run/run_preprocess.sh
```

该脚本会执行以下步骤：
1. 处理数据库模式信息
2. 生成 few-shot 示例
3. 准备查询相关信息

**核心处理步骤**：
1. **数据库模式处理**：提取表结构、字段信息和外键关系
2. **Few-shot 生成**：使用 `src/database_process/generate_question.py` 生成结构化的 few-shot 示例
3. **嵌入生成**：为表和字段生成嵌入向量，用于相似度计算

### 2.3 生成过程详解

1. **提取相似问题**：从 DAIL-SQL 数据中提取与当前查询相似的问题
2. **结构化 Few-shot**：将 Query-SQL Pair 扩展为 Query-CoT-SQL Pair 形式
3. **保存处理结果**：生成的 few-shot 示例保存在 `fewshot/questions.json` 文件中

## 3. 配置设置

### 3.1 LLM API 配置

需要在 `src/llm/model.py` 中配置 LLM API 密钥：

- **GPT 模型**：设置 OpenAI API 密钥
- **DeepSeek 模型**：设置 DeepSeek API 密钥
- **Qwen 模型**：设置 DashScope API 密钥

### 3.2 运行参数配置

创建或修改运行配置文件，设置以下参数：

- `data_mode`：数据模式（如 "dev"、"test"）
- `db_root_path`：数据库根路径
- `pipeline_nodes`：Pipeline 节点配置
- `pipeline_setup`：Pipeline 设置（JSON 格式）

## 4. 框架运行

### 4.1 启动主程序

```bash
sh run/run_main.sh
```

**运行流程**：
1. **加载数据集**：从指定路径加载处理好的数据
2. **初始化任务**：为每个查询创建处理任务
3. **构建 Pipeline**：根据配置构建处理管道
4. **执行任务**：逐个处理查询，生成 SQL
5. **生成结果**：将生成的 SQL 保存到结果目录

### 4.2 Pipeline 执行流程

1. **generate_db_schema**：生成数据库模式信息
2. **extract_col_value**：提取列值信息
3. **extract_query_noun**：提取查询中的名词
4. **column_retrieve_and_other_info**：检索相关列和其他信息
5. **candidate_generate**：生成 SQL 候选
6. **align_correct**：对齐和纠正生成的 SQL
7. **vote**：对多个候选进行投票选择
8. **evaluation**：评估生成结果

## 5. 结果评估

生成的 SQL 会保存到 `results` 目录中，按以下结构组织：
```
results/
└── {data_mode}/
    └── {pipeline_nodes}/
        └── {dataset_name}/
            └── {run_time}/
                ├── logs/
                ├── -args.json
                └── {question_id}_{db_id}.json
```

### 5.1 评估指标

- **执行准确率 (EX)**：SQL 是否能正确执行并返回正确结果
- **逻辑形式准确率 (LF)**：SQL 结构是否正确
- **R-VES**：在不同评估设置下的综合表现

## 6. 注意事项

1. **API 密钥配置**：确保正确配置了 LLM API 密钥，否则无法调用模型
2. **数据路径设置**：在 `src/runner/database_manager.py` 中正确设置数据路径
3. **计算资源**：处理大量查询时可能需要较长时间，请确保有足够的计算资源
4. **网络连接**：调用外部 LLM API 时需要稳定的网络连接

## 7. 自定义扩展

### 7.1 添加新的 Pipeline 节点

1. 在 `src/pipeline/` 目录下创建新的节点文件
2. 在 `workflow_builder.py` 中注册新节点
3. 更新运行配置，包含新节点

### 7.2 替换 LLM 模型

1. 在 `src/llm/model.py` 中添加新的模型类
2. 更新 `model_chose` 函数以支持新模型
3. 在配置中指定使用新模型

## 8. 故障排除

- **API 调用失败**：检查 API 密钥和网络连接
- **数据加载错误**：检查数据路径和文件格式
- **Pipeline 构建失败**：检查节点配置和依赖关系
- **内存不足**：减少批量处理的查询数量

## 9. 总结

OpenSearch-SQL 框架是一个基于预训练 LLM 的 Text-to-SQL 系统，通过以下步骤实现从自然语言到 SQL 的转换：

1. **环境搭建**：安装必要的依赖
2. **数据预处理**：准备 few-shot 示例和数据库模式
3. **配置设置**：设置 LLM API 和运行参数
4. **框架运行**：执行 Pipeline 处理流程
5. **结果评估**：评估生成的 SQL 质量

该框架的核心优势在于：
- 不需要额外的模型训练
- 支持多种 LLM 模型
- 采用结构化 CoT 方法提升性能
- 通过 Alignment 技术缓解模型幻觉问题
- 模块化设计，易于扩展和定制