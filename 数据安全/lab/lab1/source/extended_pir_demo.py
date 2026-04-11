from secrets import token_bytes
from time import perf_counter

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from phe import paillier


PLAINTEXT_MESSAGES = [
    "学号2312966，本条消息用于验证扩展版PIR。",
    "Paillier负责隐藏查询位置，AES负责保护长消息内容。",
    (
        "本实验演示客户端通过PIR取回密文后再本地解密。"
        "为了触发分块恢复流程，这里将同一段说明文字重复多次。"
        "服务器只保存 AES-GCM 密文，客户端通过多轮 PIR 逐块恢复目标密文，"
        "随后再使用本地保存的对称密钥完成解密。"
        "本实验演示客户端通过PIR取回密文后再本地解密。"
        "为了触发分块恢复流程，这里将同一段说明文字重复多次。"
        "服务器只保存 AES-GCM 密文，客户端通过多轮 PIR 逐块恢复目标密文，"
        "随后再使用本地保存的对称密钥完成解密。"
    ),
    "服务器只能看到加密选择向量，无法区分目标下标。",
]
TARGET_INDEX = 2
BENCHMARK_RUNS = 5
AES_KEY_SIZE = 32
AES_NONCE_SIZE = 12


def preview_hex(data, head=16, tail=16):
    """返回十六进制预览，避免打印完整长字节串。"""
    hex_text = data.hex()
    if len(hex_text) <= head + tail:
        return hex_text
    return f"{hex_text[:head]}...{hex_text[-tail:]}"


def build_encrypted_query(public_key, target_index, message_count):
    """构造加密后的 one-hot 选择向量。"""
    encrypted_query = []

    for index in range(message_count):
        bit = 1 if index == target_index else 0
        encrypted_query.append(public_key.encrypt(bit))

    return encrypted_query


def server_compute_response(messages, encrypted_query):
    """服务器对一列分块密文执行同态聚合。"""
    response = None

    for message, encrypted_bit in zip(messages, encrypted_query):
        term = encrypted_bit * message
        response = term if response is None else response + term

    return response


def encrypt_messages_with_aes(messages, key):
    """客户端用同一对称密钥加密消息，返回 nonce+ciphertext。"""
    aesgcm = AESGCM(key)
    encrypted_messages = []

    for message in messages:
        nonce = token_bytes(AES_NONCE_SIZE)
        ciphertext = aesgcm.encrypt(nonce, message.encode("utf-8"), None)
        encrypted_messages.append(nonce + ciphertext)

    return encrypted_messages


def compute_chunk_size(public_key):
    """根据 Paillier 模数计算安全的单块字节数，确保分块整数小于 n。"""
    modulus_bytes = (public_key.n.bit_length() - 1) // 8
    return max(1, modulus_bytes - 1)


def chunk_bytes(data, chunk_size):
    """把字节串按固定长度切分为整数块。"""
    blocks = []

    for start in range(0, len(data), chunk_size):
        chunk = data[start : start + chunk_size]
        blocks.append(int.from_bytes(chunk, "big"))

    return blocks


def prepare_server_chunks(encrypted_messages, chunk_size):
    """将所有 AES 密文补齐后按列组织，便于多轮 PIR 取回。"""
    chunked_messages = [chunk_bytes(item, chunk_size) for item in encrypted_messages]
    max_chunks = max(len(item) for item in chunked_messages)
    chunk_matrix = []
    length_list = [len(item) for item in encrypted_messages]

    for blocks in chunked_messages:
        row = blocks + [0] * (max_chunks - len(blocks))
        chunk_matrix.append(row)

    columns = []
    for column_index in range(max_chunks):
        columns.append([row[column_index] for row in chunk_matrix])

    return {
        "chunk_matrix": chunk_matrix,
        "columns": columns,
        "length_list": length_list,
        "max_chunks": max_chunks,
    }


def reconstruct_bytes(blocks, original_length, chunk_size):
    """将解密出的整数块恢复为原始字节串。"""
    recovered = bytearray()
    block_count = len(blocks)

    for index, block in enumerate(blocks):
        if index == block_count - 1:
            block_length = original_length - chunk_size * (block_count - 1)
        else:
            block_length = chunk_size
        block_bytes = block.to_bytes(block_length, "big")
        recovered.extend(block_bytes)

    return bytes(recovered)


