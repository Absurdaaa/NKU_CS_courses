#include "mlp_dcu_optimized.h"

// 全局内存池实例
MemoryPool g_memoryPool(false);

// 基本矩阵乘法核函数
__global__ void basic_matmul_kernel(const double* A, const double* B, double* C, int M, int N, int K) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (row < M && col < N) {
        double sum = 0.0;
        for (int k = 0; k < K; ++k) {
            sum += A[row * K + k] * B[k * N + col];
        }
        C[row * N + col] = sum;
    }
}

// 分块矩阵乘法核函数 - 优化版本
__global__ void tiled_matmul_kernel(const double* A, const double* B, double* C, int M, int N, int K) {
    // 定义共享内存块大小
    constexpr int BLOCK_SIZE = 32;
    
    // 声明共享内存
    __shared__ double As[BLOCK_SIZE][BLOCK_SIZE];
    __shared__ double Bs[BLOCK_SIZE][BLOCK_SIZE];
    
    // 计算线程和块索引
    int bx = blockIdx.x;
    int by = blockIdx.y;
    int tx = threadIdx.x;
    int ty = threadIdx.y;
    
    // 计算全局行列索引
    int row = by * BLOCK_SIZE + ty;
    int col = bx * BLOCK_SIZE + tx;
    
    // 累加器
    double sum = 0.0;
    
    // 遍历所有子块
    for (int i = 0; i < (K + BLOCK_SIZE - 1) / BLOCK_SIZE; ++i) {
        // 协作加载A和B的子块到共享内存
        if (row < M && i * BLOCK_SIZE + tx < K) {
            As[ty][tx] = A[row * K + i * BLOCK_SIZE + tx];
        } else {
            As[ty][tx] = 0.0;
        }
        
        if (i * BLOCK_SIZE + ty < K && col < N) {
            Bs[ty][tx] = B[(i * BLOCK_SIZE + ty) * N + col];
        } else {
            Bs[ty][tx] = 0.0;
        }
        
        // 同步以确保数据加载完成
        __syncthreads();
        
        // 计算当前子块的点积
        #pragma unroll
        for (int k = 0; k < BLOCK_SIZE; ++k) {
            sum += As[ty][k] * Bs[k][tx];
        }
        
        // 同步以确保计算完成
        __syncthreads();
    }
    
    // 写入结果
    if (row < M && col < N) {
        C[row * N + col] = sum;
    }
}

// 添加偏置核函数
__global__ void add_bias_kernel(double* output, const double* bias, int rows, int cols) {
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    
    if (row < rows && col < cols) {
        output[row * cols + col] += bias[col];
    }
}

// ReLU激活函数核函数
__global__ void relu_kernel(double* data, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        data[idx] = fmax(0.0, data[idx]);
    }
}

// 融合核函数：矩阵乘法 + 偏置 + ReLU
__global__ void fused_matmul_bias_relu_kernel(const double* A, const double* B, const double* bias, 
                                             double* C, int M, int N, int K) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (row < M && col < N) {
        double sum = 0.0;
        for (int k = 0; k < K; ++k) {
            sum += A[row * K + k] * B[k * N + col];
        }
        
        // 添加偏置
        sum += bias[col];
        
        // 应用ReLU激活
        C[row * N + col] = fmax(0.0, sum);
    }
}

// 融合核函数：矩阵乘法 + 偏置
__global__ void fused_matmul_bias_kernel(const double* A, const double* B, const double* bias, 
                                        double* C, int M, int N, int K) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (row < M && col < N) {
        double sum = 0.0;
        for (int k = 0; k < K; ++k) {
            sum += A[row * K + k] * B[k * N + col];
        }
        
        // 添加偏置
        sum += bias[col];
        
        // 保存结果
        C[row * N + col] = sum;
    }
}

// LinearLayer的前向传播实现
void LinearLayer::forward(const Matrix& input, Matrix& output, int optimization_flags) {
    int batch_size = input.getRows();
    
    // 确保输出矩阵大小正确
    if (output.getRows() != batch_size || output.getCols() != output_dim) {
        // 如果输出矩阵尺寸不匹配，重新创建
        output = Matrix(batch_size, output_dim, optimization_flags & OPT_MEMORY_POOL);
    }
    
    // 分配设备内存
    output.allocateDevice();
    
    // 如果使用融合核函数
    if (optimization_flags & OPT_FUSED_KERNELS) {
        matrixMultiplyAddBiasReLU(input, weights, bias, output);
    } else {
        // 执行矩阵乘法
        matrixMultiply(input, weights, output, optimization_flags);
        
        // 添加偏置
        addBias(output, bias, optimization_flags);
    }
}

