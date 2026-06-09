import re
from datetime import datetime
from op_DB import backend_db_op

class user_input_init():
    def __init__(self,input):
        self.input = input
        self.trans = input
        self.hints = []

        self.time_replace = False
        self.term_replace = False

    def time_recognition(self):

        today = [int(i) for i in datetime.now().date().strftime('%Y-%m-%d').split('-')] #[2024, 11, 21]

        dd_patterns = [
            r'(\d{2,4}-\d{1,2}-\d{1,2})',  # YYYY-MM-DD
            r'(\d{2,4}/(\d{1,2})/\d{1,2})',  # YYYY/MM/DD
            r'(\d{2,4}\\\d{1,2}\\\d{1,2})',  # YYYY\MM\DD
            r'(\d{2,4}\.\d{1,2}\.\d{1,2})',  # YYYY.MM.DD
            r'(\d{2,4}年\d{1,2}月\d{1,2}日)' # YYYY年MM月DD日

        ]
        combined_dd_pattern = '|'.join(pattern for pattern in dd_patterns)

        mm_patterns = [
            r'(\d{2,4}-\d{1,2})',  # YYYY-MM
            r'(\d{2,4}/\d{1,2})',  # YYYY/MM
            r'(\d{2,4}\\\d{1,2})',  # YYYY\MM
            r'(\d{2,4}\.\d{1,2})',  # YYYY.MM
            r'(\d{2,4}年\d{1,2}月)'  # YYYY年MM月
        ]
        combined_mm_pattern = '|'.join(pattern for pattern in mm_patterns)

        #先找日期
        dd_dates = []
        matches = re.findall(combined_dd_pattern, self.input)
        for match in matches:
            match = list([x.strip() for x in match if x.strip()!=''])[0]
            dd_dates.append(match)
        
        for dd in dd_dates:
            self.trans = self.trans.replace(dd, '某日期')

        #再找月份
        mm_dates = []
        matches = re.findall(combined_mm_pattern, self.trans)
        for match in matches:
            match = list([x.strip() for x in match if x.strip() != ''])[0]
            mm_dates.append(match)

        for mm in mm_dates:
            self.trans = self.trans.replace(mm, '某月份')
        print('替换日期：', self.trans)

        self.time_replace = True
        return self

    def term_recognition(self):
        term_df = backend_db_op().query_table('term_list')
        field_df = backend_db_op().query_table('field_info')

        for term in term_df['term']:
            if term in self.trans:
                term_type = term_df[term_df['term'] == term]['type'].values[0]
                matched_fields = field_df[field_df['field_name'] == term_type]
                if len(matched_fields) > 0:
                    field_des = matched_fields['field_description'].values[0]
                    self.hints.append([term, term_type, field_des])
                    self.trans = self.trans.replace(term, "某"+field_des)
                else:
                    # 如果没有找到字段描述，使用 term_type 作为默认值
                    self.hints.append([term, term_type, term_type])
                    self.trans = self.trans.replace(term, "某"+term_type)
                    print(f'警告：未找到字段 {term_type} 的描述信息')

        print('替换名词：',self.trans)

        self.term_replace = True
        return self
    
    def gen_hints(self):
        if self.term_replace == False:
            self.term_recognition()
        hint_str = '问题中的关键词有：'
        for item in self.hints:
            hint_str += f"{item[0]},对应数据中的{item[1]}字段,字段含义是{item[2]};"
        return(hint_str)
    
    def full_process(self):
        return self.term_recognition().time_recognition()

if __name__ == '__main__':
    input = user_input_init("你好，今天几号")
    input.full_process()
    hints = input.gen_hints()

    print(input.hints)