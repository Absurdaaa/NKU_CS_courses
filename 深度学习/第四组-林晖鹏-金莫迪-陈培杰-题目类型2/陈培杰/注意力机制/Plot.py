import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import os

import torch


def check_dir():
    """检查并创建 results 文件夹"""
    if not os.path.exists('results'):
        os.makedirs('results')


def plot_models_comparison(losses1, val_losses1, bleus1,
                           losses2, val_losses2, bleus2,
                           name1="Vanilla Seq2Seq", name2="Attention Seq2Seq"):
    """
    需求 1：绘制2个模型的对比图（1行3列的子图）
    """
    check_dir()
    epochs = range(1, len(losses1) + 1)

    # 设置画布大小，1行3列
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # 1. Train Loss 对比
    axes[0].plot(epochs, losses1, label=f'{name1}', marker='o', linestyle='-')
    axes[0].plot(epochs, losses2, label=f'{name2}', marker='s', linestyle='-')
    axes[0].set_title('Training Loss Comparison')
    axes[0].set_xlabel('Epochs')
    axes[0].set_ylabel('Loss')
    axes[0].legend()
    axes[0].grid(True, linestyle='--', alpha=0.6)

    # 2. Validate Loss 对比
    axes[1].plot(epochs, val_losses1, label=f'{name1}', marker='o', linestyle='-')
    axes[1].plot(epochs, val_losses2, label=f'{name2}', marker='s', linestyle='-')
    axes[1].set_title('Validation Loss Comparison')
    axes[1].set_xlabel('Epochs')
    axes[1].set_ylabel('Loss')
    axes[1].legend()
    axes[1].grid(True, linestyle='--', alpha=0.6)

    # 3. Validate BLEU 对比
    axes[2].plot(epochs, bleus1, label=f'{name1}', marker='o', linestyle='-')
    axes[2].plot(epochs, bleus2, label=f'{name2}', marker='s', linestyle='-')
    axes[2].set_title('Validation BLEU Score Comparison')
    axes[2].set_xlabel('Epochs')
    axes[2].set_ylabel('BLEU Score')
    axes[2].legend()
    axes[2].grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.savefig('results/models_comparison.png', dpi=300)
    print("对比图已保存至 results/models_comparison.png")
    plt.close()


def plot_single_model_metrics(train_losses, val_losses, val_bleus, model_name):
    """
    需求 2：绘制单个模型的3个指标（Loss使用左侧Y轴，BLEU使用右侧Y轴）
    """
    check_dir()
    epochs = range(1, len(train_losses) + 1)

    fig, ax1 = plt.subplots(figsize=(8, 6))

    # 绘制 Loss (左 Y 轴)
    color1, color2 = 'tab:red', 'tab:orange'
    ax1.set_xlabel('Epochs')
    ax1.set_ylabel('Loss', color=color1)
    line1 = ax1.plot(epochs, train_losses, color=color1, label='Train Loss', marker='o')
    line2 = ax1.plot(epochs, val_losses, color=color2, label='Validate Loss', marker='s')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True, linestyle='--', alpha=0.6)

    # 创建共享 X 轴的右 Y 轴
    ax2 = ax1.twinx()
    color3 = 'tab:blue'
    ax2.set_ylabel('BLEU Score', color=color3)
    line3 = ax2.plot(epochs, val_bleus, color=color3, label='Validate BLEU', marker='^')
    ax2.tick_params(axis='y', labelcolor=color3)

    # 合并图例
    lines = line1 + line2 + line3
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')

    plt.title(f'{model_name} - Metrics Overview')
    fig.tight_layout()

    filename = f"results/{model_name.replace(' ', '_')}_metrics.png"
    plt.savefig(filename, dpi=300)
    print(f"[{model_name}] 趋势图已保存至 {filename}")
    plt.close()


def save_test_bleu(model1_name, bleu1, model2_name, bleu2):
    """
    需求 3：保存测试集 BLEU 分数到 txt 文件
    """
    check_dir()
    filepath = 'results/test_bleu_scores.txt'
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 30 + "\n")
        f.write("Test Set BLEU Scores\n")
        f.write("=" * 30 + "\n")
        f.write(f"Model: {model1_name}\n")
        f.write(f"Score: {bleu1:.2f}\n")
        f.write("-" * 30 + "\n")
        f.write(f"Model: {model2_name}\n")
        f.write(f"Score: {bleu2:.2f}\n")
        f.write("=" * 30 + "\n")
    print(f"测试集 BLEU 分数已保存至 {filepath}")


def plot_attention_heatmap(attention_weights, model_name, lengths=None, sample_idx=None):
    """
    参数:
    - ...
    - sample_idx: 指定查看 Batch 中哪一个样本。如果为 None，则自动选择最长的。
    """
    os.makedirs('results', exist_ok=True)

    # 1. 确定要绘制的样本索引
    if sample_idx is None:
        if lengths is not None:
            sample_idx = torch.argmax(lengths).item() if torch.is_tensor(lengths) else np.argmax(lengths)
        else:
            valid_dec_lengths = (attention_weights.sum(dim=-1) > 0.5).sum(dim=-1)
            sample_idx = valid_dec_lengths.argmax().item()

    # 2. 提取该样本的注意力权重
    attention = attention_weights[sample_idx].cpu().detach().numpy()

    # 3. 截断 Padding 部分 (修复了中间包含 0 导致漏算的问题)
    # 寻找 Decoder 最后一行有效步骤的索引 (+1 得到长度)
    dec_sums = attention.sum(axis=-1)
    valid_dec_indices = np.where(dec_sums > 0.5)[0]
    real_dec_len = valid_dec_indices[-1] + 1 if len(valid_dec_indices) > 0 else attention.shape[0]

    # 寻找 Encoder 最后一列有效步骤的索引
    if lengths is not None:
        real_enc_len = lengths[sample_idx].item() if torch.is_tensor(lengths[sample_idx]) else lengths[sample_idx]
    else:
        enc_sums = attention.sum(axis=0)
        valid_enc_indices = np.where(enc_sums > 1e-4)[0]
        real_enc_len = valid_enc_indices[-1] + 1 if len(valid_enc_indices) > 0 else attention.shape[1]

    # 裁剪矩阵
    attention_cropped = attention[:real_dec_len, :real_enc_len]

    # 4. 绘制热力图
    fig_width = max(8.0, real_enc_len * 0.3)
    fig_height = max(6.0, real_dec_len * 0.3)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    sns.heatmap(attention_cropped, cmap='viridis', cbar=True, ax=ax)

    ax.set_xlabel('Encoder Position')
    ax.set_ylabel('Decoder Position')
    ax.set_title(f'{model_name} - Attention Weights Heatmap (Longest, Idx: {sample_idx})')

    fig.tight_layout()
    filename = f"results/{model_name.replace(' ', '_')}_attention_heatmap.png"
    plt.savefig(filename, dpi=300)
    print(f"[{model_name}] 注意力热力图已保存至 {filename} (尺寸: {real_dec_len}x{real_enc_len})")
    plt.close(fig)