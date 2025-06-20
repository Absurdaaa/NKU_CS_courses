#ifndef MLP_DCU_OPTIMIZED_H
#define MLP_DCU_OPTIMIZED_H

#include <hip/hip_runtime.h>
#include <hipblas/hipblas.h>
#include <iostream>
#include <vector>
#include <string>
#include <chrono>
#include <memory>
#include <random>
#include <cmath>
#include <cassert>
#include <cstring>
#include <unordered_map>
#include <mutex>
#include <omp.h>
#include <fstream> // 添加缺失的头文件

// 错误检查宏
#define HIP_CHECK(status) { \
    if (status != hipSuccess) { \
        std::cerr << "HIP错误: " << hipGetErrorString(status) << " at line " << __LINE__ << std::endl; \
        exit(EXIT_FAILURE); \
    } \
}

#define HIPBLAS_CHECK(status) { \
    if (status != HIPBLAS_STATUS_SUCCESS) { \
        std::cerr << "hipBLAS错误: " << status << " at line " << __LINE__ << std::endl; \
        exit(EXIT_FAILURE); \
    } \
}

// 优化选项枚举
enum OptimizationFlags {
    OPT_NONE = 0,
    OPT_TILED_MATMUL = 1,
    OPT_FUSED_KERNELS = 2,
    OPT_MEMORY_POOL = 4,
    OPT_HIPBLAS = 8,
    OPT_MULTI_DCU = 16,
    OPT_ALL = 31
};

// 内存池类
class MemoryPool {
private:
    std::unordered_map<size_t, std::vector<double*>> device_pools;
    std::mutex mutex;
    bool enabled;

public:
    MemoryPool(bool enabled = true) : enabled(enabled) {}

    ~MemoryPool() {
        release();
    }

    double* allocate(size_t size) {
        if (!enabled) {
            double* ptr;
            HIP_CHECK(hipMalloc(&ptr, size * sizeof(double)));
            return ptr;
        }

        std::lock_guard<std::mutex> lock(mutex);
        
        if (!device_pools[size].empty()) {
            double* ptr = device_pools[size].back();
            device_pools[size].pop_back();
            return ptr;
        }
        
        double* ptr;
        HIP_CHECK(hipMalloc(&ptr, size * sizeof(double)));
        return ptr;
    }
    
    void free(double* ptr, size_t size) {
        if (!enabled) {
            HIP_CHECK(hipFree(ptr));
            return;
        }

        std::lock_guard<std::mutex> lock(mutex);
        device_pools[size].push_back(ptr);
    }
    
    void release() {
        std::lock_guard<std::mutex> lock(mutex);
        for (auto& pool : device_pools) {
            for (auto ptr : pool.second) {
                hipFree(ptr);
            }
        }
        device_pools.clear();
    }

    void setEnabled(bool value) {
        enabled = value;
    }
};

// 全局内存池
extern MemoryPool g_memoryPool;

// 计时工具类
class Timer {
private:
    std::chrono::high_resolution_clock::time_point start_time;
    std::chrono::high_resolution_clock::time_point end_time;
    bool running;

public:
    Timer() : running(false) {}

    void start() {
        start_time = std::chrono::high_resolution_clock::now();
        running = true;
    }

    void stop() {
        end_time = std::chrono::high_resolution_clock::now();
        running = false;
    }

    double elapsedMilliseconds() const {
        auto end = running ? std::chrono::high_resolution_clock::now() : end_time;
        return std::chrono::duration<double, std::milli>(end - start_time).count();
    }
};

// 矩阵类，用于管理设备和主机内存
class Matrix {
private:
    int rows;
    int cols;
    double* h_data;  // 主机内存
    double* d_data;  // 设备内存
    bool device_allocated;
    bool host_allocated;
    bool use_memory_pool;

public:
    // 构造函数
    Matrix(int rows, int cols, bool use_memory_pool = false) 
        : rows(rows), cols(cols), 
          device_allocated(false), 
          host_allocated(false),
          h_data(nullptr), d_data(nullptr),
          use_memory_pool(use_memory_pool) {}

    // 析构函数
    ~Matrix() {
        freeMemory();
    }

    // 拷贝构造函数 - 深拷贝
    Matrix(const Matrix& other) : rows(other.rows), cols(other.cols),
                                 device_allocated(false),
                                 host_allocated(false),
                                 h_data(nullptr), d_data(nullptr),
                                 use_memory_pool(other.use_memory_pool) {
        // 复制主机数据（如果存在）
        if (other.host_allocated) {
            allocateHost();
            std::memcpy(h_data, other.h_data, rows * cols * sizeof(double));
        }
        
        // 复制设备数据（如果存在）
        if (other.device_allocated) {
            allocateDevice();
            HIP_CHECK(hipMemcpy(d_data, other.d_data, rows * cols * sizeof(double), hipMemcpyDeviceToDevice));
        }
    }

