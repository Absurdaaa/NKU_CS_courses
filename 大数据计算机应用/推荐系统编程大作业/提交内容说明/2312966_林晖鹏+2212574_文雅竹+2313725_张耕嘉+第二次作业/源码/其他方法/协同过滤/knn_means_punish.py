from pickle import FALSE
import numpy as np
import pandas as pd
import os
import time
from sklearn.metrics import mean_squared_error
from math import sqrt
import sys
import io
import itertools
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
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

class KNNRecommender:
    """
    基于KNN的推荐系统，支持基于用户和基于物品的协同过滤
    """
    def __init__(self, k=50, method='item', similarity='pearson_baseline', alpha=0.5):
        """
        初始化KNN推荐器
        
        Parameters:
        -----------
        k : 邻居数量
        method : 协同过滤方法，'user'表示基于用户，'item'表示基于物品
        similarity : 相似度计算方法，支持'cosine'和'pearson','pearson_baseline'
        alpha : 活跃用户惩罚系数
        """
        self.k = k
        self.method = method
        self.similarity = similarity
        self.alpha = alpha
        self.user_item_matrix = None
        self.similarity_matrix = None
        self.user_means = None
        self.item_means = None
        self.unique_users = None
        self.unique_items = None
        self.user_to_index = None
        self.item_to_index = None
        self.index_to_user = None
        self.index_to_item = None
        self.user_rating_counts = None
        
    def fit(self, ratings_df):
        """训练KNN模型"""
        print(f"训练KNN模型 (方法: {self.method}, 相似度: {self.similarity}, k: {self.k}, alpha: {self.alpha})...")
        start_time = time.time()
        
        # 提取唯一的用户ID和物品ID
        self.unique_users = sorted(ratings_df['user_id'].unique())
        self.unique_items = sorted(ratings_df['item_id'].unique())
        
        # 创建ID到索引的映射
        self.user_to_index = {user: idx for idx, user in enumerate(self.unique_users)}
        self.item_to_index = {item: idx for idx, item in enumerate(self.unique_items)}
        self.index_to_user = {idx: user for user, idx in self.user_to_index.items()}
        self.index_to_item = {idx: item for item, idx in self.item_to_index.items()}
        
        # 初始化用户-物品评分矩阵
        self.user_item_matrix = np.zeros((len(self.unique_users), len(self.unique_items)))
        
        # 填充评分矩阵
        for _, row in ratings_df.iterrows():
            user_idx = self.user_to_index[row['user_id']]
            item_idx = self.item_to_index[row['item_id']]
            self.user_item_matrix[user_idx, item_idx] = row['rating']
        
        # 计算用户和物品的平均评分
        mask = self.user_item_matrix > 0
        self.user_means = np.sum(self.user_item_matrix, axis=1) / np.sum(mask, axis=1)
        self.user_means = np.nan_to_num(self.user_means)
        
        item_sums = np.sum(self.user_item_matrix, axis=0)
        item_counts = np.sum(mask, axis=0)
        self.item_means = np.zeros_like(item_sums)
        nonzero_items = item_counts > 0
        self.item_means[nonzero_items] = item_sums[nonzero_items] / item_counts[nonzero_items]
        
        # 新增：统计用户评分次数
        self.user_rating_counts = ratings_df['user_id'].value_counts().to_dict()
        
        # 新增：创建中心化后的评分矩阵
        self.centered_user_item_matrix = np.copy(self.user_item_matrix)
        if self.method == 'user':
            # 基于用户的协同过滤：减去用户平均评分
            for i in range(len(self.unique_users)):
                user_mask = mask[i]
                self.centered_user_item_matrix[i, user_mask] -= self.user_means[i]
        else:  # self.method == 'item'
            # 基于物品的协同过滤：减去物品平均评分
            for j in range(len(self.unique_items)):
                item_mask = mask[:, j]
                self.centered_user_item_matrix[item_mask, j] -= self.item_means[j]
        
        # 根据方法计算相似度矩阵
        print("计算相似度矩阵...")
        if self.method == 'user':
            self.similarity_matrix = self._compute_similarity(self.centered_user_item_matrix)
        else:  # self.method == 'item'
            self.similarity_matrix = self._compute_similarity(self.centered_user_item_matrix.T)
        
        training_time = time.time() - start_time
        print(f"训练完成，耗时: {training_time:.2f}秒")
        
    def _compute_similarity(self, matrix):
        """
        计算相似度矩阵
        """
        n_rows = matrix.shape[0]
        similarity_matrix = np.zeros((n_rows, n_rows))
        
        # 对评分进行中心化 (这里centered_matrix是局部变量，不影响self.centered_user_item_matrix)
        centered_matrix_local = np.zeros_like(matrix)
        if self.method == 'user':
            for i in range(n_rows):
                mask = matrix[i] > 0
                if np.sum(mask) > 0:
                    centered_matrix_local[i, mask] = matrix[i, mask] - self.user_means[i]
        else:  # self.method == 'item'
            for i in range(n_rows):
                mask = matrix[i] > 0
                if np.sum(mask) > 0:
                    centered_matrix_local[i, mask] = matrix[i, mask] - self.item_means[i]
        
        if self.similarity == 'pearson_baseline':
            # 计算基于基线预测的皮尔逊相关系数 (添加活跃用户惩罚)
            for i in range(n_rows):
                if i % 50 == 0:
                    print(f"pearson_baseline相似度：正在处理第{i}行/共{n_rows}行")
                for j in range(i, n_rows):
                    # 找到两行都有评分的列
                    mask = (matrix[i] > 0) & (matrix[j] > 0)
                    common_indices = np.where(mask)[0] # 获取共同评分用户的索引 (对于item-based)
                    
                    if len(common_indices) > 1:  # 至少需要两个共同评分
                        # 获取共同评分用户的实际ID
                        common_users_ids = [self.index_to_user[idx] for idx in common_indices]
                        
                        # 计算权重
                        weights = np.array([1 / (1 + self.alpha * self.user_rating_counts.get(user_id, 0)) 
                                            for user_id in common_users_ids])
                        
                        # 获取共同评分
                        a_ratings = matrix[i][mask]
                        b_ratings = matrix[j][mask]
                        
                        # 计算基线预测 (这里假设method是item-based，所以使用item_means)
                        baseline_i = self.item_means[i]
                        baseline_j = self.item_means[j]
                        
                        # 计算中心化后的评分 (应用权重)
                        a_centered_weighted = (a_ratings - baseline_i) * weights
                        b_centered_weighted = (b_ratings - baseline_j) * weights
                        
                        # 计算带权重的皮尔逊系数的分子和分母
                        numerator = np.sum(a_centered_weighted * b_centered_weighted)
                        denominator = np.sqrt(np.sum(a_centered_weighted**2)) * np.sqrt(np.sum(b_centered_weighted**2))
                        
                        # 避免除以零
                        similarity = numerator / denominator if denominator > 0 else 0
                        
                        similarity_matrix[i, j] = similarity
                        similarity_matrix[j, i] = similarity
        
        # 计算相似度 (cosine和pearson使用 centered_matrix_local)
        elif self.similarity == 'cosine':
            # 计算余弦相似度
            for i in range(n_rows):
                if i % 50 == 0:
                    print(f"cosine相似度：正在处理第{i}行/共{n_rows}行")
                for j in range(i, n_rows):
                    mask = (matrix[i] > 0) & (matrix[j] > 0)
                    if np.sum(mask) > 0:
                        a = centered_matrix_local[i, mask]
                        b = centered_matrix_local[j, mask]
                        
                        # 计算余弦相似度
                        norm_a = np.linalg.norm(a)
                        norm_b = np.linalg.norm(b)
                        
                        if norm_a > 0 and norm_b > 0:
                            similarity = np.dot(a, b) / (norm_a * norm_b)
                        else:
                            similarity = 0
                    else:
                        similarity = 0
                    
                    similarity_matrix[i, j] = similarity
                    similarity_matrix[j, i] = similarity
        elif self.similarity == 'pearson':
            # 计算皮尔逊相关系数
            for i in range(n_rows):
                if i % 50 == 0:
                    print(f"pearson相似度：正在处理第{i}行/共{n_rows}行")
                for j in range(i, n_rows):
                    mask = (matrix[i] > 0) & (matrix[j] > 0)
                    if np.sum(mask) > 1:  # 至少需要两个共同评分
                        a = matrix[i, mask]
                        b = matrix[j, mask]
                        
                        # 如果标准差为0，直接设为0
                        if np.std(a) == 0 or np.std(b) == 0:
                            similarity = 0
                        else:
                            # 计算皮尔逊相关系数
                            correlation = np.corrcoef(a, b)[0, 1]
                            similarity = 0 if np.isnan(correlation) else correlation
                        
                        similarity_matrix[i, j] = similarity
                        similarity_matrix[j, i] = similarity
        return similarity_matrix
        
    def predict(self, user_id, item_id):
        """预测指定用户对指定物品的评分"""
        # 如果用户或物品不在训练集中，则返回平均评分
        if user_id not in self.user_to_index or item_id not in self.item_to_index:
            return np.mean(self.user_means)
        
        user_idx = self.user_to_index[user_id]
        item_idx = self.item_to_index[item_id]
        
        # 如果用户已经对物品进行了评分，则返回实际评分
        if self.user_item_matrix[user_idx, item_idx] > 0:
            return self.user_item_matrix[user_idx, item_idx]
        
        if self.method == 'user':
            # 基于用户的协同过滤
            similarities = self.similarity_matrix[user_idx]
            rated_mask = self.user_item_matrix[:, item_idx] > 0
            
            if not np.any(rated_mask):
                return self.user_means[user_idx]
                
            sim_users = similarities[rated_mask]
            # 使用中心化后的评分
            ratings = self.centered_user_item_matrix[rated_mask, item_idx]
            
            if len(sim_users) > self.k:
                top_k_indices = np.argsort(sim_users)[-self.k:]
                sim_users = sim_users[top_k_indices]
                ratings = ratings[top_k_indices]
            
            if len(sim_users) == 0 or np.sum(np.abs(sim_users)) == 0:
                return self.user_means[user_idx]
                
            weighted_sum = np.sum(sim_users * ratings)
            sum_weights = np.sum(np.abs(sim_users))
            
            # 加上目标用户的平均评分（还原为实际评分）
            predicted_rating = self.user_means[user_idx] + (weighted_sum / sum_weights)
            predicted_rating = max(0, min(100, predicted_rating))
            
            return predicted_rating
            
        else:  # self.method == 'item'
            # 基于物品的协同过滤
            similarities = self.similarity_matrix[item_idx]
            rated_mask = self.user_item_matrix[user_idx] > 0
            
            if not np.any(rated_mask):
                return self.item_means[item_idx]
                
            sim_items = similarities[rated_mask]
            # 使用中心化后的评分
            ratings = self.centered_user_item_matrix[user_idx, rated_mask]
            
            if len(sim_items) > self.k:
                top_k_indices = np.argsort(sim_items)[-self.k:]
                sim_items = sim_items[top_k_indices]
                ratings = ratings[top_k_indices]
            
            if len(sim_items) == 0 or np.sum(np.abs(sim_items)) == 0:
                return self.item_means[item_idx]
                
            weighted_sum = np.sum(sim_items * ratings)
            sum_weights = np.sum(np.abs(sim_items))
            
            # 加上目标物品的平均评分（还原为实际评分）
            predicted_rating = self.item_means[item_idx] + (weighted_sum / sum_weights)
            predicted_rating = max(0, min(100, predicted_rating))
            
            return predicted_rating
            
    def compute_rmse(self, ratings_df):
        """
        计算RMSE (均方根误差)
        """
        actual = []
        predicted = []
        
        for _, row in ratings_df.iterrows():
            user_id = row['user_id']
            item_id = row['item_id']
            rating = row['rating']
            
            pred = self.predict(user_id, item_id)
            
            actual.append(rating)
            predicted.append(pred)
            
        rmse = sqrt(mean_squared_error(actual, predicted))
        return rmse
    
    def eval(self, test_df):
        """
        在测试集上评估模型性能
        """
        print("在测试集上评估模型...")
        start_time = time.time()
        
        actual = []
        predicted = []
        
        for _, row in test_df.iterrows():
            user_id = row['user_id']
            item_id = row['item_id']
            rating = row['rating']
            
            pred = self.predict(user_id, item_id)
            
            actual.append(rating)
            predicted.append(pred)
            
        mse = mean_squared_error(actual, predicted)
        rmse = sqrt(mse)
        
        eval_time = time.time() - start_time
        
        mae = np.mean(np.abs(np.array(actual) - np.array(predicted)))
        print(f"误差 (MAE): {mae:.4f}")
        
        print(f"测试集评估完成，耗时: {eval_time:.2f}秒")
        print(f"均方误差 (MSE): {mse:.4f}")
        print(f"均方根误差 (RMSE): {rmse:.4f}")
        
        return rmse, mse

