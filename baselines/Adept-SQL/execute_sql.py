from op_DB import user_db_op

def execute_sql(sql):

    sql = sql.strip().replace('`', '')
    
    res = user_db_op().sql_execute(sql)
    print(res[0:5])
    if 'SQLerror' in res[0]:
        sql_exe_info = f'SQL syntax error! {res[0]["SQLerror"]}'
        res = []
    else:
        sql_exe_info = f'SQL executed successfully! {len(res)} row(s) returned.'

    return sql_exe_info, res


if __name__ == '__main__':
    db_id = 2
    sql = " SELECT      station_id,      name,      capacity FROM      new_york_citibike_citibike_stations WHERE      region_id = 5 ORDER BY      capacity DESC LIMIT 5; "
    sql_exe_info, res = execute_sql(sql)
    print(sql_exe_info)