def run_extended_pir_demo(messages, target_index):
    """模拟客户端持有 AES 密钥、服务器持有 AES 密文的扩展版 PIR。"""
    timings = {}

    start = perf_counter()
    public_key, private_key = paillier.generate_paillier_keypair()
    timings["keygen"] = perf_counter() - start

    start = perf_counter()
    aes_key = token_bytes(AES_KEY_SIZE)
    encrypted_messages = encrypt_messages_with_aes(messages, aes_key)
    timings["aes_encrypt"] = perf_counter() - start

    chunk_size = compute_chunk_size(public_key)
    prepared = prepare_server_chunks(encrypted_messages, chunk_size)

    start = perf_counter()
    encrypted_query = build_encrypted_query(public_key, target_index, len(messages))
    timings["query"] = perf_counter() - start

    start = perf_counter()
    encrypted_blocks = []
    for column in prepared["columns"]:
        encrypted_blocks.append(server_compute_response(column, encrypted_query))
    timings["server"] = perf_counter() - start

    start = perf_counter()
    decrypted_blocks = [private_key.decrypt(block) for block in encrypted_blocks]
    selected_ciphertext = reconstruct_bytes(
        decrypted_blocks,
        prepared["length_list"][target_index],
        chunk_size,
    )
    timings["paillier_decrypt"] = perf_counter() - start

    start = perf_counter()
    nonce = selected_ciphertext[:AES_NONCE_SIZE]
    ciphertext = selected_ciphertext[AES_NONCE_SIZE:]
    recovered_message = AESGCM(aes_key).decrypt(nonce, ciphertext, None).decode("utf-8")
    timings["aes_decrypt"] = perf_counter() - start

    return {
        "public_key": public_key,
        "aes_key": aes_key,
        "encrypted_messages": encrypted_messages,
        "target_ciphertext": encrypted_messages[target_index],
        "selected_ciphertext": selected_ciphertext,
        "chunk_size": chunk_size,
        "chunk_count": prepared["max_chunks"],
        "encrypted_query": encrypted_query,
        "decrypted_blocks": decrypted_blocks,
        "recovered_message": recovered_message,
        "expected_message": messages[target_index],
        "timings": timings,
    }


def benchmark_average_timings(messages, target_index, runs):
    """重复统计扩展版 PIR 各阶段平均耗时。"""
    timing_keys = ["keygen", "aes_encrypt", "query", "server", "paillier_decrypt", "aes_decrypt"]
    totals = {key: 0.0 for key in timing_keys}

    for _ in range(runs):
        result = run_extended_pir_demo(messages, target_index)
        for key in timing_keys:
            totals[key] += result["timings"][key]

    return {key: totals[key] / runs for key in timing_keys}


def main():
    result = run_extended_pir_demo(PLAINTEXT_MESSAGES, TARGET_INDEX)
    average_timings = benchmark_average_timings(
        PLAINTEXT_MESSAGES,
        TARGET_INDEX,
        BENCHMARK_RUNS,
    )

    print("========== 基于 AES-GCM + Paillier 的扩展版 PIR 模拟 ==========")
    print(f"消息总数: {len(PLAINTEXT_MESSAGES)}")
    print(f"目标位置(从 0 开始): {TARGET_INDEX}")
    print(f"目标明文: {result['expected_message']}")
    print()

    print("1. 客户端本地生成 AES 密钥并预加密消息")
    print(f"   AES-256 密钥预览: {preview_hex(result['aes_key'])}")
    print(f"   目标密文预览: {preview_hex(result['target_ciphertext'])}")
    print(f"   耗时: {result['timings']['aes_encrypt']:.6f} s")
    print()

    print("2. 客户端生成 Paillier 密钥并构造 PIR 查询")
    print(f"   公钥模数 n 的十进制位数: {len(str(result['public_key'].n))}")
    print(f"   单块字节数: {result['chunk_size']}")
    print(f"   目标密文共分块: {result['chunk_count']}")
    print(f"   密钥生成耗时: {result['timings']['keygen']:.6f} s")
    print(f"   查询构造耗时: {result['timings']['query']:.6f} s")
    print()

    print("3. 服务器按块执行多轮 PIR 响应")
    print(f"   服务器同态计算耗时: {result['timings']['server']:.6f} s")
    print(f"   首个恢复块整数: {result['decrypted_blocks'][0]}")
    print()

    print("4. 客户端恢复 AES 密文并解密明文")
    print(f"   恢复出的目标密文是否一致: {result['selected_ciphertext'] == result['target_ciphertext']}")
    print(f"   恢复明文: {result['recovered_message']}")
    print(f"   是否与目标消息一致: {result['recovered_message'] == result['expected_message']}")
    print(f"   Paillier 解密耗时: {result['timings']['paillier_decrypt']:.6f} s")
    print(f"   AES 解密耗时: {result['timings']['aes_decrypt']:.6f} s")
    print()

    print(f"5. 连续运行 {BENCHMARK_RUNS} 次后的平均耗时")
    print(f"   平均密钥生成耗时: {average_timings['keygen']:.6f} s")
    print(f"   平均 AES 预加密耗时: {average_timings['aes_encrypt']:.6f} s")
    print(f"   平均查询向量构造耗时: {average_timings['query']:.6f} s")
    print(f"   平均服务器同态计算耗时: {average_timings['server']:.6f} s")
    print(f"   平均 Paillier 解密耗时: {average_timings['paillier_decrypt']:.6f} s")
    print(f"   平均 AES 解密耗时: {average_timings['aes_decrypt']:.6f} s")


if __name__ == "__main__":
    main()