    // 移动构造函数
    Matrix(Matrix&& other) noexcept : rows(other.rows), cols(other.cols),
                                     h_data(other.h_data), d_data(other.d_data),
                                     device_allocated(other.device_allocated),
                                     host_allocated(other.host_allocated),
                                     use_memory_pool(other.use_memory_pool) {
        // 重置源对象，防止析构时释放内存
        other.h_data = nullptr;
        other.d_data = nullptr;
        other.device_allocated = false;
        other.host_allocated = false;
        other.rows = 0;
        other.cols = 0;
    }

    // 拷贝赋值运算符 - 深拷贝
    Matrix& operator=(const Matrix& other) {
        if (this != &other) {
            // 释放当前资源
            freeMemory();
            
            // 复制新资源
            rows = other.rows;
            cols = other.cols;
            use_memory_pool = other.use_memory_pool;
            
            // 复制主机数据（如果存在）
            if (other.host_allocated) {
                allocateHost();
                std::memcpy(h_data, other.h_data, rows * cols * sizeof(double));
            }
            
            // 复制设备数据（如果存在）
            if (other.device_allocated) {
                allocateDevice();
                HIP_CHECK(hipMemcpy(d_data, other.d_data, rows * cols * sizeof(double), hipMemcpyDeviceToDevice));
            }
        }
        return *this;
    }

    // 移动赋值运算符
    Matrix& operator=(Matrix&& other) noexcept {
        if (this != &other) {
            // 释放当前资源
            freeMemory();
            
            // 移动资源
            rows = other.rows;
            cols = other.cols;
            h_data = other.h_data;
            d_data = other.d_data;
            device_allocated = other.device_allocated;
            host_allocated = other.host_allocated;
            use_memory_pool = other.use_memory_pool;
            
            // 重置源对象，防止析构时释放内存
            other.h_data = nullptr;
            other.d_data = nullptr;
            other.device_allocated = false;
            other.host_allocated = false;
            other.rows = 0;
            other.cols = 0;
        }
        return *this;
    }

    // 获取维度
    int getRows() const { return rows; }
    int getCols() const { return cols; }
    int size() const { return rows * cols; }

    // 分配主机内存
    void allocateHost() {
        if (!host_allocated) {
            h_data = new double[rows * cols]();
            host_allocated = true;
        }
    }

    // 分配设备内存
    void allocateDevice() {
        if (!device_allocated) {
            if (use_memory_pool) {
                d_data = g_memoryPool.allocate(rows * cols);
            } else {
                HIP_CHECK(hipMalloc(&d_data, rows * cols * sizeof(double)));
            }
            device_allocated = true;
        }
    }

    // 释放内存
    void freeMemory() {
        if (host_allocated && h_data != nullptr) {
            delete[] h_data;
            h_data = nullptr;
            host_allocated = false;
        }
        if (device_allocated && d_data != nullptr) {
            if (use_memory_pool) {
                g_memoryPool.free(d_data, rows * cols);
            } else {
                HIP_CHECK(hipFree(d_data));
            }
            d_data = nullptr;
            device_allocated = false;
        }
    }

    // 随机初始化
    void randomInit(double min = -1.0, double max = 1.0) {
        if (!host_allocated) {
            allocateHost();
        }

        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_real_distribution<double> dist(min, max);

        for (int i = 0; i < rows * cols; ++i) {
            h_data[i] = dist(gen);
        }
    }

    // 主机到设备的数据传输
    void copyToDevice() {
        if (!device_allocated) {
            allocateDevice();
        }
        if (host_allocated) {
            HIP_CHECK(hipMemcpy(d_data, h_data, rows * cols * sizeof(double), hipMemcpyHostToDevice));
        }
    }

    // 设备到主机的数据传输
    void copyToHost() {
        if (!host_allocated) {
            allocateHost();
        }
        if (device_allocated) {
            HIP_CHECK(hipMemcpy(h_data, d_data, rows * cols * sizeof(double), hipMemcpyDeviceToHost));
        }
    }

    // 获取设备数据指针
    double* getDeviceData() const {
        return d_data;
    }

    // 获取主机数据指针
    double* getHostData() const {
        return h_data;
    }

    // 设置是否使用内存池
    void setUseMemoryPool(bool value) {
        use_memory_pool = value;
    }

