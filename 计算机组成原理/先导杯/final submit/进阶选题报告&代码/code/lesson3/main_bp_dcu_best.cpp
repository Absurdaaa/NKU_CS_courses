#include "mlp_bp_dcu.h"
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <chrono>
#include <iomanip>
#include <cmath>
#include <algorithm>
#include <random>
#include <numeric>

//编译命令
//hipcc -std=c++17 main_bp_dcu_best.cpp mlp_bp_dcu.cpp -o mlp_bp_dcu_best -lhipblas -fopenmp -O3 -Wno-unused-result

// 预定义参数
#define INPUT_DIM 10       // 输入维度
#define HIDDEN_DIM 128     // 隐藏层维度（推荐128或256）
#define OUTPUT_DIM 1       // 输出维度
#define BATCH_SIZE 256     // 批次大小
#define EPOCHS 400         // 训练周期
#define LEARNING_RATE 1e-3 // 学习率


// 可视化预测结果
void visualizePredictions(const std::vector<double>& predictions, 
                         const std::vector<double>& targets,
                         const std::string& filename) {
    // 保存预测结果到CSV文件，用于外部绘图
    std::ofstream file(filename);
    if (!file) {
        std::cerr << "无法打开文件进行写入: " << filename << std::endl;
        return;
    }
    
    file << "index,prediction,target,error" << std::endl;
    
    size_t size = std::min(predictions.size(), targets.size());
    for (size_t i = 0; i < size; ++i) {
        double error = predictions[i] - targets[i];
        file << i << "," 
             << predictions[i] << "," 
             << targets[i] << "," 
             << error << std::endl;
    }
    
    file.close();
    
    std::cout << "预测结果已保存到 " << filename << std::endl;
    std::cout << "可以使用外部工具（如Python matplotlib）绘制图表" << std::endl;
}

// 计算均方误差
double calculateMSE(const std::vector<double>& predictions, const std::vector<double>& targets) {
    if (predictions.size() != targets.size() || predictions.empty()) {
        return -1.0;
    }
    
    double sum_squared_error = 0.0;
    for (size_t i = 0; i < predictions.size(); ++i) {
        double error = predictions[i] - targets[i];
        sum_squared_error += error * error;
    }
    
    return sum_squared_error / predictions.size();
}

// 计算平均绝对误差
double calculateMAE(const std::vector<double>& predictions, const std::vector<double>& targets) {
    if (predictions.size() != targets.size() || predictions.empty()) {
        return -1.0;
    }
    
    double sum_absolute_error = 0.0;
    for (size_t i = 0; i < predictions.size(); ++i) {
        double error = std::abs(predictions[i] - targets[i]);
        sum_absolute_error += error;
    }
    
    return sum_absolute_error / predictions.size();
}


int main() {
    std::cout << "基于DCU的深层MLP带宽预测实验" << std::endl;
    std::cout << "=================================================" << std::endl;

    // 检测设备
    int deviceCount;
    HIP_CHECK(hipGetDeviceCount(&deviceCount));
    std::cout << "检测到 " << deviceCount << " 个HIP设备" << std::endl;
    if (deviceCount == 0) {
        std::cerr << "未找到HIP设备，退出程序" << std::endl;
        return -1;
    }
    HIP_CHECK(hipSetDevice(0));
    hipDeviceProp_t deviceProp;
    HIP_CHECK(hipGetDeviceProperties(&deviceProp, 0));
    std::cout << "使用设备: " << deviceProp.name << std::endl;
    std::cout << "=================================================" << std::endl;

    // 加载数据集
    std::cout << "加载带宽数据..." << std::endl;
    Dataset dataset(INPUT_DIM, BATCH_SIZE);
    if (!dataset.loadFromJSON("starlink_bw.json")) {
        std::cerr << "加载数据失败，退出程序" << std::endl;
        return -1;
    }

    std::cout << "数据加载成功" << std::endl;
    std::cout << "训练集大小: " << dataset.getTrainSize() << std::endl;
    std::cout << "测试集大小: " << dataset.getTestSize() << std::endl;
    std::cout << "=================================================" << std::endl;

    // 创建深层MLP模型
    std::cout << "创建更深更宽的MLP模型..." << std::endl;
    MLP model(OPT_ALL & ~OPT_MULTI_DCU);

    // 网络架构：三层隐藏层 + ReLU
    model.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, HIDDEN_DIM));
    model.addLayer(std::make_shared<ReLULayer>());
    model.addLayer(std::make_shared<LinearLayer>(HIDDEN_DIM, HIDDEN_DIM));
    model.addLayer(std::make_shared<ReLULayer>());
    model.addLayer(std::make_shared<LinearLayer>(HIDDEN_DIM, OUTPUT_DIM));

    model.printArchitecture();
    std::cout << "参数总数: " << model.getParamCount() << std::endl;
    std::cout << "=================================================" << std::endl;

    // 创建训练器
    Trainer trainer(model, dataset, LEARNING_RATE, EPOCHS);

    // 训练模型
    std::cout << "开始训练模型..." << std::endl;
    trainer.train();

    // 保存训练历史
    trainer.saveHistory("training_history_best.csv");
    std::cout << "训练历史已保存到 training_history_best.csv" << std::endl;

    // 保存模型
    model.saveModel("bandwidth_predictor_bset.model");
    std::cout << "模型已保存到 bandwidth_predictor_bset.model" << std::endl;
    std::cout << "=================================================" << std::endl;

    // 评估模型
    std::cout << "评估模型..." << std::endl;
    double test_loss = trainer.evaluate(true);
    std::cout << "测试集损失: " << test_loss << std::endl;

    // 获取测试集
    Matrix X_test, y_test;
    dataset.getTestSet(X_test, y_test);

    // 预测
    std::vector<double> predictions = trainer.predict(X_test);

    // 获取真实值
    y_test.copyToHost();
    std::vector<double> targets(y_test.size());
    std::memcpy(targets.data(), y_test.getHostData(), y_test.size() * sizeof(double));
    targets = dataset.denormalizeData(targets);

    // 计算误差
    double mse = calculateMSE(predictions, targets);
    double mae = calculateMAE(predictions, targets);

    std::cout << "均方误差 (MSE): " << mse << std::endl;
    std::cout << "平均绝对误差 (MAE): " << mae << std::endl;

    // 可视化预测结果
    visualizePredictions(predictions, targets, "predictions_best.csv");
    std::cout << "=================================================" << std::endl;


    Matrix X_train, y_train;
    dataset.getTrainSet(X_train, y_train);
    // 获取真实值
    std::vector<double> predictions2 = trainer.predict(X_train);
    y_train.copyToHost();
    std::vector<double> targets2(y_train.size());
    std::memcpy(targets2.data(), y_train.getHostData(), y_train.size() * sizeof(double));
    targets2 = dataset.denormalizeData(targets2);

    visualizePredictions(predictions2, targets2, "predictions_train_best.csv");

    return 0;
}