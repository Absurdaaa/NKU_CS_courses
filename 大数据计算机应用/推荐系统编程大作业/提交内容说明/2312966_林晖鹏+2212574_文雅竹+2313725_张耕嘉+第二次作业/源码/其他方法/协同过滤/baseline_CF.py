import numpy as np
import pandas as pd
import time
# from sklearn.metrics import mean_squared_error
from math import sqrt
from scipy.sparse import csr_matrix
# from sklearn.metrics.pairwise import cosine_similarit

def cosine_similarity(X, Y=None):
    # 确保输入为numpy数组
    X = np.asarray(X)
    
    if Y is None:
        Y = X
    else:
        Y = np.asarray(Y)
    
    # 归一化，计算每行的L2范数
    X_normalized = X / np.sqrt(np.sum(X**2, axis=1))[:, np.newaxis]
    Y_normalized = Y / np.sqrt(np.sum(Y**2, axis=1))[:, np.newaxis]
    
    # 处理可能的NaN值（当某行全为0时）
    X_normalized = np.nan_to_num(X_normalized)
    Y_normalized = np.nan_to_num(Y_normalized)
    
    # 计算余弦相似度矩阵
    return np.dot(X_normalized, Y_normalized.T)


def mean_squared_error(y_true, y_pred):
    return np.mean((np.array(y_true) - np.array(y_pred)) ** 2)

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
    
def compute_iuf_similarity(item_user_matrix):
    """
    使用IUF（逆用户频率）权重计算物品相似度
    
    Parameters:
    -----------
    item_user_matrix: 物品-用户矩阵，每行是一个物品，每列是一个用户
    
    Returns:
    --------
    IUF加权的物品相似度矩阵
    """
    n_items, n_users = item_user_matrix.shape
    sim_matrix = np.zeros((n_items, n_items))
    
    # 计算每个用户的评分数量
    user_ratings_count = np.sum(item_user_matrix > 0, axis=0)
    
    # 计算IUF权重 (log(N/n_u))
    # N是总用户数，n_u是评价过物品i的用户数
    iuf_weights = np.log(n_users / (user_ratings_count + 1e-10))
    
    # 应用IUF权重到评分矩阵
    weighted_matrix = np.zeros_like(item_user_matrix)
    for u in range(n_users):
        mask = item_user_matrix[:, u] > 0
        weighted_matrix[mask, u] = item_user_matrix[mask, u] * iuf_weights[u]
    
    norms = np.sqrt(np.sum(weighted_matrix ** 2, axis=1))
    norms[norms == 0] = 1e-10  # 避免除以零

    # 步骤2：归一化物品向量(除以其范数)
    normalized_weighted_matrix = weighted_matrix / norms[:, np.newaxis]

    # 步骤3：通过矩阵乘法一次性计算所有余弦相似度
    # A·B^T 可以得到所有物品之间的点积，对于归一化后的向量，点积就等于余弦相似度
    sim_matrix = np.dot(normalized_weighted_matrix, normalized_weighted_matrix.T)
        
    return sim_matrix