    // 打印矩阵内容（用于调试）
    void print(int max_rows = 5, int max_cols = 5) const {
        if (!host_allocated) {
            std::cout << "矩阵未在主机内存中分配" << std::endl;
            return;
        }

        int r = std::min(max_rows, rows);
        int c = std::min(max_cols, cols);

        for (int i = 0; i < r; ++i) {
            for (int j = 0; j < c; ++j) {
                std::cout << h_data[i * cols + j] << " ";
            }
            if (c < cols) std::cout << "...";
            std::cout << std::endl;
        }
        if (r < rows) std::cout << "..." << std::endl;
    }
};

// 层接口
class Layer {
public:
    virtual ~Layer() {}
    virtual void forward(const Matrix& input, Matrix& output, int optimization_flags) = 0;
    virtual std::string getName() const = 0;
};

// 全连接层
class LinearLayer : public Layer {
private:
    Matrix weights;
    Matrix bias;
    int input_dim;
    int output_dim;
    hipblasHandle_t hipblas_handle;
    bool hipblas_initialized;
    
    // 矩阵乘法方法
    void matrixMultiply(const Matrix& A, const Matrix& B, Matrix& C, int optimization_flags);
    void matrixMultiplyTiled(const Matrix& A, const Matrix& B, Matrix& C);
    void matrixMultiplyHipBLAS(const Matrix& A, const Matrix& B, Matrix& C);
    void matrixMultiplyBasic(const Matrix& A, const Matrix& B, Matrix& C);
    
    // 添加偏置
    void addBias(Matrix& output, const Matrix& bias, int optimization_flags);
    
    // 融合操作
    void matrixMultiplyAddBiasReLU(const Matrix& A, const Matrix& B, const Matrix& bias, Matrix& C);

public:
    LinearLayer(int input_dim, int output_dim) 
        : weights(input_dim, output_dim), 
          bias(1, output_dim),
          input_dim(input_dim), 
          output_dim(output_dim),
          hipblas_initialized(false) {
        
        // 初始化权重和偏置
        weights.allocateHost();
        weights.randomInit(-0.1, 0.1);  // Xavier初始化的简化版
        weights.copyToDevice();
        
        bias.allocateHost();
        bias.randomInit(-0.1, 0.1);
        bias.copyToDevice();
    }

    ~LinearLayer() {
        if (hipblas_initialized) {
            hipblasDestroy(hipblas_handle);
        }
    }

    void forward(const Matrix& input, Matrix& output, int optimization_flags) override;

    std::string getName() const override {
        return "Linear(" + std::to_string(input_dim) + ", " + std::to_string(output_dim) + ")";
    }

    // 获取权重和偏置
    const Matrix& getWeights() const { return weights; }
    const Matrix& getBias() const { return bias; }
    
    // 初始化hipBLAS
    void initHipBLAS() {
        if (!hipblas_initialized) {
            HIPBLAS_CHECK(hipblasCreate(&hipblas_handle));
            hipblas_initialized = true;
        }
    }
};

// ReLU激活层
class ReLULayer : public Layer {
private:
    void applyReLU(Matrix& data);

public:
    ReLULayer() {}
    ~ReLULayer() {}

    void forward(const Matrix& input, Matrix& output, int optimization_flags) override;

    std::string getName() const override {
        return "ReLU";
    }
};

// 多层感知机网络
class MLP {
private:
    std::vector<std::shared_ptr<Layer>> layers;
    std::vector<Matrix> intermediate_outputs;
    Timer forward_timer;
    int optimization_flags;
    int device_id;

public:
    MLP(int optimization_flags = OPT_NONE, int device_id = 0) 
        : optimization_flags(optimization_flags), device_id(device_id) {
        
        // 如果使用hipBLAS，初始化所有LinearLayer
        if (optimization_flags & OPT_HIPBLAS) {
            HIP_CHECK(hipSetDevice(device_id));
        }
    }
    
    ~MLP() {}

    // 添加层
    void addLayer(std::shared_ptr<Layer> layer) {
        layers.push_back(layer);
        // 为中间输出分配空间（将在forward时确定大小）
        intermediate_outputs.push_back(Matrix(0, 0, optimization_flags & OPT_MEMORY_POOL));
        
        // 如果使用hipBLAS，初始化LinearLayer
        if (optimization_flags & OPT_HIPBLAS) {
            auto linear_layer = std::dynamic_pointer_cast<LinearLayer>(layer);
            if (linear_layer) {
                linear_layer->initHipBLAS();
            }
        }
    }

