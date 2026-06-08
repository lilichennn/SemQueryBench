import json.decoder
import requests
import openai
from utils.enums import LLM
import time

# Local Qwen model configuration
QWEN_CONFIG = {
    "url": "http://.../v1/chat/completions",
    "headers": {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer YOUR_KEY"
    }
}


def init_chatgpt(OPENAI_API_KEY, OPENAI_GROUP_ID, model):
    # Skip OpenAI API initialization for local Qwen model
    if model != LLM.QWEN_72B_INSTRUCT:
        openai.api_key = OPENAI_API_KEY
        openai.organization = OPENAI_GROUP_ID


def ask_completion(model, batch, temperature):
    response = openai.Completion.create(
        model=model,
        prompt=batch,
        temperature=temperature,
        max_tokens=200,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        stop=[";"]
    )
    response_clean = [_["text"] for _ in response["choices"]]
    return dict(
        response=response_clean,
        **response["usage"]
    )


def ask_chat(model, messages: list, temperature, n):
    if model == LLM.QWEN_72B_INSTRUCT:
        # Use local Qwen model
        data = {
            "model": "qwen-72b-instruct",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 400,  # Increased max tokens
            "n": n
        }
        print(f"Calling Qwen API with data: {json.dumps(data, indent=2)[:200]}...")
        try:
            response = requests.post(
                QWEN_CONFIG["url"],
                headers=QWEN_CONFIG["headers"],
                json=data,
                timeout=60  # Add 60 second timeout
            )
            print(f"Qwen API response received. Status code: {response.status_code}")
            response.raise_for_status()
            response_json = response.json()
            print(f"Qwen API response JSON: {json.dumps(response_json, indent=2)[:500]}...")
            response_clean = [choice["message"]["content"] for choice in response_json["choices"]]
            # Local model always returns a list, even when n=1
            # Get actual usage data from response
            usage = response_json.get("usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            })
        except requests.exceptions.RequestException as e:
            print(f"❌ Qwen API request failed: {e}")
            import traceback
            traceback.print_exc()
            # Return mock response for debugging
            return {
                "response": ["SELECT * FROM error_table WHERE error = 'API_TIMEOUT'"],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
    else:
        # Use OpenAI API
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=200,
            n=n
        )
        response_clean = [choice["message"]["content"] for choice in response["choices"]]
        if n == 1:
            response_clean = response_clean[0]
        usage = response["usage"]
    return dict(
        response=response_clean,
        **usage
    )


def ask_llm(model: str, batch: list, temperature: float, n:int):
    n_repeat = 0
    while True:
        try:
            if model in LLM.TASK_COMPLETIONS:
                # TODO: self-consistency in this mode
                assert n == 1
                response = ask_completion(model, batch, temperature)
            elif model in LLM.TASK_CHAT:
                # batch size must be 1
                assert len(batch) == 1, "batch must be 1 in this mode"
                messages = [{"role": "user", "content": batch[0]}]
                response = ask_chat(model, messages, temperature, n)
                # Handle response wrapping differently for different models
                if model == LLM.QWEN_72B_INSTRUCT:
                    # Qwen always returns list of responses in res['response']
                    # Each question gets 1 list of responses, so we need to wrap in another list for consistency
                    # because the main script expects res['response'] to be a list of (question responses lists)
                    response['response'] = [response['response']]
                else:
                    # For OpenAI models
                    if isinstance(response['response'], list):
                        # Already a list when n > 1
                        response['response'] = [response['response']]
                    else:
                        # Wrap single response in list when n == 1
                        response['response'] = [[response['response']]]
            break
        except openai.error.RateLimitError:
            n_repeat += 1
            print(f"Repeat for the {n_repeat} times for RateLimitError", end="\n")
            time.sleep(1)
            continue
        except json.decoder.JSONDecodeError:
            n_repeat += 1
            print(f"Repeat for the {n_repeat} times for JSONDecodeError", end="\n")
            time.sleep(1)
            continue
        except Exception as e:
            n_repeat += 1
            print(f"Repeat for the {n_repeat} times for exception: {e}", end="\n")
            time.sleep(1)
            continue

    return response

