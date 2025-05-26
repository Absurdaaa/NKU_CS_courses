#include <hip/hip_runtime.h>
#include <iostream>
#include <vector>
#include <cstdlib>
#include <cmath>
#include <ctime>

// 编译: hipcc mlp_forward.cpp -o mlp_forward
// 运行: ./mlp_forward

#define BATCH 1024  // Batch size
#define I 10        // 输入层维度
#define H 20        // 隐藏层神经元数
#define O 5         // 输出层维度

// -------------------- GPU核函数部分 --------------------

// 通用矩阵乘法核函数: C = A(MxK) * B(KxN) -> C(MxN)
__global__ void matmul_kernel(const double *A, const double *B, double *C, int M, int N, int K) {
    int row = blockIdx.y * blockDim.y + threadIdx.y; // 行索引
    int col = blockIdx.x * blockDim.x + threadIdx.x; // 列索引
    if (row < M && col < N) {
        double sum = 0.0;
        for (int k = 0; k < K; ++k) {
            // A的row行k列 乘以 B的k行col列
            sum += A[row * K + k] * B[k * N + col];
        }
        C[row * N + col] = sum;
    }
}

// Bias加法核函数: 按列加偏置(支持广播)
__global__ void add_bias_kernel(double *C, const double *B, int M, int N) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < M * N) {
        int col = idx % N; // 每一列加同一个偏置
        C[idx] += B[col];
    }
}

// ReLU激活函数核
__global__ void relu_kernel(double *A, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        A[idx] = fmax(0.0, A[idx]);
    }
}

// -------------------- 主机辅助函数 --------------------

// 随机初始化向量[-1, 1]
void random_init(std::vector<double> &mat) {
    for (auto &val : mat) {
        val = static_cast<double>(rand()) / RAND_MAX * 2 - 1;
    }
}

// -------------------- 主程序 --------------------
int main() {
    srand(time(nullptr)); // 用当前时间设置随机种子

    // 主机端分配空间
    std::vector<double> h_X(BATCH * I), h_W1(I * H), h_B1(H), h_W2(H * O), h_B2(O);
    std::vector<double> h_H(BATCH * H), h_Y(BATCH * O);

    // 数据随机初始化
    random_init(h_X);
    random_init(h_W1);
    random_init(h_B1);
    random_init(h_W2);
    random_init(h_B2);

    // 设备端指针声明
    double *d_X, *d_W1, *d_B1, *d_H, *d_W2, *d_B2, *d_Y;

    // 设备端空间分配
    hipMalloc(&d_X, BATCH * I * sizeof(double));
    hipMalloc(&d_W1, I * H * sizeof(double));
    hipMalloc(&d_B1, H * sizeof(double));
    hipMalloc(&d_H, BATCH * H * sizeof(double));
    hipMalloc(&d_W2, H * O * sizeof(double));
    hipMalloc(&d_B2, O * sizeof(double));
    hipMalloc(&d_Y, BATCH * O * sizeof(double));

    // 主机数据拷贝到设备
    hipMemcpy(d_X, h_X.data(), BATCH * I * sizeof(double), hipMemcpyHostToDevice);
    hipMemcpy(d_W1, h_W1.data(), I * H * sizeof(double), hipMemcpyHostToDevice);
    hipMemcpy(d_B1, h_B1.data(), H * sizeof(double), hipMemcpyHostToDevice);
    hipMemcpy(d_W2, h_W2.data(), H * O * sizeof(double), hipMemcpyHostToDevice);
    hipMemcpy(d_B2, h_B2.data(), O * sizeof(double), hipMemcpyHostToDevice);

    // -------------------- 前向传播 --------------------
    // 1. 隐藏层 H = ReLU(X * W1 + B1)
    // 1.1 矩阵乘法: d_H = d_X * d_W1
    dim3 blockDim1(16, 16);
    dim3 gridDim1((H + blockDim1.x - 1) / blockDim1.x, (BATCH + blockDim1.y - 1) / blockDim1.y);
    hipLaunchKernelGGL(matmul_kernel, gridDim1, blockDim1, 0, 0, d_X, d_W1, d_H, BATCH, H, I);

    // 1.2 加bias: d_H += d_B1
    int numH = BATCH * H;
    hipLaunchKernelGGL(add_bias_kernel, dim3((numH + 255) / 256), dim3(256), 0, 0, d_H, d_B1, BATCH, H);

    // 1.3 ReLU激活
    hipLaunchKernelGGL(relu_kernel, dim3((numH + 255) / 256), dim3(256), 0, 0, d_H, numH);

    // 2. 输出层 Y = H * W2 + B2 (无激活)
    // 2.1 矩阵乘法: d_Y = d_H * d_W2
    dim3 blockDim2(16, 16);
    dim3 gridDim2((O + blockDim2.x - 1) / blockDim2.x, (BATCH + blockDim2.y - 1) / blockDim2.y);
    hipLaunchKernelGGL(matmul_kernel, gridDim2, blockDim2, 0, 0, d_H, d_W2, d_Y, BATCH, O, H);

    // 2.2 加bias: d_Y += d_B2
    int numY = BATCH * O;
    hipLaunchKernelGGL(add_bias_kernel, dim3((numY + 255) / 256), dim3(256), 0, 0, d_Y, d_B2, BATCH, O);

    // -------------------- 结果拷贝回主机 --------------------
    hipMemcpy(h_Y.data(), d_Y, BATCH * O * sizeof(double), hipMemcpyDeviceToHost);

    // -------------------- 部分输出打印 --------------------
    std::cout << "前5个样本的输出结果:" << std::endl;
    for (int i = 0; i < 5; ++i) {
        std::cout << "Sample " << i << ": ";
        for (int j = 0; j < O; ++j)
            std::cout << h_Y[i * O + j] << " ";
        std::cout << std::endl;
    }

    // -------------------- 释放设备内存 --------------------
    hipFree(d_X);
    hipFree(d_W1);
    hipFree(d_B1);
    hipFree(d_H);
    hipFree(d_W2);
    hipFree(d_B2);
    hipFree(d_Y);

    return 0;
}