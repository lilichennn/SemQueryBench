## 配置说明

### 1. 数据库配置
编辑 `./p_DB/config.py` 文件，配置以下参数：
- `user_db_config`：用户数据库连接配置
- `emb_model_config`：Embedding 模型配置
- `milvusdb`：Milvus 向量数据库配置

### 2. 大模型接口配置
编辑 `./llm_config.py` 文件，配置以下参数：
- `Other_llm_config`：LLM 调用接口配置
- `emb_model_config`：Embedding 模型配置

## 运行步骤

### 1. 初始化向量数据库
```bash
python ./api/api_new_collection.py
```


### 2. 导入训练数据
```bash
python api/api_sql_upload.py
```

###  3. 启动服务
根据测试问题生成对应的 SQL 语句
```bash
python ./start.py
```