// 矩阵乘法实现 - 根据优化标志选择不同实现
void LinearLayer::matrixMultiply(const Matrix& A, const Matrix& B, Matrix& C, int optimization_flags) {
    if (optimization_flags & OPT_HIPBLAS) {
        matrixMultiplyHipBLAS(A, B, C);
    } else if (optimization_flags & OPT_TILED_MATMUL) {
        matrixMultiplyTiled(A, B, C);
    } else {
        matrixMultiplyBasic(A, B, C);
    }
}

// 基本矩阵乘法实现
void LinearLayer::matrixMultiplyBasic(const Matrix& A, const Matrix& B, Matrix& C) {
    int M = A.getRows();    // 输入批次大小
    int K = A.getCols();    // 输入特征维度
    int N = B.getCols();    // 输出特征维度
    
    // 定义块和线程大小
    constexpr int BLOCK_SIZE = 16;
    dim3 threadsPerBlock(BLOCK_SIZE, BLOCK_SIZE);
    dim3 blocksPerGrid((N + BLOCK_SIZE - 1) / BLOCK_SIZE, 
                       (M + BLOCK_SIZE - 1) / BLOCK_SIZE);
    
    // 启动核函数
    basic_matmul_kernel<<<blocksPerGrid, threadsPerBlock>>>(
        A.getDeviceData(), B.getDeviceData(), C.getDeviceData(), M, N, K);
    
    // 检查错误
    HIP_CHECK(hipGetLastError());
    HIP_CHECK(hipDeviceSynchronize());
}

// 分块矩阵乘法实现
void LinearLayer::matrixMultiplyTiled(const Matrix& A, const Matrix& B, Matrix& C) {
    int M = A.getRows();    // 输入批次大小
    int K = A.getCols();    // 输入特征维度
    int N = B.getCols();    // 输出特征维度
    
    // 定义块和线程大小
    constexpr int BLOCK_SIZE = 32;
    dim3 threadsPerBlock(BLOCK_SIZE, BLOCK_SIZE);
    dim3 blocksPerGrid((N + BLOCK_SIZE - 1) / BLOCK_SIZE, 
                       (M + BLOCK_SIZE - 1) / BLOCK_SIZE);
    
    // 启动核函数
    tiled_matmul_kernel<<<blocksPerGrid, threadsPerBlock>>>(
        A.getDeviceData(), B.getDeviceData(), C.getDeviceData(), M, N, K);
    
    // 检查错误
    HIP_CHECK(hipGetLastError());
    HIP_CHECK(hipDeviceSynchronize());
}

// hipBLAS矩阵乘法实现
void LinearLayer::matrixMultiplyHipBLAS(const Matrix& A, const Matrix& B, Matrix& C) {
    int M = A.getRows();    // 输入批次大小
    int K = A.getCols();    // 输入特征维度
    int N = B.getCols();    // 输出特征维度
    
    // 确保hipBLAS已初始化
    if (!hipblas_initialized) {
        initHipBLAS();
    }
    
    // 设置常数
    const double alpha = 1.0;
    const double beta = 0.0;
    
    // 执行矩阵乘法 C = alpha * A * B + beta * C
    // 注意：hipBLAS使用列主序，而我们使用行主序，所以需要转置操作
    // C(M,N) = A(M,K) * B(K,N) 等价于 C^T(N,M) = B^T(N,K) * A^T(K,M)
    HIPBLAS_CHECK(hipblasDgemm(
        hipblas_handle, 
        HIPBLAS_OP_N, HIPBLAS_OP_N,
        N, M, K,
        &alpha,
        B.getDeviceData(), N,
        A.getDeviceData(), K,
        &beta,
        C.getDeviceData(), N));
}

