def convert_rating_file_format(input_file, output_file):
    """
    将预测结果文件从制表符分隔格式转换为指定的分组格式
    
    Parameters:
    -----------
    input_file: 输入文件路径（当前格式）
    output_file: 输出文件路径（目标格式）
    """
    # 读取输入文件
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    # 跳过标题行
    if 'user_id' in lines[0]:
        lines = lines[1:]
    
    # 按用户ID分组评分
    user_ratings = {}
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 3:  # 确保行有足够的部分
            user_id = parts[0]
            item_id = parts[1]
            # 将评分四舍五入为整数
            rating = float(parts[2])
            
            if user_id not in user_ratings:
                user_ratings[user_id] = []
            user_ratings[user_id].append((item_id, rating))
    
    # 写入输出文件
    with open(output_file, 'w') as f:
        for user_id, ratings in user_ratings.items():
            # 写入用户ID和评分项数
            f.write(f"{user_id}|{len(ratings)}\n")
            
            # 写入每个物品的评分
            for item_id, rating in ratings:
                f.write(f"{item_id}  {rating}  \n")
                
convert_rating_file_format('ResultsFrom0.txt','ResultsFrom.txt')