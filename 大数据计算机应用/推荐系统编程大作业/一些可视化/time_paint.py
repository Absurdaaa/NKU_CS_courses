import matplotlib.pyplot as plt
import numpy as np

# 数据
iterations = [10, 15, 20, 25, 30, 35, 40, 45, 50]
training_times = [34.79, 52.17, 67.58, 85.12, 106.69, 119.10, 135.34, 147.05, 179.75]
rmse_values = [16.6534, 16.6359, 16.6218, 16.6261, 16.6316, 16.6501, 16.6613, 16.6548, 16.6666]

# 设置中文字体支持（如果需要）
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']  # 或 'Heiti SC', 'Hiragino Sans GB'
plt.rcParams['axes.unicode_minus'] = False

# 图1: 训练轮次与时间的关系
plt.figure(figsize=(10, 6))
plt.plot(iterations, training_times, marker='o', linestyle='-', linewidth=2, 
         markersize=8, color='#1f77b4')
plt.grid(True, linestyle='--', alpha=0.7)
plt.title('训练轮次与训练时间的关系', fontsize=15)
plt.xlabel('训练轮次 (n)', fontsize=12)
plt.ylabel('训练时间 (秒)', fontsize=12)
plt.xticks(iterations)
plt.tight_layout()

# 添加数据标签
for i, txt in enumerate(training_times):
    plt.annotate(f'{txt:.2f}s', (iterations[i], training_times[i]), 
                 textcoords="offset points", xytext=(0,10), ha='center')

# 保存图像
plt.savefig('training_time_vs_iterations.png', dpi=300)
plt.close()

# 图2: 训练轮次与RMSE的关系
plt.figure(figsize=(10, 6))
plt.plot(iterations, rmse_values, marker='s', linestyle='-', linewidth=2, 
         markersize=8, color='#ff7f0e')
plt.grid(True, linestyle='--', alpha=0.7)
plt.title('训练轮次与RMSE的关系', fontsize=15)
plt.xlabel('训练轮次 (n)', fontsize=12)
plt.ylabel('RMSE', fontsize=12)
plt.xticks(iterations)

# 设置y轴的范围，突出RMSE的变化
ymin = min(rmse_values) - 0.01
ymax = max(rmse_values) + 0.01
plt.ylim(ymin, ymax)

# 添加数据标签
for i, txt in enumerate(rmse_values):
    plt.annotate(f'{txt:.4f}', (iterations[i], rmse_values[i]), 
                 textcoords="offset points", xytext=(0,10), ha='center')

# 水平线标识最佳RMSE
best_rmse = min(rmse_values)
best_iter = iterations[rmse_values.index(best_rmse)]
plt.axhline(y=best_rmse, color='r', linestyle='--', alpha=0.6)
plt.axvline(x=best_iter, color='r', linestyle='--', alpha=0.6)
# plt.annotate(f'最优RMSE: {best_rmse:.4f}\n轮次: {best_iter}', 
#              xy=(best_iter, best_rmse),
#              xytext=(best_iter+5, best_rmse+0.005),
#              arrowprops=dict(facecolor='red', shrink=0.05, alpha=0.7),
#              fontsize=10)

plt.tight_layout()
plt.savefig('rmse_vs_iterations.png', dpi=300)
plt.close()

print("图表已成功保存为 'training_time_vs_iterations.png' 和 'rmse_vs_iterations.png'")