import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.sans-serif'] = ['PingFang SC', 'SimHei', 'Arial Unicode MS', 'STSong', 'Heiti SC']
plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号

# schemes = ['Baseline', 'OpenMP', 'Block', 'SIMD', 'MPI', 'HIP/DCU']
# cpu = [99, 152, 99, 99, 383, 99]
# mem = [34.5, 34.6, 34.5, 42.5, 45.1, 169.2]
# vram = [0, 0, 0, 0, 0, 10]

# x = np.arange(len(schemes))

# plt.figure(figsize=(10, 6))
# plt.bar(x-0.2, cpu, width=0.2, label='CPU利用率(%)')
# plt.bar(x, mem, width=0.2, label='最大内存(MB)')
# plt.bar(x+0.2, vram, width=0.2, label='显存(MB)')
# plt.xticks(x, schemes, rotation=30)
# plt.legend()
# plt.title('不同矩阵乘法实现的资源消耗对比')
# plt.tight_layout()
# plt.savefig('lesson1/资源对比.png', dpi=300)
# plt.show()


import matplotlib.pyplot as plt

schemes = [
    "Baseline",
    "OpenMP",
    "Block Parallel",
    "SIMD",
    "MPI",
    "DCU-HIP"
]
gflops = [0.11, 1.25, 0.14, 0.42, 0.56, 5555.43]

plt.figure(figsize=(10, 6))
bars = plt.bar(schemes, gflops, color=['#999999', '#6A8CAF', '#B8D8BA', '#F1E189', '#F7A072', '#D7263D'])

# 可选：将DCU-HIP的柱子特殊高亮
bars[-1].set_color('#D7263D')

plt.ylabel("GFLOPS")
plt.title("不同矩阵乘法实现方案的GFLOPS对比")
plt.yscale('log')  # 采用对数坐标，突出量级差异
plt.tight_layout()
plt.grid(axis='y', linestyle='--', alpha=0.6)
# 在柱子上添加数值
for bar, value in zip(bars, gflops):
    plt.text(
        bar.get_x() + bar.get_width() / 2,  # x 坐标
        value,                              # y 坐标
        f'{value:.2f}',                     # 显示的数字文本，保留两位小数
        ha='center', va='bottom',           # 水平、垂直对齐方式
        fontsize=10
    )
plt.savefig('lesson1/GFLOPS.png', dpi=300)
plt.show()