#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <list>
#include <memory>
#include <numeric>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "leveldb/cache.h"
#include "leveldb/db.h"
#include "leveldb/filter_policy.h"
#include "leveldb/iterator.h"
#include "leveldb/options.h"
#include "leveldb/write_batch.h"

namespace {

using Clock = std::chrono::steady_clock;

struct Config {
    std::string mode = "mixed";
    std::string db_path = "/tmp/leveldb_lab2";
    std::string output_prefix = "results/default";
    std::string load_pattern = "random";
    std::string run_pattern = "zipf";
    std::size_t num_keys = 100000;
    std::size_t load_keys = 100000;
    std::size_t run_ops = 200000;
    std::size_t value_size = 1024;
    std::size_t range_length = 16;
    std::size_t load_batch_size = 1000;
    int read_ratio = 80;
    int scan_ratio = 0;
    double zipf_skew = 1.2;
    bool create_if_missing = true;
    bool destroy_db = false;
    bool fill_cache = true;
    bool use_kv_cache = false;
    bool print_every_second = false;
    std::size_t kv_cache_capacity = 0;
    std::size_t write_buffer_size = 4ULL * 1024 * 1024;
    std::size_t block_size = 4ULL * 1024;
    std::size_t block_cache_size = 64ULL * 1024 * 1024;
    int bloom_bits = -1;
};

std::string FormatKey(std::size_t num) {
    char buffer[32];
    std::snprintf(buffer, sizeof(buffer), "user_key_%010zu", num);
    return std::string(buffer);
}

std::string MakeValue(std::size_t key_id, std::size_t value_size) {
    std::string value(value_size, 'a');
    std::string suffix = "_value_" + std::to_string(key_id);
    if (suffix.size() < value.size()) {
        value.replace(value.size() - suffix.size(), suffix.size(), suffix);
    } else {
        value = suffix.substr(0, value_size);
    }
    return value;
}

std::string DirName(const std::string& path) {
    std::size_t pos = path.find_last_of('/');
    if (pos == std::string::npos) {
        return ".";
    }
    if (pos == 0) {
        return "/";
    }
    return path.substr(0, pos);
}

void EnsureParentDirectory(const std::string& path) {
    std::string command = "mkdir -p \"" + DirName(path) + "\"";
    int rc = std::system(command.c_str());
    if (rc != 0) {
        throw std::runtime_error("failed to create output directory");
    }
}

std::string GetArgValue(const std::string& arg) {
    std::size_t pos = arg.find('=');
    if (pos == std::string::npos) {
        throw std::invalid_argument("missing '=' in argument: " + arg);
    }
    return arg.substr(pos + 1);
}

bool ParseBool(const std::string& value) {
    if (value == "1" || value == "true" || value == "yes") {
        return true;
    }
    if (value == "0" || value == "false" || value == "no") {
        return false;
    }
    throw std::invalid_argument("invalid bool: " + value);
}

std::size_t ParseSize(const std::string& value) {
    if (value.empty()) {
        throw std::invalid_argument("empty size");
    }
    char suffix = value.back();
    std::size_t multiplier = 1;
    std::string digits = value;
    if (suffix == 'k' || suffix == 'K') {
        multiplier = 1024ULL;
        digits.pop_back();
    } else if (suffix == 'm' || suffix == 'M') {
        multiplier = 1024ULL * 1024;
        digits.pop_back();
    } else if (suffix == 'g' || suffix == 'G') {
        multiplier = 1024ULL * 1024 * 1024;
        digits.pop_back();
    }
    return static_cast<std::size_t>(std::stoull(digits) * multiplier);
}

Config ParseArgs(int argc, char** argv) {
    Config cfg;
    for (int i = 1; i < argc; ++i) {
        std::string arg(argv[i]);
        if (arg == "--help") {
            std::cout
                << "Usage: ./leveldb_lab [options]\n"
                << "  --mode=load|readwrite|write_only|scan_only|mixed\n"
                << "  --db_path=/path/to/db\n"
                << "  --output_prefix=results/task1_case1\n"
                << "  --load_keys=2000000 --run_ops=1000000 --value_size=1024\n"
                << "  --load_batch_size=1000\n"
                << "  --write_buffer_size=4M --block_size=4K --block_cache_size=64M\n"
                << "  --bloom_bits=10 --fill_cache=true --use_kv_cache=false\n"
                << "  --kv_cache_capacity=256M --read_ratio=80 --scan_ratio=10\n"
                << "  --range_length=32 --run_pattern=zipf --zipf_skew=1.2\n"
                << "  --destroy_db=true --print_every_second=true\n";
            std::exit(0);
        } else if (arg.rfind("--mode=", 0) == 0) {
            cfg.mode = GetArgValue(arg);
        } else if (arg.rfind("--db_path=", 0) == 0) {
            cfg.db_path = GetArgValue(arg);
        } else if (arg.rfind("--output_prefix=", 0) == 0) {
            cfg.output_prefix = GetArgValue(arg);
        } else if (arg.rfind("--load_pattern=", 0) == 0) {
            cfg.load_pattern = GetArgValue(arg);
        } else if (arg.rfind("--run_pattern=", 0) == 0) {
            cfg.run_pattern = GetArgValue(arg);
        } else if (arg.rfind("--num_keys=", 0) == 0) {
            cfg.num_keys = static_cast<std::size_t>(std::stoull(GetArgValue(arg)));
        } else if (arg.rfind("--load_keys=", 0) == 0) {
            cfg.load_keys = static_cast<std::size_t>(std::stoull(GetArgValue(arg)));
        } else if (arg.rfind("--run_ops=", 0) == 0) {
            cfg.run_ops = static_cast<std::size_t>(std::stoull(GetArgValue(arg)));
        } else if (arg.rfind("--value_size=", 0) == 0) {
            cfg.value_size = static_cast<std::size_t>(std::stoull(GetArgValue(arg)));
        } else if (arg.rfind("--range_length=", 0) == 0) {
            cfg.range_length = static_cast<std::size_t>(std::stoull(GetArgValue(arg)));
        } else if (arg.rfind("--load_batch_size=", 0) == 0) {
            cfg.load_batch_size = static_cast<std::size_t>(std::stoull(GetArgValue(arg)));
        } else if (arg.rfind("--read_ratio=", 0) == 0) {
            cfg.read_ratio = std::stoi(GetArgValue(arg));
        } else if (arg.rfind("--scan_ratio=", 0) == 0) {
            cfg.scan_ratio = std::stoi(GetArgValue(arg));
        } else if (arg.rfind("--zipf_skew=", 0) == 0) {
            cfg.zipf_skew = std::stod(GetArgValue(arg));
        } else if (arg.rfind("--create_if_missing=", 0) == 0) {
            cfg.create_if_missing = ParseBool(GetArgValue(arg));
        } else if (arg.rfind("--destroy_db=", 0) == 0) {
            cfg.destroy_db = ParseBool(GetArgValue(arg));
        } else if (arg.rfind("--fill_cache=", 0) == 0) {
            cfg.fill_cache = ParseBool(GetArgValue(arg));
        } else if (arg.rfind("--use_kv_cache=", 0) == 0) {
            cfg.use_kv_cache = ParseBool(GetArgValue(arg));
        } else if (arg.rfind("--print_every_second=", 0) == 0) {
            cfg.print_every_second = ParseBool(GetArgValue(arg));
        } else if (arg.rfind("--kv_cache_capacity=", 0) == 0) {
            cfg.kv_cache_capacity = ParseSize(GetArgValue(arg));
        } else if (arg.rfind("--write_buffer_size=", 0) == 0) {
            cfg.write_buffer_size = ParseSize(GetArgValue(arg));
        } else if (arg.rfind("--block_size=", 0) == 0) {
            cfg.block_size = ParseSize(GetArgValue(arg));
        } else if (arg.rfind("--block_cache_size=", 0) == 0) {
            cfg.block_cache_size = ParseSize(GetArgValue(arg));
        } else if (arg.rfind("--bloom_bits=", 0) == 0) {
            cfg.bloom_bits = std::stoi(GetArgValue(arg));
        } else {
            throw std::invalid_argument("unknown argument: " + arg);
        }
    }
    if (cfg.load_keys == 0) {
        cfg.load_keys = cfg.num_keys;
    }
    if (cfg.num_keys == 0) {
        cfg.num_keys = cfg.load_keys;
    }
    return cfg;
}

class ZipfGenerator {
public:
    ZipfGenerator(std::size_t n, double s, uint32_t seed)
        : gen_(seed) {
        std::vector<double> weights(n);
        for (std::size_t i = 1; i <= n; ++i) {
            weights[i - 1] = 1.0 / std::pow(static_cast<double>(i), s);
        }
        dist_ = std::discrete_distribution<std::size_t>(weights.begin(), weights.end());
    }

