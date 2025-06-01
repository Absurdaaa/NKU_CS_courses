#include "mlp_bp_dcu.h"

// 全局内存池实例
MemoryPool g_memoryPool(true); // 默认启用内存池

// 初始化静态成员
int Matrix::next_id = 0;

// 核函数 - 矩阵乘法 (基础版)
__global__ void matmul_kernel(const double* A, const double* B, double* C, int M, int N, int K) {
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

// 核函数 - 矩阵乘法 (分块版)
__global__ void tiled_matmul_kernel(const double* A, const double* B, double* C, int M, int N, int K) {
    constexpr int BLOCK_SIZE = 16; // 调整块大小以优化性能
    
    __shared__ double As[BLOCK_SIZE][BLOCK_SIZE];
    __shared__ double Bs[BLOCK_SIZE][BLOCK_SIZE];
    
    int bx = blockIdx.x;
    int by = blockIdx.y;
    int tx = threadIdx.x;
    int ty = threadIdx.y;
    
    int row = by * BLOCK_SIZE + ty;
    int col = bx * BLOCK_SIZE + tx;
    
    double sum = 0.0;
    
    for (int i = 0; i < (K + BLOCK_SIZE - 1) / BLOCK_SIZE; ++i) {
        // 加载A的子块
        if (row < M && i * BLOCK_SIZE + tx < K) {
            As[ty][tx] = A[row * K + i * BLOCK_SIZE + tx];
        } else {
            As[ty][tx] = 0.0;
        }
        
        // 加载B的子块
        if (i * BLOCK_SIZE + ty < K && col < N) {
            Bs[ty][tx] = B[(i * BLOCK_SIZE + ty) * N + col];
        } else {
            Bs[ty][tx] = 0.0;
        }
        
        __syncthreads();
        
        // 计算子块乘积累加
        for (int k = 0; k < BLOCK_SIZE; ++k) {
            sum += As[ty][k] * Bs[k][tx];
        }
        
        __syncthreads();
    }
    
    if (row < M && col < N) {
        C[row * N + col] = sum;
    }
}

// 核函数 - 添加偏置
__global__ void add_bias_kernel(double* output, const double* bias, int M, int N) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;

    if (row < M && col < N) {
        output[row * N + col] += bias[col];
    }
}

// 核函数 - 融合矩阵乘法和偏置加法
__global__ void fused_matmul_add_bias_kernel(const double* A, const double* B, const double* bias, double* C, int M, int N, int K) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;

    if (row < M && col < N) {
        double sum = 0.0;
        for (int k = 0; k < K; ++k) {
            sum += A[row * K + k] * B[k * N + col];
        }
        C[row * N + col] = sum + bias[col];
    }
}

// 核函数 - ReLU激活
__global__ void relu_kernel(const double* input, double* output, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        output[idx] = max(0.0, input[idx]);
    }
}

// 核函数 - ReLU梯度
__global__ void relu_grad_kernel(const double* output, const double* grad_output, double* grad_input, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        grad_input[idx] = (output[idx] > 0.0) ? grad_output[idx] : 0.0;
    }
}

// 核函数 - 计算MSE损失和梯度
__global__ void mse_loss_grad_kernel(const double* output, const double* target, double* loss_sum, double* output_grad, int M, int N) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;

    if (row < M && col < N) {
        double diff = output[row * N + col] - target[row * N + col];
        double squared_error = diff * diff;
        
        // 使用原子加法累加损失
        atomicAdd(loss_sum, squared_error);
        
        // 计算梯度
        output_grad[row * N + col] = 2.0 * diff / M; // 除以批次大小M
    }
}

// 核函数 - 矩阵转置乘法 C = A^T * B
__global__ void matmul_transpose_kernel(const double* A, const double* B, double* C, int M, int N, int K) {
    // A: KxM, B: KxN, C: MxN
    int row = blockIdx.y * blockDim.y + threadIdx.y; // M
    int col = blockIdx.x * blockDim.x + threadIdx.x; // N

    if (row < M && col < N) {
        double sum = 0.0;
        for (int k = 0; k < K; ++k) {
            sum += A[k * M + row] * B[k * N + col];
        }
        C[row * N + col] = sum;
    }
}

// 核函数 - 矩阵乘以转置 C = A * B^T
__global__ void matmul_multiply_transpose_kernel(const double* A, const double* B, double* C, int M, int N, int K) {
    // A: MxK, B: NxK, C: MxN
    int row = blockIdx.y * blockDim.y + threadIdx.y; // M
    int col = blockIdx.x * blockDim.x + threadIdx.x; // N

    if (row < M && col < N) {
        double sum = 0.0;
        for (int k = 0; k < K; ++k) {
            sum += A[row * K + k] * B[col * K + k];
        }
        C[row * N + col] = sum;
    }
}

// 核函数 - 计算偏置梯度 (对输出梯度按行求和)
__global__ void bias_grad_kernel(const double* output_grad, double* bias_grad, int M, int N) {
    // output_grad: MxN, bias_grad: 1xN
    extern __shared__ double sdata[];
    
    int tid = threadIdx.x;
    int col = blockIdx.x;
    
    double sum = 0.0;
    for (int row = tid; row < M; row += blockDim.x) {
        sum += output_grad[row * N + col];
    }
    sdata[tid] = sum;
    __syncthreads();
    
    // 规约求和
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            sdata[tid] += sdata[tid + s];
        }
        __syncthreads();
    }
    
    // 线程0将结果写入全局内存
    if (tid == 0) {
        bias_grad[col] = sdata[0];
    }
}

