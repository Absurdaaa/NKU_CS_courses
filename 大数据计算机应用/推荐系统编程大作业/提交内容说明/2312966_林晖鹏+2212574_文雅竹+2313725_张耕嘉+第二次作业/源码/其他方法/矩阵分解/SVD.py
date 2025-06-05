import numpy as np
import pandas as pd
import itertools
from sklearn.metrics import mean_squared_error
from math import sqrt
from collections import defaultdict

class SVD:
    def __init__(self, n_factors=20, lr=0.005, reg=0.02, n_epochs=20):
        self.n_factors = n_factors
        self.lr = lr
        self.reg = reg
        self.n_epochs = n_epochs

    def fit(self, ratings):
        """
        ratings: list of (user, item, rating) tuples
        """
        self.user_map = {u: i for i, u in enumerate(set(r[0] for r in ratings))}
        self.item_map = {i: j for j, i in enumerate(set(r[1] for r in ratings))}
        self.user_inv_map = {i: u for u, i in self.user_map.items()}
        self.item_inv_map = {j: i for i, j in self.item_map.items()}

        n_users = len(self.user_map)
        n_items = len(self.item_map)

        self.mu = np.mean([r for _, _, r in ratings])

        # 初始化参数
        self.bu = np.zeros(n_users)
        self.bi = np.zeros(n_items)
        self.P = np.random.normal(scale=0.1, size=(n_users, self.n_factors))
        self.Q = np.random.normal(scale=0.1, size=(n_items, self.n_factors))

        # SGD训练
        for epoch in range(self.n_epochs):
            np.random.shuffle(ratings)
            for user, item, r in ratings:
                u = self.user_map[user]
                i = self.item_map[item]
                pred = self.mu + self.bu[u] + self.bi[i] + np.dot(self.P[u], self.Q[i])
                err = r - pred

                # 更新参数
                self.bu[u] += self.lr * (err - self.reg * self.bu[u])
                self.bi[i] += self.lr * (err - self.reg * self.bi[i])
                self.P[u] += self.lr * (err * self.Q[i] - self.reg * self.P[u])
                self.Q[i] += self.lr * (err * self.P[u] - self.reg * self.Q[i])
            # print(f"Epoch {epoch+1} completed.")

    def predict(self, user, item):
        if user not in self.user_map or item not in self.item_map:
            return self.mu
        u = self.user_map[user]
        i = self.item_map[item]
        pred = self.mu + self.bu[u] + self.bi[i] + np.dot(self.P[u], self.Q[i])
        return pred


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

def train_val_split(ratings, val_ratio=0.2, seed=42):
    np.random.seed(seed)
    shuffled = ratings[:]
    np.random.shuffle(shuffled)
    cut = int(len(shuffled) * (1 - val_ratio))
    return shuffled[:cut], shuffled[cut:]

def rmse(y_true, y_pred):
    return sqrt(mean_squared_error(y_true, y_pred))

def grid_search(ratings, n_factors_list, n_epochs_list, learning_rate_list, regularization_list):
    best_rmse_score = float('inf')
    best_model = None
    best_params = None

    train_set, val_set = train_val_split(ratings)

    for n_factors, n_epochs, lr, reg in itertools.product(
        n_factors_list, n_epochs_list, learning_rate_list, regularization_list
    ):
        model = SVD(n_factors=n_factors, lr=lr, reg=reg, n_epochs=n_epochs)
        model.fit(train_set)

        y_true = []
        y_pred = []

        for user, item, rating in val_set:
            pred = model.predict(user, item)
            y_true.append(rating)
            y_pred.append(pred)

        score = rmse(y_true, y_pred)

        print(f"Params: n_factors={n_factors}, n_epochs={n_epochs}, lr={lr}, reg={reg} => RMSE: {score:.4f}")

        if score < best_rmse_score:
            best_rmse_score = score
            best_model = model
            best_params = {
                'n_factors': n_factors,
                'n_epochs': n_epochs,
                'learning_rate': lr,
                'regularization': reg
            }

    print("\nBest Parameters:")
    for k, v in best_params.items():
        print(f"{k}: {v}")
    print(f"Validation RMSE: {best_rmse_score:.4f}")
    return best_model, best_params

# 加载数据
ratings_df = load_data_to_df("data/train.txt")
ratings = list(ratings_df.itertuples(index=False, name=None))

# 定义搜索网格
n_factors_list = [80, 100, 120]
n_epochs_list = [20, 25, 30]
learning_rate_list = [0.0005, 0.001, 0.002]
regularization_list = [0.1, 0.15, 0.2]

# 开始搜索
best_model, best_params = grid_search(
    ratings,
    n_factors_list,
    n_epochs_list,
    learning_rate_list,
    regularization_list
)
