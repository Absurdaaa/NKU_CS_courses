"""基于文本测试数据的样例测试。"""

import ast
import builtins
from pathlib import Path
import unittest
from unittest.mock import patch

from src import sliding_window


def load_text_case(case_index):
    """从 in/out 文本文件中读取一组测试样例。"""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    input_path = data_dir / f"in{case_index}.txt"
    output_path = data_dir / f"out{case_index}.txt"

    case = {}
    for line in input_path.read_text(encoding="utf-8").strip().splitlines():
        key, value = line.split("=", maxsplit=1)
        case[key.strip()] = ast.literal_eval(value.strip())

    return case, output_path.read_text(encoding="utf-8").strip()


class TextCaseTests(unittest.TestCase):
    """验证文本格式测试数据能够被正确读取并执行。"""

    def test_load_text_case_with_mocked_file_reads(self):
        """使用 mock 隔离文件读取依赖，验证样例解析逻辑。"""
        mocked_input = "mode='normal'\nnums=[1, 3, -1, -3]\nk=2\n"
        mocked_output = "[3, 3, -1]\n"

        with patch.object(
            Path,
            "read_text",
            side_effect=[mocked_input, mocked_output],
        ) as mocked_read_text:
            case, expected_text = load_text_case(99)

        self.assertEqual(case["mode"], "normal")
        self.assertEqual(case["nums"], [1, 3, -1, -3])
        self.assertEqual(case["k"], 2)
        self.assertEqual(expected_text, "[3, 3, -1]")
        self.assertEqual(mocked_read_text.call_count, 2)

    def test_text_cases_match_expected_outputs(self):
        """文本样例的输出或异常行为应与期望一致。"""
        for case_index in range(1, 23):
            case, expected_text = load_text_case(case_index)
            mode = case["mode"]
            nums = case["nums"]
            window_size = case["k"]

            if mode == "exception":
                expected_exception = getattr(builtins, expected_text)
                with self.assertRaises(expected_exception):
                    sliding_window.max_sliding_window(nums, window_size)
                continue

            if mode == "bruteforce":
                result = sliding_window.max_sliding_window_bruteforce(
                    nums,
                    window_size,
                )
            elif mode == "consistency":
                optimized_result = sliding_window.max_sliding_window(
                    nums,
                    window_size,
                )
                bruteforce_result = sliding_window.max_sliding_window_bruteforce(
                    nums,
                    window_size,
                )
                self.assertEqual(optimized_result, bruteforce_result)
                result = optimized_result
            else:
                result = sliding_window.max_sliding_window(nums, window_size)

            expected = ast.literal_eval(expected_text)
            self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
