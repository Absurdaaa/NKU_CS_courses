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

// 读取图数据并构建节点索引
void build_graph(const std::string &file_path,
                //  std::pair<std::string, std::string> edges[],
                //  int &edges_size,
                 std::vector<std::string> &nodes,
                 std::unordered_map<std::string, int> &node_index,
                 std::vector<int> &out_degrees,
                 std::vector<std::tuple<int, int, float>> &triplets)
{

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

  // edges = new std::pair<std::string, std::string>[line_count + 1];

  // 读取边并收集唯一节点
  while (std::getline(file, line))
  {
    std::istringstream iss(line);
    if (!(iss >> u >> v))
    {
      std::cerr << "Invalid line format: " << line << std::endl;
      continue;
    }

    // edges[edges_size] = {u, v};
    // edges_size++;

    node_set[u] = true;
    node_set[v] = true;
  }

  // 将节点集合转换为排序列表
  for (const auto &pair : node_set)
  {
    nodes.push_back(pair.first);
  }

  // 排序节点以确保确定性结果
  std::sort(nodes.begin(), nodes.end());

  // 建立节点索引映射
  for (int i = 0; i < nodes.size(); i++)
  {
    node_index[nodes[i]] = i;
  }

  // 重置文件指针到开头
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
  
  //重新读取一次文件，直接建立矩阵
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
    int u_id = node_index.at(u);
    int v_id = node_index.at(v);
    if(out_degrees[u_id] > 0)
    {
      // 注意：矩阵已转置 - j 行 i 列
      triplets.push_back(std::make_tuple(v_id, u_id, 1.0f / out_degrees[u_id]));
    }
    // triplets.push_back(std::make_tuple(u_id, v_id, 1.0f / out_degrees[u_id]));
  }
}

// 构建转移矩阵和死节点向量
void build_transition_matrix(
  // std::pair<std::string, std::string> edges[],
  //                            int &edges_size,
                             const std::vector<std::string> &nodes,
                             const std::unordered_map<std::string, int> &node_index,
                             SparseMatrix &M,
                             std::vector<float> &death,
                             std::vector<int> &out_degrees,
                             std::vector<std::tuple<int, int, float>> &triplets)
{

  int N = nodes.size();
  // std::vector<int> out_degrees(N, 0);
  

  // // 计算每个节点的出度
  // for (int i = 0; i < edges_size; i++)
  // {
  //   int j = node_index.at(edges[i].first);
  //   out_degrees[j]++;
  // }

  // 构建转移矩阵的三元组数据
  // for (const auto &edge : edges)
  // {
  //   int i = node_index.at(edge.first);
  //   int j = node_index.at(edge.second);

  //   if (out_degrees[i] > 0)
  //   {
  //     // 注意矩阵已转置 - j行i列
  //     triplets.push_back(std::make_tuple(j, i, 1.0f / out_degrees[i]));
  //   }
  // }
  // for (size_t i = 0; i < edges_size;)
  // {
  //   int i_idx = node_index.at(edges[i].first);
  //   int j_idx = node_index.at(edges[i].second);

  //   if (out_degrees[i_idx] > 0)
  //   {
  //     // 注意：矩阵已转置 - j 行 i 列
  //     triplets.push_back(std::make_tuple(j_idx, i_idx, 1.0f / out_degrees[i_idx]));
  //     // 用最后一个元素替换当前元素，然后删除末尾元素
  //     edges[i] = edges[edges_size];
  //     // delete edges[edges_size];
  //     edges_size--;
  //     // 不增加 i，因为替换后的新元素需要检查
  //   }
  //   else
  //   {
  //     ++i;
  //   }
  // }

  // 初始化死节点向量
  death.resize(N, 0.0f);
  for (int i = 0; i < N; i++)
  {
    if (out_degrees[i] == 0)
    {
      death[i] = 1.0f;
    }
  }

  // 构建稀疏矩阵
  M.resize(N, N);
  M.setFromTriplets(triplets);
}

// PageRank算法实现
std::vector<float> pagerank(const SparseMatrix &M, const std::vector<float> &death,
                            float damping = 0.85f, float tol = 1e-6f, int max_iter = 10000)
{

  int N = M.getRows();

  // 初始化概率向量
  std::vector<float> pr = VectorOps::constant(N, 1.0f / N);
  std::vector<float> teleport = VectorOps::constant(N, 1.0f / N);

  for (int iter_count = 0; iter_count < max_iter; iter_count++)
  {
    // 计算新的PageRank值: damping * (M * pr)
    std::vector<float> pr_new = VectorOps::multiply(M.multiply(pr), damping);

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
  std::string file_path = "Data.txt";
  std::vector<std::string> nodes;
  std::unordered_map<std::string, int> node_index;
  //初度
  std::vector<int> out_degrees;
  //稀疏矩阵的三元组数据
  std::vector<std::tuple<int, int, float>> triplets;

  // 构建图
  build_graph(file_path,nodes, node_index, out_degrees ,triplets);
  // std::cout << "图中有 " << nodes.size() << " 个节点和 " << triplets.size() << " 条边" << std::endl;

  // 构建转移矩阵
  SparseMatrix M;
  std::vector<float> death;
  build_transition_matrix(nodes, node_index, M, death, out_degrees, triplets);
  // std::cout << "转移矩阵构建完成，非零元素: " << M.nonZeros() << std::endl;

  // 释放不再需要的内存
  // edges.clear();
  // edges.shrink_to_fit();
  // delete[] edges;

  // 计算PageRank
  std::vector<float> pr_values = pagerank(M, death);

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

  // 输出前100个节点
  // for (int i = 0; i < std::min(100, (int)node_pr.size()); i++)
  // {
  //   std::cout << "节点 " << node_pr[i].first << " 的 PageRank 值为: "
  //             << std::fixed << std::setprecision(6) << node_pr[i].second << std::endl;
  // }

  // 计算PageRank值总和
  // float sum = VectorOps::sum(pr_values);
  // std::cout << "PageRank值总和: " << sum << std::endl;

  // 将Top-100节点写入文件
  std::ofstream outfile("Res_end.txt");
  // if (outfile.is_open())
  // {
  //   for (int i = 0; i < (int)node_pr.size(); i++)
  //   {
  //     outfile << node_pr[i].first << " " << std::fixed << std::setprecision(6)
  //             << node_pr[i].second << std::endl;
  //   }
  //   outfile.close();
  // }
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

  // auto end_time = std::chrono::high_resolution_clock::now();
  // auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
  // std::cout << "运行时间: " << duration.count() / 1000.0 << " 秒" << std::endl;

  return 0;
}