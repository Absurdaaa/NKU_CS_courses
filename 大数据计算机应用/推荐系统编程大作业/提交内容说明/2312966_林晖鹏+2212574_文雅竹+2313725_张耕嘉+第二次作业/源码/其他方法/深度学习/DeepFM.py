import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, accuracy_score
import numpy as np
import pandas as pd
from torch.optim.lr_scheduler import ReduceLROnPlateau

# === 数据加载函数 ===
def load_data_to_matrix(file_path):
    user_item_pairs = []
    with open(file_path, 'r') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        if '|' in lines[i]:
            parts = lines[i].strip().split('|')
            user_id = int(parts[0])
            item_count = int(parts[1])
            for j in range(1, item_count + 1):
                if i + j < len(lines):
                    item_parts = lines[i + j].strip().split()
                    if len(item_parts) == 2:
                        item_id = int(item_parts[0])
                        rating = int(item_parts[1])
                        user_item_pairs.append((user_id, item_id, rating))
            i += item_count + 1
        else:
            i += 1

    df = pd.DataFrame(user_item_pairs, columns=['user_id', 'item_id', 'rating'])
    unique_users = sorted(df['user_id'].unique())
    unique_items = sorted(df['item_id'].unique())
    user_to_index = {user: idx for idx, user in enumerate(unique_users)}
    item_to_index = {item: idx for idx, item in enumerate(unique_items)}
    return df, user_to_index, item_to_index, len(unique_users), len(unique_items)

# === Dataset 类 ===
class RatingDataset(Dataset):
    def __init__(self, df, user_to_index, item_to_index):
        self.user = df['user_id'].map(user_to_index).values
        self.item = df['item_id'].map(item_to_index).values
        self.rating = df['rating'].values

    def __len__(self):
        return len(self.user)

    def __getitem__(self, idx):
        return {
            'user': self.user[idx],
            'item': self.item[idx],
            'rating': self.rating[idx]
        }
        
def save_model(model, path="best_model.pth"):
    """
    保存模型参数到文件
    参数:
        model: 要保存的模型
        path: 保存模型的文件路径
    """
    torch.save(model.state_dict(), path)
    print(f"模型已保存到 {path}")
    
# === DeepFM 模型 ===
class DeepFM(nn.Module):
    def __init__(self, num_users, num_items, embedding_dim=16, hidden_dims=[32, 16]):
        super(DeepFM, self).__init__()
        self.user_embed = nn.Embedding(num_users, embedding_dim)
        self.item_embed = nn.Embedding(num_items, embedding_dim)

        self.linear_user = nn.Embedding(num_users, 1)
        self.linear_item = nn.Embedding(num_items, 1)

        self.dnn = nn.Sequential(
            nn.Linear(embedding_dim * 2, hidden_dims[0]),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dims[0], hidden_dims[1]),
            nn.ReLU()
        )
        self.output_dnn = nn.Linear(hidden_dims[-1], 1)

    def forward(self, user, item):
        user_emb = self.user_embed(user)
        item_emb = self.item_embed(item)

        fm_inter = torch.sum(user_emb * item_emb, dim=1, keepdim=True)
        linear = self.linear_user(user) + self.linear_item(item)

        dnn_input = torch.cat([user_emb, item_emb], dim=1)
        dnn_out = self.output_dnn(self.dnn(dnn_input))

        out = linear + fm_inter + dnn_out
        return out.squeeze(1)

# === 训练函数 ===
def train_model(model, train_loader,test_loader, epochs=5, lr=0.001):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=20, verbose=True)
    criterion = nn.MSELoss()
    
    best_loss = float('inf')
    patience = 20
    # no_improve_count = 0

    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch in train_loader:
            user = batch["user"].to(device).long()
            item = batch["item"].to(device).long()
            rating = batch["rating"].to(device).float()

            pred = model(user, item)
            loss = criterion(pred, rating)
            
        
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
        val_loss = evaluate_model(model, test_loader)
        if val_loss < best_loss:
            best_loss = val_loss
            no_improve_count = 0
            save_model(model,path="best_model.pth")  # 或保留当前参数
        print(f"Epoch {epoch+1}/{epochs} Loss: {total_loss / len(train_loader):.4f}")

# === 测试函数 ===
def evaluate_model(model, test_loader):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    preds, trues = [], []

    with torch.no_grad():
        for batch in test_loader:
            user = batch["user"].to(device).long()
            item = batch["item"].to(device).long()
            rating = batch["rating"].to(device).float()

            output = model(user, item)
            preds.extend(output.cpu().numpy())
            trues.extend(rating.cpu().numpy())

    preds = np.array(preds)
    trues = np.array(trues)

    # 计算误差指标
    mse = mean_squared_error(trues, preds)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(trues, preds)

    # 准确率（假设评分是离散值，四舍五入到最近整数）
    # acc = accuracy_score(trues, np.round(preds).clip(1, 5))

    print(f"Test MSE: {mse:.4f}")
    print(f"Test RMSE: {rmse:.4f}")
    print(f"Test MAE: {mae:.4f}")
    # print(f"Accuracy (rounded): {acc * 100:.2f}%")
    return rmse


def load_model(model, path="best_model.pth"):
    """
    从文件加载模型参数
    参数:
        model: 要加载参数的模型实例
        path: 模型参数文件路径
    """
    model.load_state_dict(torch.load(path))
    print(f"模型已从 {path} 加载")
    return model
# === 主流程 ===
if __name__ == "__main__":
    file_path = "data/train.txt"  # 替换成你的实际路径
    df, user_to_index, item_to_index, num_users, num_items = load_data_to_matrix(file_path)

    # 划分训练/测试集
    df_train, df_test = train_test_split(df, test_size=0.2, random_state=42)

    train_dataset = RatingDataset(df_train, user_to_index, item_to_index)
    test_dataset = RatingDataset(df_test, user_to_index, item_to_index)
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=256, shuffle=False)

    model = DeepFM(num_users=num_users, num_items=num_items)
    
    train_model(model, train_loader,test_loader, epochs=100 , lr=0.05)
    
    load_model(model, path="best_model.pth")  # 加载模型参数
    evaluate_model(model, test_loader)


# Test MSE: 333.9574
# Test RMSE: 18.2745
# Test MAE: 14.2371

"""
NCF (Neural Collaborative Filtering)：专为推荐设计，比 DeepFM 更专注于交互建模。

AutoRec：自编码器结构，适合矩阵补全。

Variational Autoencoder (VAE) for Collaborative Filtering。

Transformer-based models（如 SASRec, BERT4Rec）：用于序列推荐，更强大但更复杂。
"""