// 核函数 - SGD参数更新
__global__ void sgd_update_kernel(double* params, const double* grads, int size, double learning_rate) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        params[idx] -= learning_rate * grads[idx];
    }
}

// --- LinearLayer 实现 ---

// 矩阵乘法 C = A * B
void LinearLayer::matrixMultiply(const Matrix& A, const Matrix& B, Matrix& C, int optimization_flags) {
    assert(A.getCols() == B.getRows());
    assert(C.getRows() == A.getRows());
    assert(C.getCols() == B.getCols());
    assert(A.getDeviceData() != nullptr);
    assert(B.getDeviceData() != nullptr);
    assert(C.getDeviceData() != nullptr);
    assert(A.getDeviceData() != C.getDeviceData()); // 确保A和C不是同一个指针
    assert(B.getDeviceData() != C.getDeviceData()); // 确保B和C不是同一个指针

    if (optimization_flags & OPT_HIPBLAS) {
        matrixMultiplyHipBLAS(A, B, C);
    } else if (optimization_flags & OPT_TILED_MATMUL) {
        matrixMultiplyTiled(A, B, C);
    } else {
        matrixMultiplyBasic(A, B, C);
    }
}

// 基础矩阵乘法
void LinearLayer::matrixMultiplyBasic(const Matrix& A, const Matrix& B, Matrix& C) {
    int M = A.getRows();
    int N = B.getCols();
    int K = A.getCols();

    dim3 threadsPerBlock(16, 16);
    dim3 numBlocks((N + threadsPerBlock.x - 1) / threadsPerBlock.x, 
                   (M + threadsPerBlock.y - 1) / threadsPerBlock.y);

    hipLaunchKernelGGL(matmul_kernel, numBlocks, threadsPerBlock, 0, 0, 
                       A.getDeviceData(), B.getDeviceData(), C.getDeviceData(), M, N, K);
    HIP_CHECK(hipGetLastError());
}

// 分块矩阵乘法
void LinearLayer::matrixMultiplyTiled(const Matrix& A, const Matrix& B, Matrix& C) {
    int M = A.getRows();
    int N = B.getCols();
    int K = A.getCols();

    constexpr int BLOCK_SIZE = 16;
    dim3 threadsPerBlock(BLOCK_SIZE, BLOCK_SIZE);
    dim3 numBlocks((N + BLOCK_SIZE - 1) / BLOCK_SIZE, 
                   (M + BLOCK_SIZE - 1) / BLOCK_SIZE);

    hipLaunchKernelGGL(tiled_matmul_kernel, numBlocks, threadsPerBlock, 0, 0, 
                       A.getDeviceData(), B.getDeviceData(), C.getDeviceData(), M, N, K);
    HIP_CHECK(hipGetLastError());
}

// hipBLAS矩阵乘法
void LinearLayer::matrixMultiplyHipBLAS(const Matrix& A, const Matrix& B, Matrix& C) {
    int M = A.getRows();
    int N = B.getCols();
    int K = A.getCols();

    initHipBLAS(); // 确保已初始化

    const double alpha = 1.0;
    const double beta = 0.0;

    // hipBLAS使用列主序，我们的矩阵是行主序
    // C = A * B (行主序)  <=> C^T = B^T * A^T (列主序)
    // hipblasDgemm(handle, HIPBLAS_OP_T, HIPBLAS_OP_T, M, N, K, ...)
    // 或者 C = A * B (行主序) <=> C = B^T * A^T (列主序) ??? 不对
    // C_col = B_col * A_col
    // C(N, M) = B(N, K) * A(K, M)
    // hipblasDgemm(handle, HIPBLAS_OP_N, HIPBLAS_OP_N, N, M, K, ...)
    
    if (DEBUG_HIPBLAS) {
        std::cout << "hipBLAS矩阵乘法: A(" << M << "x" << K << ") * B(" << K << "x" << N << ") = C(" << M << "x" << N << ")" << std::endl;
        std::cout << "A设备指针: " << A.getDeviceData() << " (ID: " << A.getId() << ")" << std::endl;
        std::cout << "B设备指针: " << B.getDeviceData() << " (ID: " << B.getId() << ")" << std::endl;
        std::cout << "C设备指针: " << C.getDeviceData() << " (ID: " << C.getId() << ")" << std::endl;
    }
    
    assert(A.getDeviceData() != C.getDeviceData());
    assert(B.getDeviceData() != C.getDeviceData());

    HIPBLAS_CHECK(hipblasDgemm(hipblas_handle, HIPBLAS_OP_N, HIPBLAS_OP_N,
                               N, M, K, // 注意维度顺序 N, M, K
                               &alpha,
                               B.getDeviceData(), N, // B的leading dimension是N
                               A.getDeviceData(), K, // A的leading dimension是K
                               &beta,
                               C.getDeviceData(), N)); // C的leading dimension是N
}