    // 前向传播 - 添加const修饰符
    Matrix forward(const Matrix& input) const {
        if (layers.empty()) {
            throw std::runtime_error("网络中没有层");
        }
        
        // 如果使用多DCU，设置当前设备
        if (optimization_flags & OPT_MULTI_DCU) {
            HIP_CHECK(hipSetDevice(device_id));
        }

        // 创建一个非const的计时器副本
        Timer local_timer;
        local_timer.start();

        // 创建中间输出的副本
        std::vector<Matrix> local_outputs;
        local_outputs.resize(layers.size(), Matrix(0, 0, optimization_flags & OPT_MEMORY_POOL));

        // 第一层的输入
        const Matrix* current_input = &input;
        
        // 逐层前向传播
        for (size_t i = 0; i < layers.size(); ++i) {
            // 执行当前层的前向传播
            layers[i]->forward(*current_input, local_outputs[i], optimization_flags);
            current_input = &local_outputs[i];
        }

        local_timer.stop();
        
        // 返回最后一层的输出（创建一个深拷贝）
        return Matrix(*current_input);
    }

    // 打印网络结构
    void printArchitecture() const {
        std::cout << "MLP架构:" << std::endl;
        for (size_t i = 0; i < layers.size(); ++i) {
            std::cout << "  Layer " << i << ": " << layers[i]->getName() << std::endl;
        }
    }

    // 获取前向传播时间（毫秒）- 由于forward现在是const，这个函数不再有用
    // 改为在外部计时
    double getForwardTime() const {
        return forward_timer.elapsedMilliseconds();
    }
    
    // 获取/设置优化标志
    int getOptimizationFlags() const { return optimization_flags; }
    void setOptimizationFlags(int flags) { optimization_flags = flags; }
    
    // 获取/设置设备ID
    int getDeviceID() const { return device_id; }
    void setDeviceID(int id) { device_id = id; }
};

// 多DCU并行处理
void multi_dcu_forward(const std::vector<Matrix>& inputs, std::vector<Matrix>& outputs, 
                       const std::vector<MLP>& models);

// 性能测试类
class PerformanceTester {
private:
    int num_runs;
    Timer total_timer;
    std::vector<double> run_times;

public:
    PerformanceTester(int num_runs = 10) : num_runs(num_runs) {}

    // 测试MLP前向传播性能
    void testMLPForward(const MLP& mlp, const Matrix& input) {
        run_times.clear();
        
        // 预热运行
        Timer timer;
        timer.start();
        Matrix warmup_output = mlp.forward(input);
        timer.stop();
        warmup_output.copyToHost();  // 确保完成
        
        // 同步设备
        HIP_CHECK(hipDeviceSynchronize());
        
        total_timer.start();
        
        // 多次运行以获取平均性能
        for (int i = 0; i < num_runs; ++i) {
            // 确保设备同步
            HIP_CHECK(hipDeviceSynchronize());
            
            // 每次创建新的计时器
            Timer run_timer;
            run_timer.start();
            
            // 每次创建新的输出矩阵
            Matrix output = mlp.forward(input);
            
            run_timer.stop();
            
            // 确保计算完成
            output.copyToHost();
            HIP_CHECK(hipDeviceSynchronize());
            
            // 记录时间
            run_times.push_back(run_timer.elapsedMilliseconds());
            
            // 输出进度
            if (i % 5 == 0) {
                std::cout << "完成第 " << i+1 << "/" << num_runs << " 次运行" << std::endl;
            }
        }
        
        total_timer.stop();
    }

    // 打印性能结果
    void printResults() const {
        if (run_times.empty()) {
            std::cout << "没有性能测试数据" << std::endl;
            return;
        }

        double avg_time = 0.0;
        double min_time = run_times[0];
        double max_time = run_times[0];
        
        for (double time : run_times) {
            avg_time += time;
            min_time = std::min(min_time, time);
            max_time = std::max(max_time, time);
        }
        
        avg_time /= run_times.size();
        
        std::cout << "性能测试结果 (" << run_times.size() << " 次运行):" << std::endl;
        std::cout << "  平均时间: " << avg_time << " ms" << std::endl;
        std::cout << "  最小时间: " << min_time << " ms" << std::endl;
        std::cout << "  最大时间: " << max_time << " ms" << std::endl;
        std::cout << "  总运行时间: " << total_timer.elapsedMilliseconds() << " ms" << std::endl;
    }

    // 获取性能数据
    std::vector<double> getRunTimes() const {
        return run_times;
    }

    double getAverageTime() const {
        if (run_times.empty()) return 0.0;
        
        double sum = 0.0;
        for (double time : run_times) {
            sum += time;
        }
        return sum / run_times.size();
    }

    double getMinTime() const {
        if (run_times.empty()) return 0.0;
        
        double min_time = run_times[0];
        for (double time : run_times) {
            min_time = std::min(min_time, time);
        }
        return min_time;
    }

