import numpy as np
import pandas as pd

def cosine_similarity(matrix):
    """
    计算并返回用户之间的余弦相似度矩阵。
    :param matrix: 用户-物品评分矩阵 (numpy array)，行是用户, 列是物品
    :return: 用户之间的相似度矩阵 (numpy array)
    """
    # 计算用户向量的范数并归一化
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    normalized_matrix = matrix / (norms + 1e-9)
    # 点积得到相似度矩阵
    similarity = np.dot(normalized_matrix, normalized_matrix.T)
    return similarity
    
def pearson_similarity(matrix):
    """
    计算并返回用户之间的皮尔逊相关系数矩阵。
    :param matrix: 用户-物品评分矩阵 (numpy array)，行是用户, 列是物品
    :return: 用户之间的相似度矩阵 (numpy array)
    """
    # 直接使用 np.corrcoef 计算行与行（即用户与用户）之间的皮尔逊相关系数
    # rowvar=True 时，每行表示一个变量，下方的 matrix 每行是用户
    corr_mat = np.corrcoef(matrix, rowvar=True)
    return corr_mat

def main():
    """
    对示例数据使用皮尔逊相关系数进行协同过滤。
    """
    from load_dataset import load_data_to_df, train_test_split, triples_to_matrix
    
    # 参数
    top_k = 20
    file_path = 'data/train.txt'
    dataset = load_data_to_df(file_path)
    train_set, test_set = train_test_split(dataset, test_size=0.2, random_state=42)

    # 转换为用户-物品评分矩阵
    train_mat = triples_to_matrix(pd.DataFrame(train_set))
    global_mean = train_set['rating'].mean()
    user_means = train_set.groupby('user_id')['rating'].mean().to_dict()
    item_means = train_set.groupby('item_id')['rating'].mean().to_dict()

    # 创建映射
    user_id_to_index = {uid: idx for idx, uid in enumerate(train_set['user_id'].unique())}
    item_id_to_index = {iid: idx for idx, iid in enumerate(train_set['item_id'].unique())}
    index_to_user_id = {idx: uid for uid, idx in user_id_to_index.items()}
    
    test_set['user_index'] = test_set['user_id'].map(user_id_to_index)
    test_set['item_index'] = test_set['item_id'].map(item_id_to_index)
    
    predict_set = test_set.copy()

    # 计算用户相似度矩阵（只计算一次）
    user_similarity_matrix = pearson_similarity(train_mat)
    np.fill_diagonal(user_similarity_matrix, 0)  # 去掉自身相似度

    for i, row in test_set.iterrows():
        user_id = row['user_id']
        item_id = row['item_id']
        user_idx = row['user_index']
        item_idx = row['item_index']
        
        # 计算基线预测（用户平均 + 物品偏差）
        user_mean = user_means.get(user_id, global_mean)
        item_bias = item_means.get(item_id, global_mean) - global_mean
        baseline_pred = user_mean + item_bias
        
        # 如果用户或物品不在训练集中，直接使用基线预测
        if pd.isna(user_idx) or pd.isna(item_idx):
            predict_set.loc[i, 'prediction'] = baseline_pred
            predict_set.loc[i, 'bias'] = baseline_pred
            continue
        
        user_idx, item_idx = int(user_idx), int(item_idx)
        
        # 获取相似用户及其评分
        similar_users = np.argsort(-user_similarity_matrix[user_idx])[:top_k]
        
        # 筛选出对当前物品有评分的相似用户
        rated_similar_users = []
        for sim_user in similar_users:
            if train_mat[sim_user, item_idx] > 0:
                rated_similar_users.append(sim_user)
        
        # 如果没有相似用户对该物品评分，使用基线预测
        if len(rated_similar_users) == 0:
            predict_set.loc[i, 'prediction'] = baseline_pred
            predict_set.loc[i, 'bias'] = baseline_pred
            continue
        
        # 计算加权评分
        numerator = 0.0
        denominator = 0.0
        
        for sim_user in rated_similar_users:
            # 获取相似度
            sim = user_similarity_matrix[user_idx, sim_user]
            if abs(sim) < 1e-6:  # 忽略接近零的相似度
                continue
                
            # 获取相似用户对该物品的评分偏差
            sim_user_id = index_to_user_id[sim_user]
            sim_user_mean = user_means.get(sim_user_id, global_mean)
            rating_deviation = train_mat[sim_user, item_idx] - sim_user_mean
            
            numerator += sim * rating_deviation
            denominator += abs(sim)
        
        # 计算最终预测分数
        if denominator > 0:
            prediction = user_mean + (numerator / denominator)
            prediction = max(0, min(100, prediction))  # 确保预测值在合理范围内
            predict_set.loc[i, 'prediction'] = prediction
        else:
            predict_set.loc[i, 'prediction'] = baseline_pred
            
        predict_set.loc[i, 'bias'] = baseline_pred
    
    # 计算并输出RMSE
    rmse = np.sqrt(np.mean((predict_set['rating'] - predict_set['prediction']) ** 2))
    mse = rmse ** 2
    mae = np.mean(np.abs(predict_set['rating'] - predict_set['prediction']))
    print(f"均方误差 (MSE): {mse:.4f}")
    print(f"均方根误差 (RMSE): {rmse:.4f}")
    print(f"平均绝对误差 (MAE): {mae:.4f}")
    print(predict_set[['user_id', 'item_id', 'rating', 'prediction', 'bias']].head())
    # print(f"RMSE: {rmse:.4f}")

if __name__ == "__main__":
    main()