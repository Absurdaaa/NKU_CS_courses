"""使用 line_profiler 对核心函数做逐行性能分析。"""

from io import StringIO

from line_profiler import LineProfiler

from analysis.benchmark import generate_test_data
from src.sliding_window import max_sliding_window


def main():
    """执行逐行性能分析并保存结果。"""
    nums = generate_test_data(10_000)
    window_size = 100

    profiler = LineProfiler()
    profiled_function = profiler(max_sliding_window)
    profiled_function(nums, window_size)

    profiler.dump_stats("analysis/line_profile_result.lprof")

    output = StringIO()
    profiler.print_stats(stream=output)
    with open("analysis/line_profile_result.txt", "w", encoding="utf-8") as file:
        file.write("逐行性能分析对象: max_sliding_window\n")
        file.write("数据规模: n=10000\n")
        file.write("窗口大小: k=100\n\n")
        file.write(output.getvalue())


if __name__ == "__main__":
    main()