def predict_for_test_file(model, test_file, output_file):
    """
    为测试文件生成预测结果并输出到文件
    """
    # 加载测试文件
    print("加载测试数据...")
    test_user_items = []
    
    with open(test_file, 'r') as f:
        lines = f.readlines()
        
    i = 0
    while i < len(lines):
        # 处理用户头部行
        if '|' in lines[i]:
            parts = lines[i].strip().split('|')
            user_id = int(parts[0])
            item_count = int(parts[1])
            
            # 处理该用户的项目
            for j in range(1, item_count + 1):
                if i + j < len(lines):
                    item_id = int(lines[i + j].strip())
                    test_user_items.append((user_id, item_id))
            
            # 跳到下一个用户
            i += item_count + 1
        else:
            i += 1
    
    # 生成预测
    print("生成预测...")
    predictions = []
    
    for user_id, item_id in test_user_items:
        # 使用模型预测评分
        pred = model.predict(user_id, item_id)
        # 四舍五入到整数并确保在0-100之间
        predicted_rating = max(0, min(100, int(round(pred))))
        
        predictions.append((user_id, item_id, predicted_rating))
    
    # 将预测结果保存到文件
    print(f"将预测结果保存到 {output_file}...")
    with open(output_file, 'w') as f:
        current_user = None
        user_items = []
        
        for user_id, item_id, rating in predictions:
            if current_user != user_id:
                if current_user is not None:
                    f.write(f"{current_user}|{len(user_items)}\n")
                    for item, r in user_items:
                        f.write(f"{item} {r}\n")
                
                current_user = user_id
                user_items = [(item_id, rating)]
            else:
                user_items.append((item_id, rating))
        
        # 写入最后一个用户
        if current_user is not None:
            f.write(f"{current_user}|{len(user_items)}\n")
            for item, r in user_items:
                f.write(f"{item} {r}\n")
    
    print("预测完成！")

