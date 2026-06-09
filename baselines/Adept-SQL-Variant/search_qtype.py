
from user_input_process import user_input_init
from op_DB import callm3e
from op_DB import vecdb_op
from typing import Type
from types import SimpleNamespace

def search_qtype(full_processed_user_input:Type[user_input_init], assistant_id,skeleton_type):

    new_vec = callm3e().init_prompt(full_processed_user_input.trans).call() 
    not_exist_flag, qtype = vecdb_op(assistant_id).search_qtype_similarity(new_vec,0.7,skeleton_type)

    if not_exist_flag:
        return(True, 'The list of pre-stored complex SQL queries contains no similar issue; SQL will be generated autonomously.','')
    else:
        return(False, 'The similar issue has been found in the list of pre-stored complex SQL queries.', qtype)


if __name__ == "__main__":

    from user_input_process import user_input_init

    input = "In the Image Data Commons (IDC), which raw datasets have the largest number of samples? List the top five."
    full_processed_input=SimpleNamespace(trans=input)

    
    not_exist, info, qtype = search_qtype(full_processed_input,'149',"skeleton1")

    print(not_exist, info, qtype)
