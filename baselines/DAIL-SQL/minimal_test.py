import requests
import json

# Local Qwen model configuration
QWEN_CONFIG = {
    "url": "API URL",  # 替换为你的API URL
    "headers": {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer API KEY"
    }
}

def extract_sql_from_response(response):
    """从模型响应中提取纯SQL查询，更健壮的实现"""
    # 1. 清理响应内容
    response = response.strip()
    sql = ""
    
    # 2. 处理各种格式的响应
    try:
        # 处理Markdown代码块 (```sql SELECT ...; ```)
        if "```sql" in response:
            sql = response.split("```sql")[1].split("```")[0].strip()
        elif "```" in response:
            # 处理普通代码块 (``` SELECT ...; ```)
            sql = response.split("```")[1].split("```")[0].strip()
        else:
            # 3. 直接从文本中提取SQL
            # 查找所有SELECT开头的行
            lines = response.split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()
                # 不区分大小写查找SELECT
                if stripped.upper().startswith("SELECT"):
                    # 从这一行开始提取，直到遇到分号或文件结束
                    sql_lines = [stripped]
                    for next_line in lines[i+1:]:
                        next_stripped = next_line.strip()
                        sql_lines.append(next_stripped)
                        if next_stripped.endswith(");"):
                            break
                    sql = " ".join(sql_lines)
                    break
                
                # 4. 如果没有找到完整SQL，尝试其他方法
                if not sql:
                    # 检查整个响应是否包含SELECT
                    if "SELECT" in response.upper():
                        # 提取从第一个SELECT到第一个分号的内容
                        select_pos = response.upper().find("SELECT")
                        if select_pos >= 0:
                            # 提取从SELECT开始的部分
                            sql_part = response[select_pos:]
                            # 找到第一个分号
                            semicolon_pos = sql_part.find(");")
                            if semicolon_pos >= 0:
                                sql = sql_part[:semicolon_pos + 1]
                            else:
                                # 如果没有分号，使用整个部分
                                sql = sql_part
    except Exception as e:
        print(f"Error extracting SQL: {e}")
        sql = ""
    
    return sql

def test_qwen_sql_generation():
    print("=== Minimal Qwen SQL Generation Test ===")
    
    # Load a single question from the questions.json file
    with open('dataset/process/BIRD-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-200_ANS-4096/questions.json', 'r') as f:
        data = json.load(f)
    
    question = data['questions'][0]['prompt']
    print(f"\nQuestion: {question[:200]}...")
    
    # Call Qwen API directly
    try:
        data = {
            "model": "qwen-72b-instruct",
            "messages": [{"role": "user", "content": question}],
            "temperature": 0.7,
            "max_tokens": 200,
            "n": 1
        }
        
        print("\nCalling Qwen API...")
        response = requests.post(
            QWEN_CONFIG["url"],
            headers=QWEN_CONFIG["headers"],
            json=data,
            timeout=30
        )
        
        response.raise_for_status()
        response_json = response.json()
        print(f"API Response Status: {response.status_code}")
        print(f"API Response: {json.dumps(response_json, indent=2)}")
        
        # Extract the content from the response
        if "choices" in response_json and len(response_json["choices"]) > 0:
            content = response_json["choices"][0]["message"]["content"]
            print(f"\nModel Response: {content}")
            
            # Extract SQL from the response
            print("\nExtracting SQL...")
            sql = extract_sql_from_response(content)
            print(f"Extracted SQL: {sql}")
            
            # Write to results file
            with open('test_result.txt', 'w') as f:
                f.write(sql + "\n")
            print("\n✅ SQL written to test_result.txt")
        else:
            print("❌ No choices in API response")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_qwen_sql_generation()