def optimize_knn_parameters(train_df, test_df):
    """
    优化KNN算法的参数
    """
    print("开始KNN参数优化...")
    
    # 定义要测试的参数
    methods = ['item']
    similarities = ['pearson_baseline']
    #k_values = list(range(10, 101, 10))
    k_values = [11]
    #alpha_values = [0.1, 0.5, 1.0, 2.0]  # 新增alpha参数测试
    alpha_values = [0.12,0.13,0.14]
    best_rmse = float('inf')
    best_params = None
    
    results = []
    
    # 修改循环结构
    for params in itertools.product(methods, similarities, k_values, alpha_values):
        method, similarity, k, alpha = params
        
        print(f"\n测试参数: method={method}, similarity={similarity}, k={k}, alpha={alpha}")
        
        # 创建并训练模型
        model = KNNRecommender(k=k, method=method, similarity=similarity, alpha=alpha)
        model.fit(train_df)
        
        # 评估模型
        rmse, mse = model.eval(test_df)
        
        results.append({
            'method': method,
            'similarity': similarity,
            'k': k,
            'alpha': alpha,
            'rmse': rmse,
            'mse': mse
        })
        
        # 更新最佳参数
        if rmse < best_rmse:
            best_rmse = rmse
            best_params = (method, similarity, k, alpha)
    
    # 打印最优参数和结果
    method, similarity, k, alpha = best_params
    print(f"\n最优参数: method={method}, similarity={similarity}, k={k}, alpha={alpha}")
    print(f"最佳RMSE: {best_rmse:.4f}")
    
    # 打印所有结果（按RMSE排序）
    results_df = pd.DataFrame(results).sort_values('rmse')
    print("\n所有参数组合的结果（按RMSE排序）:")
    print(results_df)
    
    return best_params

