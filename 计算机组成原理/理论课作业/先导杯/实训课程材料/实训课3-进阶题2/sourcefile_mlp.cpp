#include <hip/hip_runtime.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <cmath>
#include <chrono>
#include <string>
#include <sstream>
#include <algorithm>

// 编译文件
// hipcc sourcefile_mlp.cpp -o mlp_full_dcu
// 执行文件
// ./mlp_full_dcu 或者 hipprof ./mlp_full_dcu

// 预定义参数，可根据需求修改
#define INPUT_DIM 10
#define HIDDEN_DIM 32
#define OUTPUT_DIM 1
#define BATCH_SIZE 256
#define EPOCHS 200
#define LEARNING_RATE 1e-4


// 以下函数和main函数均不为固定形式，可自行按照需求修改

// HIP kernels函数形式，需要自行设计
__global__ void matmul(const double* A, const double* B, double* C, int M, int N, int K) {
    return;
}

__global__ void compute_output_grad(const double* pred, const double* target, double* grad, int size) {
    return;
}

__global__ void compute_relu_backward(double* delta, const double* activ, int size) {
    return;
}

__global__ void compute_mse_loss(const double* pred, const double* target, double* loss, int size) {

    return;
}

__global__ void sgd_update(double* weights, const double* grad, double lr, int size) {
    return;
}

// 加载带宽数据
std::vector<double> load_json_bandwidth(const std::string& filename) {
    return {};
}

// 创建数据集
void create_dataset(const std::vector<double>& data,
                    std::vector<double>& X,
                    std::vector<double>& y) {
    return;
}

// 数据归一化处理
void normalize_data(std::vector<double>& data, double& min_val, double& max_val) {
    min_val = *std::min_element(data.begin(), data.end());
    max_val = *std::max_element(data.begin(), data.end());
    for (auto& val : data) {
        val = (val - min_val) / (max_val - min_val);
    }
    return;
}

// 数据反归一化处理
void denormalize_data(std::vector<double>& data, double min_val, double max_val) {
    for (auto& val : data) {
        val = val * (max_val - min_val) + min_val;
    }
    return;
}

// ----------------------------- Main -------------------------------
int main() {
	// 读取带宽json文件，并生成测试集和训练集

	// 训练MLP网络，包括前向传播、反向传播、梯度下降、参数更新等
    for (int epoch = 0; epoch < EPOCHS; ++epoch) {
        double total_loss = 0.0;
        
        // std::cout << "[Epoch " << epoch + 1 << "] Loss: " << total_loss << ", Time: " << ms << " ms" << std::endl;
    }

	// 推理部分，测试训练的MLP网络

    // for (size_t i = 0; i < 10; ++i)
    //     std::cout << "Predicted bandwidth at step " << i << ": " << predictions[i] << ", Actual: " << h_y[i] << std::endl;
    // std::cout << "[INFO] Mean Squared Error (MSE) on predictions: " << mse_error << std::endl;
    
    // 保存训练的神经网路，并且可以重新加载，用于重新训练或者直接进行推理预测
    return 0;
}
