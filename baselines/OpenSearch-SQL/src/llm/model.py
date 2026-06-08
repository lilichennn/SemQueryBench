import requests, time
#import dashscope
import torch
import json
import re
from runner.logger import Logger
from llm.prompts import prompts_fewshot_parse


def model_chose(step,model="qwen-72b-instruct"):
    # if model.startswith("gpt") or model.startswith("qwen-72b-instruct") or model.startswith("gemini"):
    #     return gpt_req(step,model)

    # if model.startswith("sft"):
    #     return sft_req()
    
    return gpt_req(step,model)

class req:

    def __init__(self,model, step=None) -> None:
        self.Cost = 0
        self.model=model
        self.step=step

    def log_record(self,prompt_text,output):
        logger=Logger()
        logger.log_conversation(prompt_text, "Human", self.step)
        logger.log_conversation(output, "AI", self.step)

    def fewshot_parse(self, question, evidence, sql):
        s = prompts_fewshot_parse().parse_fewshot.format(question=question,sql=sql)
        ext = self.get_ans(s)
        ext=ext.replace('```','').strip()
        ext = ext.split("#SQL:")[0]# 防止没按格式生成 至少保留SQL
        ans = self.convert_table(ext, sql)
        return ans
    def convert_table(self, s, sql):
        l = re.findall(' ([^ ]*) +AS +([^ ]*)', sql)
        x, v = s.split("#values:")
        t, s = x.split("#SELECT:")
        for li in l:
            s = s.replace(f"{li[1]}.", f"{li[0]}.")
        return t + "#SELECT:" + s + "#values:" + v

class gpt_req(req):

    def __init__(self, step,model="qwen-72b-instruct") -> None:
        super().__init__(model,step)

        if model == "MODEL NAME":
            self.api_url = "YOUR API URL"
            self.api_key = "YOUR API KEY"

        else:
            raise ValueError(f"Unsupported model: {model}")
        self.model = model

    def get_ans(self, messages, temperature=0.0, top_p=None,n=1,single=True,**k):
        last_error = None
        res = None
        if self.model == 'deepseek-r1':
            n =1
        else:
            n = max(1, min(4, n))   

        for count in range(1, 6):
            try:
                res = request(
                    url=self.api_url,
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    n=n,
                    key=self.api_key,
                    **k
                )

                # 明确处理模型服务返回的错误
                if isinstance(res, dict) and "error" in res:
                    error_msg = res.get("error", "")
                    error_type = res.get("error_type", "")

                    # 超长问题重试没意义，直接抛出
                    if "maximum input ids length" in error_msg or "maxPositionEmbeddings" in error_msg:
                        raise RuntimeError(f"Prompt too long: {res}")

                    raise RuntimeError(f"LLM API error: {res}")

                if not isinstance(res, dict) or "choices" not in res:
                    raise RuntimeError(f"Invalid LLM response: {res}")

                if n == 1 and single:
                    response_clean = res["choices"][0]["message"]["content"]
                else:
                    response_clean = res["choices"]

                if self.step != "prepare_train_queries":
                    self.log_record(messages, response_clean)

                if "usage" in res:
                    self.Cost += (
                        res["usage"].get("prompt_tokens", 0) / 1000 * 0.042
                        + res["usage"].get("completion_tokens", 0) / 1000 * 0.126
                    )

                return response_clean

            except Exception as e:
                last_error = e

                print(f"[LLM request failed] attempt={count}, error={e}")
                print(f"[LLM raw response] {res}")

                # prompt 超长，重试没有意义
                if "Prompt too long" in str(e) or "maxPositionEmbeddings" in str(e):
                    raise

                time.sleep(2)

        raise RuntimeError(f"LLM request failed after 5 attempts. Last error: {last_error}")
    


class qwen72b(req):

    def __init__(self,model) -> None:
        super().__init__(model)
    def get_ans(self, messages, temperature=0.0, debug=True):
        count = 0

        while count < 8:
            try:
                url = "API URL"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization":
                    "Bearer API KEY"
                }

                # 定义请求体
                jsons = {
                    "model":self.model,
                    "temperture":
                    temperature,
                    "top_p":
                    0.9,
                    "messages": [{
                        "role": "system",
                        "content": "You are a helpful assistant."
                    }, {
                        "role": "user",
                        "content": messages
                    }]
                }

                # 发送POST请求
                response = requests.post(url, headers=headers, json=jsons)
                if debug:
                    print(response.json)
                ans = response.json()['choices'][0]['message']['content']
                break
            except Exception as e:
                count += 1
                time.sleep(2)
                # 先检查 response 变量是否定义
                if 'response' in locals():
                    print(e, count, self.Cost, response.json())
                else:
                    print(e, count, self.Cost, "Response not available")       
        return ans

# class sft_req(req):

#     def __init__(self,model) -> None:
#         super().__init__(model)
#         self.device = "cuda:0"
#         self.tokenizer = AutoTokenizer.from_pretrained(
#             "",
#             trust_remote_code=True,
#             padding_side="right",
#             use_fast=True)
#         self.tokenizer.pad_token = self.tokenizer.eos_token = "<|EOT|>"
#         # drop device_map if running on CPU
#         self.model = AutoModelForCausalLM.from_pretrained(
#             "",
#             torch_dtype=torch.bfloat16,
#             device_map=self.device).eval()

#     def get_ans(self, text, temperature=0.0):
#         messages = [{
#             "role":
#             "system",
#             "content":
#             "You are an AI programming assistant, utilizing the DeepSeek Coder model, developed by DeepSeek Company, and you only answer questions related to computer science. For politically sensitive questions, security and privacy issues, and other non-computer science questions, you will refuse to answer."
#         }, {
#             "role": "user",
#             "content": text
#         }]
#         inputs = self.tokenizer.apply_chat_template(messages,
#                                                     add_generation_prompt=True,
#                                                     tokenize=False)
#         model_inputs = self.tokenizer([inputs],
#                                       return_tensors="pt",
#                                       max_length=8000).to("cuda")
#         # tokenizer.eos_token_id is the id of <|EOT|> token
#         generated_ids = self.model.generate(
#             model_inputs.input_ids,
#             attention_mask=model_inputs["attention_mask"],
#             max_new_tokens=800,
#             do_sample=False,
#             eos_token_id=self.tokenizer.eos_token_id,
#             pad_token_id=self.tokenizer.pad_token_id)
#         generated_ids = [
#             output_ids[len(input_ids):] for input_ids, output_ids in zip(
#                 model_inputs.input_ids, generated_ids)
#         ]

#         response = self.tokenizer.decode(generated_ids[0][:-1],
#                                          skip_special_tokens=True).strip()
#         return response


def request(url,model,messages,temperature,top_p,n,key,**k):
    res = requests.post(
                url=
                url,
                json={
                    "model":
                    model,
                    "messages": [{
                        "role": "system",
                        "content":
                        "You are an SQL expert, skilled in handling various SQL-related issues."
                    }, {
                        "role": "user",
                        "content": messages
                    }],
                    "max_tokens":
                    800,
                    "temperature":
                    temperature,
                    "top_p":top_p,
                    "n":n,
                    **k
                },
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                }).json()

    return res


