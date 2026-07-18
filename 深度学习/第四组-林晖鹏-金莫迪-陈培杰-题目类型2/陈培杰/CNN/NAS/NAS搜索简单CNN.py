import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.datasets as datasets
import torchvision.transforms as T
import os
from torch.utils.data import DataLoader, Dataset, Subset
import torch.optim as optim


def get_data():
    transforms = T.Compose([
        T.ToTensor(),
        T.Normalize(mean=(0.4914, 0.4822, 0.4465), std=(0.2023, 0.1994, 0.2010))
    ])
    train_data = datasets.CIFAR10('data', train=True, transform=transforms, download=True)

    # 在 NAS 中，训练集通常被分为两部分：
    # 一半用于更新网络权重 (w)，一半用于更新架构参数 (alpha)
    num_train = len(train_data)
    indices = list(range(num_train))
    split = num_train // 2

    train_w_data = Subset(train_data, indices[split:])
    train_a_data = Subset(train_data, indices[:split])

    w_loader = DataLoader(train_w_data, batch_size=32, shuffle=True)
    a_loader = DataLoader(train_a_data, batch_size=32, shuffle=True)

    return w_loader, a_loader

# ==========================================
# 1. 定义搜索空间中的原子操作 (Operations)
# ==========================================
# 3 / 5
class ConvBNReLU(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size):
        super(ConvBNReLU, self).__init__()
        padding = (kernel_size - 1) // 2
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=kernel_size, stride=1, padding=padding, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )
    def forward(self, x):
        return self.conv(x)