// 添加偏置实现
void LinearLayer::addBias(Matrix& output, const Matrix& bias, int optimization_flags) {
    int rows = output.getRows();
    int cols = output.getCols();
    
    // 定义块和线程大小
    constexpr int BLOCK_SIZE = 16;
    dim3 threadsPerBlock(BLOCK_SIZE, BLOCK_SIZE);
    dim3 blocksPerGrid((cols + BLOCK_SIZE - 1) / BLOCK_SIZE, 
                       (rows + BLOCK_SIZE - 1) / BLOCK_SIZE);
    
    // 启动核函数
    add_bias_kernel<<<blocksPerGrid, threadsPerBlock>>>(
        output.getDeviceData(), bias.getDeviceData(), rows, cols);
    
    // 检查错误
    HIP_CHECK(hipGetLastError());
    HIP_CHECK(hipDeviceSynchronize());
}

// 融合操作：矩阵乘法 + 偏置 + ReLU
void LinearLayer::matrixMultiplyAddBiasReLU(const Matrix& A, const Matrix& B, const Matrix& bias, Matrix& C) {
    int M = A.getRows();    // 输入批次大小
    int K = A.getCols();    // 输入特征维度
    int N = B.getCols();    // 输出特征维度
    
    // 定义块和线程大小
    constexpr int BLOCK_SIZE = 16;
    dim3 threadsPerBlock(BLOCK_SIZE, BLOCK_SIZE);
    dim3 blocksPerGrid((N + BLOCK_SIZE - 1) / BLOCK_SIZE, 
                       (M + BLOCK_SIZE - 1) / BLOCK_SIZE);
    
    // 启动融合核函数
    fused_matmul_bias_kernel<<<blocksPerGrid, threadsPerBlock>>>(
        A.getDeviceData(), B.getDeviceData(), bias.getDeviceData(), C.getDeviceData(), M, N, K);
    
    // 检查错误
    HIP_CHECK(hipGetLastError());
    HIP_CHECK(hipDeviceSynchronize());
}

// ReLULayer的前向传播实现
void ReLULayer::forward(const Matrix& input, Matrix& output, int optimization_flags) {
    // 如果输入和输出不是同一个矩阵，复制输入到输出
    if (&input != &output) {
        // 确保输出矩阵大小正确
        if (output.getRows() != input.getRows() || output.getCols() != input.getCols()) {
            // 如果输出矩阵尺寸不匹配，重新创建
            output = Matrix(input.getRows(), input.getCols(), optimization_flags & OPT_MEMORY_POOL);
        }
        
        // 分配设备内存
        output.allocateDevice();
        
        // 复制输入数据到输出
        HIP_CHECK(hipMemcpy(
            output.getDeviceData(), 
            input.getDeviceData(), 
            input.size() * sizeof(double), 
            hipMemcpyDeviceToDevice));
    }
    
    // 应用ReLU激活函数
    applyReLU(output);
}

// 应用ReLU激活函数
void ReLULayer::applyReLU(Matrix& data) {
    int size = data.size();
    
    // 定义块和线程大小
    constexpr int BLOCK_SIZE = 256;
    int blocks = (size + BLOCK_SIZE - 1) / BLOCK_SIZE;
    
    // 启动核函数
    relu_kernel<<<blocks, BLOCK_SIZE>>>(data.getDeviceData(), size);
    
    // 检查错误
    HIP_CHECK(hipGetLastError());
    HIP_CHECK(hipDeviceSynchronize());
}

// 多DCU并行处理实现
void multi_dcu_forward(const std::vector<Matrix>& inputs, std::vector<Matrix>& outputs, 
                       const std::vector<MLP>& models) {
    // 确保输入和输出数量匹配
    assert(inputs.size() == outputs.size());
    
    // 获取设备数量
    int num_devices = models.size();
    if (num_devices <= 0) {
        throw std::runtime_error("没有可用的DCU设备");
    }
    
    // 使用OpenMP并行处理
    #pragma omp parallel for num_threads(num_devices)
    for (size_t i = 0; i < inputs.size(); ++i) {
        int device_id = i % num_devices;
        
        // 设置当前设备
        HIP_CHECK(hipSetDevice(device_id));
        
        // 在对应设备上执行前向传播
        outputs[i] = models[device_id].forward(inputs[i]);
    }
}
