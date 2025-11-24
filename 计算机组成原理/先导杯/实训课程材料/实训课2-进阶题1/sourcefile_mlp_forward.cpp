#include <hip/hip_runtime.h>
#include <iostream>
#include <vector>
#include <cstdlib>
#include <cmath>

// 编译文件
// hipcc sourcefile_mlp_forward.cpp -o mlp_forward
// 执行文件
// ./mlp_forward 或者 hipprof ./mlp_forward


#define BATCH 1024
#define I 10
#define H 20
#define O 5

// 主要修改函数
__global__ void matmul_kernel(const double* A, const double* B, double* C, int M, int N, int K) {
    return;
}

__global__ void relu_kernel(double* A, int size) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < size) {
        A[idx] = fmax(0.0, A[idx]);
    }
    return;
}

void random_init(std::vector<double>& mat) {
    for (auto& val : mat) {
        val = static_cast<double>(rand()) / RAND_MAX * 2 - 1;
    }
    return;
}

int main() {
    std::vector<double> h_X(BATCH * I), h_W1(I * H), h_B1(H), h_W2(H * O), h_B2(O);
    std::vector<double> h_H(BATCH * H), h_Y(BATCH * O);

    random_init(h_X);
    random_init(h_W1);
    random_init(h_B1);
    random_init(h_W2);
    random_init(h_B2);

    // 以下均为主要修改部分
    double *d_X, *d_W1, *d_B1, *d_H, *d_W2, *d_B2, *d_Y;
    

    // Hidden layer: H = X * W1

    // Add bias and apply ReLU
    

    // Output layer: Y = H * W2

    // Add output bias
   

    // Print a few output values
    // for (int i = 0; i < 5; ++i) {
    //    std::cout << "Output[" << i << "]: ";
    //    for (int j = 0; j < O; ++j)
    //        std::cout << h_Y[i * O + j] << " ";
    //    std::cout << std::endl;
    // }

    hipFree(d_X);
    hipFree(d_W1);
    hipFree(d_B1);
    hipFree(d_H);
    hipFree(d_W2);
    hipFree(d_B2);
    hipFree(d_Y);

    return 0;
}