class ImprovedItemBasedCF:
    """
    改进的基于物品的协同过滤推荐算法
    """
    def __init__(self, k=30, sim_method='pearson', shrinkage=100, normalize=True, 
                 use_baseline=True, regularization=0.1, n_epochs=10, learning_rate=0.005):
        """
        初始化模型参数
        
        Parameters:
        -----------
        k: 用于预测的最近邻物品数量
        sim_method: 相似度度量方法 'pearson', 'cosine', 'adjusted_cosine'
        shrinkage: 相似度缩减参数(避免共同评分用户数少时的过度置信)
        normalize: 是否在预测时规范化评分
        use_baseline: 是否使用基线预测
        regularization: 基线模型的正则化参数
        n_epochs: 基线模型训练的迭代次数
        learning_rate: 基线模型的学习率
        """
        self.k = k
        self.sim_method = sim_method
        self.shrinkage = shrinkage
        self.normalize = normalize
        self.use_baseline = use_baseline
        
        # 基线模型参数
        self.regularization = regularization
        self.n_epochs = n_epochs
        self.learning_rate = learning_rate
        
        # 初始化参数
        self.user_biases = {}
        self.item_biases = {}
        self.global_mean = None
        self.item_similarity_matrix = None
        self.item_means = None
        self.user_means = None
        self.item_std = None
        self.user_item_matrix = None
        self.item_id_to_index = {}
        self.index_to_item_id = {}
        self.user_id_to_index = {}
        self.index_to_user_id = {}
    
    def _create_mappings(self, ratings_df):
        """创建ID和索引之间的映射"""
        unique_users = sorted(ratings_df['user_id'].unique())
        unique_items = sorted(ratings_df['item_id'].unique())
        
        self.user_id_to_index = {uid: idx for idx, uid in enumerate(unique_users)}
        self.item_id_to_index = {iid: idx for idx, iid in enumerate(unique_items)}
        self.index_to_user_id = {idx: uid for uid, idx in self.user_id_to_index.items()}
        self.index_to_item_id = {idx: iid for iid, idx in self.item_id_to_index.items()}
    
    def _create_matrix(self, ratings_df):
        """创建用户-物品评分矩阵"""
        n_users = len(self.user_id_to_index)
        n_items = len(self.item_id_to_index)
        
        # 获取用户和物品的索引
        user_indices = [self.user_id_to_index[uid] for uid in ratings_df['user_id']]
        item_indices = [self.item_id_to_index[iid] for iid in ratings_df['item_id']]
        ratings = ratings_df['rating'].values
        
        # 创建稀疏矩阵
        self.user_item_matrix = csr_matrix((ratings, (user_indices, item_indices)), 
                                          shape=(n_users, n_items))
        return self.user_item_matrix.toarray()
    
    def _train_baseline(self, ratings_df):
        """训练基线模型"""
        print("训练基线预测模型...")
        start_time = time.time()
        
        # 计算全局平均评分
        self.global_mean = ratings_df['rating'].mean()
        
        # 初始化用户和物品偏差
        all_users = ratings_df['user_id'].unique()
        all_items = ratings_df['item_id'].unique()
        
        self.user_biases = {user: 0 for user in all_users}
        self.item_biases = {item: 0 for item in all_items}
        
        # 使用随机梯度下降(SGD)学习偏差
        for epoch in range(self.n_epochs):
            # 打乱数据顺序
            ratings_df = ratings_df.sample(frac=1).reset_index(drop=True)
            
            # 遍历每个评分记录
            for _, row in ratings_df.iterrows():
                user = row['user_id']
                item = row['item_id']
                rating = row['rating']
                
                # 计算预测误差
                pred = self.global_mean + self.user_biases[user] + self.item_biases[item]
                error = rating - pred
                
                # 更新偏差
                self.user_biases[user] += self.learning_rate * (error - self.regularization * self.user_biases[user])
                self.item_biases[item] += self.learning_rate * (error - self.regularization * self.item_biases[item])
        
        training_time = time.time() - start_time
        print(f"基线模型训练完成，耗时: {training_time:.2f}秒")
    
    def _compute_item_similarity(self, matrix):
        """计算物品相似度矩阵"""
        print("计算物品相似度矩阵...")
        start_time = time.time()
        
        if self.sim_method == 'adjusted_cosine':
            # 对每个用户的评分减去用户平均评分（去除用户评分偏好）
            normalized_matrix = np.zeros_like(matrix)
            for u_idx in range(matrix.shape[0]):
                user_ratings = matrix[u_idx, :]
                rated_items = user_ratings > 0
                if np.any(rated_items):
                    user_mean = np.mean(user_ratings[rated_items])
                    normalized_matrix[u_idx, rated_items] = user_ratings[rated_items] - user_mean
            
            # 转置为物品-用户矩阵并计算相似度
            item_user_matrix = normalized_matrix.T
            item_similarity = cosine_similarity(item_user_matrix)
        
        elif self.sim_method == 'cosine':
            # 转置为物品-用户矩阵并计算相似度
            item_user_matrix = matrix.T
            item_similarity = cosine_similarity(item_user_matrix)
        
        elif self.sim_method == 'pearson':
            # 皮尔逊相关系数 (通过手动实现来优化计算)
            item_user_matrix = matrix.T
            
            item_similarity = pearson_similarity_items(item_user_matrix)
            
            # 应用缩减因子（如果需要）
            # if self.shrinkage > 0:
            #     # 计算共同评分数量矩阵
            #     n_users = item_user_matrix.shape[1]
            #     n_items = item_user_matrix.shape[0]
            #     common_users = np.zeros((n_items, n_items))
                
            #     for i in range(n_items):
            #         for j in range(i, n_items):
            #             mask_i = item_user_matrix[i] > 0
            #             mask_j = item_user_matrix[j] > 0
            #             n_common = np.sum(mask_i & mask_j)
                        
            #             # 应用缩减因子
            #             shrinkage_factor = n_common / (n_common + self.shrinkage)
            #             item_similarity[i, j] *= shrinkage_factor
            #             item_similarity[j, i] *= shrinkage_factor
            
            
            # n_items = item_user_matrix.shape[0]
            
            # # 创建结果矩阵
            # item_similarity = np.zeros((n_items, n_items))
            
            # # 计算每个物品的平均评分
            # item_means = np.zeros(n_items)
            # for i in range(n_items):
            #     rated = item_user_matrix[i] > 0
            #     if np.sum(rated) > 0:
            #         item_means[i] = np.mean(item_user_matrix[i, rated])
            
            # # 计算皮尔逊相关系数
            # for i in range(n_items):
            #     for j in range(i, n_items):  # 对称矩阵，只计算上三角
            #         # 找出共同评分的用户
            #         mask_i = item_user_matrix[i] > 0
            #         mask_j = item_user_matrix[j] > 0
            #         common_users = mask_i & mask_j
            #         n_common = np.sum(common_users)
                    
            #         if n_common == 0:
            #             item_similarity[i, j] = 0
            #         else:
            #             # 应用缩减调整，防止少量用户评分导致过高相似度
            #             rating_i_centered = item_user_matrix[i, common_users] - item_means[i]
            #             rating_j_centered = item_user_matrix[j, common_users] - item_means[j]
                        
            #             numerator = np.sum(rating_i_centered * rating_j_centered)
            #             denominator = np.sqrt(np.sum(rating_i_centered**2) * np.sum(rating_j_centered**2))
                        
            #             if denominator == 0:
            #                 sim = 0
            #             else:
            #                 # 应用缩减因子
            #                 sim = numerator / denominator * n_common / (n_common + self.shrinkage)
                        
            #             item_similarity[i, j] = sim
            #             item_similarity[j, i] = sim  # 对称矩阵
        elif self.sim_method == 'jaccard':
            item_user_matrix = matrix.T
            n_items = item_user_matrix.shape[0]
        # Jaccard相似度 - 仅考虑是否评分，不考虑评分值
            # 创建一个二元矩阵（只考虑是否评分）
            binary_matrix = (item_user_matrix > 0).astype(np.float32)
            
            # 计算每个物品评分的用户数（每行中的1的个数）
            item_rated_counts = np.sum(binary_matrix, axis=1)
            
            # 计算物品对之间的交集数量（矩阵乘法A·B^T）
            # 由于矩阵是二元的，点积就等于交集大小
            intersection_matrix = np.dot(binary_matrix, binary_matrix.T)
            
            # 计算并集大小：A的评分数 + B的评分数 - 交集大小
            # 使用广播机制计算所有对的并集
            union_matrix = item_rated_counts[:, np.newaxis] + item_rated_counts - intersection_matrix
            
            # 计算Jaccard相似度：交集/并集
            # 避免除以0
            union_matrix[union_matrix == 0] = 1
            item_similarity = intersection_matrix / union_matrix
        
        elif self.sim_method == 'iuf':
            item_user_matrix = matrix.T
            item_similarity = compute_iuf_similarity(item_user_matrix)    
        
        else:
            raise ValueError(f"不支持的相似度方法: {self.sim_method}")
        
        computation_time = time.time() - start_time
        print(f"相似度矩阵计算完成，耗时: {computation_time:.2f}秒")
        
        return item_similarity
    
    def fit(self, ratings_df):
        """
        训练模型
        
        Parameters:
        -----------
        ratings_df : 包含用户ID、物品ID和评分的DataFrame
        """
        print("开始训练基于物品的协同过滤模型...")
        start_time = time.time()
        
        # 创建ID和索引映射
        self._create_mappings(ratings_df)
        
        # 创建用户-物品矩阵
        matrix = self._create_matrix(ratings_df)
        
        # 计算物品平均评分
        n_items = matrix.shape[1]
        self.item_means = np.zeros(n_items)
        for i in range(n_items):
            rated = matrix[:, i] > 0
            if np.sum(rated) > 0:
                self.item_means[i] = np.mean(matrix[rated, i])
        
        # 计算用户平均评分
        n_users = matrix.shape[0]
        self.user_means = np.zeros(n_users)
        for u in range(n_users):
            rated = matrix[u, :] > 0
            if np.sum(rated) > 0:
                self.user_means[u] = np.mean(matrix[u, rated])
        
        # 如果需要，计算物品评分的标准差(用于标准化)
        if self.normalize:
            self.item_std = np.zeros(n_items)
            for i in range(n_items):
                rated = matrix[:, i] > 0
                if np.sum(rated) > 1:  # 至少需要2个评分计算标准差
                    self.item_std[i] = np.std(matrix[rated, i])
                else:
                    self.item_std[i] = 1.0  # 避免除以零
        
        # 如果使用基线预测，训练基线模型
        if self.use_baseline:
            self._train_baseline(ratings_df)
        
        # 计算物品相似度矩阵
        self.item_similarity_matrix = self._compute_item_similarity(matrix)
        
        training_time = time.time() - start_time
        print(f"模型训练完成，总耗时: {training_time:.2f}秒")
    
    def _get_baseline_prediction(self, user_id, item_id):
        """获取基线预测"""
        user_bias = self.user_biases.get(user_id, 0)
        item_bias = self.item_biases.get(item_id, 0)
        return self.global_mean + user_bias + item_bias
        
    def _get_baseline_prediction(self, user_id, item_id):
        """
        获取基线预测，增加安全检查
        """
        # 直接使用字典的get方法，当键不存在时返回默认值0
        user_bias = self.user_biases.get(user_id, 0)
        item_bias = self.item_biases.get(item_id, 0)
        return self.global_mean + user_bias + item_bias
    
    def predict(self, user_id, item_id):
        """
        预测指定用户对指定物品的评分（完整修复版）
        
        Parameters:
        -----------
        user_id : 用户ID
        item_id : 物品ID
        
        Returns:
        --------
        预测的评分值
        """
        # 检查用户和物品是否在训练集中
        if user_id not in self.user_id_to_index:
            # 用户不在训练集中，返回全局平均分或带物品偏置的预测
            return self._get_baseline_prediction(user_id, item_id) if self.use_baseline else self.global_mean
        
        if item_id not in self.item_id_to_index:
            # 物品不在训练集中，返回用户平均分加全局物品偏置
            return self._get_baseline_prediction(user_id, item_id) if self.use_baseline else self.global_mean
        
        user_idx = self.user_id_to_index[user_id]
        item_idx = self.item_id_to_index[item_id]
        
        # 获取用户评过分的物品
        try:
            user_ratings = self.user_item_matrix[user_idx].toarray().flatten()
            rated_items = np.where(user_ratings > 0)[0]
        except IndexError:
            # 捕获索引错误以进一步增强健壮性
            return self._get_baseline_prediction(user_id, item_id)
        
        if len(rated_items) == 0:
            # 用户没有评过任何物品
            return self._get_baseline_prediction(user_id, item_id)
        
        # 确保所有索引都在有效范围内（筛选有效的rated_items）
        valid_rated_items = []
        for item in rated_items:
            if item < self.item_similarity_matrix.shape[1]:
                valid_rated_items.append(item)
        
        if not valid_rated_items:
            return self._get_baseline_prediction(user_id, item_id)
        
        valid_rated_items = np.array(valid_rated_items)
        
        try:
            # 获取目标物品与其他物品的相似度
            item_similarities = self.item_similarity_matrix[item_idx, valid_rated_items]
        except IndexError:
            # 如果仍然出现索引错误，回退到基线预测
            return self._get_baseline_prediction(user_id, item_id)
        
        # 选择topk个最相似的物品
        if len(valid_rated_items) > self.k:
            try:
                top_k_indices = np.argsort(item_similarities)[-self.k:]
                top_similarities = item_similarities[top_k_indices]
                top_rated_items = valid_rated_items[top_k_indices]
            except Exception:
                # 捕获排序或索引过程中的任何错误
                return self._get_baseline_prediction(user_id, item_id)
        else:
            top_similarities = item_similarities
            top_rated_items = valid_rated_items
        
        # 获取用户对这些物品的评分
        top_ratings = user_ratings[top_rated_items]
        
        # 标准化评分部分进行保护处理
        try:
            if self.normalize:
                # 为每个相似物品获取基线预测
                baseline_predictions = []
                for i in top_rated_items:
                    if i < len(self.index_to_item_id):
                        sim_item_id = self.index_to_item_id[i]
                        baseline_predictions.append(self._get_baseline_prediction(user_id, sim_item_id))
                    else:
                        baseline_predictions.append(self.global_mean)
                
                baseline_predictions = np.array(baseline_predictions)
                rating_deviations = top_ratings - baseline_predictions
                
                if np.sum(np.abs(top_similarities)) > 0:
                    weighted_deviation = np.sum(top_similarities * rating_deviations) / np.sum(np.abs(top_similarities))
                else:
                    weighted_deviation = 0
                
                prediction = self._get_baseline_prediction(user_id, item_id) + weighted_deviation
            else:
                # 不标准化，直接计算加权平均
                if np.sum(np.abs(top_similarities)) > 0:
                    prediction = np.sum(top_similarities * top_ratings) / np.sum(np.abs(top_similarities))
                else:
                    prediction = self._get_baseline_prediction(user_id, item_id)
        except Exception as e:
            # 捕获计算过程中的任何错误
            print(f"计算预测时发生错误: {e}")
            return self._get_baseline_prediction(user_id, item_id)
            
        prediction = max(0, min(100, prediction))
        # prediction =int(round(prediction / 10.0) * 10)
        
        # 确保预测在有效范围内
        return prediction
    
    def compute_rmse(self, ratings_df):
        """计算RMSE"""
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
    
    def eval(self, test_df,output_file="results.txt"):
        """在测试集上评估模型性能"""
        print("在测试集上评估模型...")
        start_time = time.time()
        
        actual = []
        predicted = []
        
        # 如果需要保存结果，打开文件
        # with open(output_file, 'w') as f:
        #     # 写入标题行
        #     f.write("user_id\titem_id\tactual_rating\tpredicted_rating\n")
            
            # 遍历测试数据并保存结果
            # for _, row in test_df.iterrows():
            #     user_id = row['user_id']
            #     item_id = row['item_id']
            #     rating = row['rating']
                
            #     pred = self.predict(user_id, item_id)
                
            #     # 观察到评分是整数，且通常为10的倍数
            #     # pred = int(round(pred / 10.0) * 10)
                
            #     actual.append(rating)
            #     predicted.append(pred)
                
            #     # 写入每条记录
            #     f.write(f"{user_id}\t{item_id}\t{rating}\t{pred:.4f}\n")
        
        for _, row in test_df.iterrows():
            user_id = row['user_id']
            item_id = row['item_id']
            rating = row['rating']
            
            pred = self.predict(user_id, item_id)
            
            actual.append(rating)
            predicted.append(pred)
            
        mse = mean_squared_error(actual, predicted)
        rmse = sqrt(mse)
        mae = np.mean(np.abs(np.array(actual) - np.array(predicted)))
        
        eval_time = time.time() - start_time
        
        print(f"测试集评估完成，耗时: {eval_time:.2f}秒")
        print(f"均方误差 (MSE): {mse:.4f}")
        print(f"均方根误差 (RMSE): {rmse:.4f}")
        print(f"MAE:{mae:.4f}")
        
        return rmse, mse, mae, 


