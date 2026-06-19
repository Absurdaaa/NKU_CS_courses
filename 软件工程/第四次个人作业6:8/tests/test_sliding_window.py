"""滑动窗口最大值算法的单元测试。"""

# pylint: disable=too-many-public-methods

import unittest

from src import sliding_window


class SlidingWindowTests(unittest.TestCase):
    """测试核心功能与输入校验行为。"""

    def _api(self):
        self.assertTrue(
            hasattr(sliding_window, "max_sliding_window"),
            "src.sliding_window must define max_sliding_window(nums, k)",
        )
        return sliding_window.max_sliding_window

    def _bruteforce_api(self):
        self.assertTrue(
            hasattr(sliding_window, "max_sliding_window_bruteforce"),
            "src.sliding_window 必须定义 max_sliding_window_bruteforce(nums, k)",
        )
        return sliding_window.max_sliding_window_bruteforce

    def test_returns_expected_values_for_standard_case(self):
        """标准示例应返回题目期望结果。"""
        nums = [1, 3, -1, -3, 5, 3, 6, 7]

        result = self._api()(nums, 3)

        self.assertEqual(result, [3, 3, 5, 5, 6, 7])

    def test_returns_input_when_window_size_is_one(self):
        """当窗口大小为 1 时，结果应与原数组一致。"""
        nums = [4, -2, 9]

        result = self._api()(nums, 1)

        self.assertEqual(result, [4, -2, 9])

    def test_returns_single_value_when_window_covers_whole_array(self):
        """当窗口覆盖整个数组时，结果应只包含全局最大值。"""
        nums = [2, 7, 1, 5]

        result = self._api()(nums, len(nums))

        self.assertEqual(result, [7])

    def test_returns_single_value_for_single_element_array(self):
        """单元素数组在窗口大小为 1 时应返回该元素本身。"""
        nums = [42]

        result = self._api()(nums, 1)

        self.assertEqual(result, [42])

    def test_raises_value_error_when_window_is_zero(self):
        """窗口大小必须为正整数。"""
        with self.assertRaises(ValueError):
            self._api()([1, 2, 3], 0)

    def test_raises_value_error_when_window_is_negative(self):
        """窗口大小为负数时应抛出数值异常。"""
        with self.assertRaises(ValueError):
            self._api()([1, 2, 3], -1)

    def test_raises_value_error_when_window_exceeds_length(self):
        """窗口大小不能超过输入数组长度。"""
        with self.assertRaises(ValueError):
            self._api()([1, 2], 3)

    def test_raises_type_error_when_input_is_not_a_list(self):
        """当输入不是列表时，应抛出类型异常。"""
        with self.assertRaises(TypeError):
            self._api()("123", 2)

    def test_raises_type_error_when_input_is_none(self):
        """当输入为 None 时，应抛出类型异常。"""
        with self.assertRaises(TypeError):
            self._api()(None, 2)

    def test_raises_value_error_when_input_list_is_empty(self):
        """空列表不允许作为有效输入。"""
        with self.assertRaises(ValueError):
            self._api()([], 1)

    def test_raises_type_error_when_window_size_is_not_integer(self):
        """窗口大小必须是整数。"""
        with self.assertRaises(TypeError):
            self._api()([1, 2, 3], 1.5)

    def test_raises_type_error_when_list_contains_non_integer(self):
        """输入数组中的元素应全部为整数。"""
        with self.assertRaises(TypeError):
            self._api()([1, "2", 3], 2)

    def test_returns_expected_values_for_strictly_increasing_sequence(self):
        """严格递增数组的窗口最大值应始终为窗口最右端元素。"""
        nums = [1, 2, 3, 4, 5]

        result = self._api()(nums, 3)

        self.assertEqual(result, [3, 4, 5])

    def test_returns_expected_values_for_strictly_decreasing_sequence(self):
        """严格递减数组的窗口最大值应始终为窗口最左端元素。"""
        nums = [5, 4, 3, 2, 1]

        result = self._api()(nums, 2)

        self.assertEqual(result, [5, 4, 3, 2])

    def test_returns_expected_values_when_duplicates_exist(self):
        """存在重复最大值时，结果仍应正确。"""
        nums = [4, 4, 4, 2, 2]

        result = self._api()(nums, 2)

        self.assertEqual(result, [4, 4, 4, 2])

    def test_returns_expected_values_when_all_numbers_are_same(self):
        """当所有元素相同时，每个窗口的最大值也应相同。"""
        nums = [6, 6, 6, 6]

        result = self._api()(nums, 3)

        self.assertEqual(result, [6, 6])

    def test_returns_expected_values_when_numbers_are_negative(self):
        """包含负数时也应正确返回每个窗口的最大值。"""
        nums = [-7, -8, -6, -5, -9]

        result = self._api()(nums, 2)

        self.assertEqual(result, [-7, -6, -5, -5])

    def test_returns_expected_values_when_maximum_starts_at_left_edge(self):
        """窗口最大值位于左边界时，应在滑出前保持为最大值。"""
        nums = [9, 3, 2, 1]

        result = self._api()(nums, 3)

        self.assertEqual(result, [9, 3])

    def test_returns_expected_values_when_maximum_appears_at_right_edge(self):
        """窗口最大值位于右边界时，应在进入窗口后立即成为最大值。"""
        nums = [1, 2, 9, 3]

        result = self._api()(nums, 3)

        self.assertEqual(result, [9, 9])

    def test_updates_maximum_when_previous_maximum_leaves_window(self):
        """当原最大值滑出窗口后，应正确更新为新的窗口最大值。"""
        nums = [8, 1, 1, 7]

        result = self._api()(nums, 3)

        self.assertEqual(result, [8, 7])

    def test_bruteforce_api_returns_expected_values_for_standard_case(self):
        """朴素解法应在标准示例上返回正确结果。"""
        nums = [1, 3, -1, -3, 5, 3, 6, 7]

        result = self._bruteforce_api()(nums, 3)

        self.assertEqual(result, [3, 3, 5, 5, 6, 7])

    def test_bruteforce_and_optimized_implementations_match(self):
        """朴素解法和优化解法在同一输入上应得到一致结果。"""
        nums = [9, 1, 3, 7, 2, 6, 8, 4]

        optimized_result = self._api()(nums, 4)
        bruteforce_result = self._bruteforce_api()(nums, 4)

        self.assertEqual(bruteforce_result, optimized_result)


if __name__ == "__main__":
    unittest.main()
