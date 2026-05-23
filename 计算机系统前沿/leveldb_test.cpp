#include <iostream>
#include <vector>
#include <string>
#include <numeric>     // 用于 std::iota
#include <random>      // 用于随机数生成
#include <algorithm>   // 用于 std::shuffle
#include <chrono>      // 用于高精度计时

// 引入 LevelDB 头文件
#include "leveldb/db.h"
#include "leveldb/options.h"

// ============================================================================
// 工具类：Zipf 分布生成器 (用于模拟真实的“二八定律”热点访问)
// ============================================================================
class ZipfGenerator {
private:
    std::mt19937 gen_;
    std::discrete_distribution<int> dist_;

public:
    // 构造函数：预计算概率分布
    ZipfGenerator(int N, double s = 0.99) : gen_(std::random_device{}()) {
        std::vector<double> weights(N);
        for (int i = 1; i <= N; ++i) {
            weights[i - 1] = 1.0 / std::pow(i, s); // Zipf 公式
        }
        dist_ = std::discrete_distribution<int>(weights.begin(), weights.end());
    }

    // 生成下一个随机 Key 的编号 (范围 1 到 N)
    int Next() {
        return dist_(gen_) + 1;
    }
};

// ============================================================================
// 辅助函数：将整数格式化为定长字符串 Key (例如: "user_key_0001234")
// ============================================================================
std::string FormatKey(int num) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "user_key_%07d", num);
    return std::string(buffer);
}

int main() {
    // ------------------------------------------------------------------------
    // [配置参数] (建议先用这组小参数测试，避免跑太久)
    // ------------------------------------------------------------------------
    const int NUM_LOAD_KEYS = 100000; // Load 阶段：向空数据库注入 10 万条数据
    const int NUM_RUN_OPS = 200000;   // Run 阶段：执行 20 万次随机读写操作
    const std::string DB_PATH = "/tmp/leveldb_student_test"; // leveldb的存储位置，可自己设置

    std::cout << "========== 数据库压测教学程序 ==========\n";

    // ------------------------------------------------------------------------
    // 第一步：准备 Load 阶段的随机数据集
    // ------------------------------------------------------------------------
    std::cout << "[1/4] 正在生成 Load 阶段的随机打乱数据集...\n";
    std::vector<int> load_keys(NUM_LOAD_KEYS);
    // std::iota 会把数组填满 1, 2, 3 ... N
    std::iota(load_keys.begin(), load_keys.end(), 1); 
    
    // 打乱查询数据集
    std::mt19937 random_engine(std::random_device{}());
    std::shuffle(load_keys.begin(), load_keys.end(), random_engine);

    // ------------------------------------------------------------------------
    // 第二步：初始化并打开 LevelDB
    // ------------------------------------------------------------------------
    std::cout << "[2/4] 正在初始化 LevelDB...\n";
    leveldb::DB* db;
	//【重要】这里设置leveldb的option
    leveldb::Options options;
    options.create_if_missing = true;          // 如果目录不存在则创建
    options.write_buffer_size = 4 * 1024 * 1024; // 4MB 的 MemTable (写缓存)

    leveldb::Status status = leveldb::DB::Open(options, DB_PATH, &db);
    if (!status.ok()) {
        std::cerr << "LevelDB 打开失败: " << status.ToString() << "\n";
        return -1;
    }

    // ------------------------------------------------------------------------
    // 第三步：执行 Load 阶段 (初始化数据库)
    // ------------------------------------------------------------------------
    std::cout << "[3/4] 开始 Load 阶段 (随机插入 " << NUM_LOAD_KEYS << " 条数据)...\n";
    auto start_time = std::chrono::high_resolution_clock::now();

    leveldb::WriteOptions write_opts; // 默认异步写，性能好
    std::string dummy_value(100, 'x'); // 模拟 100 字节的 Value 数据 (全是 'x')

    for (int i = 0; i < NUM_LOAD_KEYS; ++i) {
        std::string key = FormatKey(load_keys[i]);
        db->Put(write_opts, key, dummy_value);
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> load_duration = end_time - start_time;
    std::cout << "  -> Load 完成！耗时: " << load_duration.count() << " 秒\n";

    // ------------------------------------------------------------------------
    // 第四步：执行 Run 阶段 
    // ------------------------------------------------------------------------
    std::cout << "[4/4] 开始 Run 阶段 (Zipf 分布, " << NUM_RUN_OPS << " 次操作)...\n";
    ZipfGenerator zipf(NUM_LOAD_KEYS, 1.2); // 初始化 Zipf 生成器，倾斜度 1.2
    
    // 准备一个均匀分布的随机数发生器，用于决定是执行 Get 还是 Put
    std::uniform_real_distribution<double> op_dist(0.0, 1.0);

    int get_count = 0, put_count = 0, not_found_count = 0;
    leveldb::ReadOptions read_opts;
    std::string read_value;

    start_time = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < NUM_RUN_OPS; ++i) {
        // 1. 通过 Zipf 分布获取一个目标 Key
        std::string target_key = FormatKey(zipf.Next());

        // 2. 掷骰子决定操作类型：例如80%读取(Get)，20%写入(Put)，可自行设置比例
        double dice = op_dist(random_engine);
        
        if (dice < 0.80) {
            // 执行读操作
			//【重要】如果实现KV cache，可在这里实现，查找leveldb之前先经过KV cache
            status = db->Get(read_opts, target_key, &read_value);
            if (status.ok()) {
                get_count++;
            } else if (status.IsNotFound()) {
                not_found_count++; // 如果之前没有 load 这个数据就会找不到
            }
        } else {
            // 执行写操作 (更新一个带时间戳的新值)
            std::string new_value = "updated_value_" + std::to_string(i);
            db->Put(write_opts, target_key, new_value);
            put_count++;
        }
    }

    end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> run_duration = end_time - start_time;

    // ------------------------------------------------------------------------
    // 输出统计报告
    // ------------------------------------------------------------------------
    std::cout << "\n========== 测试报告 ==========\n";
    std::cout << "Run 阶段总耗时: " << run_duration.count() << " 秒\n";
    std::cout << "总操作数 (QPS): " << NUM_RUN_OPS / run_duration.count() << " ops/sec\n";
    std::cout << "操作分布: 成功读取 " << get_count << " 次, 更新写入 " << put_count << " 次\n";
    if (not_found_count > 0) {
        std::cout << "警告: 有 " << not_found_count << " 次查询未找到数据 (Key 不存在)\n";
    }


    delete db;
    return 0;
}