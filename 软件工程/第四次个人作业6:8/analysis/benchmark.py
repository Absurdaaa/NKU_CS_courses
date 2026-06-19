"""滑动窗口最大值算法的性能分析脚本。"""

import cProfile
import io
import pstats
import random
import time

from src.sliding_window import max_sliding_window, max_sliding_window_bruteforce


def generate_test_data(length, seed=42):
    """生成可复现的随机整数数组。"""
    random.seed(seed)
    return [random.randint(-10_000, 10_000) for _ in range(length)]


def benchmark_function(function, nums, k):
    """执行函数一次并返回耗时和结果。"""
    start_time = time.perf_counter()
    result = function(nums, k)
    duration = time.perf_counter() - start_time
    return duration, result


def profile_function(function, nums, k):
    """返回函数的 profile 文本结果。"""
    profiler = cProfile.Profile()
    profiler.enable()
    function(nums, k)
    profiler.disable()

    output = io.StringIO()
    stats = pstats.Stats(profiler, stream=output).sort_stats("cumulative")
    stats.print_stats(20)
    return output.getvalue()


def main():
    """执行朴素解法与优化解法的基础性能对比。"""
    sizes = [1000, 5000, 10000]
    window_size = 100

    print("滑动窗口最大值性能对比")
    print(f"窗口大小: {window_size}")
    print("-" * 50)

    for size in sizes:
        nums = generate_test_data(size)
        brute_force_time, brute_force_result = benchmark_function(
            max_sliding_window_bruteforce,
            nums,
            window_size,
        )
        optimized_time, optimized_result = benchmark_function(
            max_sliding_window,
            nums,
            window_size,
        )

        if brute_force_result != optimized_result:
            raise AssertionError("朴素解法与优化解法结果不一致")

        print(f"数据规模 n={size}")
        print(f"  朴素解法耗时: {brute_force_time:.6f} 秒")
        print(f"  优化解法耗时: {optimized_time:.6f} 秒")
        print()

    print("优化解法 Profile 结果（前 20 项）：")
    print(profile_function(max_sliding_window, generate_test_data(10000), window_size))


if __name__ == "__main__":
    main()