// 矩阵转置乘法 C = A^T * B
void LinearLayer::matrixTransposeMultiply(const Matrix& A, const Matrix& B, Matrix& C, int optimization_flags) {
    // A: KxM, B: KxN, C: MxN
    int M = A.getCols(); // C的行数
    int N = B.getCols(); // C的列数
    int K = A.getRows(); // 公共维度

    // std::cout<<"A:"<<A.getRows()<<"x"<<A.getCols()<<std::endl;
    // std::cout<<"B:"<<B.getRows()<<"x"<<B.getCols()<<std::endl; 
    // std::cout<<"C:"<<C.getRows()<<"x"<<C.getCols()<<std::endl;
    
    assert(A.getRows() == B.getRows());
    if(C.getRows()!=M ||C.getCols()!=N){
        C = Matrix(M,N,C.getUseMemoryPool());
        C.allocateDevice();
    }
    assert(A.getDeviceData() != nullptr);
    assert(B.getDeviceData() != nullptr);
    assert(C.getDeviceData() != nullptr);
    assert(A.getDeviceData() != C.getDeviceData());
    assert(B.getDeviceData() != C.getDeviceData());

    

    if (optimization_flags & OPT_HIPBLAS) {
        initHipBLAS();
        const double alpha = 1.0;
        const double beta = 0.0;
        
        // if (DEBUG_HIPBLAS) {
        //     std::cout << "hipBLAS转置矩阵乘法: A^T(" << M << "x" << K << ") * B(" << K << "x" << N << ") = C(" << M << "x" << N << ")" << std::endl;
        //     std::cout << "A设备指针: " << A.getDeviceData() << " (ID: " << A.getId() << ")" << std::endl;
        //     std::cout << "B设备指针: " << B.getDeviceData() << " (ID: " << B.getId() << ")" << std::endl;
        //     std::cout << "C设备指针: " << C.getDeviceData() << " (ID: " << C.getId() << ")" << std::endl;
        // }
        
        // C_col = B_col * A_col^T
        // C(N, M) = B(N, K) * A(M, K)^T
        HIPBLAS_CHECK(hipblasDgemm(hipblas_handle, HIPBLAS_OP_T, HIPBLAS_OP_N,
                                   M, N, K, // N, M, K
                                   &alpha,
                                   A.getDeviceData(), K, // A的leading dimension是M
                                   B.getDeviceData(), K, // B的leading dimension是N
    
                                   &beta,
                                   C.getDeviceData(), M)); // C的leading dimension是N
    } else {
        dim3 threadsPerBlock(16, 16);
        dim3 numBlocks((N + threadsPerBlock.x - 1) / threadsPerBlock.x, 
                       (M + threadsPerBlock.y - 1) / threadsPerBlock.y);

        hipLaunchKernelGGL(matmul_transpose_kernel, numBlocks, threadsPerBlock, 0, 0, 
                           A.getDeviceData(), B.getDeviceData(), C.getDeviceData(), M, N, K);
        HIP_CHECK(hipGetLastError());
    }
}

// 矩阵乘以转置 C = A * B^T
void LinearLayer::matrixMultiplyTranspose(const Matrix& A, const Matrix& B, Matrix& C, int optimization_flags) {
    // A: MxK, B: NxK, C: MxN
    // std::cout<<A.getRows()<<"x"<<A.getCols()<<std::endl;
    // std::cout<<B.getRows()<<"x"<<B.getCols()<<std::endl;
    
    int M = A.getRows(); // C的行数
    int N = B.getRows(); // C的列数
    int K = A.getCols(); // 公共维度
    
    assert(A.getCols() == B.getCols());
    assert(C.getRows() == M);
    assert(C.getCols() == N);
    assert(A.getDeviceData() != nullptr);
    assert(B.getDeviceData() != nullptr);
    assert(C.getDeviceData() != nullptr);
    assert(A.getDeviceData() != C.getDeviceData());
    assert(B.getDeviceData() != C.getDeviceData());

    if (optimization_flags & OPT_HIPBLAS) {
        initHipBLAS();
        const double alpha = 1.0;
        const double beta = 0.0;
        
        // if (DEBUG_HIPBLAS) {
        //     std::cout << "hipBLAS乘转置矩阵乘法: A(" << M << "x" << K << ") * B^T(" << K << "x" << N << ") = C(" << M << "x" << N << ")" << std::endl;
        //     std::cout << "A设备指针: " << A.getDeviceData() << " (ID: " << A.getId() << ")" << std::endl;
        //     std::cout << "B设备指针: " << B.getDeviceData() << " (ID: " << B.getId() << ")" << std::endl;
        //     std::cout << "C设备指针: " << C.getDeviceData() << " (ID: " << C.getId() << ")" << std::endl;
        // }
        
        // C_col = B_col^T * A_col
        // C(N, M) = B(K, N)^T * A(K, M)
        HIPBLAS_CHECK(hipblasDgemm(hipblas_handle, HIPBLAS_OP_N, HIPBLAS_OP_T,
                                M, N, K, // M, N, K - 正确顺序
                                &alpha,
                                A.getDeviceData(), M, // A的leading dimension是M
                                B.getDeviceData(), N, // B的leading dimension是N
                                &beta,
                                C.getDeviceData(), M)); // C的leading dimension是M
    } else {
        dim3 threadsPerBlock(16, 16);
        dim3 numBlocks((N + threadsPerBlock.x - 1) / threadsPerBlock.x, 
                       (M + threadsPerBlock.y - 1) / threadsPerBlock.y);

        hipLaunchKernelGGL(matmul_multiply_transpose_kernel, numBlocks, threadsPerBlock, 0, 0, 
                           A.getDeviceData(), B.getDeviceData(), C.getDeviceData(), M, N, K);
        HIP_CHECK(hipGetLastError());
    }
}

