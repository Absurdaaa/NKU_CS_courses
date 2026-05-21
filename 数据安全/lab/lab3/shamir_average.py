import random

# 定义一个足够大的质数，用于有限域运算
# 这里使用梅森质数 2^31 - 1
PRIME = 2**31 - 1

def generate_shares(secret, n, t):
    """
    生成 n 个份额，门限为 t (Shamir 秘密共享)
    多项式形式: f(x) = secret + a1*x + a2*x^2 + ... + a(t-1)*x^(t-1)
    """
    # a0 是秘密本身，其余系数随机生成
    coefficients = [secret] + [random.randint(0, PRIME - 1) for _ in range(t - 1)]
    
    def f(x):
        result = 0
        for i, coeff in enumerate(coefficients):
            # 计算 coeff * x^i % PRIME
            result = (result + coeff * pow(x, i, PRIME)) % PRIME
        return result
    
    # 生成 (x, f(x)) 形式的份额，x 从 1 到 n
    return [(i, f(i)) for i in range(1, n + 1)]

def reconstruct_secret(shares):
    """
    使用拉格朗日插值法从份额中恢复秘密
    """
    def lagrange_interpolation(x, x_values, y_values):
        total = 0
        n = len(x_values)
        for i in range(n):
            numerator, denominator = 1, 1
            for j in range(n):
                if i == j:
                    continue
                # 计算拉格朗日基函数的分子和分母
                numerator = (numerator * (x - x_values[j])) % PRIME
                denominator = (denominator * (x_values[i] - x_values[j])) % PRIME
            
            # 基函数 L_i(x) = numerator / denominator
            # 在有限域中，除法等于乘以逆元
            term = (y_values[i] * numerator * pow(denominator, -1, PRIME)) % PRIME
            total = (total + term) % PRIME
        return total

    x_values, y_values = zip(*shares)
    return lagrange_interpolation(0, x_values, y_values)

def simulate_privacy_average():
    print("--- 三人数据平均值隐私计算模拟 (基于 Shamir (2,3) 门限共享) ---")
    
    # 1. 初始化数据：三个人的私有数据
    # 假设三个人的数据分别为 x1, x2, x3
    student_data = [60, 80, 100]
    names = ["Student 1", "Student 2", "Student 3"]
    
    print(f"原始数据: {dict(zip(names, student_data))}")
    actual_sum = sum(student_data)
    actual_avg = actual_sum / len(student_data)
    print(f"理论总和: {actual_sum}, 理论平均值: {actual_avg:.2f}")
    print("-" * 50)

    # 2. 秘密分割：每个学生将自己的数据分割成 3 个份额 (2,3 门限)
    # shares_matrix[i] 存储第 i 个学生生成的 3 个份额
    shares_matrix = []
    for i, data in enumerate(student_data):
        shares = generate_shares(data, 3, 2)
        shares_matrix.append(shares)
        print(f"{names[i]} 生成的份额: {shares}")

    # 3. 份额分发与累加：
    # 按照实验要求，每个学生将份额分发给其他学生或交给“投票员”
    # 在这里，我们模拟“投票员”收到三组份额并按索引累加
    # d1 = a1 + b1 + c1 (即所有学生给第1个位置的份额之和)
    # d2 = a2 + b2 + c2
    # d3 = a3 + b3 + c3
    
    sum_shares = []
    for j in range(3): # 对应 x=1, 2, 3
        # 收集所有学生在 x=j+1 处的份额并求和
        local_sum = sum(shares_matrix[i][j][1] for i in range(3)) % PRIME
        sum_shares.append((j + 1, local_sum))
    
    print("-" * 50)
    print(f"投票员累加后的总份额 (d1, d2, d3): {sum_shares}")

    # 4. 票数重构：投票员从三个总份额中随机选择两个进行重构
    # 选前两个份额 (x=1 和 x=2)
    reconstruction_shares = sum_shares[:2]
    reconstructed_sum = reconstruct_secret(reconstruction_shares)
    
    # 5. 计算平均值
    reconstructed_avg = reconstructed_sum / 3
    
    print(f"重构出的总和: {reconstructed_sum}")
    print(f"最终计算出的平均值: {reconstructed_avg:.2f}")
    
    # 6. 验证
    if reconstructed_sum == actual_sum:
        print("\n验证成功：隐私计算结果与直接计算一致！")
    else:
        print("\n验证失败：结果不匹配。")

if __name__ == "__main__":
    simulate_privacy_average()
