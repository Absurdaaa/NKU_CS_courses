import numpy as np
import pandas as pd
import itertools
from sklearn.metrics import mean_squared_error,mean_absolute_error
from math import sqrt
from collections import defaultdict

class SVDPP:
    def __init__(self, num_users, num_items, num_factors=20, lr=0.001, reg=0.02, epochs=20):
        self.num_users = num_users
        self.num_items = num_items
        self.num_factors = num_factors
        self.lr = lr
        self.reg = reg
        self.epochs = epochs

        # 参数初始化（标准差从0.1 -> 0.01，更稳定）
        self.global_mean = 0
        self.bu = np.zeros(num_users)
        self.bi = np.zeros(num_items)
        self.pu = np.random.normal(0, 0.01, (num_users, num_factors)).astype(np.float32)
        self.qi = np.random.normal(0, 0.01, (num_items, num_factors)).astype(np.float32)
        self.yj = np.random.normal(0, 0.01, (num_items, num_factors)).astype(np.float32)

    def fit(self, ratings, implicit_feedback):
        self.global_mean = np.mean([r for (_, _, r) in ratings])

        for epoch in range(self.epochs):
            for u, i, r_ui in ratings:
                implicit_items = implicit_feedback.get(u, [])
                sqrt_Nu = np.sqrt(len(implicit_items)) if implicit_items else 1.0

                # 隐式反馈求和项
                y_sum = np.sum(self.yj[implicit_items], axis=0) if implicit_items else np.zeros(self.num_factors,
                                                                                                dtype=np.float32)
                user_vector = self.pu[u] + y_sum / sqrt_Nu

                # 预测评分
                pred = self.global_mean + self.bu[u] + self.bi[i] + np.dot(self.qi[i], user_vector)
                e_ui = r_ui - pred

                # ✅ 限制误差值范围（防止爆炸）
                e_ui = np.clip(e_ui, -5.0, 5.0)

                # 更新偏置
                self.bu[u] += self.lr * (e_ui - self.reg * self.bu[u])
                self.bi[i] += self.lr * (e_ui - self.reg * self.bi[i])

                # 更新因子（✅ 增加 clip，防止乘法爆炸）
                pu_grad = e_ui * self.qi[i] - self.reg * self.pu[u]
                qi_grad = e_ui * user_vector - self.reg * self.qi[i]
                self.pu[u] += self.lr * np.clip(pu_grad, -10, 10)
                self.qi[i] += self.lr * np.clip(qi_grad, -10, 10)

                # 更新 yj（隐式反馈因子）
                if implicit_items:
                    for j in implicit_items:
                        yj_grad = e_ui * self.qi[i] / sqrt_Nu - self.reg * self.yj[j]
                        self.yj[j] += self.lr * np.clip(yj_grad, -10, 10)

            print(f"Epoch {epoch + 1} completed.")

    def predict(self, u, i, implicit_feedback):
        """
        对用户u和物品i预测评分
        """
        implicit_items = implicit_feedback.get(u, [])
        sqrt_Nu = np.sqrt(len(implicit_items)) if implicit_items else 1.0
        y_sum = np.sum(self.yj[implicit_items], axis=0) if implicit_items else np.zeros(self.num_factors)
        user_vector = self.pu[u] + y_sum / sqrt_Nu
        return self.global_mean + self.bu[u] + self.bi[i] + np.dot(self.qi[i], user_vector)



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
    users = set([u for u, _, _ in ratings])
    items = set([i for _, i, _ in ratings])

    shuffled = ratings[:]
    np.random.shuffle(shuffled)

    train = []
    val = []
    seen_u, seen_i = set(), set()
    for r in shuffled:
        u, i, _ = r
        if len(val) < len(ratings) * val_ratio and u in seen_u and i in seen_i:
            val.append(r)
        else:
            train.append(r)
            seen_u.add(u)
            seen_i.add(i)
    return train, val

def rmse(y_true, y_pred):
    return sqrt(mean_squared_error(y_true, y_pred))

def grid_search(ratings, n_factors_list, n_epochs_list, learning_rate_list, regularization_list):
    best_rmse_score = float('inf')
    best_model = None
    best_params = None

    train_set, val_set = train_val_split(ratings)
    print("begin search")
    for n_factors, n_epochs, lr, reg in itertools.product(
        n_factors_list, n_epochs_list, learning_rate_list, regularization_list
    ):
        model = SVDPP(n_factors=n_factors, lr=lr, reg=reg, n_epochs=n_epochs)
        print("begin fit")
        model.fit(train_set)

        y_true = []
        y_pred = []
        print("begin rmse")
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

num_users = ratings_df['user_id'].max() + 1
num_items = ratings_df['item_id'].max() + 1

# 2. 训练集和验证集划分
train_data, val_data = train_val_split(ratings, val_ratio=0.2)

# 3. 构造隐式反馈（打分>=4为喜欢）
implicit_feedback = defaultdict(list)
for u, i, r in train_data:
    if r >= 4:
        implicit_feedback[u].append(i)

# 4. 训练模型
model = SVDPP(num_users, num_items, num_factors=20, epochs=20)
model.fit(train_data, implicit_feedback)

# 5. 验证集评估
y_true = []
y_pred = []
for u, i, r in val_data:
    y_true.append(r)
    y_pred.append(model.predict(u, i, implicit_feedback))

print(f"Validation RMSE: {rmse(y_true, y_pred):.4f}")

mae = mean_absolute_error(y_true, y_pred)
print(f"Validation MAE: {mae:.4f}")
# 定义搜索网格
n_factors_list = [20,25,30]
n_epochs_list = [20,25,30]
learning_rate_list = [0.001,0.005,0.01]
regularization_list = [0.01,0.02,0.04]
# 开始搜索
best_model, best_params = grid_search(
    ratings,
    n_factors_list,
    n_epochs_list,
    learning_rate_list,
    regularization_list
)