def load_data_to_df(file_path, test = False):
    """将数据文件加载为pandas DataFrame"""
    user_item_pairs = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
    i = 0
    
    if test:
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
                          if len(item_parts) == 1:
                              item_id = int(item_parts[0])
                              user_item_pairs.append((user_id, item_id))
                  
                  # 跳到下一个用户
                  i += item_count + 1
              else:
                  i += 1
      
        # 从收集的数据创建DataFrame
        df = pd.DataFrame(user_item_pairs, columns=['user_id', 'item_id'])
        return df
    else:
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
    """将数据集分割为训练集和测试集"""
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


if __name__ == "__main__":
    # 加载数据
    print("加载数据...")
    ratings_df = load_data_to_df("data/train.txt")
    print(f"加载了 {len(ratings_df)} 条评分记录")
    
    # 分割训练集和测试集
    print("分割训练集和测试集...")
    train_df, test_df = train_test_split(ratings_df, test_size=0.2, random_state=42)
    print(f"训练集: {len(train_df)} 条记录, 测试集: {len(test_df)} 条记录")
    
    model5 = ImprovedItemBasedCF(
        k=30,                    
        sim_method='jaccard',
        shrinkage=100,
        normalize=True,
        use_baseline=True,
        regularization=0.1,
        n_epochs=20,
        learning_rate=0.01
    )
    
    model5.fit(train_df)
    rmse5, _, mae5 = model5.eval(test_df)
    # epochs_list = [10,15,20,25,30,35,40,45,50]
    # for n in epochs_list:
    #   print(f"n={n}")
    #   model5.n_epochs = n
    #   model5.fit(train_df)
    #   rmse5, _, mae5 = model5.eval(test_df)
    
    # # 创建并训练改进的基于物品的协同过滤模型
    # model = ImprovedItemBasedCF(
    #     k=30,                   # 考虑的最近邻物品数量
    #     sim_method='pearson',   # 使用皮尔逊相关系数作为相似度度量
    #     shrinkage=100,          # 相似度缩减因子
    #     normalize=True,         # 使用标准化评分
    #     use_baseline=True,      # 使用基线预测
    #     regularization=0.1,     # 基线模型正则化参数
    #     n_epochs=20,            # 基线模型训练迭代次数
    #     learning_rate=0.01     # 基线模型学习率
    # )
    
    # # 训练模型
    # model.fit(train_df)
    
    # # 在测试集上评估
    # rmse, mse, mae = model.eval(test_df)
    
    # # 可以尝试不同的参数组合来找到最佳性能
    # print("\n尝试不同的相似度度量方法...")
    # model2 = ImprovedItemBasedCF(
    #     k=30,                    
    #     sim_method='adjusted_cosine',  # 使用调整余弦相似度
    #     shrinkage=100,
    #     normalize=True,
    #     use_baseline=True,
    #     regularization=0.1,
    #     n_epochs=20,
    #     learning_rate=0.01
    # )
    
    # model3 = ImprovedItemBasedCF(
    #     k=30,                    
    #     sim_method='iuf',  # 使用调整余弦相似度
    #     shrinkage=100,
    #     normalize=True,
    #     use_baseline=True,
    #     regularization=0.1,
    #     n_epochs=20,
    #     learning_rate=0.01
    # )
    
    # model4 = ImprovedItemBasedCF(
    #     k=30,                    
    #     sim_method='cosine',  # 使用余弦相似度
    #     shrinkage=100,
    #     normalize=True,
    #     use_baseline=True,
    #     regularization=0.1,
    #     n_epochs=20,
    #     learning_rate=0.01
    # )
    
    # model5 = ImprovedItemBasedCF(
    #     k=30,                    
    #     sim_method='jaccard',
    #     shrinkage=100,
    #     normalize=True,
    #     use_baseline=True,
    #     regularization=0.1,
    #     n_epochs=20,
    #     learning_rate=0.01
    # )
    
    
    # model2.fit(train_df)
    # rmse2, _, mae2 = model2.eval(test_df)
    
    # model3.fit(train_df)
    # rmse3, _, mae3 = model3.eval(test_df)
    
    # model4.fit(train_df)
    # rmse4, _, mae4 = model4.eval(test_df)
    
    # model5.fit(train_df)
    # rmse5, _, mae5 = model5.eval(test_df)
    
    
    # print(f"\n皮尔逊相关系数 RMSE: {rmse:.4f} MSE:{rmse**2:.4f} MAE{mae:.4f}") #17.7033
    # print(f"调整余弦相似度 RMSE: {rmse2:.4f}  MSE:{rmse2**2:.4f} MAE{mae2:.4f}") #16.7907,12.7880
    # print(f"IUF加权 RMSE: {rmse3:.4f} MSE:{rmse3**2:.4f} MAE{mae3:.4f}") # 16.9200
    # print(f"余弦相似度 RMSE: {rmse4:.4f} MSE:{rmse4**2:.4f} MAE{mae4:.4f}") # 16.7297
    # print(f"Jaccard相似度 RMSE: {rmse5:.4f}  MSE:{rmse5**2:.4f} MAE{mae5:.4f}") # 16.6402 MAE: 12.6974
    
    
    #最后拿全部数据训练，然后测试
    # all_train_df = load_data_to_df("data/train.txt")
    # all_test_df = load_data_to_df("data/test.txt",True)
    
    # print(all_test_df.head())
    # print(all_train_df.head())
    
    # output_file = 'ResultsFrom0.txt'
    
    # model5.fit(all_train_df)
    
    # with open(output_file, 'w') as f:
    #     # 写入标题行
    #     f.write("user_id\titem_id\tpredicted_rating\n")
        
    #     # 遍历测试数据并保存结果
    #     for _, row in all_test_df.iterrows():
    #         user_id = row['user_id']
    #         item_id = row['item_id']
            
    #         pred = model5.predict(user_id, item_id)
            
            
    #         # 写入每条记录
    #         f.write(f"{user_id}\t{item_id}\t{pred:.4f}\n")
    
    
'''
皮尔逊：
测试集评估完成，耗时: 3.86秒
均方误差 (MSE): 303.6201
均方根误差 (RMSE): 17.4247
MAE:13.3903

调整余弦相似度
测试集评估完成，耗时: 5.90秒
均方误差 (MSE): 281.5775
均方根误差 (RMSE): 16.7803

皮尔逊相关系数 RMSE: 17.4247 MSE:303.6201 MAE13.3903
相似度矩阵计算完成，耗时: 0.07秒

调整余弦相似度 RMSE: 16.7993  MSE:282.2164 MAE12.7994
相似度矩阵计算完成，耗时: 1.14秒

IUF加权 RMSE: 16.7803 MSE:281.5775 MAE12.8370
相似度矩阵计算完成，耗时: 0.86秒

余弦相似度 RMSE: 16.6344 MSE:276.7032 MAE12.7202
相似度矩阵计算完成，耗时: 0.83秒

Jaccard相似度 RMSE: 16.6300  MSE:276.5553 MAE12.6987
相似度矩阵计算完成，耗时: 1.35秒
'''

    