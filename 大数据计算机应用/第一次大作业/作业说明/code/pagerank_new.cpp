#include <iostream>
#include <fstream>
#include <vector>
#include <unordered_map>
#include <string>
#include <algorithm>
#include <cmath>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <tuple>

// 自定义稀疏矩阵类（CSR格式 - 压缩稀疏行）
class SparseMatrix
{
private:
  std::vector<float> values;    // 非零元素值
  std::vector<int> col_indices; // 非零元素的列索引
  std::vector<int> row_ptr;     // 每行起始位置的指针
  int rows;
  int cols;

public:
  SparseMatrix() : rows(0), cols(0)
  {
    row_ptr.push_back(0); // 初始化第一个行指针
  }

  SparseMatrix(int r, int c) : rows(r), cols(c)
  {
    row_ptr.resize(r + 1, 0);
  }

  void resize(int r, int c)
  {
    rows = r;
    cols = c;
    values.clear();
    col_indices.clear();
    row_ptr.clear();
    row_ptr.resize(r + 1, 0);
  }

  // 从三元组(row, col, value)列表构建CSR格式矩阵
  void setFromTriplets(const std::vector<std::tuple<int, int, float>> &triplets)
  {
    // 预先排序三元组 - 按行优先，然后按列
    std::vector<std::tuple<int, int, float>> sorted_triplets = triplets;
    std::sort(sorted_triplets.begin(), sorted_triplets.end(),
              [](const auto &a, const auto &b)
              {
                if (std::get<0>(a) != std::get<0>(b))
                  return std::get<0>(a) < std::get<0>(b);
                return std::get<1>(a) < std::get<1>(b);
              });

    // 计算每行的非零元素数量
    std::vector<int> row_counts(rows, 0);
    for (const auto &trip : sorted_triplets)
    {
      row_counts[std::get<0>(trip)]++;
    }

    // 计算行指针
    row_ptr[0] = 0;
    for (int i = 0; i < rows; i++)
    {
      row_ptr[i + 1] = row_ptr[i] + row_counts[i];
    }

    // 分配内存
    int nnz = sorted_triplets.size();
    values.resize(nnz);
    col_indices.resize(nnz);

    // 填充值和列索引
    for (const auto &trip : sorted_triplets)
    {
      int row = std::get<0>(trip);
      int col = std::get<1>(trip);
      float val = std::get<2>(trip);

      int pos = row_ptr[row]++;
      values[pos] = val;
      col_indices[pos] = col;
    }

    // 修复行指针 (因为我们在上面的循环中修改了它们)
    for (int i = rows; i > 0; i--)
    {
      row_ptr[i] = row_ptr[i - 1];
    }
    row_ptr[0] = 0;
  }

  // 矩阵-向量乘法
  std::vector<float> multiply(const std::vector<float> &vec) const
  {
    if (vec.size() != cols)
    {
      throw std::runtime_error("矩阵与向量维度不匹配");
    }

    std::vector<float> result(rows, 0.0f);

    for (int i = 0; i < rows; i++)
    {
      for (int j = row_ptr[i]; j < row_ptr[i + 1]; j++)
      {
        result[i] += values[j] * vec[col_indices[j]];
      }
    }

    return result;
  }

  // 获取矩阵维度
  int getRows() const { return rows; }
  int getCols() const { return cols; }

  // 获取非零元素数量
  int nonZeros() const { return values.size(); }
};

// 向量操作
namespace VectorOps
{
  // 向量加法
  std::vector<float> add(const std::vector<float> &a, const std::vector<float> &b)
  {
    if (a.size() != b.size())
    {
      throw std::runtime_error("向量维度不匹配");
    }

    std::vector<float> result(a.size());
    for (size_t i = 0; i < a.size(); i++)
    {
      result[i] = a[i] + b[i];
    }
    return result;
  }

  // 向量减法
  std::vector<float> subtract(const std::vector<float> &a, const std::vector<float> &b)
  {
    if (a.size() != b.size())
    {
      throw std::runtime_error("向量维度不匹配");
    }

    std::vector<float> result(a.size());
    for (size_t i = 0; i < a.size(); i++)
    {
      result[i] = a[i] - b[i];
    }
    return result;
  }

  // 向量标量乘法
  std::vector<float> multiply(const std::vector<float> &vec, float scalar)
  {
    std::vector<float> result(vec.size());
    for (size_t i = 0; i < vec.size(); i++)
    {
      result[i] = vec[i] * scalar;
    }
    return result;
  }

  // 向量点积
  float dot(const std::vector<float> &a, const std::vector<float> &b)
  {
    if (a.size() != b.size())
    {
      throw std::runtime_error("向量维度不匹配");
    }

    float result = 0.0f;
    for (size_t i = 0; i < a.size(); i++)
    {
      result += a[i] * b[i];
    }
    return result;
  }

