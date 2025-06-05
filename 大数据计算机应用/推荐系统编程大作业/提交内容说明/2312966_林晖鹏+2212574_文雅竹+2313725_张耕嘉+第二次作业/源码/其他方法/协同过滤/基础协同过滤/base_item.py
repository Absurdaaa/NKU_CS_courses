import numpy as np
import pandas as pd

def pearson_similarity_items(matrix):
    """
    计算并返回物品之间的皮尔逊相关系数矩阵。
    :param matrix: 用户-物品评分矩阵 (numpy array)，行是用户，列是物品
    :return: 物品之间的相似度矩阵 (numpy array)
    """
    # 转置矩阵，使物品成为行
    item_matrix = matrix.T
    # 计算物品之间的相关系数
    corr_mat = np.corrcoef(item_matrix, rowvar=True)
    # 处理 NaN 值
    corr_mat = np.nan_to_num(corr_mat, nan=0.0)
    return corr_mat

def main():
    """
    基于物品的协同过滤实现。
    """
    from load_dataset import load_data_to_df, train_test_split, triples_to_matrix
    
    # 参数设置
    top_k = 20
    file_path = 'data/train.txt'
    dataset = load_data_to_df(file_path)
    train_set, test_set = train_test_split(dataset, test_size=0.2, random_state=42)

    # 转换为用户-物品评分矩阵
    train_mat = triples_to_matrix(pd.DataFrame(train_set))
    
    # 计算全局平均分和物品平均分
    global_mean = train_set['rating'].mean()
    user_means = train_set.groupby('user_id')['rating'].mean().to_dict()
    item_means = train_set.groupby('item_id')['rating'].mean().to_dict()

    # 创建映射
    user_id_to_index = {uid: idx for idx, uid in enumerate(train_set['user_id'].unique())}
    item_id_to_index = {iid: idx for idx, iid in enumerate(train_set['item_id'].unique())}
    index_to_item_id = {idx: iid for iid, idx in item_id_to_index.items()}
    
    test_set['user_index'] = test_set['user_id'].map(user_id_to_index)
    test_set['item_index'] = test_set['item_id'].map(item_id_to_index)
    
    predict_set = test_set.copy()

    # 计算物品相似度矩阵（只计算一次）
    item_similarity_matrix = pearson_similarity_items(train_mat)
    # 不需要在对角线上填充0，因为我们这次是物品与物品之间的比较

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
        
        # 获取与目标物品相似的物品
        similar_items = np.argsort(-item_similarity_matrix[item_idx])[:top_k]
        
        # 筛选出用户评过分的相似物品
        rated_similar_items = []
        for sim_item in similar_items:
            if train_mat[user_idx, sim_item] > 0:
                rated_similar_items.append(sim_item)
        
        # 如果用户没有对任何相似物品评分，使用基线预测
        if len(rated_similar_items) == 0:
            predict_set.loc[i, 'prediction'] = baseline_pred
            predict_set.loc[i, 'bias'] = baseline_pred
            continue
        
        # 计算加权评分
        numerator = 0.0
        denominator = 0.0
        
        for sim_item in rated_similar_items:
            # 获取相似度
            sim = item_similarity_matrix[item_idx, sim_item]
            if abs(sim) < 1e-6:  # 忽略接近零的相似度
                continue
                
            # 获取用户对相似物品的评分偏差
            sim_item_id = index_to_item_id[sim_item]
            sim_item_mean = item_means.get(sim_item_id, global_mean)
            rating_deviation = train_mat[user_idx, sim_item] - (user_mean + sim_item_mean - global_mean)
            
            numerator += sim * rating_deviation
            denominator += abs(sim)
        
        # 计算最终预测分数
        if denominator > 0:
            prediction = baseline_pred + (numerator / denominator)
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
    print(f"RMSE: {rmse:.4f}")

if __name__ == "__main__":
    main()