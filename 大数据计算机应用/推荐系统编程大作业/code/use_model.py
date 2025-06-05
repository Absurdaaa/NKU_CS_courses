import pandas as pd
import numpy as np
import time
from surprise import Dataset, Reader
from surprise import SVD, SVDpp, KNNBasic, KNNWithMeans, NMF, BaselineOnly, SlopeOne
from surprise.model_selection import cross_validate, train_test_split
from surprise import accuracy

def load_data_to_df(file_path):
    """
    将数据文件加载为pandas DataFrame
    """
    user_item_pairs = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
    i = 0
    while i < len(lines):
        # 处理用户头部行
        if '|' in lines[i]:
            parts = lines[i].strip().split('|')
            user_id = int(parts[0])
            item_count = int(parts[1])
            
            # 处理该用户的评分
            for j in range(1, item_count + 1):
                if i + j < len(lines):
                    item_parts = lines[i + j].strip().split()
                    if len(item_parts) == 2:
                        item_id = int(item_parts[0])
                        rating = int(item_parts[1])
                        user_item_pairs.append((user_id, item_id, rating))
            
            # 跳到下一个用户
            i += item_count + 1
        else:
            i += 1
    
    # 从收集的数据创建DataFrame
    df = pd.DataFrame(user_item_pairs, columns=['user_id', 'item_id', 'rating'])
    return df

def prepare_surprise_data(ratings_df):
    """
    准备Surprise库所需的数据格式
    """
    # 确定评分范围
    min_rating = ratings_df['rating'].min()
    max_rating = ratings_df['rating'].max()
    
    # 创建Reader对象
    reader = Reader(rating_scale=(min_rating, max_rating))
    
    # 将DataFrame转换为Surprise的Dataset格式
    data = Dataset.load_from_df(ratings_df[['user_id', 'item_id', 'rating']], reader)
    
    return data

def evaluate_model(model, trainset, testset, model_name):
    """
    评估模型性能
    """
    # 训练模型
    start_time = time.time()
    model.fit(trainset)
    train_time = time.time() - start_time
    
    # 在测试集上预测
    start_time = time.time()
    predictions = model.test(testset)
    predict_time = time.time() - start_time
    
    # 计算RMSE和MSE
    rmse = accuracy.rmse(predictions)
    mse = accuracy.mse(predictions)
    
    print(f"\n{model_name}:")
    print(f"均方误差 (MSE): {mse:.4f}")
    print(f"均方根误差 (RMSE): {rmse:.4f}")
    print(f"训练时间: {train_time:.2f}秒")
    print(f"预测时间: {predict_time:.2f}秒")
    
    return mse, rmse, train_time, predict_time, predictions

def compare_all_models(data_path, test_size=0.2, random_state=42):
    """
    比较所有模型的性能
    """
    # 加载数据
    print("加载数据...")
    ratings_df = load_data_to_df(data_path)
    print(f"加载了 {len(ratings_df)} 条评分记录")
    
    # 准备Surprise数据
    print("准备数据...")
    data = prepare_surprise_data(ratings_df)
    
    # 分割训练集和测试集
    print(f"分割数据，测试集比例: {test_size}")
    trainset, testset = train_test_split(data, test_size=test_size, random_state=random_state)
    
    # 定义要评估的模型
    models = [
        (SVD(random_state=random_state), "SVD (矩阵分解)"),
        (SVDpp(random_state=random_state), "SVD++ (增强矩阵分解)"),
        (NMF(random_state=random_state), "NMF (非负矩阵分解)"),
        (KNNBasic(k=40), "KNN Basic (基础协同过滤)"),
        (KNNWithMeans(k=40), "KNN with Means (均值修正的协同过滤)"),
        (BaselineOnly(), "Baseline (基线预测)"),
        (SlopeOne(), "Slope One")
    ]
    
    # 存储结果
    results = []
    
    # 评估每个模型
    print("\n开始评估模型:")
    for model, model_name in models:
        print(f"\n评估 {model_name}...")
        mse, rmse, train_time, predict_time, _ = evaluate_model(model, trainset, testset, model_name)
        results.append({
            'Model': model_name,
            'MSE': mse,
            'RMSE': rmse,
            'Training Time': train_time,
            'Prediction Time': predict_time
        })
    
    # 创建结果DataFrame并按MSE排序
    results_df = pd.DataFrame(results).sort_values('MSE')
    
    print("\n模型性能对比（按MSE排序）:")
    print(results_df)
    
    # 获取最佳模型并调整其参数
    if len(results) > 0:
        best_model_name = results_df.iloc[0]['Model']
        print(f"\n最佳模型是: {best_model_name}")
        
        # 为最佳模型进行参数调优
        if "SVD" in best_model_name and "SVD++" not in best_model_name:
            print("\n为SVD模型优化参数...")
            optimize_svd_parameters(data, test_size, random_state)
        elif "SVD++" in best_model_name:
            print("\nSVD++已是最佳模型，进一步调整可能耗时很长")
        elif "KNN" in best_model_name:
            print("\n为KNN模型优化参数...")
            optimize_knn_parameters(data, test_size, random_state, "with_means" in best_model_name.lower())
    
    return results_df