    std::size_t Next() {
        return dist_(gen_) + 1;
    }

private:
    std::mt19937 gen_;
    std::discrete_distribution<std::size_t> dist_;
};

class KeyGenerator {
public:
    explicit KeyGenerator(const Config& cfg)
        : cfg_(cfg),
          gen_(std::random_device{}()),
          uniform_(1, cfg_.num_keys),
          zipf_(cfg_.num_keys, cfg_.zipf_skew, std::random_device{}()) {
    }

    std::size_t Next() {
        if (cfg_.run_pattern == "uniform") {
            return uniform_(gen_);
        }
        return zipf_.Next();
    }

private:
    const Config& cfg_;
    std::mt19937 gen_;
    std::uniform_int_distribution<std::size_t> uniform_;
    ZipfGenerator zipf_;
};

struct Sample {
    double latency_us = 0.0;
    double elapsed_s = 0.0;
    std::string op;
};

class LruKVCache {
public:
    explicit LruKVCache(std::size_t capacity_bytes)
        : capacity_bytes_(capacity_bytes) {}

    bool Enabled() const {
        return capacity_bytes_ > 0;
    }

    bool Get(const std::string& key, std::string* value) {
        auto it = map_.find(key);
        if (it == map_.end()) {
            return false;
        }
        entries_.splice(entries_.begin(), entries_, it->second);
        *value = it->second->second;
        return true;
    }

