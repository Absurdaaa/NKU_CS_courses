#include "mlp_dcu_optimized.h"
#include <iomanip>
#include <fstream>
#include <sstream>

// 主程序 - 测试MLP前向传播性能与消融实验
int main() {
    std::cout << "曙光DCU前馈神经网络性能测试与消融实验" << std::endl;
    std::cout << "================================" << std::endl;

    // 初始化HIP设备
    int deviceCount;
    HIP_CHECK(hipGetDeviceCount(&deviceCount));
    std::cout << "检测到 " << deviceCount << " 个HIP设备" << std::endl;

    if (deviceCount == 0) {
        std::cerr << "错误: 未找到HIP设备" << std::endl;
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
    std::cout << "================================" << std::endl;

    try {
        // 定义网络参数
        const int BATCH_SIZE = 1024;
        const int INPUT_DIM = 10;
        const int HIDDEN_DIM = 20;
        const int OUTPUT_DIM = 5;
        const int NUM_RUNS = 20;  // 每个测试运行20次以获得稳定结果
        
        // 创建结果目录
        system("mkdir -p results");
        
        // 1. 基本功能测试 - 确保优化版本功能正确
        std::cout << "\n1. 基本功能测试" << std::endl;
        std::cout << "--------------------------------" << std::endl;
        
        // 创建输入数据
        Matrix input(BATCH_SIZE, INPUT_DIM);
        input.allocateHost();
        input.randomInit(-1.0, 1.0);
        input.copyToDevice();
        
        std::cout << "输入矩阵大小: " << BATCH_SIZE << " x " << INPUT_DIM << std::endl;
        std::cout << "输入矩阵示例:" << std::endl;
        input.print(3, 5);
        
        // 创建基准MLP网络（无优化）
        std::cout << "\n创建基准MLP网络（无优化）..." << std::endl;
        MLP baseline_mlp(OPT_NONE);
        
        // 添加层
        baseline_mlp.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, HIDDEN_DIM));
        baseline_mlp.addLayer(std::make_shared<ReLULayer>());
        baseline_mlp.addLayer(std::make_shared<LinearLayer>(HIDDEN_DIM, OUTPUT_DIM));
        
        // 打印网络结构
        baseline_mlp.printArchitecture();
        
        // 执行前向传播
        std::cout << "\n执行基准前向传播..." << std::endl;
        Matrix baseline_output = baseline_mlp.forward(input);
        baseline_output.copyToHost();
        
        std::cout << "基准输出矩阵大小: " << baseline_output.getRows() << " x " << baseline_output.getCols() << std::endl;
        std::cout << "基准输出矩阵示例:" << std::endl;
        baseline_output.print(3, 5);
        
        // 创建优化MLP网络（所有优化，不包括多DCU）
        std::cout << "\n创建优化MLP网络..." << std::endl;
        MLP optimized_mlp(OPT_ALL & ~OPT_MULTI_DCU);
        
        // 添加层
        optimized_mlp.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, HIDDEN_DIM));
        optimized_mlp.addLayer(std::make_shared<ReLULayer>());
        optimized_mlp.addLayer(std::make_shared<LinearLayer>(HIDDEN_DIM, OUTPUT_DIM));
        
        // 打印网络结构
        optimized_mlp.printArchitecture();
        
        // 执行前向传播
        std::cout << "\n执行优化前向传播..." << std::endl;
        Matrix optimized_output = optimized_mlp.forward(input);
        optimized_output.copyToHost();
        
        std::cout << "优化输出矩阵大小: " << optimized_output.getRows() << " x " << optimized_output.getCols() << std::endl;
        std::cout << "优化输出矩阵示例:" << std::endl;
        optimized_output.print(3, 5);
        
        // 验证结果一致性
        std::cout << "\n验证结果一致性..." << std::endl;
        bool results_match = true;
        double max_diff = 0.0;
        double avg_diff = 0.0;
        
        for (int i = 0; i < baseline_output.size(); ++i) {
            double diff = std::abs(baseline_output.getHostData()[i] - optimized_output.getHostData()[i]);
            max_diff = std::max(max_diff, diff);
            avg_diff += diff;
            
            if (diff > 1e-5) {
                results_match = false;
            }
        }
        
        avg_diff /= baseline_output.size();
        
        if (results_match) {
            std::cout << "结果一致性验证通过！" << std::endl;
        } else {
            std::cout << "警告: 结果存在差异" << std::endl;
        }
        
        std::cout << "最大差异: " << max_diff << std::endl;
        std::cout << "平均差异: " << avg_diff << std::endl;
        
        // 2. 消融实验
        std::cout << "\n2. 消融实验" << std::endl;
        std::cout << "--------------------------------" << std::endl;
        
        // 创建消融实验
        AblationExperiment ablation(BATCH_SIZE, INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM, NUM_RUNS);
        
        // 运行消融实验
        ablation.run();
        
        // 打印结果
        ablation.printResults();
        
        // 保存结果
        ablation.saveResultsToCSV("results/ablation_results.csv");
        
        // 3. 批次大小实验
        std::cout << "\n3. 批次大小实验" << std::endl;
        std::cout << "--------------------------------" << std::endl;
        
        // 定义不同的批次大小
        const int batch_sizes[] = {32, 64, 128, 256, 512, 1024, 2048, 4096};
        const int num_batch_tests = sizeof(batch_sizes) / sizeof(batch_sizes[0]);
        
        std::ofstream batch_file("results/batch_size_results.csv");
        batch_file << "批次大小,平均时间(ms),最小时间(ms)" << std::endl;
        
        for (int i = 0; i < num_batch_tests; ++i) {
            int batch_size = batch_sizes[i];
            std::cout << "测试批次大小: " << batch_size << std::endl;
            
            // 创建新的输入矩阵
            Matrix batch_input(batch_size, INPUT_DIM);
            batch_input.allocateHost();
            batch_input.randomInit(-1.0, 1.0);
            batch_input.copyToDevice();
            
            // 创建优化MLP网络
            MLP batch_mlp(OPT_ALL & ~OPT_MULTI_DCU);
            batch_mlp.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, HIDDEN_DIM));
            batch_mlp.addLayer(std::make_shared<ReLULayer>());
            batch_mlp.addLayer(std::make_shared<LinearLayer>(HIDDEN_DIM, OUTPUT_DIM));
            
            // 创建性能测试器
            PerformanceTester batch_tester(NUM_RUNS);
            batch_tester.testMLPForward(batch_mlp, batch_input);
            
            // 记录结果
            double avg_time = batch_tester.getAverageTime();
            double min_time = batch_tester.getMinTime();
            
            std::cout << "  平均时间: " << avg_time << " ms" << std::endl;
            std::cout << "  最小时间: " << min_time << " ms" << std::endl;
            
            batch_file << batch_size << "," << avg_time << "," << min_time << std::endl;
        }
        
        batch_file.close();
        std::cout << "批次大小实验结果已保存到 results/batch_size_results.csv" << std::endl;
        
        // 4. 隐藏层维度实验
        std::cout << "\n4. 隐藏层维度实验" << std::endl;
        std::cout << "--------------------------------" << std::endl;
        
        // 定义不同的隐藏层维度
        const int hidden_sizes[] = {10, 20, 50, 100, 200, 500};
        const int num_hidden_tests = sizeof(hidden_sizes) / sizeof(hidden_sizes[0]);
        
        std::ofstream hidden_file("results/hidden_dim_results.csv");
        hidden_file << "隐藏层维度,平均时间(ms),最小时间(ms)" << std::endl;
        
        for (int i = 0; i < num_hidden_tests; ++i) {
            int hidden_size = hidden_sizes[i];
            std::cout << "测试隐藏层维度: " << hidden_size << std::endl;
            
            // 创建优化MLP网络
            MLP hidden_mlp(OPT_ALL & ~OPT_MULTI_DCU);
            hidden_mlp.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, hidden_size));
            hidden_mlp.addLayer(std::make_shared<ReLULayer>());
            hidden_mlp.addLayer(std::make_shared<LinearLayer>(hidden_size, OUTPUT_DIM));
            
            // 创建性能测试器
            PerformanceTester hidden_tester(NUM_RUNS);
            hidden_tester.testMLPForward(hidden_mlp, input);
            
            // 记录结果
            double avg_time = hidden_tester.getAverageTime();
            double min_time = hidden_tester.getMinTime();
            
            std::cout << "  平均时间: " << avg_time << " ms" << std::endl;
            std::cout << "  最小时间: " << min_time << " ms" << std::endl;
            
            hidden_file << hidden_size << "," << avg_time << "," << min_time << std::endl;
        }
        
        hidden_file.close();
        std::cout << "隐藏层维度实验结果已保存到 results/hidden_dim_results.csv" << std::endl;
        
        // 5. 多DCU实验（如果有多个设备）
        if (deviceCount > 1) {
            std::cout << "\n5. 多DCU实验" << std::endl;
            std::cout << "--------------------------------" << std::endl;
            
            // 创建多个MLP模型，每个设备一个
            std::vector<MLP> models;
            for (int i = 0; i < deviceCount; ++i) {
                MLP model(OPT_ALL & ~OPT_MULTI_DCU, i);
                model.addLayer(std::make_shared<LinearLayer>(INPUT_DIM, HIDDEN_DIM));
                model.addLayer(std::make_shared<ReLULayer>());
                model.addLayer(std::make_shared<LinearLayer>(HIDDEN_DIM, OUTPUT_DIM));
                models.push_back(model);
            }
            
            // 创建多个输入和输出
            std::vector<Matrix> inputs;
            std::vector<Matrix> outputs;
            
            for (int i = 0; i < deviceCount; ++i) {
                Matrix multi_input(BATCH_SIZE, INPUT_DIM);
                multi_input.allocateHost();
                multi_input.randomInit(-1.0, 1.0);
                multi_input.copyToDevice();
                inputs.push_back(multi_input);
                
                Matrix multi_output(BATCH_SIZE, OUTPUT_DIM);
                outputs.push_back(multi_output);
            }
            
            // 测量多DCU并行性能
            Timer multi_dcu_timer;
            multi_dcu_timer.start();
            
            for (int i = 0; i < NUM_RUNS; ++i) {
                multi_dcu_forward(inputs, outputs, models);
                HIP_CHECK(hipDeviceSynchronize());
            }
            
            multi_dcu_timer.stop();
            
            double multi_dcu_time = multi_dcu_timer.elapsedMilliseconds() / NUM_RUNS;
            std::cout << "多DCU平均时间: " << multi_dcu_time << " ms" << std::endl;
            
            // 保存结果
            std::ofstream multi_dcu_file("results/multi_dcu_results.csv");
            multi_dcu_file << "设备数量,平均时间(ms)" << std::endl;
            multi_dcu_file << deviceCount << "," << multi_dcu_time << std::endl;
            multi_dcu_file.close();
            
            std::cout << "多DCU实验结果已保存到 results/multi_dcu_results.csv" << std::endl;
        }
        
        std::cout << "\n所有实验完成!" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "发生异常: " << e.what() << std::endl;
        return -1;
    }
    
    return 0;
}
