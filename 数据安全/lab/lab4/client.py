import pymysql
import random
import argparse
import csv
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import base64

local_table = {}
key = get_random_bytes(16)
base_iv = get_random_bytes(16)
DB_HOST = "localhost"
DB_USER = "user"
DB_PASSWD = "123456"
DB_NAME = "test_db"


def ConnectDB():
    return pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASSWD, database=DB_NAME)


def FetchOne(cur):
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("empty result")
    return row


def AES_ENC(plaintext, iv):
    # AES 加密
    aes = AES.new(key, AES.MODE_CBC, iv=iv)
    padded_data = pad(plaintext, AES.block_size, style='pkcs7')
    ciphertext = aes.encrypt(padded_data)
    return ciphertext


def AES_DEC(ciphertext, iv):
    # AES 解密
    aes = AES.new(key, AES.MODE_CBC, iv=iv)
    padded_data = aes.decrypt(ciphertext)
    plaintext = unpad(padded_data, AES.block_size, style='pkcs7')
    return plaintext


def Random_Encrypt(plaintext):
    #  随机生成 iv 来保证加密结果的随机性
    iv = get_random_bytes(16)
    ciphertext = AES_ENC(iv + AES_ENC(plaintext.encode('utf-8'), iv), base_iv)
    ciphertext = base64.b64encode(ciphertext)
    return ciphertext.decode('utf-8')


def Random_Decrypt(ciphertext):
    plaintext = AES_DEC(base64.b64decode(ciphertext.encode('utf-8')) ,base_iv)
    plaintext = AES_DEC(plaintext[16:],plaintext[: 16])
    return plaintext.decode('utf-8')


def CalPos(plaintext):
    # 插入 plaintext，返回对应的 Pos
    presum = sum([v for k, v in local_table.items() if k < plaintext])
    if plaintext in local_table:
        local_table[plaintext] += 1
        return random.randint(presum, presum + local_table[plaintext] - 1)
    else:
        local_table[plaintext] = 1
        return presum


def GetLeftPos(plaintext):
    return sum([v for k, v in local_table.items() if k < plaintext])


def GetRightPos(plaintext):
    return sum([v for k, v in local_table.items() if k <= plaintext])


def Insert(plaintext):
    ciphertext = Random_Encrypt(plaintext)
    pos = CalPos(plaintext)
    conn = ConnectDB()
    cur = conn.cursor()
    cur.execute("select FHInsert(%s, %s)", (pos, ciphertext))
    encoding = int(FetchOne(cur)[0])
    cur.execute("insert into example values (%s, %s)", (encoding, ciphertext))
    update_range = None
    updated_rows = 0
    final_encoding = encoding
    if encoding == 0:
        cur.execute("select FHStart(), FHEnd()")
        start_update, end_update = FetchOne(cur)
        update_range = (int(start_update), int(end_update))
        cur.execute(
            "update example "
            "set encoding = FHUpdate(ciphertext) "
            "where (encoding >= FHStart() and encoding < FHEnd()) or (encoding = 0)"
        )
        updated_rows = cur.rowcount
        cur.execute("select encoding from example where ciphertext = %s", (ciphertext,))
        final_encoding = int(FetchOne(cur)[0])
    conn.commit()
    conn.close()
    return {
        "pos": pos,
        "encoding": encoding,
        "update_range": update_range,
        "updated_rows": updated_rows,
        "final_encoding": final_encoding,
    }


def Search(left, right):
    # 搜索[left,right]中的信息
    left_pos = GetLeftPos(left)
    right_pos = GetRightPos(right)
    # 连接数据库
    conn = ConnectDB()
    cur = conn.cursor()
    cur.execute(
    f"select    ciphertext    from     example    where     encoding     >=    FHSearch({left_pos})     and    encoding     < FHSearch({right_pos})")
    rest = cur.fetchall()
    for x in rest:
        print(f"ciphtertext: {x[0]} plaintext: {Random_Decrypt(x[0])}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--value", default="apple")
    parser.add_argument("--repeat", type=int, default=500)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--report-every", type=int, default=1)
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--debug", action="store_true", help="enable C++ FHSetDebug logging (to MySQL error.log)")
    parser.add_argument("--csv", default=None, help="export per-insertion data to CSV file")
    args = parser.parse_args()

    random.seed(args.seed)

    # 开启 C++ 侧调试日志
    if args.debug:
        dbg = ConnectDB()
        dbg_cursor = dbg.cursor()
        dbg_cursor.execute("select FHSetDebug(1)")
        dbg.close()
        print("[client] FHSetDebug(1) enabled, see MySQL error log for rebalance/recode events")

    # 准备 CSV 写入
    csv_file = None
    csv_writer = None
    if args.csv:
        csv_file = open(args.csv, "w", newline="")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["round", "value", "pos", "encoding", "final_encoding",
                             "is_recode", "update_start", "update_end", "updated_rows"])

    recode_count = 0
    for i in range(1, args.repeat + 1):
        result = Insert(args.value)
        if result["encoding"] == 0:
            recode_count += 1

        # 写入 CSV
        if csv_writer:
            is_rec = 1 if result["encoding"] == 0 else 0
            ustart = result["update_range"][0] if result["update_range"] else ""
            uend = result["update_range"][1] if result["update_range"] else ""
            csv_writer.writerow([
                i, args.value, result["pos"], result["encoding"],
                result["final_encoding"], is_rec, ustart, uend,
                result["updated_rows"]
            ])

        if args.report_every > 0 and (i % args.report_every == 0 or result["encoding"] == 0):
            print(
                f"i={i} value={args.value} pos={result['pos']} "
                f"enc={result['encoding']} final={result['final_encoding']} "
                f"range={result['update_range']} updated={result['updated_rows']}"
            )

    print(f"repeat={args.repeat} value={args.value} seed={args.seed} recode={recode_count}")

    # 查询 Server 侧统计
    if args.debug:
        conn = ConnectDB()
        cur = conn.cursor()
        cur.execute("select FHGetRebalanceCnt()")
        rb_cnt = int(cur.fetchone()[0])
        cur.execute("select FHGetRecodeCnt()")
        rc_cnt = int(cur.fetchone()[0])
        conn.close()
        print(f"rebalance_cnt={rb_cnt} recode_cnt(server)={rc_cnt}")

    # 关闭 CSV
    if csv_file:
        csv_file.close()
        print(f"CSV saved to {args.csv}")

    if args.search:
        Search(args.value, args.value)