    void Put(const std::string& key, const std::string& value) {
        if (!Enabled()) {
            return;
        }
        std::size_t entry_bytes = key.size() + value.size();
        if (entry_bytes > capacity_bytes_) {
            Clear();
            return;
        }
        auto it = map_.find(key);
        if (it != map_.end()) {
            current_bytes_ -= it->second->first.size() + it->second->second.size();
            entries_.erase(it->second);
            map_.erase(it);
        }
        entries_.push_front(std::make_pair(key, value));
        map_[key] = entries_.begin();
        current_bytes_ += entry_bytes;
        Shrink();
    }

    void Invalidate(const std::string& key) {
        auto it = map_.find(key);
        if (it == map_.end()) {
            return;
        }
        current_bytes_ -= it->second->first.size() + it->second->second.size();
        entries_.erase(it->second);
        map_.erase(it);
    }

    void Clear() {
        entries_.clear();
        map_.clear();
        current_bytes_ = 0;
    }

private:
    using List = std::list<std::pair<std::string, std::string>>;

    void Shrink() {
        while (current_bytes_ > capacity_bytes_ && !entries_.empty()) {
            auto it = std::prev(entries_.end());
            current_bytes_ -= it->first.size() + it->second.size();
            map_.erase(it->first);
            entries_.erase(it);
        }
    }

