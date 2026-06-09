from call_llm import callLLM


def generate_sql(prompt, llm):

    res = callLLM(llm).init_prompt('You are the most experienced SQL expert in the company.',prompt).call().get_response_content()
    res = res.strip().removeprefix('```sql').removesuffix('```')
    return res


if __name__ == "__main__":

    pass