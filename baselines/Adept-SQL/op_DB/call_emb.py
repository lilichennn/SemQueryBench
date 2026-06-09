import requests
from config import *

class callm3e():
    def __init__(self) -> None:

        self.server = emb_model_config.server
        self.header = {
        "Content-Type":emb_model_config.ContentType,
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

        self.llm_response = requests.post(url = self.server, 
                                          json = self.input, 
                                          headers = self.header).json()
        vector = self.llm_response['data'][0]['embedding']

        return(vector)

if __name__ == '__main__':

    res = callm3e().init_prompt('你是谁啊？').call()
    print(type(res),len(res))

