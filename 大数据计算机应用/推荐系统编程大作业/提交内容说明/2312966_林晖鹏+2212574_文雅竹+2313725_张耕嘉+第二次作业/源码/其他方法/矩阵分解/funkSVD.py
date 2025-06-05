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
    
    Parameters:
    -----------
    df : 数据DataFrame
    test_size : 测试集比例
    random_state : 随机种子
    
    Returns:
    --------
    训练集和测试集
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

class FunkSVD:
    """
    实现FunkSVD矩阵分解推荐算法
    """
    def __init__(self, n_factors=100, n_epochs=20, learning_rate=0.005, 
                 regularization=0.02, init_mean=0, init_std=0.1, bias_regularization=0.005):
        """
        初始化FunkSVD模型
        
        Parameters:
        -----------
        n_factors : 潜在因子数量
        n_epochs : 迭代次数
        learning_rate : 学习率
        regularization : 因子正则化参数
        init_mean : 初始化因子的均值
        init_std : 初始化因子的标准差
        bias_regularization : 偏置项正则化参数
        """
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.learning_rate = learning_rate
        self.regularization = regularization
        self.init_mean = init_mean
        self.init_std = init_std
        self.bias_regularization = bias_regularization
        
        # 模型参数
        self.global_mean = None
        self.user_biases = None
        self.item_biases = None
        self.user_factors = None
        self.item_factors = None
        
        # ID映射
        self.user_to_index = None
        self.item_to_index = None
        self.index_to_user = None
        self.index_to_item = None
        self.unique_users = None
        self.unique_items = None
        
    def fit(self, ratings_df):
        """
        训练FunkSVD模型
        
        Parameters:
        -----------
        ratings_df : 包含用户ID、物品ID和评分的DataFrame
        """
        print("训练FunkSVD模型...")
        start_time = time.time()
        
        # 提取唯一的用户ID和物品ID
        self.unique_users = sorted(ratings_df['user_id'].unique())
        self.unique_items = sorted(ratings_df['item_id'].unique())
        
        # 创建ID到索引的映射
        self.user_to_index = {user: idx for idx, user in enumerate(self.unique_users)}
        self.item_to_index = {item: idx for idx, item in enumerate(self.unique_items)}
        self.index_to_user = {idx: user for user, idx in self.user_to_index.items()}
        self.index_to_item = {idx: item for item, idx in self.item_to_index.items()}
        
        n_users = len(self.unique_users)
        n_items = len(self.unique_items)
        
        # 计算全局平均评分
        self.global_mean = ratings_df['rating'].mean()
        print(f"全局平均评分: {self.global_mean:.2f}")
        
        # 初始化偏置项和因子矩阵
        self.user_biases = np.zeros(n_users)
        self.item_biases = np.zeros(n_items)
        
        # 使用正态分布初始化因子矩阵
        self.user_factors = np.random.normal(self.init_mean, self.init_std, (n_users, self.n_factors))
        self.item_factors = np.random.normal(self.init_mean, self.init_std, (n_items, self.n_factors))
        
        # 创建训练数据
        train_data = []
        for _, row in ratings_df.iterrows():
            user_idx = self.user_to_index[row['user_id']]
            item_idx = self.item_to_index[row['item_id']]
            rating = row['rating']
            train_data.append((user_idx, item_idx, rating))
        
        # 使用随机梯度下降训练模型
        for epoch in range(self.n_epochs):
            # 打乱训练数据
            np.random.shuffle(train_data)
            
            # 记录训练误差
            train_error = 0
            
            # 更新模型参数
            for user_idx, item_idx, rating in train_data:
                # 计算预测评分
                pred = self._predict_by_index(user_idx, item_idx)
                
                # 计算误差
                error = rating - pred
                train_error += error ** 2
                
                # 更新偏置项
                self.user_biases[user_idx] += self.learning_rate * (error - self.bias_regularization * self.user_biases[user_idx])
                self.item_biases[item_idx] += self.learning_rate * (error - self.bias_regularization * self.item_biases[item_idx])
                
                # 更新因子
                user_factor = self.user_factors[user_idx]
                item_factor = self.item_factors[item_idx]
                
                # 保存旧因子用于更新
                old_user_factor = user_factor.copy()
                old_item_factor = item_factor.copy()
                
                # 更新用户因子
                self.user_factors[user_idx] += self.learning_rate * (error * old_item_factor - self.regularization * old_user_factor)
                # 更新物品因子
                self.item_factors[item_idx] += self.learning_rate * (error * old_user_factor - self.regularization * old_item_factor)
            
            # 计算当前epoch的RMSE
            train_rmse = np.sqrt(train_error / len(train_data))
            
            # 每5个epoch或最后一个epoch输出训练进度
            if (epoch + 1) % 5 == 0 or epoch == 0 or epoch == self.n_epochs - 1:
                print(f"Epoch {epoch+1}/{self.n_epochs}: 训练RMSE = {train_rmse:.4f}")
        
        training_time = time.time() - start_time
        print(f"训练完成，耗时: {training_time:.2f}秒")
    
    def _predict_by_index(self, user_idx, item_idx):
        """
        基于索引预测评分
        
        Parameters:
        -----------
        user_idx : 用户索引
        item_idx : 物品索引
        
        Returns:
        --------
        预测的评分值
        """
        # 基础预测 = 全局平均 + 用户偏差 + 物品偏差
        baseline_pred = self.global_mean + self.user_biases[user_idx] + self.item_biases[item_idx]
        
        # 矩阵分解部分 = 用户因子与物品因子的点积
        mf_pred = np.dot(self.user_factors[user_idx], self.item_factors[item_idx])
        
        # 组合预测
        return baseline_pred + mf_pred
        
    def predict(self, user_id, item_id):
        """
        预测指定用户对指定物品的评分
        
        Parameters:
        -----------
        user_id : 用户ID
        item_id : 物品ID
        
        Returns:
        --------
        预测的评分值
        """
        # 如果用户或物品不在训练集中
        if user_id not in self.user_to_index or item_id not in self.item_to_index:
            # 返回全局平均评分
            return self.global_mean
        
        user_idx = self.user_to_index[user_id]
        item_idx = self.item_to_index[item_id]
        
        return self._predict_by_index(user_idx, item_idx)
    
    def compute_rmse(self, ratings_df):
        """
        计算RMSE (均方根误差)
        
        Parameters:
        -----------
        ratings_df : 包含用户ID、物品ID和评分的DataFrame
        
        Returns:
        --------
        RMSE值
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
        
        Parameters:
        -----------
        test_df : 测试数据DataFrame
        
        Returns:
        --------
        RMSE和MSE值
        """
        print("在测试集上评估FunkSVD模型...")
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
        mae = np.mean(np.abs(np.array(actual) - np.array(predicted)))
        
        eval_time = time.time() - start_time
        
        print(f"测试集评估完成，耗时: {eval_time:.2f}秒")
        print(f"均方误差 (MSE): {mse:.4f}")
        print(f"均方根误差 (RMSE): {rmse:.4f}")
        print(f"平均绝对误差 (MAE): {mae:.4f}")
        
        return rmse, mse

