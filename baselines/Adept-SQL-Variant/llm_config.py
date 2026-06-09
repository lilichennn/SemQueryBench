import types


Other_llm_config={
    'server' : "YOUR SERVER",
    "ContentType": "application/json",
    "Accept": "application/json",
    "Authorization": "YOUR TOKEN",
    "modelname":'YOUR MODEL'
}
Other_llm_config = types.SimpleNamespace(**Other_llm_config)

###只有一个EMB MODEL
emb_model_config = {
    'server' : 'YOUR SERVER',
    'ContentType' : 'application/json',
    'Accept' : 'application/json',
    'Authorization' : 'YOUR TOKEN',
    'modelname' : 'YOUR MODEL'
}
emb_model_config = types.SimpleNamespace(**emb_model_config)