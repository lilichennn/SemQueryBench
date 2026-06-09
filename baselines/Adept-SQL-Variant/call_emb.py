import requests
from sentence_transformers import SentenceTransformer
from llm_config import emb_model_config



class callm3e():
    def __init__(self) -> None:


        self.server = emb_model_config.server
        self.header = {
            "Content-Type": emb_model_config.ContentType,
            "Accept": emb_model_config.Accept,
            "Authorization": emb_model_config.Authorization
        }
        self.modelname = emb_model_config.modelname

    def init_prompt(self,  prompt):

        #print(sys_prompt,prompt)
        self.input = {
        "model": self.modelname,
        "input": prompt
        }

        return(self)
    
    def call(self):
        try:
            self.llm_response = requests.post(url = self.server, 
                                            json = self.input, 
                                            headers = self.header).json()
            vector = self.llm_response['data'][0]['embedding']
        except:
            vector = 'Emb Fail'

        return(vector)

def vectorize_localmodel(somestr):

    try:
        model = SentenceTransformer("./m3e-base")
        print("INFO: model loaded.")
        vector = list(model.encode(somestr, normalize_embeddings=True))
    
    except:
        vector = 'Emb Fail'

    return(vector)


if __name__ == '__main__':


    
    res = callm3e().init_prompt('how are you').call()
    print(type(res),res)

