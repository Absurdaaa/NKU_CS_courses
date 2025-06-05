
import numpy as np
import pandas as pd

def load_data_to_df(file_path):
    """
    将数据文件加载为pandas DataFrame
    """
    user_item_pairs = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
    i = 0
    while i < len(lines):
        # 处理用户头部行
        if '|' in lines[i]:
            parts = lines[i].strip().split('|')
            user_id = int(parts[0])
            item_count = int(parts[1])
            
            # 处理该用户的评分
            for j in range(1, item_count + 1):
                if i + j < len(lines):
                    item_parts = lines[i + j].strip().split()
                    if len(item_parts) == 2:
                        item_id = int(item_parts[0])
                        rating = int(item_parts[1])
                        user_item_pairs.append((user_id, item_id, rating))
            
            # 跳到下一个用户
            i += item_count + 1
        else:
            i += 1
    
    # 从收集的数据创建DataFrame
    df = pd.DataFrame(user_item_pairs, columns=['user_id', 'item_id', 'rating'])
    return df

def train_test_split(df, test_size=0.2, random_state=42):
    """
    将数据集分割为训练集和测试集
    """
    # 设置随机种子
    np.random.seed(random_state)
    
    # 随机打乱数据
    shuffled_indices = np.random.permutation(len(df))
    test_set_size = int(len(df) * test_size)
    test_indices = shuffled_indices[:test_set_size]
    train_indices = shuffled_indices[test_set_size:]
    
    # 分割为训练集和测试集
    train_df = df.iloc[train_indices].reset_index(drop=True)
    test_df = df.iloc[test_indices].reset_index(drop=True)
    
    return train_df, test_df
    
def triples_to_matrix(triples):
    """
    将三元组 (user_id, item_id, rating) 转换为用户-物品评分矩阵
    :param triples: 包含三元组的 DataFrame，列为 ['user_id', 'item_id', 'rating']
    :return: 用户-物品评分矩阵 (numpy array)
    """
    # 使用 pivot 将三元组转换为矩阵
    rating_matrix = triples.pivot(index='user_id', columns='item_id', values='rating').fillna(0)
    return rating_matrix.values  # 转换为 numpy array

    