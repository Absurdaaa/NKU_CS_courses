import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
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