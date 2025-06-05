# /Users/linshangjin/NKU_CS_courses/大数据计算机应用/推荐系统编程大作业/read_data.py
import pandas as pd
import numpy as np

# 上传数据集
def load_data_to_matrix(file_path):
    # Initialize containers
    user_item_pairs = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
    i = 0
    while i < len(lines):
        # Process user header line
        if '|' in lines[i]:
            parts = lines[i].strip().split('|')
            user_id = int(parts[0])
            item_count = int(parts[1])
            
            # Process this user's ratings
            for j in range(1, item_count + 1):
                if i + j < len(lines):
                    item_parts = lines[i + j].strip().split()
                    if len(item_parts) == 2:
                        item_id = int(item_parts[0])
                        rating = int(item_parts[1])
                        user_item_pairs.append((user_id, item_id, rating))
            
            # Skip to the next user
            i += item_count + 1
        else:
            i += 1
    
    # Create DataFrame from collected data
    df = pd.DataFrame(user_item_pairs, columns=['user_id', 'item_id', 'rating'])
    
    # Extract unique user IDs and item IDs
    unique_users = sorted(df['user_id'].unique())
    unique_items = sorted(df['item_id'].unique())
    
    # Create a mapping from ID to matrix index
    user_to_index = {user: idx for idx, user in enumerate(unique_users)}
    item_to_index = {item: idx for idx, item in enumerate(unique_items)}
    
    # Initialize matrix with zeros
    user_item_matrix = np.zeros((len(unique_users), len(unique_items)))
    
    # Fill in the matrix with ratings
    for _, row in df.iterrows():
        user_idx = user_to_index[row['user_id']]
        item_idx = item_to_index[row['item_id']]
        user_item_matrix[user_idx, item_idx] = row['rating']
    
    return user_item_matrix, unique_users, unique_items

# 打印数据集信息
def Print_dataset(matrix,users,items):
    print(f"Matrix shape: {matrix.shape}")
    print(f"Number of users: {len(users)}")
    print(f"Number of items: {len(items)}")
    print(f"Matrix sample:\n{matrix[:5, :5]}")  # Print first 5x5 elements
    
    # 打印评分的最大值和最小值
    print(f"全部数据 - 最大值: {matrix.max()}")
    print(f"全部数据 - 最小值: {matrix.min()}")
    # 只考虑非零评分
    nonzero_ratings = matrix[matrix > 0]
    if len(nonzero_ratings) > 0:
        print(f"非零评分 - 最大值: {nonzero_ratings.max()}")
        print(f"非零评分 - 最小值: {nonzero_ratings.min()}")
        print(f"非零评分 - 平均值: {nonzero_ratings.mean():.2f}")
        print(f"评分数量: {len(nonzero_ratings)}")
        print(f"评分稀疏度: {len(nonzero_ratings) / (matrix.shape[0] * matrix.shape[1]):.4f}")
    return
# Example usage
if __name__ == "__main__":
    matrix, users, items = load_data_to_matrix("data/train.txt")
    Print_dataset(matrix,users,items)
    
        
    