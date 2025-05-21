import matplotlib.pyplot as plt
import re
import os
import numpy as np
from scipy.interpolate import interp1d


def parse_file(filename):
    """Parse file to extract guesses and time data."""
    if not os.path.exists(filename):
        print(f"Warning: File {filename} does not exist or is empty.")
        return [], []
    
    guesses = []
    times = []
    
    with open(filename, 'r') as f:
        content = f.read()
        # 使用正则表达式匹配 "Guesses: X, Time: Y seconds" 格式的行
        pattern = r'Guesses:\s+(\d+),\s+Time:\s+([\d.]+)\s+seconds'
        matches = re.findall(pattern, content)
        
        for match in matches:
            guesses.append(int(match[0]))
            times.append(float(match[1]))
    
    return guesses, times


def plot_graphs():
    """Plot and save all graphs."""
    # 文件路径
    serial_file = "o1.txt"
    openmp_file = "openop_o1.txt"
    pthread_file = "pthread_o1.txt"
    
    # 解析文件
    serial_guesses, serial_times = parse_file(serial_file)
    openmp_guesses, openmp_times = parse_file(openmp_file)
    pthread_guesses, pthread_times = parse_file(pthread_file)
    
    # 数据检查
    if not serial_guesses or not serial_times:
        print("Error: Serial execution data not available. Cannot calculate speedup.")
        return
    
    # 设置全局字体
    plt.rcParams['font.sans-serif'] = ['Arial']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 创建插值函数来匹配不同猜测数下的时间
    if serial_guesses and serial_times:
        serial_interp = interp1d(serial_guesses, serial_times, kind='linear', fill_value='extrapolate')
    
    # 计算加速比
    openmp_speedup = []
    openmp_speedup_guesses = []
    if openmp_guesses and openmp_times:
        for i, guess in enumerate(openmp_guesses):
            if guess <= max(serial_guesses) and guess >= min(serial_guesses):
                serial_time = serial_interp(guess)
                if serial_time > 0:
                    speedup = serial_time / openmp_times[i]
                    openmp_speedup.append(speedup)
                    openmp_speedup_guesses.append(guess)
    
    pthread_speedup = []
    pthread_speedup_guesses = []
    if pthread_guesses and pthread_times:
        for i, guess in enumerate(pthread_guesses):
            if guess <= max(serial_guesses) and guess >= min(serial_guesses):
                serial_time = serial_interp(guess)
                if serial_time > 0:
                    speedup = serial_time / pthread_times[i]
                    pthread_speedup.append(speedup)
                    pthread_speedup_guesses.append(guess)
    
    # 创建加速比图表
    plt.figure(figsize=(10, 6))
    
    # 串行版本的加速比始终为1
    plt.plot(serial_guesses, [1] * len(serial_guesses), '-', color='blue', label='Serial (baseline)')
    
    if openmp_speedup and openmp_speedup_guesses:
        plt.plot(openmp_speedup_guesses, openmp_speedup, '-', color='red', label='OpenMP')
    
    if pthread_speedup and pthread_speedup_guesses:
        plt.plot(pthread_speedup_guesses, pthread_speedup, '-', color='green', label='Pthread')
    
    plt.title('Speedup Comparison - All Algorithms')
    plt.xlabel('Number of Guesses')
    plt.ylabel('Speedup (Serial/Parallel)')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig('speedup_comparison1.png', dpi=300)
    print("Saved: speedup_comparisono2.png")
    

if __name__ == "__main__":
    plot_graphs()
    print("All graphs have been generated successfully.")
