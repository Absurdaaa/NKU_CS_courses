from time import perf_counter

from phe import paillier


# 服务器保存的消息列表。基础版实验中直接使用整数消息，便于验证结果。
MESSAGE_LIST = [135, 246, 357, 468, 579, 680, 791, 802]
# 客户端想要获取的目标下标，采用从 0 开始的计数方式。
TARGET_INDEX = 4
# 为了减小随机波动，耗时测试默认连续运行 10 次并取平均值。
BENCHMARK_RUNS = 10


def preview_ciphertext(encrypted_number, head=18, tail=18):
    """返回密文的大整数预览，避免终端输出过长。"""
    value = str(encrypted_number.ciphertext())
    if len(value) <= head + tail:
        return value
    return f"{value[:head]}...{value[-tail:]}"


def build_encrypted_query(public_key, target_index, message_count):
    """构造加密后的 one-hot 选择向量。"""
    selection_vector = []
    encrypted_query = []

    for index in range(message_count):
        # 目标位置为 1，其余位置为 0；服务器最终只能看到其加密结果。
        bit = 1 if index == target_index else 0
        selection_vector.append(bit)
        encrypted_query.append(public_key.encrypt(bit))

    return selection_vector, encrypted_query


def server_compute_response(messages, encrypted_query):
    """服务器在密文域中计算响应，但无法得知客户端真正查询的位置。"""
    response = None

    for message, encrypted_bit in zip(messages, encrypted_query):
        # encrypted_bit * message 对应 E(s_j) 的标量乘法，得到 E(s_j * M_j)。
        term = encrypted_bit * message
        # 再利用加法同态把所有项相加，最终得到 E(sum(s_j * M_j))。
        response = term if response is None else response + term

    return response


def demonstrate_homomorphism(public_key, private_key):
    """先验证 phe 提供的加法同态和数乘同态接口。"""
    plaintext_a = 12
    plaintext_b = 23

    encrypted_a = public_key.encrypt(plaintext_a)
    encrypted_b = public_key.encrypt(plaintext_b)

    # 密文加密文，对应明文相加。
    homomorphic_sum = encrypted_a + encrypted_b
    # 密文乘明文整数，对应明文数乘。
    homomorphic_scalar = encrypted_a * 5

    return {
        "plaintext_a": plaintext_a,
        "plaintext_b": plaintext_b,
        "sum_result": private_key.decrypt(homomorphic_sum),
        "scalar_result": private_key.decrypt(homomorphic_scalar),
    }


def run_basic_pir_demo(messages, target_index):
    """串联完整的基础版 PIR 流程，并记录各阶段耗时。"""
    timings = {}
    # 第一步：客户端生成 Paillier 公私钥。
    start = perf_counter()
    public_key, private_key = paillier.generate_paillier_keypair()
    timings["keygen"] = perf_counter() - start
    # 第二步：客户端构造加密选择向量并发送给服务器。
    start = perf_counter()
    selection_vector, encrypted_query = build_encrypted_query(
        public_key, target_index, len(messages)
    )
    timings["query"] = perf_counter() - start
    # 第三步：服务器在密文上完成聚合计算，返回目标消息对应的密文。
    start = perf_counter()
    response = server_compute_response(messages, encrypted_query)
    timings["server"] = perf_counter() - start
    # 第四步：客户端用私钥解密服务器响应，恢复目标消息。
    start = perf_counter()
    decrypted_message = private_key.decrypt(response)
    timings["decrypt"] = perf_counter() - start
    return {
        "public_key": public_key,
        "selection_vector": selection_vector,
        "encrypted_query": encrypted_query,
        "response": response,
        "decrypted_message": decrypted_message,
        "expected_message": messages[target_index],
        "timings": timings,
    }


def benchmark_average_timings(messages, target_index, runs):
    """连续运行多次实验，对各阶段耗时取平均值。"""
    timing_keys = ["keygen", "query", "server", "decrypt"]
    totals = {key: 0.0 for key in timing_keys}

    for _ in range(runs):
        result = run_basic_pir_demo(messages, target_index)
        for key in timing_keys:
            totals[key] += result["timings"][key]

    return {key: totals[key] / runs for key in timing_keys}


def main():
    # 运行一次完整实验，并将关键现象输出到终端。
    result = run_basic_pir_demo(MESSAGE_LIST, TARGET_INDEX)
    average_timings = benchmark_average_timings(
        MESSAGE_LIST, TARGET_INDEX, BENCHMARK_RUNS
    )

    print("========== 基于 Paillier 的基础版 PIR 模拟 ==========")
    print(f"消息列表: {MESSAGE_LIST}")
    print(f"目标位置(从 0 开始): {TARGET_INDEX}")
    print(f"目标消息: {result['expected_message']}")
    print()

    print("1. 客户端生成密钥")
    print(f"   公钥模数 n 的十进制位数: {len(str(result['public_key'].n))}")
    print(f"   耗时: {result['timings']['keygen']:.6f} s")
    print()

    print("2. 客户端构造加密选择向量")
    print(f"   明文选择向量: {result['selection_vector']}")
    print(
        "   前三个查询密文预览:",
        [preview_ciphertext(item) for item in result["encrypted_query"][:3]],
    )
    print(f"   耗时: {result['timings']['query']:.6f} s")
    print()

    print("3. 服务器在密文上执行同态计算")
    print(f"   返回密文预览: {preview_ciphertext(result['response'])}")
    print(f"   耗时: {result['timings']['server']:.6f} s")
    print()

    print("4. 客户端解密服务器响应")
    print(f"   解密结果: {result['decrypted_message']}")
    print(f"   是否与目标消息一致: {result['decrypted_message'] == result['expected_message']}")
    print(f"   耗时: {result['timings']['decrypt']:.6f} s")
    print()

    print(f"5. 连续运行 {BENCHMARK_RUNS} 次后的平均耗时")
    print(f"   平均密钥生成耗时: {average_timings['keygen']:.6f} s")
    print(f"   平均查询向量构造耗时: {average_timings['query']:.6f} s")
    print(f"   平均服务器同态计算耗时: {average_timings['server']:.6f} s")
    print(f"   平均客户端解密耗时: {average_timings['decrypt']:.6f} s")


if __name__ == "__main__":
    main()
