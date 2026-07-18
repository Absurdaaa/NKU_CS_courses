import math
import os

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from sklearn.manifold import TSNE
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score


def plot_learning_curves(results_dict):
    """
    绘制 6 个模型的 Train Loss, Val Loss, Val Acc 对比图 (1行3列)
    results_dict 结构示例:
    {
        'rnn1': {'train_losses': [...], 'validate_losses': [...], 'validate_accuracy': [...]},
        'rnn2': {...},
        ...
    }
    """
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    model_names = list(results_dict.keys())

    # 1. 绘制 Train Loss
    for name in model_names:
        axes[0].plot(results_dict[name]['train_losses'], label=name)
    axes[0].set_title('Training Loss')
    axes[0].set_xlabel('Epochs')
    axes[0].set_ylabel('Loss')
    axes[0].legend()
    axes[0].grid(True, linestyle='--', alpha=0.7)

    # 2. 绘制 Validation Loss
    for name in model_names:
        axes[1].plot(results_dict[name]['validate_losses'], label=name)
    axes[1].set_title('Validation Loss')
    axes[1].set_xlabel('Epochs')
    axes[1].set_ylabel('Loss')
    axes[1].legend()
    axes[1].grid(True, linestyle='--', alpha=0.7)

    # 3. 绘制 Validation Accuracy
    for name in model_names:
        axes[2].plot(results_dict[name]['validate_accuracy'], label=name)
    axes[2].set_title('Validation Accuracy')
    axes[2].set_xlabel('Epochs')
    axes[2].set_ylabel('Accuracy')
    axes[2].legend()
    axes[2].grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()
    plt.savefig("results/learning_curves_comparison.png", dpi=300)
    plt.close()


def plot_confusion_matrices(results_dict, class_names=None):
    """
    绘制 6 个模型的混淆矩阵热力图 (2行3列布局)
    要求 results_dict 中包含 'y_true' 和 'y_pred'
    """
    model_names = list(results_dict.keys())

    # 根据模型数量动态决定行数和列数（你刚好有 6 个模型，2x3 完美契合）
    rows, cols = 2, 3
    fig, axes = plt.subplots(rows, cols, figsize=(18, 10))
    axes = axes.flatten()  # 展平为一维方便循环

    for i, name in enumerate(model_names):
        if i >= len(axes):
            break

        y_true = results_dict[name]['y_true']
        y_pred = results_dict[name]['y_pred']

        cm = confusion_matrix(y_true, y_pred)

        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[i],
                    xticklabels=class_names, yticklabels=class_names)
        axes[i].set_title(f'{name} Confusion Matrix')
        axes[i].set_xlabel('Predicted Label')
        axes[i].set_ylabel('True Label')

    plt.tight_layout()
    plt.savefig("results/confusion_matrices_grid.png", dpi=300)
    plt.close()