// 添加偏置
void LinearLayer::addBias(Matrix& output, const Matrix& bias_vec, int optimization_flags) {
    assert(output.getCols() == bias_vec.getCols());
    assert(bias_vec.getRows() == 1);
    assert(output.getDeviceData() != nullptr);
    assert(bias_vec.getDeviceData() != nullptr);

    int M = output.getRows();
    int N = output.getCols();

    dim3 threadsPerBlock(16, 16);
    dim3 numBlocks((N + threadsPerBlock.x - 1) / threadsPerBlock.x, 
                   (M + threadsPerBlock.y - 1) / threadsPerBlock.y);

    hipLaunchKernelGGL(add_bias_kernel, numBlocks, threadsPerBlock, 0, 0, 
                       output.getDeviceData(), bias_vec.getDeviceData(), M, N);
    HIP_CHECK(hipGetLastError());
}

// 融合矩阵乘法和偏置加法
void LinearLayer::matrixMultiplyAddBias(const Matrix& A, const Matrix& B, const Matrix& bias_vec, Matrix& C) {
    assert(A.getCols() == B.getRows());
    assert(C.getRows() == A.getRows());
    assert(C.getCols() == B.getCols());
    assert(C.getCols() == bias_vec.getCols());
    assert(bias_vec.getRows() == 1);
    assert(A.getDeviceData() != nullptr);
    assert(B.getDeviceData() != nullptr);
    assert(bias_vec.getDeviceData() != nullptr);
    assert(C.getDeviceData() != nullptr);
    assert(A.getDeviceData() != C.getDeviceData());
    assert(B.getDeviceData() != C.getDeviceData());
    assert(bias_vec.getDeviceData() != C.getDeviceData());

    int M = A.getRows();
    int N = B.getCols();
    int K = A.getCols();

    dim3 threadsPerBlock(16, 16);
    dim3 numBlocks((N + threadsPerBlock.x - 1) / threadsPerBlock.x, 
                   (M + threadsPerBlock.y - 1) / threadsPerBlock.y);

    hipLaunchKernelGGL(fused_matmul_add_bias_kernel, numBlocks, threadsPerBlock, 0, 0, 
                       A.getDeviceData(), B.getDeviceData(), bias_vec.getDeviceData(), C.getDeviceData(), M, N, K);
    HIP_CHECK(hipGetLastError());
}

// LinearLayer 前向传播
void LinearLayer::forward(const Matrix& input, Matrix& output, int optimization_flags) {
    assert(input.getCols() == input_dim);
    
    // 调整输出矩阵大小并确保分配设备内存
    output.resize(input.getRows(), output_dim);
    output.ensureDeviceAllocated();
    
    // 确保权重和偏置在设备上
    weights.ensureDeviceAllocated();
    bias.ensureDeviceAllocated();
    
    // 保存输入用于反向传播（深拷贝）
    last_input = input; // 使用拷贝赋值运算符进行深拷贝
    last_input.ensureDeviceAllocated(); // 确保拷贝后的last_input在设备上

    if (optimization_flags & OPT_FUSED_KERNELS) {
        matrixMultiplyAddBias(input, weights, bias, output);
    } else {
        matrixMultiply(input, weights, output, optimization_flags);
        addBias(output, bias, optimization_flags);
    }
}

// LinearLayer 反向传播
void LinearLayer::backward(const Matrix& input, const Matrix& output, const Matrix& output_grad, 
                         Matrix& input_grad, int optimization_flags) {

    Matrix local_output_grad(output_grad);
    local_output_grad.ensureDeviceAllocated();

    // std::cout<<"input:"<<input.getRows()<<"x"<<input.getCols()<<std::endl;  
    // std::cout<<"output:"<<output.getRows()<<"x"<<output.getCols()<<std::endl;    
    // std::cout<<"output_grad:"<<output_grad.getRows()<<"x"<<output_grad.getCols()<<std::endl;


    assert(local_output_grad.getRows() == input.getRows());
    assert(local_output_grad.getCols() == output_dim);

    // std::cout<<"LinearLayer 反向传播"<<std::endl;
    
    // 确保所有输入矩阵都在设备上
    input.syncDevice(); // 确保input数据准备好
    output_grad.syncDevice(); // 确保output_grad数据准备好
    weights.ensureDeviceAllocated();
    dw.ensureDeviceAllocated();
    db.ensureDeviceAllocated();
    input_grad.resize(input.getRows(), input.getCols()); // 调整输入梯度大小
    input_grad.ensureDeviceAllocated();
    
    // 计算权重梯度 dw = input^T * output_grad
    dw.resize(input_dim, output_dim); // 确保dw维度正确

    // std::cout<<"dw:"<<dw.getRows()<<"x"<<dw.getCols()<<std::endl;
    // std::cout<<"input:"<<input.getRows()<<"x"<<input.getCols()<<std::endl; 
    // std::cout<<"output_grad:"<<output_grad.getRows()<<"x"<<output_grad.getCols()<<std::endl;

    dw.ensureDeviceAllocated();
    matrixTransposeMultiply(input, local_output_grad, dw, optimization_flags);

    // std::cout<<"dw:"<<dw.getRows()<<"x"<<dw.getCols()<<std::endl;
    
    // 计算偏置梯度 db = sum(output_grad, axis=0)
    db.resize(1, output_dim); // 确保db维度正确
    db.ensureDeviceAllocated();
    int M = local_output_grad.getRows();
    int N = local_output_grad.getCols();
    dim3 threadsPerBlock(256); // 调整线程块大小
    dim3 numBlocks(N);
    size_t shared_mem_size = threadsPerBlock.x * sizeof(double);
    hipLaunchKernelGGL(bias_grad_kernel, numBlocks, threadsPerBlock, shared_mem_size, 0, 
                       local_output_grad.getDeviceData(), db.getDeviceData(), M, N);
    HIP_CHECK(hipGetLastError());
    
    // 计算输入梯度 input_grad = output_grad * weights^T

    // std::cout<<local_output_grad.getRows()<<"x"<<local_output_grad.getCols()<<std::endl;
    // std::cout<<weights.getRows()<<"x"<<weights.getCols()<<std::endl;
    //这里不需要专制计算？
    matrixMultiplyTranspose(local_output_grad, weights, input_grad, optimization_flags);
}

