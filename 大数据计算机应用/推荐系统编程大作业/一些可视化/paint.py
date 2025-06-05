import matplotlib.pyplot as plt
import numpy as np
# 设置中文显示
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']  # 或 'Heiti SC', 'Hiragino Sans GB'
plt.rcParams['axes.unicode_minus'] = False
# 准备数据
methods = ['Pearson', 'Adjusted\nCosine', 'IUF', 'Cosine', 'Jaccard']
rmse_values = [17.4247, 16.7993, 16.7803, 16.6344, 16.6300]
mae_values = [13.3903, 12.7994, 12.8370, 12.7202, 12.6987]
computation_times = [0.07, 1.14, 0.86, 0.83, 1.35]

# 设置画布和子图
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
fig.suptitle('相似度方法性能比较', fontsize=16, fontweight='bold')

# 设置颜色
colors = ['#FF9999', '#66B2FF', '#99FF99', '#FFCC99', '#C2C2F0']

# RMSE柱状图
bars1 = ax1.bar(methods, rmse_values, color=colors, width=0.6)
ax1.set_title('RMSE比较', fontsize=14)
ax1.set_ylabel('RMSE值', fontsize=12)
ax1.set_ylim(16, 18)  # 设置y轴范围以突出差异
ax1.grid(axis='y', linestyle='--', alpha=0.7)

# 为RMSE柱状图添加数值标签
for bar in bars1:
    height = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., height + 0.05,
            f'{height:.4f}', ha='center', va='bottom', fontsize=10)

# MAE柱状图
bars2 = ax2.bar(methods, mae_values, color=colors, width=0.6)
ax2.set_title('MAE比较', fontsize=14)
ax2.set_ylabel('MAE值', fontsize=12)
ax2.set_ylim(12, 14)  # 设置y轴范围以突出差异
ax2.grid(axis='y', linestyle='--', alpha=0.7)

# 为MAE柱状图添加数值标签
for bar in bars2:
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height + 0.05,
            f'{height:.4f}', ha='center', va='bottom', fontsize=10)

# 添加计算时间注释
for i, (bar1, bar2) in enumerate(zip(bars1, bars2)):
    ax1.text(bar1.get_x() + bar1.get_width()/2., bar1.get_height() - 0.4,
            f'{computation_times[i]}秒', ha='center', va='top', fontsize=9, color='white', fontweight='bold')

# 调整布局
plt.tight_layout(rect=[0, 0, 1, 0.95])

# 添加图例说明最低值
min_rmse_idx = np.argmin(rmse_values)
min_mae_idx = np.argmin(mae_values)

ax1.text(0.5, 0.05, f'最佳方法: {methods[min_rmse_idx]} (最低RMSE)', 
        transform=ax1.transAxes, ha='center', fontsize=11, bbox=dict(facecolor='lightyellow', alpha=0.5))

ax2.text(0.5, 0.05, f'最佳方法: {methods[min_mae_idx]} (最低MAE)', 
        transform=ax2.transAxes, ha='center', fontsize=11, bbox=dict(facecolor='lightyellow', alpha=0.5))

# 保存图像并显示
plt.savefig('similarity_methods_comparison.png', dpi=300, bbox_inches='tight')
plt.show()