def save_metrics_to_txt(results_dict, filename="results/evaluation_reports.txt", class_names=None):
    """
    将混淆矩阵和分类报告 (Classification Report) 输出到同一个 TXT 文件中
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 50 + "\n")
        f.write("MODEL EVALUATION REPORTS\n")
        f.write("=" * 50 + "\n\n")

        for name, data in results_dict.items():
            y_true = data['y_true']
            y_pred = data['y_pred']

            f.write(f"--- Model: {name} ---\n\n")

            # 1. 写入混淆矩阵
            cm = confusion_matrix(y_true, y_pred)
            f.write("Confusion Matrix:\n")
            np.savetxt(f, cm, fmt='%d', delimiter='\t')
            f.write("\n")

            # 2. 写入分类报告
            target_names = [str(c) for c in class_names] if class_names else None
            report = classification_report(y_true, y_pred, target_names=target_names, zero_division=0)
            f.write("Classification Report:\n")
            f.write(report)
            f.write("\n" + "=" * 50 + "\n\n")

    print(f"✅ 混淆矩阵与分类报告已成功保存至 {filename}")


def save_test_accuracy_to_csv(results_dict, filename="results/test_accuracies.csv"):
    """
    计算 6 个模型在测试集上的 Accuracy，并输出为一个 CSV 文件
    """
    accuracies = []

    for name, data in results_dict.items():
        y_true = data['y_true']
        y_pred = data['y_pred']
        acc = accuracy_score(y_true, y_pred)
        accuracies.append({"Model": name, "Test_Accuracy": round(acc, 4)})

    df = pd.DataFrame(accuracies)
    df.to_csv(filename, index=False)
    print(f"✅ 测试集 Accuracy 已成功保存至 {filename}")
    print(df)


def _ensure_results_dir(results_dir):
    os.makedirs(results_dir, exist_ok=True)


def _apply_cn_font():
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False


def compute_perplexity(avg_loss, results_dir="results", filename="metrics.txt"):
    """
    根据验证集平均损失计算困惑度，并追加写入结果文件
    """
    _ensure_results_dir(results_dir)
    ppl = math.exp(avg_loss)
    print(f"Perplexity (PPL) = exp(loss) = {ppl:.6f}")

    metrics_path = os.path.join(results_dir, filename)
    with open(metrics_path, 'a', encoding='utf-8') as f:
        f.write(f"Avg Loss: {avg_loss:.6f}\n")
        f.write(f"Perplexity (PPL): {ppl:.6f}\n")
        f.write("-" * 40 + "\n")

    return ppl


def plot_loss_curve(train_losses, val_losses, save_path="results/loss_curve.png"):
    """
    绘制训练/验证损失曲线并保存
    """
    if len(train_losses) != len(val_losses):
        raise ValueError("train_losses 和 val_losses 的长度必须一致")

    _ensure_results_dir(os.path.dirname(save_path) or "results")

    _apply_cn_font()

    epochs = range(1, len(train_losses) + 1)
    plt.figure(figsize=(8, 5))
    plt.plot(epochs, train_losses, label='Train Loss')
    plt.plot(epochs, val_losses, label='Val Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('训练/验证损失曲线')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()


def plot_tsne_clusters(hidden_states, labels, save_path="results/tsne_clusters.png", perplexity=30):
    """
    对隐藏状态做 t-SNE 降维并绘制聚类散点图
    """
    hidden_states = np.asarray(hidden_states)
    if hidden_states.ndim != 2:
        raise ValueError("hidden_states 必须是二维数组: (num_samples, hidden_size)")
    if len(labels) != hidden_states.shape[0]:
        raise ValueError("labels 的长度必须与 hidden_states 的样本数一致")

    n_samples = hidden_states.shape[0]
    if n_samples < 2:
        raise ValueError("样本数过少，无法进行 t-SNE")

    # perplexity 必须小于样本数
    safe_perplexity = min(perplexity, max(1, n_samples - 1))

    _apply_cn_font()

    tsne = TSNE(
        n_components=2,
        perplexity=safe_perplexity,
        init='pca',
        learning_rate='auto',
        random_state=42,
    )
    emb = tsne.fit_transform(hidden_states)

    _ensure_results_dir(os.path.dirname(save_path) or "results")

    df = pd.DataFrame({
        'x': emb[:, 0],
        'y': emb[:, 1],
        'label': labels,
    })

    plt.figure(figsize=(9, 7))
    sns.scatterplot(data=df, x='x', y='y', hue='label', palette='tab10', s=30, alpha=0.8)
    plt.title('隐藏状态 t-SNE 聚类可视化')
    plt.xlabel('t-SNE 1')
    plt.ylabel('t-SNE 2')
    plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0)
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout(rect=[0, 0, 0.82, 1])
    plt.savefig(save_path, dpi=300)
    plt.close()


if __name__ == '__main__':
    # 模拟验证集平均损失并计算困惑度
    mock_avg_loss = 2.30
    compute_perplexity(mock_avg_loss)

    # 模拟训练/验证损失曲线
    mock_train_losses = [2.6, 2.2, 1.9, 1.6, 1.4]
    mock_val_losses = [2.7, 2.3, 2.0, 1.7, 1.5]
    plot_loss_curve(mock_train_losses, mock_val_losses)

    # 模拟隐藏状态与标签并绘制 t-SNE
    np.random.seed(42)
    num_samples = 200
    hidden_size = 64
    mock_hidden_states = np.random.randn(num_samples, hidden_size)
    mock_labels = np.random.choice(
        ['Chinese', 'English', 'Russian', 'Spanish'],
        size=num_samples,
    ).tolist()
    plot_tsne_clusters(mock_hidden_states, mock_labels)