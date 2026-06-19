"""滑动窗口最大值算法实现。"""

from collections import deque


def validate_inputs(nums, k):
    """统一校验输入，避免错误在核心算法内部扩散。"""
    if not isinstance(nums, list):
        raise TypeError("nums 必须是整数列表")
    if not isinstance(k, int):
        raise TypeError("k 必须是整数")
    if not nums:
        raise ValueError("nums 不能为空")
    if any(not isinstance(value, int) for value in nums):
        raise TypeError("nums 中的元素必须全部为整数")
    if k <= 0:
        raise ValueError("k 必须大于 0")
    if k > len(nums):
        raise ValueError("k 不能大于 nums 的长度")


def max_sliding_window_bruteforce(nums, k):
    """使用朴素方法计算每个滑动窗口中的最大值。"""
    validate_inputs(nums, k)
    result = []

    # 保留朴素解法的目的不是作为默认实现，而是作为正确性对照和性能基线。
    for start in range(len(nums) - k + 1):
        result.append(max(nums[start : start + k]))

    return result


def max_sliding_window(nums, k):
    """使用单调队列在线性时间内求解滑动窗口最大值。"""
    validate_inputs(nums, k)
    # 队列中保存的是候选最大值的下标，而不是元素值本身，
    # 这样既能判断元素是否滑出窗口，也能直接回到原数组取值。
    window_indexes = deque()
    result = []

    for index, value in enumerate(nums):
        # 队首下标一旦离开窗口范围，就不可能再成为后续窗口的最大值。
        if window_indexes and window_indexes[0] <= index - k:
            window_indexes.popleft()

        # 新元素进入前，移除所有不可能再成为最大值的较小元素，
        # 从而保证队首始终对应当前窗口的最大值。
        while window_indexes and nums[window_indexes[-1]] <= value:
            window_indexes.pop()
        window_indexes.append(index)

        # 只有在窗口首次形成之后，队首对应的值才是一个有效输出。
        if index >= k - 1:
            result.append(nums[window_indexes[0]])

    return result