// LinearLayer 参数更新
void LinearLayer::updateParams(double learning_rate) {
    weights.ensureDeviceAllocated();
    bias.ensureDeviceAllocated();
    dw.ensureDeviceAllocated();
    db.ensureDeviceAllocated();

    // 更新权重 W = W - lr * dW
    int weight_size = weights.size();
    dim3 threadsPerBlock_w(256);
    dim3 numBlocks_w((weight_size + threadsPerBlock_w.x - 1) / threadsPerBlock_w.x);
    hipLaunchKernelGGL(sgd_update_kernel, numBlocks_w, threadsPerBlock_w, 0, 0, 
                       weights.getDeviceData(), dw.getDeviceData(), weight_size, learning_rate);
    HIP_CHECK(hipGetLastError());

    // 更新偏置 b = b - lr * db
    int bias_size = bias.size();
    dim3 threadsPerBlock_b(256);
    dim3 numBlocks_b((bias_size + threadsPerBlock_b.x - 1) / threadsPerBlock_b.x);
    hipLaunchKernelGGL(sgd_update_kernel, numBlocks_b, threadsPerBlock_b, 0, 0, 
                       bias.getDeviceData(), db.getDeviceData(), bias_size, learning_rate);
    HIP_CHECK(hipGetLastError());
}

// LinearLayer 保存参数
void LinearLayer::saveParams(std::ofstream& file) const {
    weights.copyToHost();
    bias.copyToHost();
    
    int rows = weights.getRows();
    int cols = weights.getCols();
    file.write(reinterpret_cast<const char*>(&rows), sizeof(int));
    file.write(reinterpret_cast<const char*>(&cols), sizeof(int));
    file.write(reinterpret_cast<const char*>(weights.getHostData()), rows * cols * sizeof(double));
    
    rows = bias.getRows();
    cols = bias.getCols();
    file.write(reinterpret_cast<const char*>(&rows), sizeof(int));
    file.write(reinterpret_cast<const char*>(&cols), sizeof(int));
    file.write(reinterpret_cast<const char*>(bias.getHostData()), rows * cols * sizeof(double));
}

// LinearLayer 加载参数
void LinearLayer::loadParams(std::ifstream& file) {
    int rows, cols;
    file.read(reinterpret_cast<char*>(&rows), sizeof(int));
    file.read(reinterpret_cast<char*>(&cols), sizeof(int));
    weights.resize(rows, cols);
    weights.allocateHost();
    file.read(reinterpret_cast<char*>(weights.getHostData()), rows * cols * sizeof(double));
    weights.copyToDevice();
    
    file.read(reinterpret_cast<char*>(&rows), sizeof(int));
    file.read(reinterpret_cast<char*>(&cols), sizeof(int));
    bias.resize(rows, cols);
    bias.allocateHost();
    file.read(reinterpret_cast<char*>(bias.getHostData()), rows * cols * sizeof(double));
    bias.copyToDevice();
}

// --- ReLULayer 实现 ---

// 应用ReLU激活函数
void ReLULayer::applyReLU(const Matrix& input, Matrix& output) {
    assert(input.getRows() == output.getRows());
    assert(input.getCols() == output.getCols());
    assert(input.getDeviceData() != nullptr);
    assert(output.getDeviceData() != nullptr);
    assert(input.getDeviceData() != output.getDeviceData());

    int size = input.size();
    dim3 threadsPerBlock(256);
    dim3 numBlocks((size + threadsPerBlock.x - 1) / threadsPerBlock.x);

    hipLaunchKernelGGL(relu_kernel, numBlocks, threadsPerBlock, 0, 0, 
                       input.getDeviceData(), output.getDeviceData(), size);
    HIP_CHECK(hipGetLastError());
}

// 应用ReLU导数
void ReLULayer::applyReLUGrad(const Matrix& output, const Matrix& grad_output, Matrix& grad_input) {
    assert(output.size() == grad_output.size());
    assert(output.size() == grad_input.size());
    assert(output.getDeviceData() != nullptr);
    assert(grad_output.getDeviceData() != nullptr);
    assert(grad_input.getDeviceData() != nullptr);
    assert(output.getDeviceData() != grad_input.getDeviceData());
    assert(grad_output.getDeviceData() != grad_input.getDeviceData());

    int size = output.size();
    dim3 threadsPerBlock(256);
    dim3 numBlocks((size + threadsPerBlock.x - 1) / threadsPerBlock.x);

    hipLaunchKernelGGL(relu_grad_kernel, numBlocks, threadsPerBlock, 0, 0, 
                       output.getDeviceData(), grad_output.getDeviceData(), grad_input.getDeviceData(), size);
    HIP_CHECK(hipGetLastError());
}

// ReLULayer 前向传播
void ReLULayer::forward(const Matrix& input, Matrix& output, int optimization_flags) {
    // 调整输出矩阵大小并确保分配设备内存
    output.resize(input.getRows(), input.getCols());
    output.ensureDeviceAllocated();
    
    // 应用ReLU
    applyReLU(input, output);
    
    // 保存输出用于反向传播（深拷贝）
    last_output = output; // 使用拷贝赋值运算符进行深拷贝
    last_output.ensureDeviceAllocated(); // 确保拷贝后的last_output在设备上
}