def predict_for_test_file(model, test_file, output_file):
    """
    为测试文件生成预测结果并输出到文件
    
    Parameters:
    -----------
    model : 训练好的模型
    test_file : 测试数据文件路径
    output_file : 输出文件路径
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

def optimize_funksvd_parameters(train_df, test_df, random_state=42):
    """
    优化FunkSVD算法的参数
    
    Parameters:
    -----------
    train_df : 训练数据DataFrame
    test_df : 测试数据DataFrame
    random_state : 随机种子
    
    Returns:
    --------
    最优参数组合
    """
    print("开始FunkSVD参数优化...")
    
    # 定义要测试的参数
    n_factors_list = [50, 100]
    n_epochs_list = [20, 30]
    learning_rate_list = [0.005, 0.01]
    regularization_list = [0.02, 0.05]
    
    best_rmse = float('inf')
    best_params = None
    
    results = []
    
    # 为了节省时间，只测试部分组合
    for n_factors in n_factors_list:
        for n_epochs in n_epochs_list:
            for learning_rate in learning_rate_list:
                for regularization in regularization_list:
                    print(f"\n测试参数: n_factors={n_factors}, n_epochs={n_epochs}, "
                          f"learning_rate={learning_rate}, regularization={regularization}")
                    
                    # 设置随机种子
                    np.random.seed(random_state)
                    
                    # 创建并训练模型
                    model = FunkSVD(n_factors=n_factors, n_epochs=n_epochs, 
                                    learning_rate=learning_rate, regularization=regularization)
                    model.fit(train_df)
                    
                    # 评估模型
                    rmse, mse = model.eval(test_df)
                    
                    results.append({
                        'n_factors': n_factors,
                        'n_epochs': n_epochs,
                        'learning_rate': learning_rate,
                        'regularization': regularization,
                        'rmse': rmse,
                        'mse': mse
                    })
                    
                    # 更新最佳参数
                    if rmse < best_rmse:
                        best_rmse = rmse
                        best_params = (n_factors, n_epochs, learning_rate, regularization)
    
    # 打印最优参数和结果
    if best_params:
        n_factors, n_epochs, learning_rate, regularization = best_params
        print(f"\n最优参数: n_factors={n_factors}, n_epochs={n_epochs}, "
              f"learning_rate={learning_rate}, regularization={regularization}")
        print(f"最佳RMSE: {best_rmse:.4f}")
        
        # 打印所有结果（按RMSE排序）
        results_df = pd.DataFrame(results).sort_values('rmse')
        print("\n所有参数组合的结果（按RMSE排序）:")
        print(results_df)
        
        return best_params
    
    return None

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
        best_params = optimize_funksvd_parameters(train_df, test_df)
        if best_params:
            n_factors, n_epochs, learning_rate, regularization = best_params
            # 使用最佳参数训练最终模型
            model = FunkSVD(n_factors=n_factors, n_epochs=n_epochs,
                          learning_rate=learning_rate, regularization=regularization)
        else:
            # 使用默认参数
            model = FunkSVD()
    else:
        # 使用默认参数
        model = FunkSVD(n_factors=100, n_epochs=20, learning_rate=0.005, regularization=2)

    # 训练最终模型
    model.fit(train_df)

    # 在测试集上评估
    rmse, mse = model.eval(test_df)

#     # 可选：为测试文件生成预测
#     # predict_for_test_file(model, "data/test.txt", "data/funksvd_predictions.txt")

# import pandas as pd
# import numpy as np


# def grid_search_funksvd(train_df, val_df,
#                         n_factors_list=[80, 100, 120],
#                         n_epochs_list=[20, 25, 30],  # 训练更充分
#                         learning_rate_list=[0.0005, 0.001, 0.002],
#                         regularization_list=[0.1, 0.15, 0.2],
#                         bias_reg_list=[0.005],
#                         random_state=42):
#     """
#     使用网格搜索寻找FunkSVD的最优超参数组合