if __name__ == "__main__":
    # 加载数据
    print("加载数据...")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(project_root, "data", "train.txt")
    ratings_df = load_data_to_df(file_path)
    print(f"加载了 {len(ratings_df)} 条评分记录")
    
    # 分割训练集和测试集
    print("分割训练集和测试集...")
    train_df, test_df = train_test_split(ratings_df, test_size=0.2, random_state=42)
    print(f"训练集: {len(train_df)} 条记录, 测试集: {len(test_df)} 条记录")
    
    # 是否进行参数优化
    do_optimize = False
    
    if do_optimize:
        # 优化参数
        best_params = optimize_knn_parameters(train_df, test_df)
        method, similarity, k, alpha = best_params
    else:
        # 使用默认参数
        method = 'item'  # 'user' or 'item'
        similarity = 'pearson_baseline'  # 'cosine' or 'pearson' or 'pearson_baseline'
        k = 11  # 邻居数量
        alpha = 0.11 # 默认alpha值
    
    # 训练最终模型
    model = KNNRecommender(k=k, method=method, similarity=similarity, alpha=alpha)
    model.fit(train_df)
    
    # 在测试集上评估
    rmse, mse = model.eval(test_df)
    
    # 可选：为测试文件生成预测
    # predict_for_test_file(model, "data/test.txt", "data/knn_predictions.txt")
    '''

method=item, similarity=pearson_baseline, k=11, alpha=0.11
均方误差 (MSE): 346.8207
均方根误差 (RMSE): 18.6231
    '''