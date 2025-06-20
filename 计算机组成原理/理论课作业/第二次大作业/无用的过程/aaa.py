import csv

def extract_column_set(csv_path):
    col_set = set()
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # 跳过表头
        for row in reader:
            if len(row) >= 3:
                col_set.add(row[0].strip())  # 第一列
                col_set.add(row[2].strip())  # 第三列
    return col_set

# 调用
result_set = extract_column_set('clean_triples_2.csv')

# 打印结果
print(f"共提取实体 {len(result_set)} 个：")
for item in sorted(result_set):
    print(item)
    
    
Abort Behavior Control Controls values Example Level Location One Read