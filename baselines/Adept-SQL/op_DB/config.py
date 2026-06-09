import types


####Backend MySQL configuration shared by all assistants. This configuration is optional.
backendb = {
    'url' : 'YOUR URL',
    'port' : 'YOUR PORT',
    'password' : 'YOUR PASSWORD',
    'user_name' : 'YOUR user_name',
    'database' : 'YOUR DATABSE'
    }
backendb = types.SimpleNamespace(**backendb)

####Each assistant must have its own embedding collection. This is required.
milvusdb = {
    'url' : 'YOUR URL',
    'port' : 'YOUR PORT',
    'password' : 'YOUR PASSWORD',
    'user_name' : 'YOUR user_name',
    'database' : 'YOUR DATABSE',
    'collection' : 'table_name'  ####  Optional. Not currently needed.
}
milvusdb = types.SimpleNamespace(**milvusdb)

### EMB MODEL This is required.
emb_model_config = {
    'server' : 'YOUR URL',
    'ContentType' : 'application/json',
    'Accept' : 'application/json',
    'Authorization' : 'Bearer [YOUR SKEY]',
    'modelname' : 'YOUR MODEL_NAME'
}
emb_model_config = types.SimpleNamespace(**emb_model_config)

### user_db This is required.
user_db_config = {
    'ip': 'YOUR IP',           
    'port': 'YOUR PORT',
    'user_name':'YOUR user_name',
    'user_password': 'YOUR user_name',
    'db_name': 'YOUR DATABSE'         
}

#------------------------------------------------------------------------
if __name__ == "__main__":
    print("backendb", backendb)
    print("milvusdb", milvusdb)