  // 向量L1范数
  float l1Norm(const std::vector<float> &vec)
  {
    float sum = 0.0f;
    for (float v : vec)
    {
      sum += std::fabs(v);
    }
    return sum;
  }

  // 向量求和
  float sum(const std::vector<float> &vec)
  {
    float total = 0.0f;
    for (float v : vec)
    {
      total += v;
    }
    return total;
  }

  // 创建常量向量
  std::vector<float> constant(size_t size, float value)
  {
    return std::vector<float>(size, value);
  }
}

//建立节点索引，并且估计边数,统计初度
void build_node(const std::string &file_path,
               std::vector<std::string> &nodes,
               std::unordered_map<std::string, int> &node_index,
                   std::vector<int> &out_degrees){
  std::ifstream file(file_path);
  if (!file.is_open())
  {
    std::cerr << "无法打开文件: " << file_path << std::endl;
    return;
  }
  std::string line, u, v;
  std::unordered_map<std::string, bool> node_set;
  size_t line_count = 0;
  std::string line0;
  // 获取文件大小以估计行数
  file.seekg(0, std::ios::end);
  size_t file_size = file.tellg();
  file.seekg(0, std::ios::beg);
  while (std::getline(file, line0))
  {
    line_count++;
  }
  // 重置文件指针到开头
  file.clear();
  file.seekg(0, std::ios::beg);
  // 读取边并收集唯一节点
  while (std::getline(file, line))
  {
    std::istringstream iss(line);
    if (!(iss >> u >> v))
    {
      std::cerr << "Invalid line format: " << line << std::endl;
      continue;
    }
    node_set[u] = true;
    node_set[v] = true;
  }
  // 将节点集合转换为排序列表
  for (const auto &pair : node_set){
    nodes.push_back(pair.first);
  }
  // 排序节点以确保确定性结果
  std::sort(nodes.begin(), nodes.end());
  // 建立节点索引映射
  for (int i = 0; i < nodes.size(); i++){
    node_index[nodes[i]] = i;
  }
  
  //统计初度
  file.clear();
  file.seekg(0, std::ios::beg);
  // 建立out_degrees初度
  out_degrees.resize(nodes.size(), 0);
  while (std::getline(file, line))
  {
    std::istringstream iss(line);
    if (!(iss >> u >> v))
    {
      std::cerr << "Invalid line format: " << line << std::endl;
      continue;
    }
    int u_id = node_index.at(u);
    out_degrees[u_id]++;
  }
}

//读取数据，并且只储存固定idx的边
void build_graph_part(const std::string &file_path,
                      std::vector<std::string> &nodes,
                      std::unordered_map<std::string, int> &node_index,
                      std::vector<int> &out_degrees,
                      std::vector<std::tuple<int, int, float>> &triplets,
                      SparseMatrix &M,
                      int idx_start,
                      int idx_end)
{
  std::ifstream file(file_path);
  if (!file.is_open())
  {
    std::cerr << "无法打开文件: " << file_path << std::endl;
    return;
  }
  std::string line, u, v;
  // 先统计边数
  int line_count = 0;
  while (std::getline(file, line))
  {
    std::istringstream iss(line);
    if (!(iss >> u >> v))
    {
      std::cerr << "Invalid line format: " << line << std::endl;
      continue;
    }
    int v_id = node_index.at(v);
    if (v_id > idx_end || v_id < idx_start) // 如果不在氛围内
    {
      continue;
    }
    line_count++;
  }

  file.clear();
  file.seekg(0, std::ios::beg);
  triplets.reserve(line_count);
  while (std::getline(file, line))
  {
    std::istringstream iss(line);
    if (!(iss >> u >> v))
    {
      std::cerr << "Invalid line format: " << line << std::endl;
      continue;
    }
    
    int v_id = node_index.at(v);
    if (v_id > idx_end || v_id < idx_start) // 如果不在氛围内
    {
      continue;
    }
    int u_id = node_index.at(u);

    if (out_degrees[u_id] > 0)
    {
      // 注意：矩阵已转置 - j 行 i 列,u->v
      triplets.push_back(std::make_tuple(v_id - idx_start, u_id, 1.0f / out_degrees[u_id]));
    }
  }
  // 构建稀疏矩阵
  int N = nodes.size();
  M.resize(idx_end-idx_start+1, N);
  M.setFromTriplets(triplets);
}

//构建死节点向量
void build_death(
    const std::vector<std::string> &nodes,
    const std::unordered_map<std::string, int> &node_index,
    std::vector<float> &death,
    std::vector<int> &out_degrees){
  int N = nodes.size();
  death.resize(N, 0.0f);
  for (int i = 0; i < N; i++)
  {
    if (out_degrees[i] == 0)
    {
      death[i] = 1.0f;
    }
  }
}

