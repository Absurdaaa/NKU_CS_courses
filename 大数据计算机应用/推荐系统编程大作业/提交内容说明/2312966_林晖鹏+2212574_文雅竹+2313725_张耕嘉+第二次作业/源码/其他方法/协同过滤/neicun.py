import numpy as np
import pandas as pd
import time
from math import sqrt
from scipy.sparse import csr_matrix
import psutil
import os
import tracemalloc
from memory_profiler import profile
import gc

def memory_usage():
    """获取当前进程的内存使用情况（以MB为单位）"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    # 返回以MB为单位的内存使用量
    return memory_info.rss / 1024 / 1024

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
            # 皮尔逊相关系数
            item_user_matrix = matrix.T
            item_similarity = pearson_similarity_items(item_user_matrix)
        
        elif self.sim_method == 'jaccard':
            item_user_matrix = matrix.T
            n_items = item_user_matrix.shape[0]
            # Jaccard相似度 - 仅考虑是否评分，不考虑评分值
            # 创建一个二元矩阵（只考虑是否评分）
            binary_matrix = (item_user_matrix > 0).astype(np.float32)
            
            # 计算每个物品评分的用户数（每行中的1的个数）
            item_rated_counts = np.sum(binary_matrix, axis=1)
            
            # 计算物品对之间的交集数量
            intersection_matrix = np.dot(binary_matrix, binary_matrix.T)
            
            # 计算并集大小：A的评分数 + B的评分数 - 交集大小
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
        
        # 记录训练开始时的内存使用
        start_mem = memory_usage()
        print(f"训练开始时的内存使用: {start_mem:.2f} MB")
        
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
        
        # 记录矩阵创建后的内存使用
        matrix_mem = memory_usage()
        print(f"矩阵创建后的内存使用: {matrix_mem:.2f} MB")
        print(f"矩阵增加的内存: {matrix_mem - start_mem:.2f} MB")
        
        # 计算物品相似度矩阵
        self.item_similarity_matrix = self._compute_item_similarity(matrix)
        
        # 记录相似度矩阵计算后的内存使用
        sim_mem = memory_usage()
        print(f"相似度矩阵计算后的内存使用: {sim_mem:.2f} MB")
        print(f"相似度矩阵增加的内存: {sim_mem - matrix_mem:.2f} MB")
        
        # 释放原始评分矩阵的内存
        del matrix
        gc.collect()
        
        training_time = time.time() - start_time
        print(f"模型训练完成，总耗时: {training_time:.2f}秒")
        print(f"训练最终内存使用: {memory_usage():.2f} MB")
    
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
        预测指定用户对指定物品的评分
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
        
        # 确保预测在有效范围内
        return prediction
    
    def eval(self, test_df, output_file="results.txt"):
        """在测试集上评估模型性能"""
        print("在测试集上评估模型...")
        start_time = time.time()
        
        # 记录评估开始时的内存使用
        start_mem = memory_usage()
        print(f"评估开始时的内存使用: {start_mem:.2f} MB")
        
        actual = []
        predicted = []
        
        # 如果需要保存结果，打开文件
        with open(output_file, 'w') as f:
            # 写入标题行
            f.write("user_id\titem_id\tactual_rating\tpredicted_rating\n")
            
            # 遍历测试数据并保存结果
            for _, row in test_df.iterrows():
                user_id = row['user_id']
                item_id = row['item_id']
                rating = row['rating']
                
                pred = self.predict(user_id, item_id)
                
                actual.append(rating)
                predicted.append(pred)
                
                # 写入每条记录
                f.write(f"{user_id}\t{item_id}\t{rating}\t{pred:.4f}\n")
        
        mse = mean_squared_error(actual, predicted)
        rmse = sqrt(mse)
        mae = np.mean(np.abs(np.array(actual) - np.array(predicted)))
        
        eval_time = time.time() - start_time
        eval_mem = memory_usage()
        
        print(f"测试集评估完成，耗时: {eval_time:.2f}秒")
        print(f"评估结束时的内存使用: {eval_mem:.2f} MB")
        print(f"评估过程内存增加: {eval_mem - start_mem:.2f} MB")
        print(f"均方误差 (MSE): {mse:.4f}")
        print(f"均方根误差 (RMSE): {rmse:.4f}")
        print(f"MAE:{mae:.4f}")
        
        return rmse, mse, mae

def save_predictions(model, test_df, output_file):
    """保存预测结果到文件"""
    print(f"保存预测结果到 {output_file}...")
    start_time = time.time()
    
    with open(output_file, 'w') as f:
        # 写入标题行
        f.write("user_id\titem_id\tpredicted_rating\n")
        
        # 遍历测试数据并保存结果
        for _, row in test_df.iterrows():
            user_id = row['user_id']
            item_id = row['item_id']
            
            pred = model.predict(user_id, item_id)
            
            # 写入每条记录
            f.write(f"{user_id}\t{item_id}\t{pred:.4f}\n")
    
    save_time = time.time() - start_time
    print(f"预测结果保存完成，耗时: {save_time:.2f}秒")

def convert_to_required_format(input_file, output_file):
    """
    将预测结果文件从制表符分隔格式转换为指定的分组格式
    
    Parameters:
    -----------
    input_file: 输入文件路径（当前格式）
    output_file: 输出文件路径（目标格式）
    """
    print(f"转换结果格式，从 {input_file} 到 {output_file}...")
    
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
            rating = round(float(parts[2]))
            
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
    
    print(f"格式转换完成")

def load_data_to_df(file_path, test=False):
    """将数据文件加载为pandas DataFrame"""
    print(f"加载数据文件: {file_path}...")
    start_mem = memory_usage()
    
    user_item_pairs = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    print(f"文件加载到内存, 共 {len(lines)} 行")
    
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
    
    load_mem = memory_usage()
    print(f"数据加载完成，共 {len(df)} 条记录")
    print(f"数据加载使用内存: {load_mem - start_mem:.2f} MB")
    
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

@profile
def main():
    # 开启内存跟踪
    tracemalloc.start()
    
    # 记录开始时的内存使用
    start_snapshot = tracemalloc.take_snapshot()
    start_mem = memory_usage()
    print(f"开始时的内存使用: {start_mem:.2f} MB")
    
    # 加载数据
    all_train_df = load_data_to_df("data/train.txt")
    all_test_df = load_data_to_df("data/test.txt", test=True)
    
    # 创建并训练模型
    model = ImprovedItemBasedCF(
        k=30,
        sim_method='jaccard',
        shrinkage=100,
        normalize=True,
        use_baseline=True,
        regularization=0.1,
        n_epochs=10,  # 减少迭代次数以节省时间
        learning_rate=0.01
    )
    
    # 训练模型
    model.fit(all_train_df)
    
    # 保存预测结果
    output_file = 'predictions.txt'
    save_predictions(model, all_test_df, output_file)
    
    # 转换为所需格式
    convert_to_required_format(output_file, 'formatted_predictions.txt')
    
    # 记录结束时的内存使用
    end_mem = memory_usage()
    end_snapshot = tracemalloc.take_snapshot()
    
    # 显示内存统计
    print(f"结束时的内存使用: {end_mem:.2f} MB")
    print(f"总内存增加: {end_mem - start_mem:.2f} MB")
    
    # 显示详细的内存统计
    top_stats = end_snapshot.compare_to(start_snapshot, 'lineno')
    print("\n内存增长最多的前10个地方:")
    for stat in top_stats[:10]:
        print(stat)
    
    # 停止内存跟踪
    tracemalloc.stop()

if __name__ == "__main__":
    main()