// ReLULayer 反向传播
void ReLULayer::backward(const Matrix& input, const Matrix& output, const Matrix& output_grad, 
                         Matrix& input_grad, int optimization_flags) {
    assert(output_grad.getRows() == input.getRows());
    assert(output_grad.getCols() == input.getCols());
    
    // 确保所有输入矩阵都在设备上
    last_output.ensureDeviceAllocated(); // 使用保存的输出
    output_grad.syncDevice(); // 确保output_grad数据准备好
    input_grad.resize(input.getRows(), input.getCols()); // 调整输入梯度大小
    input_grad.ensureDeviceAllocated();
    
    // 计算ReLU梯度
    applyReLUGrad(last_output, output_grad, input_grad);
}

// --- MLP 实现 ---

// 计算损失和输出梯度（MSE损失）
void MLP::computeLoss(const Matrix& output, const Matrix& target, double& loss, Matrix& output_grad) {
    assert(output.getRows() == target.getRows());
    assert(output.getCols() == target.getCols());
    // assert(output.getRows() == output_grad.getRows());
    // assert(output.getCols() == output_grad.getCols());
    assert(output.getDeviceData() != nullptr);
    assert(target.getDeviceData() != nullptr);
    // assert(output_grad.getDeviceData() != nullptr);
    // assert(output.getDeviceData() != output_grad.getDeviceData());
    // assert(target.getDeviceData() != output_grad.getDeviceData());

    int M = output.getRows();
    int N = output.getCols();
    
    // 用于累加损失的设备内存
    double* d_loss_sum;
    HIP_CHECK(hipMalloc(&d_loss_sum, sizeof(double)));
    HIP_CHECK(hipMemset(d_loss_sum, 0, sizeof(double)));

    dim3 threadsPerBlock(16, 16);
    dim3 numBlocks((N + threadsPerBlock.x - 1) / threadsPerBlock.x, 
                   (M + threadsPerBlock.y - 1) / threadsPerBlock.y);

    hipLaunchKernelGGL(mse_loss_grad_kernel, numBlocks, threadsPerBlock, 0, 0, 
                       output.getDeviceData(), target.getDeviceData(), d_loss_sum, output_grad.getDeviceData(), M, N);
    HIP_CHECK(hipGetLastError());
    
    // 将设备上的损失和复制回主机
    double h_loss_sum;
    HIP_CHECK(hipMemcpy(&h_loss_sum, d_loss_sum, sizeof(double), hipMemcpyDeviceToHost));
    HIP_CHECK(hipFree(d_loss_sum));
    
    loss = h_loss_sum / M; // 计算平均损失
}

// 保存模型参数
void MLP::saveModel(const std::string& filename) const {
    std::ofstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("无法打开文件保存模型: " + filename);
    }
    
    int num_layers = layers.size();
    file.write(reinterpret_cast<const char*>(&num_layers), sizeof(int));
    
    for (const auto& layer : layers) {
        layer->saveParams(file);
    }
    
    file.close();
}

// 加载模型参数
void MLP::loadModel(const std::string& filename) {
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("无法打开文件加载模型: " + filename);
    }
    
    int num_layers;
    file.read(reinterpret_cast<char*>(&num_layers), sizeof(int));
    
    if (num_layers != layers.size()) {
        throw std::runtime_error("模型文件中的层数与当前网络不匹配");
    }
    
    for (auto& layer : layers) {
        layer->loadParams(file);
    }
    
    file.close();
}

// --- 多DCU并行处理 ---
void multi_dcu_forward(const std::vector<Matrix>& inputs, std::vector<Matrix>& outputs, 
                       const std::vector<MLP>& models) {
    int num_devices = models.size();
    assert(inputs.size() == outputs.size());
    assert(models.size() == num_devices);
    
    #pragma omp parallel for num_threads(num_devices)
    for (int i = 0; i < inputs.size(); ++i) {
        int device_id = i % num_devices;
        HIP_CHECK(hipSetDevice(device_id));
        
        // 在对应设备上执行前向传播
        // 注意：MLP::forward现在是const，它内部会创建局部输出来避免修改成员变量
        // 我们需要将结果赋值给outputs[i]
        outputs[i] = models[device_id].forward(inputs[i]);
    }
}

// --- Dataset 实现 ---

// 创建滑动窗口样本
void Dataset::createWindowSamples(const std::vector<double>& data, 
                                std::vector<std::vector<double>>& X, 
                                std::vector<double>& y) {
    X.clear();
    y.clear();
    for (size_t i = 0; i + window_size < data.size(); ++i) {
        std::vector<double> window(data.begin() + i, data.begin() + i + window_size);
        X.push_back(window);
        y.push_back(data[i + window_size]);
    }
}

