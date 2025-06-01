#ifndef MLP_BP_DCU_H
#define MLP_BP_DCU_H

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
#include <fstream>
#include <algorithm>
#include <numeric>

// 调试开关
#define DEBUG_HIPBLAS 1
#define DEBUG_MATRIX_PTR 1

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
    
    // 生成唯一ID用于调试
    static int next_id;
    int id;

public:
    // 默认构造函数
    Matrix() : rows(0), cols(0), h_data(nullptr), d_data(nullptr), 
               device_allocated(false), host_allocated(false), use_memory_pool(false) {
        id = next_id++;
        // if (DEBUG_MATRIX_PTR) {
        //     std::cout << "Matrix #" << id << " 默认构造" << std::endl;
        // }
    }
    
    // 构造函数
    Matrix(int rows, int cols, bool use_memory_pool = false) 
        : rows(rows), cols(cols), 
          device_allocated(false), 
          host_allocated(false),
          h_data(nullptr), d_data(nullptr),
          use_memory_pool(use_memory_pool) {
        id = next_id++;
        // if (DEBUG_MATRIX_PTR) {
        //     std::cout << "Matrix #" << id << " 构造 (" << rows << "x" << cols << ")" << std::endl;
        // }
    }

    // 析构函数
    ~Matrix() {
        // if (DEBUG_MATRIX_PTR) {
        //     std::cout << "Matrix #" << id << " 析构" << std::endl;
        // }
        freeMemory();
    }

    // 拷贝构造函数 - 深拷贝
    Matrix(const Matrix& other) : rows(other.rows), cols(other.cols),
                                 device_allocated(false),
                                 host_allocated(false),
                                 h_data(nullptr), d_data(nullptr),
                                 use_memory_pool(other.use_memory_pool) {
        id = next_id++;
        // if (DEBUG_MATRIX_PTR) {
        //     std::cout << "Matrix #" << id << " 拷贝构造自 #" << other.id << std::endl;
        // }
        
        // 复制主机数据（如果存在）
        if (other.host_allocated && other.h_data != nullptr) {
            allocateHost();
            std::memcpy(h_data, other.h_data, rows * cols * sizeof(double));
        }
        
        // 复制设备数据（如果存在）
        if (other.device_allocated && other.d_data != nullptr) {
            allocateDevice();
            HIP_CHECK(hipMemcpy(d_data, other.d_data, rows * cols * sizeof(double), hipMemcpyDeviceToDevice));
        }
    }

    // 移动构造函数
    Matrix(Matrix&& other) noexcept : rows(other.rows), cols(other.cols),
                                     h_data(other.h_data), d_data(other.d_data),
                                     device_allocated(other.device_allocated),
                                     host_allocated(other.host_allocated),
                                     use_memory_pool(other.use_memory_pool),
                                     id(other.id) {
        // if (DEBUG_MATRIX_PTR) {
        //     std::cout << "Matrix #" << id << " 移动构造" << std::endl;
        // }
        
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
            // if (DEBUG_MATRIX_PTR) {
            //     std::cout << "Matrix #" << id << " 拷贝赋值自 #" << other.id << std::endl;
            // }
            
            // 释放当前资源
            freeMemory();
            
            // 复制新资源
            rows = other.rows;
            cols = other.cols;
            use_memory_pool = other.use_memory_pool;
            
            // 复制主机数据（如果存在）
            if (other.host_allocated && other.h_data != nullptr) {
                allocateHost();
                std::memcpy(h_data, other.h_data, rows * cols * sizeof(double));
            }
            
            // 复制设备数据（如果存在）
            if (other.device_allocated && other.d_data != nullptr) {
                allocateDevice();
                HIP_CHECK(hipMemcpy(d_data, other.d_data, rows * cols * sizeof(double), hipMemcpyDeviceToDevice));
            }
        }
        return *this;
    }

    // 移动赋值运算符
    Matrix& operator=(Matrix&& other) noexcept {
        if (this != &other) {
            // if (DEBUG_MATRIX_PTR) {
            //     std::cout << "Matrix #" << id << " 移动赋值自 #" << other.id << std::endl;
            // }
            
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
            // 不移动id，保持原有id
            
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
    int getId() const { return id; }

    // 分配主机内存
    void allocateHost() {
        if (!host_allocated || h_data == nullptr) {
            h_data = new double[rows * cols]();
            host_allocated = true;
            // if (DEBUG_MATRIX_PTR) {
            //     std::cout << "Matrix #" << id << " 分配主机内存" << std::endl;
            // }
        }
    }

    // 分配设备内存
    void allocateDevice() {
        if (!device_allocated || d_data == nullptr) {
            if (use_memory_pool) {
                d_data = g_memoryPool.allocate(rows * cols);
            } else {
                HIP_CHECK(hipMalloc(&d_data, rows * cols * sizeof(double)));
            }
            device_allocated = true;
            
            // 初始化为0
            HIP_CHECK(hipMemset(d_data, 0, rows * cols * sizeof(double)));
            
            // if (DEBUG_MATRIX_PTR) {
            //     std::cout << "Matrix #" << id << " 分配设备内存: " << d_data << std::endl;
            // }
        }
    }

    // 释放内存
    void freeMemory() {
        if (host_allocated && h_data != nullptr) {
            // if (DEBUG_MATRIX_PTR) {
            //     std::cout << "Matrix #" << id << " 释放主机内存" << std::endl;
            // }
            delete[] h_data;
            h_data = nullptr;
            host_allocated = false;
        }
        if (device_allocated && d_data != nullptr) {
            // if (DEBUG_MATRIX_PTR) {
            //     std::cout << "Matrix #" << id << " 释放设备内存: " << d_data << std::endl;
            // }
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
        if (!host_allocated || h_data == nullptr) {
            allocateHost();
        }

        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_real_distribution<double> dist(min, max);

        for (int i = 0; i < rows * cols; ++i) {
            h_data[i] = dist(gen);
        }
    }

    // Xavier初始化
    void xavierInit() {
        if (!host_allocated || h_data == nullptr) {
            allocateHost();
        }

        std::random_device rd;
        std::mt19937 gen(rd());
        double limit = std::sqrt(6.0 / (rows + cols));
        std::uniform_real_distribution<double> dist(-limit, limit);

        for (int i = 0; i < rows * cols; ++i) {
            h_data[i] = dist(gen);
        }
    }

    // 主机到设备的数据传输
    void copyToDevice() {
        if (!device_allocated || d_data == nullptr) {
            allocateDevice();
        }
        if (host_allocated && h_data != nullptr) {
            HIP_CHECK(hipMemcpy(d_data, h_data, rows * cols * sizeof(double), hipMemcpyHostToDevice));
            // if (DEBUG_MATRIX_PTR) {
            //     std::cout << "Matrix #" << id << " 复制到设备: " << d_data << std::endl;
            // }
        }
    }

    // 设备到主机的数据传输
    void copyToHost() const {
        if (!host_allocated || h_data == nullptr) {
            // 在const方法中修改对象状态需要使用mutable或const_cast
            const_cast<Matrix*>(this)->allocateHost();
        }
        if (device_allocated && d_data != nullptr) {
            HIP_CHECK(hipMemcpy(const_cast<double*>(h_data), d_data, rows * cols * sizeof(double), hipMemcpyDeviceToHost));
            // if (DEBUG_MATRIX_PTR) {
            //     std::cout << "Matrix #" << id << " 复制到主机" << std::endl;
            // }
        }
    }

    // 获取设备数据指针
    double* getDeviceData() const {
        // if (DEBUG_MATRIX_PTR && device_allocated) {
        //     std::cout << "Matrix #" << id << " 获取设备指针: " << d_data << std::endl;
        // }
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
    
    // 获取是否使用内存池
    bool getUseMemoryPool() const {
        return use_memory_pool;
    }

    // 填充指定值
    void fill(double value) {
        if (!host_allocated || h_data == nullptr) {
            allocateHost();
        }
        
        for (int i = 0; i < rows * cols; ++i) {
            h_data[i] = value;
        }
        
        if (device_allocated && d_data != nullptr) {
            copyToDevice();
        }
    }

    // 打印矩阵内容（用于调试）
    void print(int max_rows = 5, int max_cols = 5) const {
        if (!host_allocated || h_data == nullptr) {
            if (device_allocated && d_data != nullptr) {
                const_cast<Matrix*>(this)->copyToHost();
            } else {
                std::cout << "矩阵未在主机或设备内存中分配" << std::endl;
                return;
            }
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
    
    // 检查矩阵是否有效
    bool isValid() const {
        return (rows > 0 && cols > 0) && 
               ((host_allocated && h_data != nullptr) || 
                (device_allocated && d_data != nullptr));
    }
    
    // 确保设备内存已分配
    void ensureDeviceAllocated() {
        if (!device_allocated || d_data == nullptr) {
            allocateDevice();
            
            // 如果主机内存已分配，则复制到设备
            if (host_allocated && h_data != nullptr) {
                copyToDevice();
            }
        }
    }
    
    // 同步设备
    void syncDevice() const {
        HIP_CHECK(hipDeviceSynchronize());
    }
    
    // 重置矩阵大小，保留数据（如果可能）
    void resize(int new_rows, int new_cols) {
        if (rows == new_rows && cols == new_cols) {
            return;  // 大小相同，无需调整
        }
        
        // if (DEBUG_MATRIX_PTR) {
        //     std::cout << "Matrix #" << id << " 调整大小: " << rows << "x" << cols 
        //              << " -> " << new_rows << "x" << new_cols << std::endl;
        // }
        
        // 保存旧数据（如果需要）
        double* old_h_data = nullptr;
        double* old_d_data = nullptr;
        int old_rows = rows;
        int old_cols = cols;
        bool had_host_data = host_allocated && h_data != nullptr;
        bool had_device_data = device_allocated && d_data != nullptr;
        
        if (had_host_data) {
            old_h_data = h_data;
        }
        
        if (had_device_data) {
            old_d_data = d_data;
        }
        
        // 重置状态
        h_data = nullptr;
        d_data = nullptr;
        host_allocated = false;
        device_allocated = false;
        rows = new_rows;
        cols = new_cols;
        
        // 重新分配内存
        if (had_host_data) {
            allocateHost();
            
            // 复制旧数据（尽可能多）
            int copy_rows = std::min(old_rows, new_rows);
            int copy_cols = std::min(old_cols, new_cols);
            
            for (int i = 0; i < copy_rows; ++i) {
                std::memcpy(h_data + i * new_cols, 
                           old_h_data + i * old_cols, 
                           copy_cols * sizeof(double));
            }
            
            // 释放旧内存
            delete[] old_h_data;
        }
        
        if (had_device_data) {
            allocateDevice();
            
            // 如果主机内存已更新，则复制到设备
            if (had_host_data) {
                copyToDevice();
            } else {
                // 直接在设备上复制（尽可能多）
                int copy_rows = std::min(old_rows, new_rows);
                int copy_cols = std::min(old_cols, new_cols);
                
                // 为每行创建单独的复制操作
                for (int i = 0; i < copy_rows; ++i) {
                    HIP_CHECK(hipMemcpy(
                        d_data + i * new_cols,
                        old_d_data + i * old_cols,
                        copy_cols * sizeof(double),
                        hipMemcpyDeviceToDevice
                    ));
                }
            }
            
            // 释放旧内存
            if (use_memory_pool) {
                g_memoryPool.free(old_d_data, old_rows * old_cols);
            } else {
                HIP_CHECK(hipFree(old_d_data));
            }
        }
    }
};



// 层接口 - 支持前向和反向传播
class Layer {
public:
    virtual ~Layer() {}
    
    // 前向传播
    virtual void forward(const Matrix& input, Matrix& output, int optimization_flags) = 0;
    
    // 反向传播
    virtual void backward(const Matrix& input, const Matrix& output, const Matrix& output_grad, 
                         Matrix& input_grad, int optimization_flags) = 0;
    
    // 参数更新
    virtual void updateParams(double learning_rate) = 0;
    
    // 获取层名称
    virtual std::string getName() const = 0;
    
    // 获取参数数量
    virtual int getParamCount() const = 0;
    
    // 保存参数
    virtual void saveParams(std::ofstream& file) const = 0;
    
    // 加载参数
    virtual void loadParams(std::ifstream& file) = 0;
};

// 全连接层
class LinearLayer : public Layer {
private:
    Matrix weights;      // 权重矩阵
    Matrix bias;         // 偏置向量
    Matrix dw;           // 权重梯度
    Matrix db;           // 偏置梯度
    Matrix last_input;   // 保存前向传播的输入，用于反向传播
    int input_dim;       // 输入维度
    int output_dim;      // 输出维度
    hipblasHandle_t hipblas_handle;
    bool hipblas_initialized;
    
    // 矩阵乘法方法
    void matrixMultiply(const Matrix& A, const Matrix& B, Matrix& C, int optimization_flags);
    void matrixMultiplyTiled(const Matrix& A, const Matrix& B, Matrix& C);
    void matrixMultiplyHipBLAS(const Matrix& A, const Matrix& B, Matrix& C);
    void matrixMultiplyBasic(const Matrix& A, const Matrix& B, Matrix& C);
    
    // 矩阵转置乘法 C = A^T * B
    void matrixTransposeMultiply(const Matrix& A, const Matrix& B, Matrix& C, int optimization_flags);
    
    // 矩阵乘以转置 C = A * B^T
    void matrixMultiplyTranspose(const Matrix& A, const Matrix& B, Matrix& C, int optimization_flags);
    
    // 添加偏置
    void addBias(Matrix& output, const Matrix& bias, int optimization_flags);
    
    // 融合操作
    void matrixMultiplyAddBias(const Matrix& A, const Matrix& B, const Matrix& bias, Matrix& C);

public:
    LinearLayer(int input_dim, int output_dim) 
        : weights(input_dim, output_dim), 
          bias(1, output_dim),
          dw(input_dim, output_dim),
          db(1, output_dim),
          last_input(0, 0),
          input_dim(input_dim), 
          output_dim(output_dim),
          hipblas_initialized(false) {
        
        // 初始化权重和偏置
        weights.allocateHost();
        weights.xavierInit();  // Xavier初始化
        weights.copyToDevice();
        
        bias.allocateHost();
        bias.fill(0.0);  // 偏置初始化为0
        bias.copyToDevice();
        
        // 初始化梯度
        dw.allocateHost();
        dw.fill(0.0);
        dw.copyToDevice();
        
        db.allocateHost();
        db.fill(0.0);
        db.copyToDevice();
    }

    ~LinearLayer() {
        if (hipblas_initialized) {
            hipblasDestroy(hipblas_handle);
        }
    }

    // 前向传播
    void forward(const Matrix& input, Matrix& output, int optimization_flags) override;
    
    // 反向传播
    void backward(const Matrix& input, const Matrix& output, const Matrix& output_grad, 
                 Matrix& input_grad, int optimization_flags) override;
    
    // 参数更新
    void updateParams(double learning_rate) override;

    std::string getName() const override {
        return "Linear(" + std::to_string(input_dim) + ", " + std::to_string(output_dim) + ")";
    }
    
    // 获取参数数量
    int getParamCount() const override {
        return weights.size() + bias.size();
    }
    
    // 保存参数
    void saveParams(std::ofstream& file) const override;
    
    // 加载参数
    void loadParams(std::ifstream& file) override;

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
    Matrix last_output;  // 保存前向传播的输出，用于反向传播
    
    // 应用ReLU激活函数
    void applyReLU(const Matrix& input, Matrix& output);
    
    // 应用ReLU导数
    void applyReLUGrad(const Matrix& output, const Matrix& grad_output, Matrix& grad_input);

public:
    ReLULayer() {}
    ~ReLULayer() {}

    // 前向传播
    void forward(const Matrix& input, Matrix& output, int optimization_flags) override;
    
    // 反向传播
    void backward(const Matrix& input, const Matrix& output, const Matrix& output_grad, 
                 Matrix& input_grad, int optimization_flags) override;
    
    // ReLU层没有参数，更新为空操作
    void updateParams(double learning_rate) override {}

    std::string getName() const override {
        return "ReLU";
    }
    
    // ReLU层没有参数
    int getParamCount() const override { return 0; }
    
    // ReLU层没有参数，保存为空操作
    void saveParams(std::ofstream& file) const override {}
    
    // ReLU层没有参数，加载为空操作
    void loadParams(std::ifstream& file) override {}
};

// 多层感知机网络
class MLP {
private:
    std::vector<std::shared_ptr<Layer>> layers;
    std::vector<Matrix> intermediate_outputs;
    std::vector<Matrix> intermediate_grads;
    Timer forward_timer;
    Timer backward_timer;
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
        // 为中间输出和梯度分配空间（将在forward/backward时确定大小）
        intermediate_outputs.push_back(Matrix(0, 0, optimization_flags & OPT_MEMORY_POOL));
        intermediate_grads.push_back(Matrix(0, 0, optimization_flags & OPT_MEMORY_POOL));
        
        // 如果使用hipBLAS，初始化LinearLayer
        if (optimization_flags & OPT_HIPBLAS) {
            auto linear_layer = std::dynamic_pointer_cast<LinearLayer>(layer);
            if (linear_layer) {
                linear_layer->initHipBLAS();
            }
        }
    }

    // 前向传播
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
        local_outputs.resize(layers.size());

        // 第一层的输入
        const Matrix* current_input = &input;
        
        // 确保输入矩阵在设备上
        if (!current_input->getDeviceData()) {
            const_cast<Matrix*>(current_input)->ensureDeviceAllocated();
        }
        
        // 逐层前向传播
        for (size_t i = 0; i < layers.size(); ++i) {
            // 执行当前层的前向传播
            layers[i]->forward(*current_input, local_outputs[i], optimization_flags);
            
            // 确保输出矩阵在设备上
            if (!local_outputs[i].getDeviceData()) {
                local_outputs[i].ensureDeviceAllocated();
            }
            
            current_input = &local_outputs[i];
        }

        local_timer.stop();
        
        // 同步设备，确保所有操作完成
        HIP_CHECK(hipDeviceSynchronize());
        
        // 返回最后一层的输出（创建一个深拷贝）
        return Matrix(*current_input);
    }
    
    // 反向传播
    void backward(const Matrix& input, const Matrix& target, double& loss) {
        if (layers.empty()) {
            throw std::runtime_error("网络中没有层");
        }
        
        // 如果使用多DCU，设置当前设备
        if (optimization_flags & OPT_MULTI_DCU) {
            HIP_CHECK(hipSetDevice(device_id));
        }
        
        // 确保输入和目标矩阵在设备上
        if (!input.getDeviceData()) {
            const_cast<Matrix&>(input).ensureDeviceAllocated();
        }
        
        if (!target.getDeviceData()) {
            const_cast<Matrix&>(target).ensureDeviceAllocated();
        }
        
        // 前向传播，保存中间结果
        forward_timer.start();
        
        // 第一层的输入
        const Matrix* current_input = &input;
        
        // 逐层前向传播，保存中间结果
        for (size_t i = 0; i < layers.size(); ++i) {
            // 确保中间输出矩阵已分配
            if (intermediate_outputs[i].getRows() == 0) {
                // 第一次运行，需要分配空间
                if (i == layers.size() - 1) {
                    // 最后一层的输出维度是1（回归任务）
                    intermediate_outputs[i] = Matrix(input.getRows(), 1, optimization_flags & OPT_MEMORY_POOL);
                } else {
                    // 中间层的输出维度由层决定
                    auto linear_layer = std::dynamic_pointer_cast<LinearLayer>(layers[i]);
                    if (linear_layer) {
                        intermediate_outputs[i] = Matrix(input.getRows(), linear_layer->getWeights().getCols(), 
                                                       optimization_flags & OPT_MEMORY_POOL);
                    }
                }
            }
            
            // 确保中间输出矩阵在设备上
            intermediate_outputs[i].ensureDeviceAllocated();
            
            // 执行当前层的前向传播
            layers[i]->forward(*current_input, intermediate_outputs[i], optimization_flags);
            current_input = &intermediate_outputs[i];
        }
        
        forward_timer.stop();
        
        // 计算损失和输出梯度
        Matrix output_grad(target.getRows(), target.getCols(), optimization_flags & OPT_MEMORY_POOL);
        output_grad.ensureDeviceAllocated();
        
        computeLoss(intermediate_outputs.back(), target, loss, output_grad);
        
        // 反向传播
        backward_timer.start();
        
        // 确保中间梯度矩阵已分配
        for (size_t i = 0; i < layers.size(); ++i) {
            if (intermediate_grads[i].getRows() == 0) {
                if (i == 0) {
                    // 第一层的梯度维度与输入相同
                    intermediate_grads[i] = Matrix(input.getRows(), input.getCols(), optimization_flags & OPT_MEMORY_POOL);
                } else {
                    // 中间层的梯度维度与该层的输入维度相同，即上一层的输出维度
                    intermediate_grads[i] = Matrix(input.getRows(), intermediate_outputs[i-1].getCols(), 
                                                 optimization_flags & OPT_MEMORY_POOL);
                }
            }
            
            // 确保中间梯度矩阵在设备上
            intermediate_grads[i].ensureDeviceAllocated();
        }
        
        // 从最后一层开始，逐层反向传播
        Matrix* current_grad = &output_grad;
        
        for (int i = layers.size() - 1; i >= 0; --i) {
            const Matrix& current_output = intermediate_outputs[i];
            const Matrix& current_input = (i > 0) ? intermediate_outputs[i-1] : input;
            Matrix& current_input_grad = (i > 0) ? intermediate_grads[i-1] : intermediate_grads[0];
            
            // 执行当前层的反向传播
            layers[i]->backward(current_input, current_output, *current_grad, 
                               current_input_grad, optimization_flags);
            
            current_grad = &current_input_grad;
        }
        
        backward_timer.stop();
        
        // 同步设备，确保所有操作完成
        HIP_CHECK(hipDeviceSynchronize());
    }
    
    // 更新参数
    void updateParams(double learning_rate) {
        for (auto& layer : layers) {
            layer->updateParams(learning_rate);
        }
        
        // 同步设备，确保所有操作完成
        HIP_CHECK(hipDeviceSynchronize());
    }
    
    // 计算损失和输出梯度（MSE损失）
    void computeLoss(const Matrix& output, const Matrix& target, double& loss, Matrix& output_grad);

    // 打印网络结构
    void printArchitecture() const {
        std::cout << "MLP架构:" << std::endl;
        for (size_t i = 0; i < layers.size(); ++i) {
            std::cout << "  Layer " << i << ": " << layers[i]->getName() << std::endl;
        }
    }

    // 获取前向传播时间（毫秒）
    double getForwardTime() const {
        return forward_timer.elapsedMilliseconds();
    }
    
    // 获取反向传播时间（毫秒）
    double getBackwardTime() const {
        return backward_timer.elapsedMilliseconds();
    }
    
    // 获取/设置优化标志
    int getOptimizationFlags() const { return optimization_flags; }
    void setOptimizationFlags(int flags) { optimization_flags = flags; }
    
    // 获取/设置设备ID
    int getDeviceID() const { return device_id; }
    void setDeviceID(int id) { device_id = id; }
    
    // 获取参数总数
    int getParamCount() const {
        int count = 0;
        for (const auto& layer : layers) {
            count += layer->getParamCount();
        }
        return count;
    }
    
    // 保存模型参数
    void saveModel(const std::string& filename) const;
    
    // 加载模型参数
    void loadModel(const std::string& filename);
};

// 多DCU并行处理
void multi_dcu_forward(const std::vector<Matrix>& inputs, std::vector<Matrix>& outputs, 
                       const std::vector<MLP>& models);

// 数据集类
class Dataset {
private:
    std::vector<Matrix> X_train;  // 训练输入
    std::vector<Matrix> y_train;  // 训练目标
    std::vector<Matrix> X_test;   // 测试输入
    std::vector<Matrix> y_test;   // 测试目标
    double min_val;               // 归一化最小值
    double max_val;               // 归一化最大值
    int window_size;              // 滑动窗口大小
    int batch_size;               // 批次大小
    
    // 创建滑动窗口样本
    void createWindowSamples(const std::vector<double>& data, 
                            std::vector<std::vector<double>>& X, 
                            std::vector<double>& y);
    
public:
    Dataset(int window_size = 10, int batch_size = 256) 
        : window_size(window_size), batch_size(batch_size), min_val(0.0), max_val(1.0) {}
    
    // 加载JSON带宽数据
    bool loadFromJSON(const std::string& filename);
    
    // 归一化数据
    void normalizeData(std::vector<double>& data);
    
    // 反归一化数据
    std::vector<double> denormalizeData(const std::vector<double>& data) const;
    
    // 创建训练和测试集
    void createTrainTestSplit(double train_ratio = 0.8);
    
    // 获取批次数量
    int getNumBatches() const {
        return (X_train.size() + batch_size - 1) / batch_size;
    }
    
    // 获取指定批次
    void getBatch(int batch_idx, Matrix& X_batch, Matrix& y_batch) const;
    
    // 获取测试集
    void getTestSet(Matrix& X_test_matrix, Matrix& y_test_matrix) const;

    void getTrainSet(Matrix& X_test_matrix, Matrix& y_test_matrix) const;
    
    // 获取归一化参数
    double getMinVal() const { return min_val; }
    double getMaxVal() const { return max_val; }
    
    // 获取窗口大小
    int getWindowSize() const { return window_size; }
    
    // 获取批次大小
    int getBatchSize() const { return batch_size; }
    
    // 获取训练集大小
    int getTrainSize() const { return X_train.size(); }
    
    // 获取测试集大小
    int getTestSize() const { return X_test.size(); }
};

// 训练器类
class Trainer {
private:
    MLP& model;
    Dataset& dataset;
    double learning_rate;
    int epochs;
    std::vector<double> train_losses;
    std::vector<double> test_losses;
    std::vector<double> train_times;
    Timer epoch_timer;
    
public:
    Trainer(MLP& model, Dataset& dataset, double learning_rate = 0.001, int epochs = 100)
        : model(model), dataset(dataset), learning_rate(learning_rate), epochs(epochs) {}
    
    // 训练模型
    void train();
    
    // 评估模型
    double evaluate(bool is_test_set = true);
    
    // 预测
    std::vector<double> predict(const Matrix& X);
    
    // 获取训练损失历史
    const std::vector<double>& getTrainLosses() const { return train_losses; }
    
    // 获取测试损失历史
    const std::vector<double>& getTestLosses() const { return test_losses; }
    
    // 获取训练时间历史
    const std::vector<double>& getTrainTimes() const { return train_times; }
    
    // 保存训练历史
    void saveHistory(const std::string& filename) const;
    
    // 保存预测结果
    void savePredictions(const std::string& filename, const std::vector<double>& predictions, 
                        const std::vector<double>& targets) const;
};

#endif // MLP_BP_DCU_H
