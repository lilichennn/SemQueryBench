import argparse
import json
from datetime import datetime
from typing import Any, Dict, List
import argparse
import os
from runner.run_manager import RunManager

def load_dataset(data_path: str) -> List[Dict[str, Any]]:
    """
    Loads the dataset from the specified path.

    Args:
        data_path (str): Path to the data file.

    Returns:
        List[Dict[str, Any]]: The loaded dataset.
    """
    with open(data_path, 'r', encoding='utf-8') as file:
        dataset = json.load(file)
    return dataset

def main(args):
    """
    Main function to run the pipeline with the specified configuration.
    """

    db_json=os.path.join(args.db_root_path,'data_preprocess',f'{args.data_mode}.json')
    

    dataset = load_dataset(db_json)

    run_manager = RunManager(args)
    run_manager.initialize_tasks(args.start,args.end,dataset)
    run_manager.run_tasks()
    run_manager.generate_sql_files()

if __name__ == '__main__':

    # 设定目标工作目录
    target_dir = r'.\OpenSerch-SQL'
    try:
        os.chdir(target_dir)
        print(f"working dire: {os.getcwd()}")
    except FileNotFoundError:
        print(f"dire doesnot exist - {target_dir}")
    
    # ... 下面是你原来的 argparse 代码
    # 👇TODO 
    LLM_NAME =  "gpt-5.4"
    BERT_MODEL = r"YOUR BERT MODEL PATH"
    # 👆TODO
    pipeline_setup={
    "generate_db_schema": {
        "engine":LLM_NAME,
        "bert_model": BERT_MODEL,  
        "device":"cuda"
    },
    "extract_col_value": {
        "engine":LLM_NAME,
        "temperature":0.0
    },
    "extract_query_noun": {
        "engine":LLM_NAME,
        "temperature":0.0
    },
    "column_retrieve_and_other_info": {
        "engine":LLM_NAME,
        "bert_model": BERT_MODEL,  
        "device":"cuda",
        "temperature":0.3,
        "top_k":10
    },
    "candidate_generate":{
        "engine":LLM_NAME,
        "temperature": 0.7,  
        "n":5,
        "return_question":"True",
        "single":"False"
    },
    "align_correct":{
        "engine":LLM_NAME,
        "n":5,
        "bert_model": BERT_MODEL,  
        "device":"cuda",
        "align_methods":"style_align+function_align+agent_align"
    }
}
    
    args_parser = argparse.ArgumentParser()

    # 👇TODO
    args_parser.add_argument('--db_root_path', type=str, default='Bird/easy'
                             , help="Path to the data file.")
    args_parser.add_argument('--start', type=int, default=0
                             , help="Start point")
    args_parser.add_argument('--end', type=int, default=1
                             , help="End point")
    # 👆TODO

    args_parser.add_argument('--data_mode', type=str, default='dev'
                            , help="Mode of the data to be processed.")
    args_parser.add_argument('--pipeline_nodes', type=str, default='generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation'
                             , help="Pipeline nodes configuration.")
    args_parser.add_argument('--pipeline_setup', type=str, default=json.dumps(pipeline_setup)
                             , help="Pipeline setup in JSON format.")
    args_parser.add_argument('--use_checkpoint', action='store_true'
                             , help="Flag to use checkpointing.")
    args_parser.add_argument('--checkpoint_nodes', type=str, required=False
                             , help="Checkpoint nodes configuration.")
    args_parser.add_argument('--checkpoint_dir', type=str, required=False
                             , help="Directory for checkpoints.")
    args_parser.add_argument('--log_level', type=str, default='warning'
                             , help="Logging level.")
    args = args_parser.parse_args()
    args.run_start_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    if args.use_checkpoint:
        print('Using checkpoint')
        if not args.checkpoint_nodes:
            raise ValueError('Please provide the checkpoint nodes to use checkpoint')
        if not args.checkpoint_dir:
            raise ValueError('Please provide the checkpoint path to use checkpoint')
    
    main(args)