// 加载JSON带宽数据
bool Dataset::loadFromJSON(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "无法打开文件: " << filename << std::endl;
        return false;
    }
    
    // 读取整个文件内容
    std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    file.close();
    
    // 解析JSON数组
    std::vector<double> data;
    
    // 简单的JSON数组解析（假设格式正确）
    size_t pos = content.find('[');
    size_t end = content.find(']', pos);
    
    if (pos == std::string::npos || end == std::string::npos) {
        std::cerr << "JSON格式错误" << std::endl;
        return false;
    }
    
    std::string array_content = content.substr(pos + 1, end - pos - 1);
    std::stringstream ss(array_content);
    std::string item;
    
    while (std::getline(ss, item, ',')) {
        // 去除空格
        item.erase(std::remove_if(item.begin(), item.end(), ::isspace), item.end());
        if (!item.empty()) {
            try {
                double value = std::stod(item);
                data.push_back(value);
            } catch (const std::exception& e) {
                std::cerr << "解析错误: " << e.what() << " 在项: " << item << std::endl;
            }
        }
    }

    if (data.empty()) {
        std::cerr << "错误: 未能从JSON文件中加载任何带宽数据" << std::endl;
        return false;
    }

    // 归一化数据
    normalizeData(data);

    // 创建滑动窗口样本
    std::vector<std::vector<double>> X_all;
    std::vector<double> y_all;
    createWindowSamples(data, X_all, y_all);
    
    if (X_all.empty()) {
        std::cerr << "错误: 创建滑动窗口样本失败，数据量可能不足" << std::endl;
        return false;
    }

    // 划分训练集和测试集
    int train_size = static_cast<int>(X_all.size() * 0.8);
    int test_size = X_all.size() - train_size;

    X_train.resize(train_size);
    y_train.resize(train_size);
    X_test.resize(test_size);
    y_test.resize(test_size);

    for (int i = 0; i < train_size; ++i) {
        X_train[i] = Matrix(1, window_size);
        X_train[i].allocateHost();
        std::memcpy(X_train[i].getHostData(), X_all[i].data(), window_size * sizeof(double));
        X_train[i].copyToDevice();
        
        y_train[i] = Matrix(1, 1);
        y_train[i].allocateHost();
        y_train[i].getHostData()[0] = y_all[i];
        y_train[i].copyToDevice();
    }

    for (int i = 0; i < test_size; ++i) {
        X_test[i] = Matrix(1, window_size);
        X_test[i].allocateHost();
        std::memcpy(X_test[i].getHostData(), X_all[train_size + i].data(), window_size * sizeof(double));
        X_test[i].copyToDevice();
        
        y_test[i] = Matrix(1, 1);
        y_test[i].allocateHost();
        y_test[i].getHostData()[0] = y_all[train_size + i];
        y_test[i].copyToDevice();
    }

    return true;
}

// 归一化数据 (Min-Max Scaling)
void Dataset::normalizeData(std::vector<double>& data) {
    if (data.empty()) return;
    min_val = *std::min_element(data.begin(), data.end());
    max_val = *std::max_element(data.begin(), data.end());
    double range = max_val - min_val;
    if (range == 0.0) range = 1.0; // 避免除以零
    for (double& val : data) {
        val = (val - min_val) / range;
    }
}

// 反归一化数据
std::vector<double> Dataset::denormalizeData(const std::vector<double>& data) const {
    std::vector<double> denormalized_data = data;
    double range = max_val - min_val;
    if (range == 0.0) range = 1.0;
    for (double& val : denormalized_data) {
        val = val * range + min_val;
    }
    return denormalized_data;
}

// 获取指定批次
void Dataset::getBatch(int batch_idx, Matrix& X_batch, Matrix& y_batch) const {
    int start_idx = batch_idx * batch_size;
    int end_idx = std::min(start_idx + batch_size, (int)X_train.size());
    int current_batch_size = end_idx - start_idx;

    if (current_batch_size <= 0) {
        X_batch.resize(0, 0);
        y_batch.resize(0, 0);
        return;
    }

    X_batch.resize(current_batch_size, window_size);
    y_batch.resize(current_batch_size, 1);
    X_batch.allocateHost();
    y_batch.allocateHost();

    for (int i = 0; i < current_batch_size; ++i) {
        X_train[start_idx + i].copyToHost(); // 确保主机数据最新
        y_train[start_idx + i].copyToHost(); // 确保主机数据最新
        
        std::memcpy(X_batch.getHostData() + i * window_size, 
                   X_train[start_idx + i].getHostData(), 
                   window_size * sizeof(double));
                   
        std::memcpy(y_batch.getHostData() + i, 
                   y_train[start_idx + i].getHostData(), 
                   sizeof(double));
    }
    
    X_batch.copyToDevice();
    y_batch.copyToDevice();
}

// 获取测试集
void Dataset::getTestSet(Matrix& X_test_matrix, Matrix& y_test_matrix) const {
    int test_size = X_test.size();
    if (test_size == 0) {
        X_test_matrix.resize(0, 0);
        y_test_matrix.resize(0, 0);
        return;
    }

    X_test_matrix.resize(test_size, window_size);
    y_test_matrix.resize(test_size, 1);
    X_test_matrix.allocateHost();
    y_test_matrix.allocateHost();

    for (int i = 0; i < test_size; ++i) {
        X_test[i].copyToHost(); // 确保主机数据最新
        y_test[i].copyToHost(); // 确保主机数据最新
        
        std::memcpy(X_test_matrix.getHostData() + i * window_size, 
                   X_test[i].getHostData(), 
                   window_size * sizeof(double));
                   
        std::memcpy(y_test_matrix.getHostData() + i, 
                   y_test[i].getHostData(), 
                   sizeof(double));
    }
    
    X_test_matrix.copyToDevice();
    y_test_matrix.copyToDevice();
}

