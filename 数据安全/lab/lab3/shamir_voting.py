import random

# 使用与之前一致的大质数
PRIME = 2**31 - 1

def generate_shares(secret, n, t):
    """生成 n 个份额，门限为 t"""
    coefficients = [secret] + [random.randint(0, PRIME - 1) for _ in range(t - 1)]
    def f(x):
        result = 0
        for i, coeff in enumerate(coefficients):
            result = (result + coeff * pow(x, i, PRIME)) % PRIME
        return result
    return [(i, f(i)) for i in range(1, n + 1)]

def reconstruct_secret(shares):
    """从份额中重构秘密"""
    x_values, y_values = zip(*shares)
    def lagrange(x):
        total = 0
        for i in range(len(x_values)):
            num, den = 1, 1
            for j in range(len(x_values)):
                if i == j: continue
                num = (num * (x - x_values[j])) % PRIME
                den = (den * (x_values[i] - x_values[j])) % PRIME
            term = (y_values[i] * num * pow(den, -1, PRIME)) % PRIME
            total = (total + term) % PRIME
        return total
    return lagrange(0)

def simulate_voting_experiment():
    print("--- 实验 3.2：基于 Shamir (2,3) 门限的隐私投票系统 ---")
    
    # 1. 初始化设置
    candidates = ["Alice", "Bob", "Charles", "Douglas"]
    students = ["Student 1", "Student 2", "Student 3"]
    
    # 模拟学生的投票（每个学生对每个候选人投 0 或 1）
    # 格式: votes[student_index][candidate_index]
    actual_votes = [
        [1, 0, 1, 1], # Student 1 的投票
        [0, 1, 1, 0], # Student 2 的投票
        [1, 1, 0, 1]  # Student 3 的投票
    ]
    
    print("原始投票情况：")
    header = "          " + "  ".join(candidates)
    print(header)
    for i, s_votes in enumerate(actual_votes):
        print(f"{students[i]}:  " + "      ".join(map(str, s_votes)))
    
    # 计算理论总票数用于最后验证
    theoretical_results = [sum(actual_votes[s][c] for s in range(3)) for c in range(4)]
    print("-" * 60)

    # 2. 秘密分割
    # 为每个候选人的每一票生成 3 个份额
    # all_shares[candidate_index][student_index] = [(1, y1), (2, y2), (3, y3)]
    all_shares = [[[] for _ in range(3)] for _ in range(4)]
    
    for c_idx in range(4):
        for s_idx in range(3):
            vote = actual_votes[s_idx][c_idx]
            shares = generate_shares(vote, 3, 2) # (2,3) 门限
            all_shares[c_idx][s_idx] = shares

    # 3. 份额分发与累加（模拟投票员的操作）
    # 投票员会对每个候选人收到的 3 组份额进行按位置累加
    # final_candidate_shares[candidate_index] = [(1, sum_y1), (2, sum_y2), (3, sum_y3)]
    final_candidate_shares = []
    
    for c_idx in range(4):
        candidate_sum_shares = []
        for x_val in range(1, 4): # 对应 x=1, 2, 3
            # 累加所有学生对该候选人在 x 处的份额
            total_y_at_x = sum(all_shares[c_idx][s_idx][x_val-1][1] for s_idx in range(3)) % PRIME
            candidate_sum_shares.append((x_val, total_y_at_x))
        final_candidate_shares.append(candidate_sum_shares)

    print("投票员汇总后的部分份额展示（仅展示 Alice 的前两个份额）：")
    print(f"Alice's aggregated shares (subset): {final_candidate_shares[0][:2]}")
    print("-" * 60)

    # 4. 票数重构
    print("最终统计结果：")
    reconstructed_results = []
    for c_idx in range(4):
        # 模拟从 3 个汇总份额中随机选 2 个进行重构
        subset_shares = random.sample(final_candidate_shares[c_idx], 2)
        total_votes = reconstruct_secret(subset_shares)
        reconstructed_results.append(total_votes)
        print(f"候选人 {candidates[c_idx]:7}: {total_votes} 票")

    # 5. 验证
    print("-" * 60)
    if reconstructed_results == theoretical_results:
        print("验证成功：隐私统计的总票数与直接相加结果完全一致！")
    else:
        print("验证失败：结果不匹配。")

if __name__ == "__main__":
    simulate_voting_experiment()
