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



class BaselineModel:
    """
    基线预测算法实现
    预测公式: rating = global_mean + user_bias + item_bias
    """
    def __init__(self, regularization=0.1, n_epochs=20, learning_rate=0.005):
        """
        初始化基线预测模型
        
        Parameters:
        -----------
        regularization : 正则化参数，防止过拟合
        n_epochs : 迭代次数
        learning_rate : 学习率
        """
        self.regularization = regularization
        self.n_epochs = n_epochs
        self.learning_rate = learning_rate
        self.global_mean = None
        self.user_biases = {}
        self.item_biases = {}
        
    def fit(self, ratings_df):
        """
        训练基线预测模型
        
        Parameters:
        -----------
        ratings_df : 包含用户ID、物品ID和评分的DataFrame
        """
        print("训练基线预测模型...")
        start_time = time.time()
        
        # 计算全局平均评分
        self.global_mean = ratings_df['rating'].mean()
        print(f"全局平均评分: {self.global_mean:.2f}")
        
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
            
            # 计算当前epoch的训练误差
            if (epoch + 1) % 5 == 0 or epoch == 0:
                train_rmse = self.compute_rmse(ratings_df)
                print(f"Epoch {epoch+1}/{self.n_epochs}: 训练RMSE = {train_rmse:.4f}")
        
        training_time = time.time() - start_time
        print(f"训练完成，耗时: {training_time:.2f}秒")
        
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
        # 获取用户偏差，如果用户不存在则为0
        user_bias = self.user_biases.get(user_id, 0)
        
        # 获取物品偏差，如果物品不存在则为0
        item_bias = self.item_biases.get(item_id, 0)
        
        # 预测评分
        predicted_rating = self.global_mean + user_bias + item_bias
        
        return predicted_rating
    
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
        mae = np.mean(np.abs(np.array(actual) - np.array(predicted)))
        
        
        eval_time = time.time() - start_time
        
        print(f"测试集评估完成，耗时: {eval_time:.2f}秒")
        print(f"均方误差 (MSE): {mse:.4f}")
        print(f"均方根误差 (RMSE): {rmse:.4f}")
        print(f"均方误差 (MAE): {mae:.4f}")
        
        return rmse, mse

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

def predict_for_test_file(model, train_file, test_file, output_file):
    """
    为测试文件生成预测结果并输出到文件
    
    Parameters:
    -----------
    model : 训练好的模型
    train_file : 训练数据文件路径
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

if __name__ == "__main__":
    # 加载数据
    print("加载数据...")
    ratings_df = load_data_to_df("data/train.txt")
    print(f"加载了 {len(ratings_df)} 条评分记录")
    
    # 分割训练集和测试集
    print("分割训练集和测试集...")
    train_df, test_df = train_test_split(ratings_df, test_size=0.2, random_state=42)
    print(f"训练集: {len(train_df)} 条记录, 测试集: {len(test_df)} 条记录")
    
    # 训练模型
    model = BaselineModel(regularization=0.1, n_epochs=20, learning_rate=0.005)
    model.fit(train_df)
    
    # 在测试集上评估
    rmse, mse = model.eval(test_df)
    
    # 可选：为测试文件生成预测
    # 如果存在测试文件，可以取消下面的注释来生成预测
    # predict_for_test_file(model, "../data/train.txt", "../data/test.txt", "../data/baseline_predictions.txt")