class MaxPool(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(MaxPool, self).__init__()
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

    def forward(self, x):
        out = self.pool(x)
        return out

# 跳跃连接操作 (Identity)
class SkipConnect(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(SkipConnect, self).__init__()
        if in_channels == out_channels:
            self.conv = nn.Identity()
        else:
            self.conv = nn.Sequential(
                nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=1, bias=False),
                nn.BatchNorm2d(out_channels),
                nn.ReLU(True)
            )
    def forward(self, x):
        return self.conv(x)


# ==========================================
# 2. 定义混合算子层 (Mixed Layer)
# ==========================================

class MixedLayer(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(MixedLayer, self).__init__()
        self.ops = nn.ModuleList([
            ConvBNReLU(in_channels, out_channels, kernel_size=3),
            ConvBNReLU(in_channels, out_channels, kernel_size=5),
            SkipConnect(in_channels, out_channels)
        ])
    def forward(self, x, weights):
        # 现在的 Output = weight_3x3 * Conv3(x) + weight_5x5 * Conv5(x)
        return sum(w * op(x) for w, op in zip(weights, self.ops))

# ==========================================
# 3. 定义整体超网模型 (Supernet)
# ==========================================
class SuperNet(nn.Module):
    def __init__(self, num_classes=10, k_max=4):
        super(SuperNet, self).__init__()

        self.first_conv = nn.Sequential(
            nn.Conv2d(in_channels=3, out_channels=32, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True)
        )

        # 定义宏观网络拓扑（Macro-architecture）
        self.layers = nn.ModuleList()
        # 定义宏观网络拓扑配置: (输入通道, 输出通道, 是否在末尾加池化)
        # 按照 32->16->8->4 的尺寸变化，只有前 3 个 stage 需要池化
        stage_config = [
            # [in_channels, out_channels, use_pool]
            [32, 64, True],     # Stage 1: 输出 64 x 16 x 16
            [64, 128, True],    # Stage 2: 输出 128 x 8 x 8
            [128, 256, True],   # Stage 3: 输出 256 x 4 x 4
            [256, 512, False]   # Stage 4: 输出 512 x 4 x 4 (不加池化)
        ]

        self.search_num_layers = 0  # 用于记录总共有多少个搜索层
        for in_channels, out_channels, use_pool in stage_config:
            # 1. 每一阶段固定有【1 层升维搜索层】
            self.layers.append(MixedLayer(in_channels, out_channels))
            self.search_num_layers += 1

            # 2. 紧接着有【k_max 层通道不变的搜索层】
            for k in range(k_max):
                self.layers.append(MixedLayer(out_channels, out_channels))
                self.search_num_layers += 1

            # 3. 根据配置决定是否在末尾加【固定降采样层】
            if use_pool:
                self.layers.append(MaxPool(out_channels, out_channels))

        # 结尾固定结构：AdaptiveAveragePool2d + 全连接层
        self.last_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Linear(512, num_classes)

        # ==========================================
        # 架构参数 (Architecture Parameters) 注册
        # ==========================================
        # 每个 MixedLayer 有 3 个候选算子 (3x3, 5x5, SkipConnect)
        self.num_ops = 3

        # 现在 alphas 的形状会自动根据 stage 数量和 k_max 计算出来
        # 例如 4个阶段，每个阶段 (1 + 4) = 5 个搜索层，总共就是 20 层。形状为 [20, 3]
        self.alphas = nn.Parameter(data=1e-3 * torch.randn(size=(self.search_num_layers, self.num_ops)))

    def forward(self, x):
        x = self.first_conv(x)

        # 在特征传播前，将当前的 alphas 转化为概率权重
        layer_weights = torch.sigmoid(self.alphas)

        search_layer_idx = 0
        for layer in self.layers:
            if isinstance(layer, MixedLayer):
                # 遇到搜索层，传入对应的概率权重
                x = layer(x, layer_weights[search_layer_idx])
                search_layer_idx += 1
            else:
                x = layer(x)

        x = self.last_pool(x)
        x = x.view(x.shape[0], -1)
        x = self.classifier(x)
        return x

    def get_derived_architecture(self, max_skips=5):
        """训练完成后，获取最终的离散网络结构"""
        """带有 P-DARTS 风格全局硬截断的离散化过程"""
        arch = []
        op_names = ['Conv3x3', 'Conv5x5', 'SkipConnect']

        with torch.no_grad():
            # 1. 获取所有层的架构权重 (转为 numpy 方便处理)
            alphas_np = self.alphas.detach().cpu().numpy()
            # 2. 提取所有层 SkipConnect (索引为 2) 的权重得分
            skip_scores = alphas_np[:, 2]
            # 3. 确定允许保留的 SkipConnect 的最低门槛分数
            # 降序排列后，取第 max_skips 个分数作为及格线
            if len(skip_scores) > max_skips:
                skip_threshold = sorted(skip_scores, reverse=True)[max_skips - 1]
            else:
                skip_threshold = -float('inf')

            # 记录实际已保留的 Skip 数量 (作为双重保险，防止分数完全相同导致超标)
            skip_count = 0

            # 4. 逐层推导最终结构
            for i in range(self.search_num_layers):
                scores = alphas_np[i]

                # 按得分从大到小排序，获取算子索引
                sorted_indices = scores.argsort()[::-1]
                # 既然 forward 用了 Sigmoid，这里直接对原始 alphas 取 argmax 即可
                # 默认取当前层得分最高的算子
                best_candidate = sorted_indices[0]

                if best_candidate == 2:
                    if scores[2] >= skip_threshold and skip_count <= max_skips:
                        skip_count += 1
                    else:
                        best_candidate = sorted_indices[1]

                arch.append(f"Layer_{i + 1}: {op_names[best_candidate]}")
        return arch


def train_model(model, w_loader, a_loader, criterion, optimizer_w, optimizer_a, device, epochs=50):
    os.makedirs('results', exist_ok=True)

    # 设定预热的 Epoch 数量，比如前 15 个 Epoch 只训练权重
    warmup_epochs = 15

    f_loss = open('results/loss_log.txt', 'w', encoding='utf-8')
    f_arch = open('results/arch_log.txt', 'w', encoding='utf-8')

    model.train()
    for epoch in range(epochs):
        # 将 loader_a 转为迭代器，以便在每个 w 的步骤前走一步 a
        iter_a = iter(a_loader)

        for step, (inputs_w, targets_w) in enumerate(w_loader):
            inputs_w, targets_w = inputs_w.to(device), targets_w.to(device)

            # --- Phase 1: 更新架构参数 alpha (使用验证数据) ---
            if epoch >= warmup_epochs:
                try:
                    inputs_a, targets_a = next(iter_a)
                except StopIteration:
                    iter_a = iter(a_loader)
                    inputs_a, targets_a = next(iter_a)

                inputs_a, targets_a = inputs_a.to(device), targets_a.to(device)

                optimizer_a.zero_grad()
                outputs_a = model(inputs_a)
                loss_a = criterion(outputs_a, targets_a)

                # ==========================================
                # FairDARTS: 引入 0-1 惩罚项
                # ==========================================
                alphas_sigmoid = torch.sigmoid(model.alphas)
                loss_01 = -torch.mean((alphas_sigmoid - 0.5) ** 2)

                loss_a = loss_a + 1.0 * loss_01

                loss_a.backward()
                optimizer_a.step()
            else:
                # 在预热期，为了防止打印时 loss_a 报错，给它一个默认值或者跳过计算
                loss_a = torch.tensor(0.0)

            # --- Phase 2: 更新网络权重 w (使用训练数据) ---
            optimizer_w.zero_grad()
            outputs_w = model(inputs_w)
            loss_w = criterion(outputs_w, targets_w)
            loss_w.backward()
            optimizer_w.step()

            if step % 100 == 0:
                loss_str = f"Epoch [{epoch + 1}/{epochs}] Step {step} | Loss W: {loss_w.item():.4f} | Loss A: {loss_a.item():.4f}"
                print(loss_str)
                f_loss.write(loss_str + '\n')
                f_loss.flush()

        current_arch = model.get_derived_architecture()
        alphas_matrix = torch.sigmoid(model.alphas).detach().cpu().numpy()
        arch_str_1 = f"==> Epoch {epoch + 1} 结束，当前搜索到的结构偏好: {current_arch}"
        arch_str_2 = f"==> 当前架构权重 (Alphas):\n{alphas_matrix}"

        # 打印到终端
        print(arch_str_1)
        print(arch_str_2)

        # 写入第二个 txt 并立即刷新到硬盘
        f_arch.write(arch_str_1 + '\n')
        f_arch.write(arch_str_2 + '\n')
        f_arch.write("-" * 50 + '\n')  # 加一条分割线，方便阅读
        f_arch.flush()

    f_loss.close()
    f_arch.close()


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Using: {device}')

    w_loader, a_loader = get_data()

    model = SuperNet().to(device)
    criterion = nn.CrossEntropyLoss()

    # 优化器 1：负责更新常规网络权重 (w)
    optimizer_w = optim.SGD(
        [p for n, p in model.named_parameters() if n != 'alphas'],
        lr=0.025, momentum=0.9, weight_decay=3e-4
    )

    # 优化器 2：负责更新架构参数 (alphas)
    optimizer_a = optim.Adam(
        [model.alphas],
        lr=3e-4, weight_decay=0
    )

    train_model(model, w_loader, a_loader, criterion, optimizer_w, optimizer_a, device)


if __name__ == '__main__':
    main()