#     参数：
#     ----------
#     train_df : 训练集DataFrame
#     val_df : 验证集DataFrame
#     n_factors_list : 潜在因子数列表
#     n_epochs_list : 训练轮数列表
#     learning_rate_list : 学习率列表
#     regularization_list : 因子正则化列表
#     bias_reg_list : 偏置正则化列表
#     random_state : 随机种子

#     返回：
#     ----------
#     best_params : 最优参数字典
#     best_rmse : 最优RMSE
#     results_df : 所有实验结果的DataFrame
#     """
#     np.random.seed(random_state)
#     best_rmse = float('inf')
#     best_params = None
#     results = []

#     total_tests = (len(n_factors_list) * len(n_epochs_list) * len(learning_rate_list)
#                    * len(regularization_list) * len(bias_reg_list))
#     print(f"开始调参，共测试{total_tests}组参数组合...")

#     for n_factors in n_factors_list:
#         for n_epochs in n_epochs_list:
#             for lr in learning_rate_list:
#                 for reg in regularization_list:
#                     for bias_reg in bias_reg_list:
#                         print(f"\n测试参数: n_factors={n_factors}, n_epochs={n_epochs}, "
#                               f"learning_rate={lr}, regularization={reg}, bias_reg={bias_reg}")

#                         model = FunkSVD(n_factors=n_factors, n_epochs=n_epochs,
#                                         learning_rate=lr, regularization=reg,
#                                         bias_regularization=bias_reg)
#                         model.fit(train_df)
#                         rmse = model.eval(val_df)[0]
#                         print(f"验证集RMSE: {rmse:.4f}")

#                         results.append({
#                             'n_factors': n_factors,
#                             'n_epochs': n_epochs,
#                             'learning_rate': lr,
#                             'regularization': reg,
#                             'bias_regularization': bias_reg,
#                             'rmse': rmse
#                         })

#                         if rmse < best_rmse:
#                             best_rmse = rmse
#                             best_params = {
#                                 'n_factors': n_factors,
#                                 'n_epochs': n_epochs,
#                                 'learning_rate': lr,
#                                 'regularization': reg,
#                                 'bias_regularization': bias_reg
#                             }

#     results_df = pd.DataFrame(results).sort_values('rmse')
#     print(f"\n最优参数组合: {best_params}")
#     print(f"最优验证集RMSE: {best_rmse:.4f}")
#     return best_params, best_rmse, results_df


# # 先加载数据和划分训练、验证集（例如20%为验证集）
# ratings_df = load_data_to_df("data/train.txt")
# train_df, val_df = train_test_split(ratings_df, test_size=0.2, random_state=42)

# # 调用自动调参
# best_params, best_rmse, all_results = grid_search_funksvd(train_df, val_df)

'''
全局平均评分: 69.90
Epoch 1/20: 训练RMSE = 19.2722
Epoch 5/20: 训练RMSE = 15.4651
Epoch 10/20: 训练RMSE = 11.7171
Epoch 15/20: 训练RMSE = 10.4247
Epoch 20/20: 训练RMSE = 10.0058
训练完成，耗时: 23.44秒
在测试集上评估FunkSVD模型...
测试集评估完成，耗时: 0.62秒
均方误差 (MSE): 293.1474
均方根误差 (RMSE): 17.1215
'''