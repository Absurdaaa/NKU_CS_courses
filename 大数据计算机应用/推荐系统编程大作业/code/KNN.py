import numpy as np
import pandas as pd
import time
from sklearn.metrics import mean_squared_error
from math import sqrt

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
    def __init__(self, k=40, method='user', similarity='cosine'):
        """
        初始化KNN推荐器
        
        Parameters:
        -----------
        k : 邻居数量
        method : 协同过滤方法，'user'表示基于用户，'item'表示基于物品
        similarity : 相似度计算方法，支持'cosine'和'pearson'
        """
        self.k = k
        self.method = method
        self.similarity = similarity
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
        
    def fit(self, ratings_df):
        """
        训练KNN模型
        """
        print(f"训练KNN模型 (方法: {self.method}, 相似度: {self.similarity}, k: {self.k})...")
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
        
        # 根据方法计算相似度矩阵
        print("计算相似度矩阵...")
        if self.method == 'user':
            self.similarity_matrix = self._compute_similarity(self.user_item_matrix)
        else:  # self.method == 'item'
            self.similarity_matrix = self._compute_similarity(self.user_item_matrix.T)
        
        training_time = time.time() - start_time
        print(f"训练完成，耗时: {training_time:.2f}秒")
        
    def _compute_similarity(self, matrix):
        """
        计算相似度矩阵
        """
        n_rows = matrix.shape[0]
        similarity_matrix = np.zeros((n_rows, n_rows))
        
        # 对评分进行中心化
        centered_matrix = np.zeros_like(matrix)
        if self.method == 'user':
            for i in range(n_rows):
                mask = matrix[i] > 0
                if np.sum(mask) > 0:
                    centered_matrix[i, mask] = matrix[i, mask] - self.user_means[i]
        else:  # self.method == 'item'
            for i in range(n_rows):
                mask = matrix[i] > 0
                if np.sum(mask) > 0:
                    centered_matrix[i, mask] = matrix[i, mask] - self.item_means[i]
        
        # 计算相似度
        if self.similarity == 'cosine':
            # 计算余弦相似度
            for i in range(n_rows):
                for j in range(i, n_rows):
                    # 找到两行都有评分的列
                    mask = (matrix[i] > 0) & (matrix[j] > 0)
                    if np.sum(mask) > 0:
                        a = centered_matrix[i, mask]
                        b = centered_matrix[j, mask]
                        
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
                for j in range(i, n_rows):
                    # 找到两行都有评分的列
                    mask = (matrix[i] > 0) & (matrix[j] > 0)
                    if np.sum(mask) > 1:  # 至少需要两个共同评分
                        a = matrix[i, mask]
                        b = matrix[j, mask]
                        
                        # 计算皮尔逊相关系数
                        correlation = np.corrcoef(a, b)[0, 1]
                        
                        if not np.isnan(correlation):
                            similarity_matrix[i, j] = correlation
                            similarity_matrix[j, i] = correlation
        
        return similarity_matrix
        
    def predict(self, user_id, item_id):
        """
        预测指定用户对指定物品的评分
        """
        # 如果用户或物品不在训练集中，则返回平均评分
        if user_id not in self.user_to_index or item_id not in self.item_to_index:
            # 返回全局平均评分
            return np.mean(self.user_means)
        
        user_idx = self.user_to_index[user_id]
        item_idx = self.item_to_index[item_id]
        
        # 如果用户已经对物品进行了评分，则返回实际评分
        if self.user_item_matrix[user_idx, item_idx] > 0:
            return self.user_item_matrix[user_idx, item_idx]
        
        if self.method == 'user':
            # 基于用户的协同过滤
            
            # 获取当前用户的相似度向量
            similarities = self.similarity_matrix[user_idx]
            
            # 找到对当前物品有评分的用户
            rated_mask = self.user_item_matrix[:, item_idx] > 0
            
            # 如果没有用户对此物品有评分，则返回当前用户的平均评分
            if not np.any(rated_mask):
                return self.user_means[user_idx]
            
            # 过滤出对该物品有评分的用户的相似度和评分
            sim_users = similarities[rated_mask]
            ratings = self.user_item_matrix[rated_mask, item_idx]
            
            # 如果用户数量超过k，则只选择k个最相似的用户
            if len(sim_users) > self.k:
                # 获取前k个相似用户的索引
                top_k_indices = np.argsort(sim_users)[-self.k:]
                sim_users = sim_users[top_k_indices]
                ratings = ratings[top_k_indices]
            
            # 如果没有足够的相似用户，则返回当前用户的平均评分
            if len(sim_users) == 0 or np.sum(np.abs(sim_users)) == 0:
                return self.user_means[user_idx]
            
            # 计算加权平均评分
            weighted_sum = np.sum(sim_users * ratings)
            sum_weights = np.sum(np.abs(sim_users))
            
            predicted_rating = weighted_sum / sum_weights
            
            # 确保评分在合理范围内
            predicted_rating = max(0, min(100, predicted_rating))
            
            return predicted_rating
            
        else:  # self.method == 'item'
            # 基于物品的协同过滤
            
            # 获取当前物品的相似度向量
            similarities = self.similarity_matrix[item_idx]
            
            # 找到当前用户评分过的物品
            rated_mask = self.user_item_matrix[user_idx] > 0
            
            # 如果用户没有任何评分记录，则返回物品的平均评分
            if not np.any(rated_mask):
                return self.item_means[item_idx]
            
            # 过滤出用户评分过的物品的相似度和评分
            sim_items = similarities[rated_mask]
            ratings = self.user_item_matrix[user_idx, rated_mask]
            
            # 如果物品数量超过k，则只选择k个最相似的物品
            if len(sim_items) > self.k:
                # 获取前k个相似物品的索引
                top_k_indices = np.argsort(sim_items)[-self.k:]
                sim_items = sim_items[top_k_indices]
                ratings = ratings[top_k_indices]
            
            # 如果没有足够的相似物品，则返回该物品的平均评分
            if len(sim_items) == 0 or np.sum(np.abs(sim_items)) == 0:
                return self.item_means[item_idx]
            
            # 计算加权平均评分
            weighted_sum = np.sum(sim_items * ratings)
            sum_weights = np.sum(np.abs(sim_items))
            
            predicted_rating = weighted_sum / sum_weights
            
            # 确保评分在合理范围内
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
    methods = ['user', 'item']
    similarities = ['cosine', 'pearson']
    k_values = [10, 20, 40, 60, 80]
    
    best_rmse = float('inf')
    best_params = None
    
    results = []
    
    for method in methods:
        for similarity in similarities:
            for k in k_values:
                print(f"\n测试参数: method={method}, similarity={similarity}, k={k}")
                
                # 创建并训练模型
                model = KNNRecommender(k=k, method=method, similarity=similarity)
                model.fit(train_df)
                
                # 评估模型
                rmse, mse = model.eval(test_df)
                
                results.append({
                    'method': method,
                    'similarity': similarity,
                    'k': k,
                    'rmse': rmse,
                    'mse': mse
                })
                
                # 更新最佳参数
                if rmse < best_rmse:
                    best_rmse = rmse
                    best_params = (method, similarity, k)
    
    # 打印最优参数和结果
    method, similarity, k = best_params
    print(f"\n最优参数: method={method}, similarity={similarity}, k={k}")
    print(f"最佳RMSE: {best_rmse:.4f}")
    
    # 打印所有结果（按RMSE排序）
    results_df = pd.DataFrame(results).sort_values('rmse')
    print("\n所有参数组合的结果（按RMSE排序）:")
    print(results_df)
    
    return best_params

if __name__ == "__main__":
    # 加载数据
    print("加载数据...")
    ratings_df = load_data_to_df("data/train.txt")
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
        method, similarity, k = best_params
    else:
        # 使用默认参数
        method = 'user'  # 'user' or 'item'
        similarity = 'cosine'  # 'cosine' or 'pearson'
        k = 40
    
    # 训练最终模型
    model = KNNRecommender(k=k, method=method, similarity=similarity)
    model.fit(train_df)
    
    # 在测试集上评估
    rmse, mse = model.eval(test_df)
    
    # 可选：为测试文件生成预测
    # predict_for_test_file(model, "data/test.txt", "data/knn_predictions.txt")
