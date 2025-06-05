import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np
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



# === 数据集定义 ===
class RatingDataset(Dataset):
    def __init__(self, df):
        self.users = torch.tensor(df['user'].values, dtype=torch.long)
        self.items = torch.tensor(df['item'].values, dtype=torch.long)
        self.ratings = torch.tensor(df['rating'].values, dtype=torch.float32)

    def __len__(self):
        return len(self.users)

    def __getitem__(self, idx):
        return self.users[idx], self.items[idx], self.ratings[idx]

# === NCF 模型 ===
class NCF(nn.Module):
    def __init__(self, num_users, num_items, emb_size=16, hidden_dims=[64, 32, 16]):
        super(NCF, self).__init__()
        self.user_emb_gmf = nn.Embedding(num_users, emb_size)
        self.item_emb_gmf = nn.Embedding(num_items, emb_size)
        self.user_emb_mlp = nn.Embedding(num_users, emb_size)
        self.item_emb_mlp = nn.Embedding(num_items, emb_size)

        self.mlp = nn.Sequential(
            nn.Linear(emb_size * 2, hidden_dims[0]),
            nn.ReLU(),
            nn.Linear(hidden_dims[0], hidden_dims[1]),
            nn.ReLU(),
            nn.Linear(hidden_dims[1], hidden_dims[2]),
            nn.ReLU()
        )

        self.final = nn.Linear(hidden_dims[2] + emb_size, 1)

    def forward(self, user, item):
        gmf_user = self.user_emb_gmf(user)
        gmf_item = self.item_emb_gmf(item)
        gmf_out = gmf_user * gmf_item

        mlp_user = self.user_emb_mlp(user)
        mlp_item = self.item_emb_mlp(item)
        mlp_out = self.mlp(torch.cat([mlp_user, mlp_item], dim=-1))

        concat = torch.cat([gmf_out, mlp_out], dim=-1)
        output = self.final(concat)
        return output.squeeze()

# === 训练函数 ===
def train_ncf(df, user_to_index, item_to_index, num_users, num_items,
              epochs=50, batch_size=128, lr=0.05):

    # 映射 user 和 item 到索引
    df['user'] = df['user_id'].map(user_to_index)
    df['item'] = df['item_id'].map(item_to_index)
    
    # 对评分进行归一化
    min_rating = df['rating'].min()
    max_rating = df['rating'].max()
    df['rating'] = (df['rating'] - min_rating) / (max_rating - min_rating)

    # 划分训练集和测试集（2:8）
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)

    train_loader = DataLoader(RatingDataset(train_df), batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(RatingDataset(test_df), batch_size=batch_size)

    # 设备选择
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 初始化模型
    model = NCF(num_users, num_items).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5, verbose=True)
    
    best_loss = float('inf')

    # === 训练过程 ===
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0
        for user, item, rating in train_loader:
            user, item, rating = user.to(device), item.to(device), rating.to(device)
            pred = model(user, item)
            loss = criterion(pred, rating)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f"Epoch {epoch}/{epochs}, Loss: {total_loss:.4f}")

    # === 测试集评估 ===
    model.eval()
    preds, targets = [], []
    with torch.no_grad():
        for user, item, rating in test_loader:
            user, item = user.to(device), item.to(device)
            pred = model(user, item).cpu().numpy()
            preds.extend(pred)
            targets.extend(rating.numpy())

    # preds = np.array(preds)
    # targets = np.array(targets)
    
    # 反归一化评分
    preds = np.array(preds) * (max_rating - min_rating) + min_rating
    targets = np.array(targets) * (max_rating - min_rating) + min_rating
    
    mse = np.mean((preds - targets) ** 2)
    rmse = np.sqrt(mse)
    mae = np.mean(np.abs(preds - targets))

    print(f"\nTest MSE: {mse:.4f}")
    print(f"Test RMSE: {rmse:.4f}")
    print(f"Test MAE: {mae:.4f}")


# 加载数据
df, user_to_index, item_to_index, num_users, num_items = load_data_to_matrix('data/train.txt')

# 训练 NCF 模型
train_ncf(df, user_to_index, item_to_index, num_users, num_items, epochs=25)

# Test MSE: 346.1344
# Test RMSE: 18.6047
# Test MAE: 14.3145