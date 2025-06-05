import numpy as np
from collections import defaultdict
from sklearn.metrics import mean_squared_error
from math import sqrt

class SlopeOne:
    def __init__(self, min_freq=0, default_pred=0.0):
        self.deviations = defaultdict(lambda: defaultdict(float))
        self.frequencies = defaultdict(lambda: defaultdict(int))
        self.user_ratings = defaultdict(dict)
        self.min_freq = min_freq
        self.default_pred = default_pred

    def fit(self, ratings):
        """
        ratings: list of (user, item, rating)
        """
        # 存储用户评分
        for user, item, rating in ratings:
            self.user_ratings[user][item] = rating

        # 计算偏差和频次
        for user, items in self.user_ratings.items():
            for item1, rating1 in items.items():
                for item2, rating2 in items.items():
                    if item1 != item2:
                        self.deviations[item1][item2] += rating1 - rating2
                        self.frequencies[item1][item2] += 1

        # 计算平均偏差
        for item1 in self.deviations:
            for item2 in self.deviations[item1]:
                self.deviations[item1][item2] /= self.frequencies[item1][item2]

    def predict(self, user, target_item):
        numerator = 0.0
        denominator = 0

        if user not in self.user_ratings:
            return self.default_pred  # 无法预测

        for item, rating in self.user_ratings[user].items():
            if target_item in self.deviations and item in self.deviations[target_item]:
                freq = self.frequencies[target_item][item]
                if freq < self.min_freq:
                    continue

                dev = self.deviations[target_item][item]
                numerator += (rating + dev) * freq
                denominator += freq

        if denominator == 0:
            return self.default_pred

        return numerator / denominator


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

def get_train_val_split_matrix(ratings_matrix, val_ratio=0.2, seed=42):
    """
    输入：原始评分矩阵
    输出：训练矩阵、验证集列表（u, i, rating）
    """
    np.random.seed(seed)
    R = ratings_matrix.copy()
    users, items = R.nonzero()
    nonzero_indices = list(zip(users, items))
    np.random.shuffle(nonzero_indices)

    val_size = int(len(nonzero_indices) * val_ratio)
    val_indices = nonzero_indices[:val_size]

    val_set = [(u, i, R[u, i]) for u, i in val_indices]

    # 抹掉验证集评分
    for u, i in val_indices:
        R[u, i] = 0.0

    return R, val_set


def rmse(y_true, y_pred):
    return sqrt(mean_squared_error(y_true, y_pred))


def grid_search_slope_one_matrix(ratings_matrix, min_freq_list, default_pred_list):
    best_rmse_score = float('inf')
    best_model = None
    best_params = None

    R_train, val_set = get_train_val_split_matrix(ratings_matrix)

    # 构建训练集
    train_data = [(u, i, R_train[u, i]) for u in range(R_train.shape[0])
                  for i in range(R_train.shape[1]) if R_train[u, i] > 0]

    for min_freq in min_freq_list:
        for default_pred in default_pred_list:
            model = SlopeOne(min_freq=min_freq, default_pred=default_pred)
            model.fit(train_data)

            y_true, y_pred = [], []
            for u, i, true_rating in val_set:
                pred = model.predict(u, i)
                y_true.append(true_rating)
                y_pred.append(pred)

            score = rmse(y_true, y_pred)
            print(f"Params: min_freq={min_freq}, default_pred={default_pred} => RMSE: {score:.4f}")
            
            mae = np.mean(np.abs(np.array(y_true) - np.array(y_pred)))
            
            print(mae)
            print(score*score)

            if score < best_rmse_score:
                best_rmse_score = score
                best_model = model
                best_params = {
                    'min_freq': min_freq,
                    'default_pred': default_pred
                }

    print("\n✅ Best Parameters:")
    for k, v in best_params.items():
        print(f"{k}: {v}")
    print(f"📉 Validation RMSE: {best_rmse_score:.4f}")
    return best_model, best_params


if __name__ == "__main__":
    import pandas as pd

    ratings_df = load_data_to_df("data/train.txt")
    n_users = ratings_df['user_id'].max() + 1
    n_items = ratings_df['item_id'].max() + 1
    R = np.zeros((n_users, n_items))
    for row in ratings_df.itertuples(index=False):
        R[row.user_id, row.item_id] = row.rating

    min_freq_list = [2]
    default_pred_list = [0.0, 50.0, np.mean(ratings_df['rating'])]

    best_model, best_params = grid_search_slope_one_matrix(
        R,
        min_freq_list,
        default_pred_list
    )
