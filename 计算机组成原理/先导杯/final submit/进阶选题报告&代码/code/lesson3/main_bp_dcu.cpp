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

// 编译命令：hipcc -std=c++17 main_bp_dcu.cpp mlp_bp_dcu.cpp -o mlp_bp_dcu -lhipblas -fopenmp

// 预定义参数
#define INPUT_DIM 10      // 输入维度（窗口大小）
#define HIDDEN_DIM 32     // 隐藏层维度
#define OUTPUT_DIM 1      // 输出维度
#define BATCH_SIZE 256    // 批次大小
#define EPOCHS 200        // 训练周期数
#define LEARNING_RATE 1e-4 // 学习率

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

// 性能测试 - 前向传播
void benchmarkForward(MLP& model, const Matrix& input, int num_runs = 100) {
    // 预热
    Matrix output = model.forward(input);
    
    // 计时
    std::vector<double> times;
    for (int i = 0; i < num_runs; ++i) {
        Timer timer;
        timer.start();
        output = model.forward(input);
        timer.stop();
        times.push_back(timer.elapsedMilliseconds());
    }
    
    // 计算统计数据
    double avg_time = std::accumulate(times.begin(), times.end(), 0.0) / times.size();
    double min_time = *std::min_element(times.begin(), times.end());
    double max_time = *std::max_element(times.begin(), times.end());
    
    // 计算吞吐量（每秒样本数）
    double throughput = input.getRows() / (avg_time / 1000.0);
    
    std::cout << "前向传播性能测试结果 (" << num_runs << " 次运行):" << std::endl;
    std::cout << "  平均时间: " << avg_time << " ms" << std::endl;
    std::cout << "  最小时间: " << min_time << " ms" << std::endl;
    std::cout << "  最大时间: " << max_time << " ms" << std::endl;
    std::cout << "  吞吐量: " << throughput << " 样本/秒" << std::endl;
}

// 性能测试 - 反向传播
void benchmarkBackward(MLP& model, const Matrix& input, const Matrix& target, int num_runs = 100) {
    // 预热
    double loss;
    model.backward(input, target, loss);
    
    // 计时
    std::vector<double> times;
    for (int i = 0; i < num_runs; ++i) {
        Timer timer;
        timer.start();
        model.backward(input, target, loss);
        timer.stop();
        times.push_back(timer.elapsedMilliseconds());
    }
    
    // 计算统计数据
    double avg_time = std::accumulate(times.begin(), times.end(), 0.0) / times.size();
    double min_time = *std::min_element(times.begin(), times.end());
    double max_time = *std::max_element(times.begin(), times.end());
    
    // 计算吞吐量（每秒样本数）
    double throughput = input.getRows() / (avg_time / 1000.0);
    
    std::cout << "反向传播性能测试结果 (" << num_runs << " 次运行):" << std::endl;
    std::cout << "  平均时间: " << avg_time << " ms" << std::endl;
    std::cout << "  最小时间: " << min_time << " ms" << std::endl;
    std::cout << "  最大时间: " << max_time << " ms" << std::endl;
    std::cout << "  吞吐量: " << throughput << " 样本/秒" << std::endl;
}