def optimize_svd_parameters(data, test_size, random_state):
    """优化SVD模型参数"""
    # 分割数据
    trainset, testset = train_test_split(data, test_size=test_size, random_state=random_state)
    
    # 定义要测试的参数
    n_factors_list = [50, 100, 150]
    n_epochs_list = [20, 30]
    lr_all_list = [0.005, 0.01]
    reg_all_list = [0.02, 0.1]
    
    best_mse = float('inf')
    best_params = None
    
    for n_factors in n_factors_list:
        for n_epochs in n_epochs_list:
            for lr_all in lr_all_list:
                for reg_all in reg_all_list:
                    model = SVD(n_factors=n_factors, n_epochs=n_epochs, 
                              lr_all=lr_all, reg_all=reg_all, random_state=random_state)
                    
                    model.fit(trainset)
                    predictions = model.test(testset)
                    mse = accuracy.mse(predictions)
                    
                    print(f"SVD参数: n_factors={n_factors}, n_epochs={n_epochs}, " 
                          f"lr_all={lr_all}, reg_all={reg_all} -> MSE: {mse:.4f}")
                    
                    if mse < best_mse:
                        best_mse = mse
                        best_params = (n_factors, n_epochs, lr_all, reg_all)
    
    if best_params:
        n_factors, n_epochs, lr_all, reg_all = best_params
        print(f"\n最佳SVD参数: n_factors={n_factors}, n_epochs={n_epochs}, "
              f"lr_all={lr_all}, reg_all={reg_all}")
        print(f"最佳MSE: {best_mse:.4f}")
        
        # 使用最佳参数重新训练并评估
        best_model = SVD(n_factors=n_factors, n_epochs=n_epochs, 
                       lr_all=lr_all, reg_all=reg_all, random_state=random_state)
        evaluate_model(best_model, trainset, testset, "优化后的SVD")

def optimize_knn_parameters(data, test_size, random_state, with_means=True):
    """优化KNN模型参数"""
    # 分割数据
    trainset, testset = train_test_split(data, test_size=test_size, random_state=random_state)
    
    # 定义要测试的参数
    k_list = [20, 30, 40, 50, 60]
    sim_options_list = [
        {'name': 'cosine', 'user_based': True},
        {'name': 'pearson', 'user_based': True},
        {'name': 'pearson_baseline', 'user_based': True},
        {'name': 'cosine', 'user_based': False},
        {'name': 'pearson', 'user_based': False},
        {'name': 'pearson_baseline', 'user_based': False}
    ]
    
    best_mse = float('inf')
    best_params = None
    
    for k in k_list:
        for sim_options in sim_options_list:
            if with_means:
                model = KNNWithMeans(k=k, sim_options=sim_options)
                model_name = "KNN with Means"
            else:
                model = KNNBasic(k=k, sim_options=sim_options)
                model_name = "KNN Basic"
            
            model.fit(trainset)
            predictions = model.test(testset)
            mse = accuracy.mse(predictions)
            
            user_based_str = "用户" if sim_options['user_based'] else "物品"
            print(f"{model_name}参数: k={k}, 相似度={sim_options['name']}, " 
                  f"基于{user_based_str} -> MSE: {mse:.4f}")
            
            if mse < best_mse:
                best_mse = mse
                best_params = (k, sim_options)
    
    if best_params:
        k, sim_options = best_params
        user_based_str = "用户" if sim_options['user_based'] else "物品"
        print(f"\n最佳{model_name}参数: k={k}, 相似度={sim_options['name']}, 基于{user_based_str}")
        print(f"最佳MSE: {best_mse:.4f}")
        
        # 使用最佳参数重新训练并评估
        if with_means:
            best_model = KNNWithMeans(k=k, sim_options=sim_options)
        else:
            best_model = KNNBasic(k=k, sim_options=sim_options)
        
        evaluate_model(best_model, trainset, testset, f"优化后的{model_name}")

