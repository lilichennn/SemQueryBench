


$db_root_directory = "Bird/hard" 
$bert_model = "YOUR BERT MODEL PATH" 
$fewshot_llm = "llm model NAME"
$DAIL_SQL = "$db_root_directory/skeletonsql_dev.json"


$dev_json = "test/test.json"
$train_json = "train/train.json"
$dev_table = "test/test_tables.json"
$train_table = "train/train_tables.json"


python -u src/database_process/data_preprocess.py `
    --db_root_directory $db_root_directory `
    --dev_json $dev_json `
    --train_json $train_json `
    --dev_table $dev_table `
    --train_table $train_table


python -u src/database_process/gen_question_similarity.py `
    --db_root_directory $db_root_directory `
    --bert_model $bert_model `
    --k_shot 5


python -u src/database_process/prepare_train_queries.py `
    --db_root_directory $db_root_directory `
    --model $fewshot_llm `
    --start 0 `
    --end 999 `
    --max_workers 5

python -u src/database_process/generate_question.py `
    --db_root_directory $db_root_directory `
    --DAIL_SQL $DAIL_SQL

python -u src/database_process/make_emb.py `
    --db_root_directory $db_root_directory `
    --bert_model $bert_model 