void Dataset::getTrainSet(Matrix& X_test_matrix, Matrix& y_test_matrix) const {
    int test_size = X_train.size();
    if (test_size == 0) {
        X_test_matrix.resize(0, 0);
        y_test_matrix.resize(0, 0);
        return;
    }

    X_test_matrix.resize(test_size, window_size);
    y_test_matrix.resize(test_size, 1);
    X_test_matrix.allocateHost();
    y_test_matrix.allocateHost();

    for (int i = 0; i < test_size; ++i) {
        X_train[i].copyToHost(); // 确保主机数据最新
        y_train[i].copyToHost(); // 确保主机数据最新
        
        std::memcpy(X_test_matrix.getHostData() + i * window_size, 
                   X_train[i].getHostData(), 
                   window_size * sizeof(double));
                   
        std::memcpy(y_test_matrix.getHostData() + i, 
                   y_train[i].getHostData(), 
                   sizeof(double));
    }
    
    X_test_matrix.copyToDevice();
    y_test_matrix.copyToDevice();
}

// --- Trainer 实现 ---

// 训练模型
void Trainer::train() {
    train_losses.clear();
    test_losses.clear();
    train_times.clear();
    int num_batches = dataset.getNumBatches();

    std::cout << "开始训练..." << std::endl;
    std::cout << "总轮数: " << epochs << std::endl;
    std::cout << "学习率: " << learning_rate << std::endl;
    std::cout << "批次大小: " << dataset.getBatchSize() << std::endl;
    std::cout << "训练样本数: " << dataset.getTrainSize() << std::endl;
    std::cout << "测试样本数: " << dataset.getTestSize() << std::endl;
    model.printArchitecture();

    for (int epoch = 0; epoch < epochs; ++epoch) {
        epoch_timer.start();
        double epoch_loss = 0.0;
        
        // 随机打乱训练数据索引（可选）
        // std::vector<int> indices(dataset.getTrainSize());
        // std::iota(indices.begin(), indices.end(), 0);
        // std::random_shuffle(indices.begin(), indices.end());

        for (int batch_idx = 0; batch_idx < num_batches; ++batch_idx) {
            Matrix X_batch(0, 0, model.getOptimizationFlags() & OPT_MEMORY_POOL);
            Matrix y_batch(0, 0, model.getOptimizationFlags() & OPT_MEMORY_POOL);
            dataset.getBatch(batch_idx, X_batch, y_batch);
            
            if (X_batch.getRows() == 0) continue; // 跳过空批次

            double batch_loss = 0.0;
            model.backward(X_batch, y_batch, batch_loss);
            model.updateParams(learning_rate);
            epoch_loss += batch_loss;
        }
        
        epoch_timer.stop();
        double epoch_time = epoch_timer.elapsedMilliseconds() / 1000.0; // 秒
        train_times.push_back(epoch_time);
        
        double avg_epoch_loss = epoch_loss / num_batches;
        train_losses.push_back(avg_epoch_loss);
        
        // 在每个epoch结束时评估测试集损失
        double test_loss = evaluate(true);
        test_losses.push_back(test_loss);

        std::cout << "Epoch [" << epoch + 1 << "/" << epochs << "] "
                  << "训练损失: " << avg_epoch_loss << " "
                  << "测试损失: " << test_loss << " "
                  << "耗时: " << epoch_time << " s" << std::endl;
    }
    std::cout << "训练完成!" << std::endl;
}

// 评估模型
double Trainer::evaluate(bool is_test_set) {
    Matrix X_eval(0, 0, model.getOptimizationFlags() & OPT_MEMORY_POOL);
    Matrix y_eval(0, 0, model.getOptimizationFlags() & OPT_MEMORY_POOL);
    
    if (is_test_set) {
        dataset.getTestSet(X_eval, y_eval);
    } else {
        // 获取整个训练集进行评估（如果需要）
        // dataset.getTrainSet(X_eval, y_eval); 
        return -1.0; // 暂不支持评估整个训练集
    }
    
    if (X_eval.getRows() == 0) return 0.0;

    Matrix predictions = model.forward(X_eval);
    double loss = 0.0;
    // Matrix dummy_grad(0, 0, model.getOptimizationFlags() & OPT_MEMORY_POOL); // 评估时不需要梯度
    Matrix dummy_grad(predictions.getRows(), predictions.getCols(), model.getOptimizationFlags() & OPT_MEMORY_POOL);
    dummy_grad.allocateDevice();
    model.computeLoss(predictions, y_eval, loss, dummy_grad);
    return loss;
}

// 预测
std::vector<double> Trainer::predict(const Matrix& X) {
    Matrix predictions_matrix = model.forward(X);
    predictions_matrix.copyToHost();
    
    std::vector<double> predictions(predictions_matrix.size());
    std::memcpy(predictions.data(), predictions_matrix.getHostData(), predictions_matrix.size() * sizeof(double));
    
    // 反归一化
    return dataset.denormalizeData(predictions);
}

// 保存训练历史
void Trainer::saveHistory(const std::string& filename) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "错误: 无法打开文件保存训练历史 " << filename << std::endl;
        return;
    }
    file << "Epoch,TrainLoss,TestLoss,Time(s)" << std::endl;
    for (size_t i = 0; i < train_losses.size(); ++i) {
        file << i + 1 << "," 
             << train_losses[i] << "," 
             << (i < test_losses.size() ? test_losses[i] : 0.0) << "," 
             << (i < train_times.size() ? train_times[i] : 0.0) << std::endl;
    }
    file.close();
}

// 保存预测结果
void Trainer::savePredictions(const std::string& filename, const std::vector<double>& predictions, 
                            const std::vector<double>& targets) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "错误: 无法打开文件保存预测结果 " << filename << std::endl;
        return;
    }
    file << "Target,Prediction" << std::endl;
    size_t n = std::min(predictions.size(), targets.size());
    for (size_t i = 0; i < n; ++i) {
        file << targets[i] << "," << predictions[i] << std::endl;
    }
    file.close();
}
