# 源代码说明

本目录用于提交本次作业所需的最小代码集合，包含源代码、单元测试代码和测试数据。

## 目录结构

```text
code/
├── README.md
├── data/
│   ├── in1.txt
│   ├── out1.txt
│   ├── ...
│   ├── in22.txt
│   ├── out22.txt
│   └── sample_cases.json
├── src/
│   ├── __init__.py
│   └── sliding_window.py
└── tests/
    ├── __init__.py
    ├── test_sliding_window.py
    └── test_txt_cases.py
```

## 文件说明

- `src/sliding_window.py`：滑动窗口最大值的核心实现，包含朴素解法、单调队列优化解法和输入校验逻辑。
- `tests/test_sliding_window.py`：使用 `unittest` 编写的单元测试，覆盖正常输入、边界输入、异常输入以及两种实现的一致性验证。
- `tests/test_txt_cases.py`：从 `in1.txt` 到 `in22.txt`、`out1.txt` 到 `out22.txt` 中读取测试数据并执行验证。
- `data/in*.txt`、`data/out*.txt`：文本格式测试样例，共 22 组，覆盖正常输出、异常输入、朴素解法验证和一致性验证。
- `data/sample_cases.json`：保留的结构化测试数据样例文件。

## 运行方式

在 `code/` 目录下执行：

```bash
python3 -m unittest tests.test_sliding_window tests.test_txt_cases -v
```

## 结果说明

- 主接口为 `max_sliding_window(nums, k)`。
- 朴素对照实现为 `max_sliding_window_bruteforce(nums, k)`。
- 当前测试文件既可直接验证算法正确性，也可展示如何从文本样例文件中读取输入并校验输出。