// PageRank算法实现
std::vector<float> pagerank(const std::string &file_path,
                            int parts_num,
                            std::vector<float> &death,
                            std::vector<std::string> &nodes,
                            std::vector<int> &out_degrees,
                                std::unordered_map<std::string, int> &node_index,
                            float damping = 0.85f, float tol = 1e-6f, int max_iter = 10000)
{
  int N = nodes.size();
  // 初始化概率向量
  std::vector<float> pr = VectorOps::constant(N, 1.0f / N);
  std::vector<float> teleport = VectorOps::constant(N, 1.0f / N);
  std::vector<float> pr_new = VectorOps::constant(N, 0);
  std::cout<<1<<std::endl;

  for (int iter_count = 0; iter_count < max_iter; iter_count++)
  {
    pr_new = VectorOps::constant(N, 0);
    for(int part =0;part<parts_num;part++){
      int idx_start = part * N / parts_num;
      int idx_end = (part + 1) * N / parts_num - 1;
      SparseMatrix M_part;
      std::vector<std::tuple<int, int, float>> triplets;
      triplets.clear();
      build_graph_part(file_path, nodes, node_index, out_degrees, triplets, M_part, idx_start, idx_end);
      std::vector<float> pr_new_part;
      pr_new_part.resize(idx_end-idx_start+1,0);
      pr_new_part = VectorOps::multiply(M_part.multiply(pr), damping);
      //逐元素加到pr_new
      for(int i = 0; i < pr_new_part.size(); i++){
        pr_new[i+idx_start] += pr_new_part[i];
      }
    }
    std::cout << iter_count << std::endl;
    // 添加死节点贡献: damping/N * (death·pr) * ones(N)
    float death_contribution = damping / N * VectorOps::dot(death, pr);
    std::vector<float> death_vector = VectorOps::constant(N, death_contribution);
    pr_new = VectorOps::add(pr_new, death_vector);

    // 添加随机跳转: (1-damping) * teleport
    std::vector<float> random_jump = VectorOps::multiply(teleport, 1.0f - damping);
    pr_new = VectorOps::add(pr_new, random_jump);

    // 计算收敛误差
    std::vector<float> diff = VectorOps::subtract(pr_new, pr);
    float err = VectorOps::l1Norm(diff);
    pr = pr_new;

    if (err < tol)
    {
      std::cout << "迭代第" << iter_count << "次之后，PageRank 收敛" << std::endl;
      return pr;
    }
  }

  std::cout << "警告：达到最大迭代次数" << max_iter << "，但未收敛" << std::endl;
  return pr;
}

int main()
{
  auto start_time = std::chrono::high_resolution_clock::now();

  std::string file_path = "Data.txt";
  std::vector<std::string> nodes;
  std::unordered_map<std::string, int> node_index;
  // 初度
  std::vector<int> out_degrees;

  // 构建图
  build_node(file_path, nodes, node_index, out_degrees);
  std::cout<<1<<std::endl;
  std::cout << "图中有 " << nodes.size()<<std::endl;

  std::vector<float> death;
  build_death(nodes, node_index,death, out_degrees);
  std::cout << "转移矩阵构建完成，非零元素: " <<std::endl;

  // 计算PageRank
  std::vector<float> pr_values = pagerank(file_path, 30, death, nodes,out_degrees, node_index);

  // 将节点与其PageRank值组合
  std::vector<std::pair<std::string, float>> node_pr;
  for (int i = 0; i < nodes.size(); i++)
  {
    node_pr.push_back({nodes[i], pr_values[i]});
  }

  // 按PageRank值降序排序
  std::sort(node_pr.begin(), node_pr.end(),
            [](const auto &a, const auto &b)
            { return a.second > b.second; });

  // // 输出前100个节点
  // for (int i = 0; i < std::min(100, (int)node_pr.size()); i++)
  // {
  //   std::cout << "节点 " << node_pr[i].first << " 的 PageRank 值为: "
  //             << std::fixed << std::setprecision(6) << node_pr[i].second << std::endl;
  // }

  // 计算PageRank值总和
  // float sum = VectorOps::sum(pr_values);
  // std::cout << "PageRank值总和: " << sum << std::endl;

  // 将Top-100节点写入文件
  std::ofstream outfile("Res12_new.txt");
  if (outfile.is_open())
  {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(8);
    for (const auto &p : node_pr)
    {
      oss << p.first << " " << p.second << "\n";
    }
    outfile << oss.str();
    outfile.close();

    // 释放内存
    std::vector<std::pair<std::string, float>>().swap(node_pr);
  }

  auto end_time = std::chrono::high_resolution_clock::now();
  auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
  std::cout << "运行时间: " << duration.count() / 1000.0 << " 秒" << std::endl;

  return 0;
}