// 消融实验 - 测试不同优化组合
void ablationStudy(const Dataset& dataset) {
    // 优化组合
    std::vector<std::pair<int, std::string>> optimization_configs = {
        {OPT_NONE, "基准版本"},
        {OPT_TILED_MATMUL, "分块矩阵乘法"},
        {OPT_FUSED_KERNELS, "融合核函数"},
        {OPT_HIPBLAS, "hipBLAS加速"},
        {OPT_MEMORY_POOL, "内存池优化"},
        {OPT_TILED_MATMUL | OPT_FUSED_KERNELS, "分块矩阵乘法 + 融合核函数"},
        {OPT_HIPBLAS | OPT_MEMORY_POOL, "hipBLAS加速 + 内存池优化"},
        {OPT_ALL & ~OPT_MULTI_DCU, "所有优化（不包括多DCU）"},
        {OPT_ALL, "所有优化"}
    };
    
    // 获取测试数据
    Matrix X_test, y_test;
    dataset.getTestSet(X_test, y_test);
    
    // 结果保存
    std::ofstream result_file("ablation_results.csv");
    result_file << "optimization,forward_time_ms,backward_time_ms,total_time_ms,speedup" << std::endl;
    
    double baseline_time = 0.0;
    
    for (const auto& config : optimization_configs) {
        int opt_flags = config.first;
        std::string opt_name = config.second;
        
        std::cout << "\n测试优化配置: " << opt_name << std::endl;
        
        // 创建模型
        MLP model(opt_flags);
        
        // 添加层
        model.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, HIDDEN_DIM));
        model.addLayer(std::make_shared<ReLULayer>());
        model.addLayer(std::make_shared<LinearLayer>(HIDDEN_DIM, OUTPUT_DIM));
        
        // 测试前向传播
        Timer forward_timer;
        forward_timer.start();
        Matrix output = model.forward(X_test);
        forward_timer.stop();
        double forward_time = forward_timer.elapsedMilliseconds();
        
        // 测试反向传播
        Timer backward_timer;
        backward_timer.start();
        double loss;
        model.backward(X_test, y_test, loss);
        backward_timer.stop();
        double backward_time = backward_timer.elapsedMilliseconds();
        
        double total_time = forward_time + backward_time;
        
        // 计算加速比
        double speedup = 1.0;
        if (opt_flags == OPT_NONE) {
            baseline_time = total_time;
        } else {
            speedup = baseline_time / total_time;
        }
        
        // 输出结果
        std::cout << "  前向传播时间: " << forward_time << " ms" << std::endl;
        std::cout << "  反向传播时间: " << backward_time << " ms" << std::endl;
        std::cout << "  总时间: " << total_time << " ms" << std::endl;
        std::cout << "  加速比: " << speedup << "x" << std::endl;
        
        // 保存结果
        result_file << opt_name << "," 
                   << forward_time << "," 
                   << backward_time << "," 
                   << total_time << "," 
                   << speedup << std::endl;
    }
    
    result_file.close();
    std::cout << "\n消融实验结果已保存到 ablation_results.csv" << std::endl;
}

// 批次大小实验 - 测试不同批次大小对性能的影响
void batchSizeExperiment(const Dataset& dataset, int opt_flags = OPT_ALL & ~OPT_MULTI_DCU) {
    // 批次大小
    // std::vector<int> batch_sizes = {32, 64, 128, 256, 512, 1024, 2048};
    std::vector<int> batch_sizes = {32, 64, 128, 256, 512};
    
    // 结果保存
    std::ofstream result_file("batch_size_results.csv");
    result_file << "batch_size,forward_time_ms,backward_time_ms,total_time_ms,samples_per_second" << std::endl;
    
    for (int batch_size : batch_sizes) {
        std::cout << "\n测试批次大小: " << batch_size << std::endl;
        
        // 创建输入和目标矩阵
        Matrix X(batch_size, INPUT_DIM);
        Matrix y(batch_size, OUTPUT_DIM);
        
        // 随机初始化
        X.allocateHost();
        X.randomInit();
        X.copyToDevice();
        
        y.allocateHost();
        y.randomInit();
        y.copyToDevice();
        
        // 创建模型
        MLP model(opt_flags);
        
        // 添加层
        model.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, HIDDEN_DIM));
        model.addLayer(std::make_shared<ReLULayer>());
        model.addLayer(std::make_shared<LinearLayer>(HIDDEN_DIM, OUTPUT_DIM));
        
        // 测试前向传播
        Timer forward_timer;
        forward_timer.start();
        Matrix output = model.forward(X);
        forward_timer.stop();
        double forward_time = forward_timer.elapsedMilliseconds();
        
        // 测试反向传播
        Timer backward_timer;
        backward_timer.start();
        double loss;
        model.backward(X, y, loss);
        backward_timer.stop();
        double backward_time = backward_timer.elapsedMilliseconds();
        
        double total_time = forward_time + backward_time;
        double samples_per_second = batch_size / (total_time / 1000.0);
        
        // 输出结果
        std::cout << "  前向传播时间: " << forward_time << " ms" << std::endl;
        std::cout << "  反向传播时间: " << backward_time << " ms" << std::endl;
        std::cout << "  总时间: " << total_time << " ms" << std::endl;
        std::cout << "  吞吐量: " << samples_per_second << " 样本/秒" << std::endl;
        
        // 保存结果
        result_file << batch_size << "," 
                   << forward_time << "," 
                   << backward_time << "," 
                   << total_time << "," 
                   << samples_per_second << std::endl;
    }
    
    result_file.close();
    std::cout << "\n批次大小实验结果已保存到 batch_size_results.csv" << std::endl;
}