def predict_for_test_file(train_file, test_file, output_file):
    """为测试文件生成预测结果并输出到文件"""
    # 加载训练数据
    print("加载训练数据...")
    train_df = load_data_to_df(train_file)
    
    # 准备Surprise数据
    reader = Reader(rating_scale=(train_df['rating'].min(), train_df['rating'].max()))
    train_data = Dataset.load_from_df(train_df[['user_id', 'item_id', 'rating']], reader)
    trainset = train_data.build_full_trainset()
    
    # 使用经过验证最优的算法 (例如SVD)
    model = SVD(n_factors=100, n_epochs=20, lr_all=0.005, reg_all=0.02)
    print("训练模型...")
    model.fit(trainset)
    
    # 加载测试文件
    print("加载测试数据...")
    test_user_items = []
    
    with open(test_file, 'r') as f:
        lines = f.readlines()
        
    i = 0
    while i < len(lines):
        # 处理用户头部行
        if '|' in lines[i]:
            parts = lines[i].strip().split('|')
            user_id = int(parts[0])
            item_count = int(parts[1])
            
            # 处理该用户的项目
            for j in range(1, item_count + 1):
                if i + j < len(lines):
                    item_id = int(lines[i + j].strip())
                    test_user_items.append((user_id, item_id))
            
            # 跳到下一个用户
            i += item_count + 1
        else:
            i += 1
    
    # 生成预测
    print("生成预测...")
    predictions = []
    
    for user_id, item_id in test_user_items:
        # 使用模型预测评分
        pred = model.predict(uid=user_id, iid=item_id)
        predicted_rating = int(round(pred.est))  # 四舍五入到整数
        
        # 确保评分在范围内
        predicted_rating = max(min(predicted_rating, int(train_df['rating'].max())), int(train_df['rating'].min()))
        
        predictions.append((user_id, item_id, predicted_rating))
    
    # 将预测结果保存到文件
    print(f"将预测结果保存到 {output_file}...")
    with open(output_file, 'w') as f:
        current_user = None
        user_items = []
        
        for user_id, item_id, rating in predictions:
            if current_user != user_id:
                if current_user is not None:
                    f.write(f"{current_user}|{len(user_items)}\n")
                    for item, r in user_items:
                        f.write(f"{item} {r}\n")
                
                current_user = user_id
                user_items = [(item_id, rating)]
            else:
                user_items.append((item_id, rating))
        
        # 写入最后一个用户
        if current_user is not None:
            f.write(f"{current_user}|{len(user_items)}\n")
            for item, r in user_items:
                f.write(f"{item} {r}\n")
    
    print("预测完成！")

if __name__ == "__main__":
    # 比较所有模型性能
    print("===== 推荐系统模型性能评估 =====")
    results = compare_all_models("data/train.txt", test_size=0.2, random_state=42)
    
    # 可选：生成预测结果
    # 如果存在测试文件，可以取消下面的注释来生成预测
    # predict_for_test_file("data/train.txt", "data/test.txt", "data/predictions.txt")
'''
===== 推荐系统模型性能评估 =====
加载数据...
加载了 90854 条评分记录
准备数据...
分割数据，测试集比例: 0.2

开始评估模型:

评估 SVD (矩阵分解)...
RMSE: 18.1765
MSE: 330.3852

SVD (矩阵分解):
均方误差 (MSE): 330.3852
均方根误差 (RMSE): 18.1765
训练时间: 0.73秒
预测时间: 0.12秒

评估 SVD++ (增强矩阵分解)...
RMSE: 21.6765
MSE: 469.8692

SVD++ (增强矩阵分解):
均方误差 (MSE): 469.8692
均方根误差 (RMSE): 21.6765
训练时间: 37.57秒
预测时间: 6.37秒

评估 NMF (非负矩阵分解)...
RMSE: 62.4329
MSE: 3897.8638

NMF (非负矩阵分解):
均方误差 (MSE): 3897.8638
均方根误差 (RMSE): 62.4329
训练时间: 1.61秒
预测时间: 0.07秒

评估 KNN Basic (基础协同过滤)...
Computing the msd similarity matrix...
Done computing similarity matrix.
RMSE: 19.7223
MSE: 388.9690

KNN Basic (基础协同过滤):
均方误差 (MSE): 388.9690
均方根误差 (RMSE): 19.7223
训练时间: 0.11秒
预测时间: 0.64秒

评估 KNN with Means (均值修正的协同过滤)...
Computing the msd similarity matrix...
Done computing similarity matrix.
RMSE: 18.6910
MSE: 349.3535

KNN with Means (均值修正的协同过滤):
均方误差 (MSE): 349.3535
均方根误差 (RMSE): 18.6910
训练时间: 0.08秒
预测时间: 0.65秒

评估 Baseline (基线预测)...
Estimating biases using als...
RMSE: 17.4380
MSE: 304.0848

Baseline (基线预测):
均方误差 (MSE): 304.0848
均方根误差 (RMSE): 17.4380
训练时间: 0.18秒
预测时间: 0.08秒

评估 Slope One...
RMSE: 17.9268
MSE: 321.3686

Slope One:
均方误差 (MSE): 321.3686
均方根误差 (RMSE): 17.9268
训练时间: 2.55秒
预测时间: 3.75秒

模型性能对比（按MSE排序）:
                        Model          MSE       RMSE  Training Time  Prediction Time
5             Baseline (基线预测)   304.084797  17.438027       0.180731         0.082614
6                   Slope One   321.368559  17.926755       2.549058         3.752839
0                  SVD (矩阵分解)   330.385245  18.176503       0.734646         0.115601
4  KNN with Means (均值修正的协同过滤)   349.353483  18.691000       0.084882         0.651987
3          KNN Basic (基础协同过滤)   388.968951  19.722296       0.109915         0.643428
1              SVD++ (增强矩阵分解)   469.869230  21.676467      37.574519         6.374574
2                NMF (非负矩阵分解)  3897.863846  62.432875       1.611001         0.067965

最佳模型是: Baseline (基线预测)
'''