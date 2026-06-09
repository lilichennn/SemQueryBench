from pymilvus import MilvusClient,Collection,utility,CollectionSchema,FieldSchema,DataType,connections
from time import sleep

from config import *
from call_emb import callm3e


class vecdb_op:
    def __init__(self, assistant_id = '0'):
        

        self.client = MilvusClient(uri = f"http://{milvusdb.url}:{milvusdb.port}",
                            token = f"{milvusdb.user_name}:{milvusdb.password}",
                            db_name = milvusdb.database)
        print("INFO: Milvusdb connected.")

     
        collection = 'assistant'+str(assistant_id)
        milvusdb.collection = collection 

    def check_collection(self):

        res = self.client.list_collections()
        if milvusdb.collection not in res:
            print("INFO: Creating collection...")
            schema = MilvusClient.create_schema(enable_dynamic_field=False)
            schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
            schema.add_field(field_name='emb_qtype', datatype=DataType.FLOAT_VECTOR, dim=768)
            schema.add_field(field_name='qtype', datatype=DataType.VARCHAR, max_length=400)
            schema.add_field(field_name="question", datatype=DataType.VARCHAR, max_length=400)
            schema.add_field(field_name="sql", datatype=DataType.VARCHAR, max_length=2000)
            schema.add_field(field_name="skeleton_type", datatype=DataType.VARCHAR, max_length=2000)
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="emb_qtype", 
                index_type="IVF_FLAT",
                metric_type="L2",
                params = {"nlist":2048}
            )
            self.client.create_collection(
                collection_name = milvusdb.collection,
                schema=schema,
                index_params=index_params
            )
            return("Collection created.")
        else:
            return("Collection already existed.")


    def search_qtype_similarity(self,new_vec,distanct,skeleton_type=None):


        if not skeleton_type:
            equ = None  
        else:
            equ = f"skeleton_type == '{skeleton_type}'"
        result = self.client.search(
            collection_name=milvusdb.collection,
            data=[new_vec],
            search_params={"metric_type": "L2", "params": {"nprobe": 10}},  
            limit=1,
            filter=equ,  
            output_fields=["qtype", "question"]
        )
        try:
            dist = round(float(result[0][0]['distance']),2)
            qtype =  result[0][0]['entity']['qtype']
            self.question=result[0][0]['entity']['question']
            print(f'The most similar question is:[{dist}]{qtype}')
        except :
            dist = 1.0

        if dist < distanct:
            return(False, qtype)
        else:
            return(True,'NO similar question')

    def insert_sqlQA(self,data):
        
        new_vec = callm3e().init_prompt(data['qtype']).call()
        flag, oldqtype = self.search_qtype_similarity(new_vec,0)
        #flag = True
        if flag:
            data['emb_qtype'] = new_vec
            try:
                insert_res = self.client.insert(
                    collection_name=milvusdb.collection,
                    data = data)
                sleep(2)
                return('INFO: Insert successed.'+str(insert_res))
            except Exception as e:
                return('ERROR: Insert failed.'+str(e))
        else:
            return('ERROR: Similar Question already exists: '+ oldqtype)

    def modify_sqlQA(self, data):

        res = self.client.delete(
            collection_name=milvusdb.collection,
            filter=f'qtype in ["{data["qtype"]}"]'
        )
        print(res)
        sleep(2)
        res = self.insert_sqlQA(data)
        return(res)
    
    def list_sqlQA(self, data):
        page_size = data['size']
        current_page = data['page']
        offset = (current_page - 1) * page_size

        exprstr = "qtype != ''"
        if('qtype' in data and data['qtype'] != ''):
            exprstr = f"qtype == '{data['qtype']}'"  
            
        print(exprstr)
        try:
            results = self.client.query(collection_name=milvusdb.collection, filter=exprstr ,offset=offset, limit=10,output_fields=["id", "qtype", "question1", "sql1", "question2", "sql2"])
        except Exception as e:
            if " collection not found" in str(e):
                results = []
            else:
                raise e
        return (results)


    def retrive_sqlQA(self, qtype):
        result = self.client.search( collection_name=milvusdb.collection,
                                    data=[ [0.0] * 768], 
                                    search_params={"metric_type":"L2", "params":{"nprobe":10}}, 
                                    limit = 1,
                                    output_fields=["qtype","question","sql"],
                                    filter=f'qtype in ["{qtype}"]')
        return (result[0][0]['entity'])
    
    def delete_sqlQA(self, qtype):
        res = self.client.delete(
            collection_name=milvusdb.collection,
            filter=f'qtype in ["{qtype}"]'
        )
        sleep(2)
        return(res) #{'delete_count': 1}
    def del_collect(self):# 删除现有的collection
        try:
            if self.client.has_collection(milvusdb.collection):
                self.client.drop_collection(milvusdb.collection)
                print(f"INFO: Collection '{milvusdb.collection}' dropped successfully.")
            else:
                print(f"INFO: Collection '{milvusdb.collection}' does not exist, no need to delete.")
        except Exception as e:
            print(f"ERROR: Failed to drop collection '{milvusdb.collection}': {e}")


if __name__ == '__main__':
    
    res = vecdb_op(assistant_id = '148').del_collect()