// 隐藏层维度实验 - 测试不同隐藏层维度对性能和准确性的影响
void hiddenDimExperiment(const Dataset& dataset, int opt_flags = OPT_ALL & ~OPT_MULTI_DCU) {
    // 隐藏层维度
    std::vector<int> hidden_dims = {16, 32, 64, 128, 256};
    
    // 获取测试数据
    Matrix X_test, y_test;
    dataset.getTestSet(X_test, y_test);
    
    // 结果保存
    std::ofstream result_file("hidden_dim_results.csv");
    result_file << "hidden_dim,forward_time_ms,backward_time_ms,total_time_ms,mse,mae" << std::endl;
    
    for (int hidden_dim : hidden_dims) {
        std::cout << "\n测试隐藏层维度: " << hidden_dim << std::endl;
        
        // 创建模型
        MLP model(opt_flags);
        
        // 添加层
        model.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, hidden_dim));
        model.addLayer(std::make_shared<ReLULayer>());
        model.addLayer(std::make_shared<LinearLayer>(hidden_dim, OUTPUT_DIM));
        
        // 测试前向传播
        Timer forward_timer;
        forward_timer.start();
        Matrix output = model.forward(X_test);
        forward_timer.stop();
        double forward_time = forward_timer.elapsedMilliseconds();
        
        // 测试反向传播
        Timer backward_timer;
        backward_timer.start();
        double loss;
        model.backward(X_test, y_test, loss);
        backward_timer.stop();
        double backward_time = backward_timer.elapsedMilliseconds();
        
        double total_time = forward_time + backward_time;
        
        // 计算误差
        output.copyToHost();
        y_test.copyToHost();
        
        std::vector<double> predictions(output.size());
        std::vector<double> targets(y_test.size());
        
        std::memcpy(predictions.data(), output.getHostData(), output.size() * sizeof(double));
        std::memcpy(targets.data(), y_test.getHostData(), y_test.size() * sizeof(double));
        
        double mse = calculateMSE(predictions, targets);
        double mae = calculateMAE(predictions, targets);
        
        // 输出结果
        std::cout << "  前向传播时间: " << forward_time << " ms" << std::endl;
        std::cout << "  反向传播时间: " << backward_time << " ms" << std::endl;
        std::cout << "  总时间: " << total_time << " ms" << std::endl;
        std::cout << "  MSE: " << mse << std::endl;
        std::cout << "  MAE: " << mae << std::endl;
        
        // 保存结果
        result_file << hidden_dim << "," 
                   << forward_time << "," 
                   << backward_time << "," 
                   << total_time << "," 
                   << mse << "," 
                   << mae << std::endl;
    }
    
    result_file.close();
    std::cout << "\n隐藏层维度实验结果已保存到 hidden_dim_results.csv" << std::endl;
}