    std::size_t capacity_bytes_ = 0;
    std::size_t current_bytes_ = 0;
    List entries_;
    std::unordered_map<std::string, List::iterator> map_;
};

struct Summary {
    std::size_t total_ops = 0;
    std::size_t get_ops = 0;
    std::size_t put_ops = 0;
    std::size_t scan_ops = 0;
    std::size_t not_found = 0;
    std::size_t kv_cache_hits = 0;
    std::size_t kv_cache_misses = 0;
    double total_seconds = 0.0;
    double qps = 0.0;
    double p50_us = 0.0;
    double p90_us = 0.0;
    double p99_us = 0.0;
    double p999_us = 0.0;
};

double Percentile(std::vector<double> values, double ratio) {
    if (values.empty()) {
        return 0.0;
    }
    std::sort(values.begin(), values.end());
    std::size_t index = static_cast<std::size_t>(ratio * static_cast<double>(values.size() - 1));
    return values[index];
}

Summary BuildSummary(const std::vector<Sample>& samples, const Summary& counters) {
    Summary s = counters;
    std::vector<double> latencies;
    latencies.reserve(samples.size());
    for (const auto& sample : samples) {
        latencies.push_back(sample.latency_us);
    }
    s.total_ops = samples.size();
    s.p50_us = Percentile(latencies, 0.50);
    s.p90_us = Percentile(latencies, 0.90);
    s.p99_us = Percentile(latencies, 0.99);
    s.p999_us = Percentile(latencies, 0.999);
    if (s.total_seconds > 0.0) {
        s.qps = static_cast<double>(s.total_ops) / s.total_seconds;
    }
    return s;
}

void WriteCsv(const std::string& path, const std::vector<Sample>& samples) {
    EnsureParentDirectory(path);
    std::ofstream out(path.c_str());
    out << "op_index,elapsed_s,latency_us,op\n";
    for (std::size_t i = 0; i < samples.size(); ++i) {
        out << i << ',' << std::fixed << std::setprecision(6) << samples[i].elapsed_s
            << ',' << samples[i].latency_us << ',' << samples[i].op << '\n';
    }
}

void WriteSummary(const std::string& path, const Config& cfg, const Summary& s) {
    EnsureParentDirectory(path);
    std::ofstream out(path.c_str());
    out << "mode," << cfg.mode << '\n';
    out << "db_path," << cfg.db_path << '\n';
    out << "num_keys," << cfg.num_keys << '\n';
    out << "load_keys," << cfg.load_keys << '\n';
    out << "run_ops," << cfg.run_ops << '\n';
    out << "value_size," << cfg.value_size << '\n';
    out << "write_buffer_size," << cfg.write_buffer_size << '\n';
    out << "block_size," << cfg.block_size << '\n';
    out << "block_cache_size," << cfg.block_cache_size << '\n';
    out << "bloom_bits," << cfg.bloom_bits << '\n';
    out << "fill_cache," << (cfg.fill_cache ? 1 : 0) << '\n';
    out << "use_kv_cache," << (cfg.use_kv_cache ? 1 : 0) << '\n';
    out << "kv_cache_capacity," << cfg.kv_cache_capacity << '\n';
    out << "range_length," << cfg.range_length << '\n';
    out << "run_pattern," << cfg.run_pattern << '\n';
    out << "zipf_skew," << cfg.zipf_skew << '\n';
    out << "total_ops," << s.total_ops << '\n';
    out << "get_ops," << s.get_ops << '\n';
    out << "put_ops," << s.put_ops << '\n';
    out << "scan_ops," << s.scan_ops << '\n';
    out << "not_found," << s.not_found << '\n';
    out << "kv_cache_hits," << s.kv_cache_hits << '\n';
    out << "kv_cache_misses," << s.kv_cache_misses << '\n';
    out << "total_seconds," << s.total_seconds << '\n';
    out << "qps," << s.qps << '\n';
    out << "p50_us," << s.p50_us << '\n';
    out << "p90_us," << s.p90_us << '\n';
    out << "p99_us," << s.p99_us << '\n';
    out << "p999_us," << s.p999_us << '\n';
}

void PrintConfig(const Config& cfg) {
    std::cout << "========== LevelDB Lab Runner ==========\n";
    std::cout << "mode=" << cfg.mode << "\n";
    std::cout << "db_path=" << cfg.db_path << "\n";
    std::cout << "num_keys=" << cfg.num_keys << ", load_keys=" << cfg.load_keys
              << ", run_ops=" << cfg.run_ops << "\n";
    std::cout << "value_size=" << cfg.value_size << ", range_length=" << cfg.range_length << "\n";
    std::cout << "load_batch_size=" << cfg.load_batch_size << "\n";
    std::cout << "write_buffer_size=" << cfg.write_buffer_size
              << ", block_size=" << cfg.block_size
              << ", block_cache_size=" << cfg.block_cache_size << "\n";
    std::cout << "bloom_bits=" << cfg.bloom_bits
              << ", fill_cache=" << cfg.fill_cache
              << ", use_kv_cache=" << cfg.use_kv_cache
              << ", kv_cache_capacity=" << cfg.kv_cache_capacity << "\n";
    std::cout << "run_pattern=" << cfg.run_pattern
              << ", read_ratio=" << cfg.read_ratio
              << ", scan_ratio=" << cfg.scan_ratio << "\n";
}

void FillDatabase(leveldb::DB* db, const Config& cfg) {
    std::vector<std::size_t> keys(cfg.load_keys);
    std::iota(keys.begin(), keys.end(), 1);
    if (cfg.load_pattern == "random") {
        std::mt19937 gen(std::random_device{}());
        std::shuffle(keys.begin(), keys.end(), gen);
    }

    leveldb::WriteOptions write_options;
    auto begin = Clock::now();
    leveldb::WriteBatch batch;
    std::size_t batch_count = 0;
    for (std::size_t i = 0; i < keys.size(); ++i) {
        batch.Put(FormatKey(keys[i]), MakeValue(keys[i], cfg.value_size));
        ++batch_count;
        if (batch_count < cfg.load_batch_size && i + 1 != keys.size()) {
            continue;
        }
        leveldb::Status status = db->Write(write_options, &batch);
        if (!status.ok()) {
            throw std::runtime_error("load failed: " + status.ToString());
        }
        batch.Clear();
        batch_count = 0;
        if ((i + 1) % 100000 == 0) {
            double seconds = std::chrono::duration<double>(Clock::now() - begin).count();
            std::cout << "load progress " << (i + 1) << "/" << keys.size()
                      << " qps=" << static_cast<double>(i + 1) / seconds << "\n";
        }
    }
}

void RunWorkload(leveldb::DB* db, const Config& cfg) {
    leveldb::ReadOptions read_options;
    read_options.fill_cache = cfg.fill_cache;
    leveldb::WriteOptions write_options;
    KeyGenerator key_generator(cfg);
    std::mt19937 gen(std::random_device{}());
    std::uniform_real_distribution<double> ratio_dist(0.0, 1.0);
    LruKVCache kv_cache(cfg.use_kv_cache ? cfg.kv_cache_capacity : 0);
    std::vector<Sample> samples;
    samples.reserve(cfg.run_ops);
    Summary counters;
    auto begin = Clock::now();
    auto last_report = begin;

    for (std::size_t i = 0; i < cfg.run_ops; ++i) {
        std::size_t key_id = key_generator.Next();
        std::string key = FormatKey(key_id);
        double dice = ratio_dist(gen);
        std::string op = "get";
        bool is_scan = false;
        bool is_put = false;
        if (cfg.mode == "write_only") {
            op = "put";
            is_put = true;
        } else if (cfg.mode == "scan_only") {
            op = "scan";
            is_scan = true;
        } else if (cfg.mode == "readwrite" || cfg.mode == "mixed") {
            if (dice * 100.0 >= cfg.read_ratio) {
                op = "put";
                is_put = true;
            }
            if (!is_put && cfg.scan_ratio > 0) {
                double scan_threshold = static_cast<double>(cfg.scan_ratio) / static_cast<double>(cfg.read_ratio);
                if ((dice / (static_cast<double>(cfg.read_ratio) / 100.0)) < scan_threshold) {
                    op = "scan";
                    is_scan = true;
                }
            }
        }

        auto op_begin = Clock::now();
        if (is_put) {
            std::string value = MakeValue(key_id + i, cfg.value_size);
            leveldb::Status status = db->Put(write_options, key, value);
            if (!status.ok()) {
                throw std::runtime_error("put failed: " + status.ToString());
            }
            kv_cache.Invalidate(key);
            counters.put_ops++;
        } else if (is_scan) {
            std::unique_ptr<leveldb::Iterator> it(db->NewIterator(read_options));
            std::size_t scanned = 0;
            for (it->Seek(key); it->Valid() && scanned < cfg.range_length; it->Next()) {
                ++scanned;
            }
            if (!it->status().ok()) {
                throw std::runtime_error("scan failed: " + it->status().ToString());
            }
            counters.scan_ops++;
        } else {
            std::string value;
            bool hit = false;
            if (kv_cache.Enabled()) {
                hit = kv_cache.Get(key, &value);
                if (hit) {
                    counters.kv_cache_hits++;
                } else {
                    counters.kv_cache_misses++;
                }
            }
            if (!hit) {
                leveldb::Status status = db->Get(read_options, key, &value);
                if (status.ok()) {
                    if (kv_cache.Enabled()) {
                        kv_cache.Put(key, value);
                    }
                } else if (status.IsNotFound()) {
                    counters.not_found++;
                } else {
                    throw std::runtime_error("get failed: " + status.ToString());
                }
            }
            counters.get_ops++;
        }
        auto op_end = Clock::now();
        samples.push_back(Sample{
            std::chrono::duration<double, std::micro>(op_end - op_begin).count(),
            std::chrono::duration<double>(op_end - begin).count(),
            op,
        });

        if (cfg.print_every_second && std::chrono::duration<double>(op_end - last_report).count() >= 1.0) {
            const Sample& last = samples.back();
            std::cout << "t=" << std::fixed << std::setprecision(1) << last.elapsed_s
                      << "s ops=" << samples.size()
                      << " last_op=" << last.op
                      << " last_latency_us=" << std::setprecision(2) << last.latency_us << "\n";
            last_report = op_end;
        }
    }

    counters.total_seconds = std::chrono::duration<double>(Clock::now() - begin).count();
    Summary summary = BuildSummary(samples, counters);
    WriteCsv(cfg.output_prefix + "_timeline.csv", samples);
    WriteSummary(cfg.output_prefix + "_summary.csv", cfg, summary);

    std::cout << "\n========== Summary ==========\n";
    std::cout << "total_ops=" << summary.total_ops << "\n";
    std::cout << "qps=" << summary.qps << "\n";
    std::cout << "p50_us=" << summary.p50_us << ", p90_us=" << summary.p90_us
              << ", p99_us=" << summary.p99_us << ", p999_us=" << summary.p999_us << "\n";
    std::cout << "get_ops=" << summary.get_ops << ", put_ops=" << summary.put_ops
              << ", scan_ops=" << summary.scan_ops << ", not_found=" << summary.not_found << "\n";
    std::cout << "kv_cache_hits=" << summary.kv_cache_hits
              << ", kv_cache_misses=" << summary.kv_cache_misses << "\n";
    std::cout << "summary_csv=" << cfg.output_prefix + "_summary.csv" << "\n";
    std::cout << "timeline_csv=" << cfg.output_prefix + "_timeline.csv" << "\n";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        Config cfg = ParseArgs(argc, argv);
        PrintConfig(cfg);

        leveldb::Options options;
        options.create_if_missing = cfg.create_if_missing;
        options.write_buffer_size = cfg.write_buffer_size;
        options.block_size = cfg.block_size;
        options.block_cache = leveldb::NewLRUCache(cfg.block_cache_size);

        std::unique_ptr<const leveldb::FilterPolicy> filter_guard;
        if (cfg.bloom_bits > 0) {
            filter_guard.reset(leveldb::NewBloomFilterPolicy(cfg.bloom_bits));
            options.filter_policy = filter_guard.get();
        }

        if (cfg.destroy_db) {
            leveldb::Status destroy_status = leveldb::DestroyDB(cfg.db_path, options);
            if (!destroy_status.ok()) {
                std::cerr << "warning: destroy db returned " << destroy_status.ToString() << "\n";
            }
        }

        leveldb::DB* raw_db = nullptr;
        leveldb::Status open_status = leveldb::DB::Open(options, cfg.db_path, &raw_db);
        if (!open_status.ok()) {
            std::cerr << "open db failed: " << open_status.ToString() << "\n";
            return 1;
        }
        std::unique_ptr<leveldb::DB> db(raw_db);

        if (cfg.mode == "load") {
            FillDatabase(db.get(), cfg);
        } else {
            if (cfg.load_keys > 0 && cfg.destroy_db) {
                FillDatabase(db.get(), cfg);
            }
            RunWorkload(db.get(), cfg);
        }

        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "fatal: " << ex.what() << "\n";
        return 1;
    }
}
