import requests
#from op_DB.config import *
from llm_config import *
from op_DB import backend_db_op

class callLLM():
    def __init__(self, modelcode = 'qwen') -> None:

        
        try:
            modelcode = int(modelcode)
            db = backend_db_op().query_table('llm_api')
            llmapi = db[db['id'] == modelcode].to_dict()

            self.llm_server = llmapi['url'][0]
            self.llm_header = {
            "Content-Type": 'application/json',
            "Accept":'application/json',
            "Authorization": 'Bearer '+ llmapi['token'][0]
            }
            self.modelname = llmapi['name'][0]

        #config
        except:
                self.llm_server = Other_llm_config.server
                self.llm_header = {
                "Content-Type": Other_llm_config.ContentType,
                "Accept":Other_llm_config.Accept,
                "Authorization": Other_llm_config.Authorization
                }
                self.modelname = Other_llm_config.modelname


    def init_prompt(self, sys_prompt, prompt):

        #print(sys_prompt,prompt)
        messages= [
            {"role": "system",  "content": sys_prompt},
            {"role": "user",    "content": prompt}
            ]
        
        self.llm_input = {
            "model": self.modelname,
            "messages": messages,
            "temperature": 0.1
        }

        return(self)
    
    def call(self):

        print('----calling llm: '+str(self.llm_input['model']))
        self.llm_response = requests.post(url = self.llm_server, 
                                          json = self.llm_input,   ### callLLM.llm_input_init(user_input)
                                          headers = self.llm_header).json()
        print('----llm response:\n', self.llm_response)

        return(self)


    def get_response_content(self):

        if self.llm_response['choices']:
            self.llmcontent = self.llm_response['choices'][0]['message']['content']
        else: 
            self.llmcontent = 'LLM Connection Failed'
        #print('---- postprocess the llm response:\n'+str(self.llmcontent))

        return(self.llmcontent)



if __name__ == '__main__':


    res = callLLM('qwen-72b-instruct').init_prompt('You are an early childhood educator. You need to answer children\'s questions.', 'Who are you?').call().get_response_content()
    print(type(res), len(res))




