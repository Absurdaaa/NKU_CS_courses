#include <iostream>
#include <vector>
#include <random>
#include <cmath>
#include <chrono>
#include <hip/hip_runtime.h>

#define BLOCK_SIZE 32  // 建议设置为16，兼容性更好

int N, M, P;

__global__ void matmul_kernel(const double *A, const double *B, double *C, int n, int m, int p) {
    __shared__ double Asub[BLOCK_SIZE][BLOCK_SIZE];
    __shared__ double Bsub[BLOCK_SIZE][BLOCK_SIZE];

    int bx = blockIdx.x, by = blockIdx.y;
    int tx = threadIdx.x, ty = threadIdx.y;
    int row = by * BLOCK_SIZE + ty;
    int col = bx * BLOCK_SIZE + tx;
    double sum = 0.0;

    for (int t = 0; t < (m + BLOCK_SIZE - 1) / BLOCK_SIZE; ++t) {
        if (row < n && t * BLOCK_SIZE + tx < m)
            Asub[ty][tx] = A[row * m + t * BLOCK_SIZE + tx];
        else
            Asub[ty][tx] = 0.0;
        if (col < p && t * BLOCK_SIZE + ty < m)
            Bsub[ty][tx] = B[(t * BLOCK_SIZE + ty) * p + col];
        else
            Bsub[ty][tx] = 0.0;
        __syncthreads();

        for (int k = 0; k < BLOCK_SIZE; ++k)
            sum += Asub[ty][k] * Bsub[k][tx];
        __syncthreads();
    }

    if (row < n && col < p)
        C[row * p + col] = sum;
}

void init_matrix(std::vector<double>& mat) {
    std::mt19937 gen(42);
    std::uniform_real_distribution<double> dist(-1.0, 1.0);
    for (auto& x : mat)
        x = dist(gen);
}

void matmul_cpu(const std::vector<double>& A, const std::vector<double>& B, std::vector<double>& C) {
    for (int i = 0; i < N; ++i)
        for (int j = 0; j < P; ++j) {
            double sum = 0.0;
            for (int k = 0; k < M; ++k)
                sum += A[i * M + k] * B[k * P + j];
            C[i * P + j] = sum;
        }
}

bool validate(const std::vector<double>& ref, const std::vector<double>& test) {
    for (size_t i = 0; i < ref.size(); ++i)
        if (std::abs(ref[i] - test[i]) > 1e-6)
            return false;
    return true;
}

int main(int argc, char* argv[]) {
    int repeat = 100; // <<<---- 加大循环次数
    if (argc < 4) {
        N = 1024;
        M = 2048;
        P = 512;
    } else {
        N = std::atoi(argv[1]);
        M = std::atoi(argv[2]);
        P = std::atoi(argv[3]);
    }
    if (argc >= 5) {
        repeat = std::atoi(argv[4]);
    }

    std::vector<double> A(N * M), B(M * P), C(N * P), C_ref(N * P);
    init_matrix(A);
    init_matrix(B);
    matmul_cpu(A, B, C_ref);

    double *d_A, *d_B, *d_C;
    hipMalloc(&d_A, sizeof(double) * N * M);
    hipMalloc(&d_B, sizeof(double) * M * P);
    hipMalloc(&d_C, sizeof(double) * N * P);

    hipMemcpy(d_A, A.data(), sizeof(double) * N * M, hipMemcpyHostToDevice);
    hipMemcpy(d_B, B.data(), sizeof(double) * M * P, hipMemcpyHostToDevice);

    dim3 threads(BLOCK_SIZE, BLOCK_SIZE);
    dim3 grid((P + BLOCK_SIZE - 1) / BLOCK_SIZE, (N + BLOCK_SIZE - 1) / BLOCK_SIZE);

    auto start = std::chrono::high_resolution_clock::now();

    // ===== 重复多次核函数 =====
    for (int i = 0; i < repeat; ++i) {
        hipLaunchKernelGGL(matmul_kernel, grid, threads, 0, 0, d_A, d_B, d_C, N, M, P);
    }
    hipDeviceSynchronize();

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;

    hipMemcpy(C.data(), d_C, sizeof(double) * N * P, hipMemcpyDeviceToHost);

    std::cout << "[HIP] Time (repeat=" << repeat << "): " << elapsed.count() << " seconds" << std::endl;
    std::cout << "[HIP] Valid: " << (validate(C_ref, C) ? "True" : "False") << std::endl;

    double total_flops = 2.0 * N * M * P * repeat;
    double gflops = total_flops / (elapsed.count() * 1e9);
    std::cout << "[HIP] GFLOPS: " << gflops << std::endl;

    hipFree(d_A);
    hipFree(d_B);
    hipFree(d_C);

    hipDeviceProp_t prop;
    hipGetDeviceProperties(&prop, 0);   
    std::cout << "maxThreadsPerBlock = " << prop.maxThreadsPerBlock << std::endl;
    return 0;
}