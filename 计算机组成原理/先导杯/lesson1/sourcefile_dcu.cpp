#include <hip/hip_runtime.h>
#include <iostream>
#include <vector>
#include <random>
#include <cmath>

#include <chrono>

// 编译
// hipcc sourcefile_dcu.cpp -o outputfile_dcu
// 执行
// ./outputfile_dcu

#define N 1024
#define M 2024
#define P 512
#define BLOCK_SIZE 16
#define BLOCK 16

// HIP核函数：每个线程负责C矩阵的一个元素
__global__ void matmul_kernel(const double *A, const double *B, double *C, int n, int m, int p)
{
    // int row = blockIdx.y * blockDim.y + threadIdx.y;
    // int col = blockIdx.x * blockDim.x + threadIdx.x;
    // if (row < n && col < p)
    // {
    //     double sum = 0.0;
    //     for (int k = 0; k < m; ++k)
    //         sum += A[row * m + k] * B[k * p + col];
    //     C[row * p + col] = sum;
    // }
    __shared__ float Asub[BLOCK][BLOCK];
    __shared__ float Bsub[BLOCK][BLOCK];
    int bx = blockIdx.x, by = blockIdx.y;
    int tx = threadIdx.x, ty = threadIdx.y;
    int row = by * BLOCK + ty;
    int col = bx * BLOCK + tx;
    float sum = 0.0f;
    for (int t = 0; t < (M + BLOCK - 1) / BLOCK; ++t) {
        if (row < N && t * BLOCK + tx < M)
            Asub[ty][tx] = A[row * M + t * BLOCK + tx];
        else
            Asub[ty][tx] = 0.f;
        if (col < P && t * BLOCK + ty < M)
            Bsub[ty][tx] = B[(t * BLOCK + ty) * P + col];
        else
            Bsub[ty][tx] = 0.f;
        __syncthreads();
        for (int k = 0; k < BLOCK; ++k)
            sum += Asub[ty][k] * Bsub[k][tx];
        __syncthreads();
    }
    if (row < N && col < P)
        C[row * P + col] = sum;
}

void init_matrix(std::vector<double> &mat)
{
    std::mt19937 gen(42);
    std::uniform_real_distribution<double> dist(-1.0, 1.0);
    for (auto &x : mat)
        x = dist(gen);
}

void matmul_cpu(const std::vector<double> &A, const std::vector<double> &B, std::vector<double> &C)
{
    for (int i = 0; i < N; ++i)
        for (int j = 0; j < P; ++j)
        {
            double sum = 0.0;
            for (int k = 0; k < M; ++k)
                sum += A[i * M + k] * B[k * P + j];
            C[i * P + j] = sum;
        }
}

bool validate(const std::vector<double> &ref, const std::vector<double> &test)
{
    for (size_t i = 0; i < ref.size(); ++i)
        if (std::abs(ref[i] - test[i]) > 1e-6)
            return false;
    return true;
}

int main()
{
    std::vector<double> A(N * M), B(M * P), C(N * P), C_ref(N * P);
    init_matrix(A);
    init_matrix(B);

    // CPU baseline
    matmul_cpu(A, B, C_ref);

    // Allocate device memory
    double *d_A, *d_B, *d_C;
    hipMalloc(&d_A, sizeof(double) * N * M);
    hipMalloc(&d_B, sizeof(double) * M * P);
    hipMalloc(&d_C, sizeof(double) * N * P);

    // Copy input matrices to device
    hipMemcpy(d_A, A.data(), sizeof(double) * N * M, hipMemcpyHostToDevice);
    hipMemcpy(d_B, B.data(), sizeof(double) * M * P, hipMemcpyHostToDevice);

    dim3 threads(BLOCK_SIZE, BLOCK_SIZE);
    dim3 grid((P + BLOCK_SIZE - 1) / BLOCK_SIZE, (N + BLOCK_SIZE - 1) / BLOCK_SIZE);

    // 计时开始
    auto start = std::chrono::high_resolution_clock::now();

    // Launch kernel
    hipLaunchKernelGGL(matmul_kernel, grid, threads, 0, 0, d_A, d_B, d_C, N, M, P);
    hipDeviceSynchronize();

    // 计时结束
    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;

    // Copy result back to host
    hipMemcpy(C.data(), d_C, sizeof(double) * N * P, hipMemcpyDeviceToHost);

    std::cout << std::fixed;
    std::cout.precision(9);
    std::cout << "[HIP] Time: " << elapsed.count() << " seconds" << std::endl;
    std::cout << "[HIP] Valid: " << validate(C_ref, C) << std::endl;

    hipFree(d_A);
    hipFree(d_B);
    hipFree(d_C);

    return 0;
}