    double getTotalTime() const {
        return total_timer.elapsedMilliseconds();
    }
};

// 消融实验类
class AblationExperiment {
private:
    std::vector<int> optimization_combinations;
    std::vector<std::string> optimization_names;
    std::vector<double> average_times;
    std::vector<double> min_times;
    int batch_size;
    int input_dim;
    int hidden_dim;
    int output_dim;
    int num_runs;

public:
    AblationExperiment(int batch_size = 1024, int input_dim = 10, int hidden_dim = 20, int output_dim = 5, int num_runs = 10)
        : batch_size(batch_size), input_dim(input_dim), hidden_dim(hidden_dim), output_dim(output_dim), num_runs(num_runs) {
        
        // 初始化优化组合
        optimization_combinations = {
            OPT_NONE,                   // 基准版本
            OPT_TILED_MATMUL,           // 仅分块矩阵乘法
            OPT_FUSED_KERNELS,          // 仅融合核函数
            OPT_MEMORY_POOL,            // 仅内存池
            OPT_HIPBLAS,                // 仅hipBLAS
            OPT_TILED_MATMUL | OPT_FUSED_KERNELS,  // 分块矩阵乘法 + 融合核函数
            OPT_TILED_MATMUL | OPT_MEMORY_POOL,    // 分块矩阵乘法 + 内存池
            OPT_FUSED_KERNELS | OPT_MEMORY_POOL,   // 融合核函数 + 内存池
            OPT_HIPBLAS | OPT_MEMORY_POOL,         // hipBLAS + 内存池
            OPT_ALL & ~OPT_MULTI_DCU,              // 所有优化（不包括多DCU）
            OPT_ALL                                // 所有优化
        };
        
        // 初始化优化名称
        optimization_names = {
            "基准版本",
            "分块矩阵乘法",
            "融合核函数",
            "内存池",
            "hipBLAS",
            "分块矩阵乘法 + 融合核函数",
            "分块矩阵乘法 + 内存池",
            "融合核函数 + 内存池",
            "hipBLAS + 内存池",
            "所有优化（不包括多DCU）",
            "所有优化"
        };
    }

    // 运行消融实验
    void run() {
        average_times.clear();
        min_times.clear();
        
        // 创建输入数据
        Matrix input(batch_size, input_dim);
        input.allocateHost();
        input.randomInit(-1.0, 1.0);
        input.copyToDevice();
        
        // 对每种优化组合进行测试
        for (size_t i = 0; i < optimization_combinations.size(); ++i) {
            int opt_flags = optimization_combinations[i];
            std::cout << "\n测试优化组合: " << optimization_names[i] << std::endl;
            
            // 设置内存池状态
            g_memoryPool.setEnabled(opt_flags & OPT_MEMORY_POOL);
            
            // 创建MLP网络
            MLP mlp(opt_flags);
            
            // 添加层
            mlp.addLayer(std::make_shared<LinearLayer>(input_dim, hidden_dim));
            mlp.addLayer(std::make_shared<ReLULayer>());
            mlp.addLayer(std::make_shared<LinearLayer>(hidden_dim, output_dim));
            
            // 创建性能测试器
            PerformanceTester tester(num_runs);
            
            // 测试前向传播性能
            tester.testMLPForward(mlp, input);
            
            // 打印性能结果
            tester.printResults();
            
            // 记录结果
            average_times.push_back(tester.getAverageTime());
            min_times.push_back(tester.getMinTime());
        }
    }

    // 保存结果到CSV文件
    void saveResultsToCSV(const std::string& filename) {
        std::ofstream file(filename);
        file << "优化组合,平均时间(ms),最小时间(ms)" << std::endl;
        
        for (size_t i = 0; i < optimization_names.size(); ++i) {
            file << optimization_names[i] << "," << average_times[i] << "," << min_times[i] << std::endl;
        }
        
        file.close();
        std::cout << "消融实验结果已保存到 " << filename << std::endl;
    }

    // 打印结果
    void printResults() {
        std::cout << "\n消融实验结果:" << std::endl;
        std::cout << "优化组合\t平均时间(ms)\t最小时间(ms)\t加速比" << std::endl;
        
        double baseline_avg = average_times[0];
        
        for (size_t i = 0; i < optimization_names.size(); ++i) {
            double speedup = baseline_avg / average_times[i];
            std::cout << optimization_names[i] << "\t" << average_times[i] << "\t" << min_times[i] << "\t" << speedup << "x" << std::endl;
        }
    }
};

#endif // MLP_DCU_OPTIMIZED_H