int main() {
    std::cout << "基于曙光DCU的前馈神经网络带宽预测性能优化" << std::endl;
    std::cout << "=================================================" << std::endl;
    
    // 检测设备
    int deviceCount;
    HIP_CHECK(hipGetDeviceCount(&deviceCount));
    std::cout << "检测到 " << deviceCount << " 个HIP设备" << std::endl;
    
    if (deviceCount == 0) {
        std::cerr << "未找到HIP设备，退出程序" << std::endl;
        return -1;
    }
    
    // 选择第一个设备
    HIP_CHECK(hipSetDevice(0));
    
    hipDeviceProp_t deviceProp;
    HIP_CHECK(hipGetDeviceProperties(&deviceProp, 0));
    std::cout << "使用设备: " << deviceProp.name << std::endl;
    std::cout << "计算能力: " << deviceProp.major << "." << deviceProp.minor << std::endl;
    std::cout << "多处理器数量: " << deviceProp.multiProcessorCount << std::endl;
    std::cout << "全局内存: " << deviceProp.totalGlobalMem / (1024 * 1024) << " MB" << std::endl;
    std::cout << "=================================================" << std::endl;
    
    // 加载数据集
    std::cout << "加载带宽数据..." << std::endl;
    Dataset dataset(INPUT_DIM, BATCH_SIZE);
    if (!dataset.loadFromJSON("starlink_bw.json")) {
        std::cerr << "加载数据失败，退出程序" << std::endl;
        return -1;
    }
    
    std::cout << "数据加载成功" << std::endl;
    std::cout << "窗口大小: " << dataset.getWindowSize() << std::endl;
    std::cout << "批次大小: " << dataset.getBatchSize() << std::endl;
    std::cout << "训练集大小: " << dataset.getTrainSize() << std::endl;
    std::cout << "测试集大小: " << dataset.getTestSize() << std::endl;
    std::cout << "=================================================" << std::endl;
    
    // 创建模型
    std::cout << "创建MLP模型..." << std::endl;
    MLP model(OPT_ALL & ~OPT_MULTI_DCU);  // 使用所有优化，除了多DCU
    
    // 添加层
    model.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, HIDDEN_DIM));
    model.addLayer(std::make_shared<ReLULayer>());
    model.addLayer(std::make_shared<LinearLayer>(HIDDEN_DIM, OUTPUT_DIM));
    
    model.printArchitecture();
    std::cout << "参数总数: " << model.getParamCount() << std::endl;
    std::cout << "=================================================" << std::endl;
    
    // 创建训练器
    std::cout << "创建训练器..." << std::endl;
    Trainer trainer(model, dataset, LEARNING_RATE, EPOCHS);
    
    // 训练模型
    std::cout << "开始训练模型..." << std::endl;
    trainer.train();
    
    // 保存训练历史
    trainer.saveHistory("training_history.csv");
    std::cout << "训练历史已保存到 training_history.csv" << std::endl;
    
    // 保存模型
    model.saveModel("bandwidth_predictor.model");
    std::cout << "模型已保存到 bandwidth_predictor.model" << std::endl;
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
    visualizePredictions(predictions, targets, "predictions.csv");
    std::cout << "=================================================" << std::endl;
    
    // 性能测试
    std::cout << "性能测试..." << std::endl;
    
    // 前向传播性能
    benchmarkForward(model, X_test);
    
    // 反向传播性能
    benchmarkBackward(model, X_test, y_test);
    
    // 消融实验
    std::cout << "\n开始消融实验..." << std::endl;
    ablationStudy(dataset);
    
    // 批次大小实验
    std::cout << "\n开始批次大小实验..." << std::endl;
    batchSizeExperiment(dataset);
    
    // 隐藏层维度实验
    std::cout << "\n开始隐藏层维度实验..." << std::endl;
    hiddenDimExperiment(dataset);
    
    std::cout << "=================================================" << std::endl;
    std::cout << "所有实验完成!" << std::endl;
    
    return 0;
}
