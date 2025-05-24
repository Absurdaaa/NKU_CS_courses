#include <iostream>
#include <vector>
#include <random>
#include <cmath>
#include <algorithm>
#include <omp.h>
#include <mpi.h>

#include <chrono>
// #include "judge.h"
#include <iomanip>
// 编译执行方式参考：
// 编译， 也可以使用g++，但使用MPI时需使用mpic
// mpic++ -fopenmp -o outputfile sourcefile.cpp

// 运行 baseline
// ./outputfile baseline

// 运行 OpenMP
// ./outputfile openmp

// 运行 子块并行优化
// ./outputfile block

// 运行 MPI（假设 4 个进程）
// mpirun -np 4 ./outputfile mpi

// 运行 MPI（假设 4 个进程）
// ./outputfile other

// 初始化矩阵（以一维数组形式表示），用于随机填充浮点数
void init_matrix(std::vector<double> &mat, int rows, int cols);

// 验证计算优化后的矩阵计算和baseline实现是否结果一致，可以设计其他验证方法，来验证计算的正确性和性能
bool validate(const std::vector<double> &A, const std::vector<double> &B, int rows, int cols, double tol = 1e-6);

// 基础的矩阵乘法baseline实现（使用一维数组）
void matmul_baseline(const std::vector<double> &A,
                     const std::vector<double> &B,
                     std::vector<double> &C, int N, int M, int P);

// 方式1: 利用OpenMP进行多线程并发的编程 （主要修改函数）
void matmul_openmp(const std::vector<double> &A,
                   const std::vector<double> &B,
                   std::vector<double> &C, int N, int M, int P);

// 方式2: 利用子块并行思想，进行缓存友好型的并行优化方法 （主要修改函数)
void matmul_block_tiling(const std::vector<double> &A,
                         const std::vector<double> &B,
                         std::vector<double> &C, int N, int M, int P, int block_size = 64);

// 方式3: 利用MPI消息传递，实现多进程并行优化 （主要修改函数）
void matmul_mpi(int N, int M, int P);

// 方式4: 其他方式 （主要修改函数）
void matmul_other(const std::vector<double> &A,
                  const std::vector<double> &B,
                  std::vector<double> &C, int N, int M, int P);

int main(int argc, char **argv)
{
  const int N = 1024, M = 2048, P = 512;
  std::string mode = argc >= 2 ? argv[1] : "baseline";
  
  // if(argc >= 5)//添加矩阵规模输入
  // {
  //   try
  //   {
  //     N = std::stoi(argv[2]);
  //     M = std::stoi(argv[3]);
  //     P = std::stoi(argv[4]);
  //   }
  //   catch (const std::exception &e)
  //   {
  //     std::cerr << "Invalid matrix size arguments. Using default sizes." << std::endl;
  //   }
  // }

  std::cout << "Matrix size: " << N << "x" << M << "x" << P << std::endl;

  if (mode == "mpi")
  {
    MPI_Init(&argc, &argv);
    matmul_mpi(N, M, P);
    MPI_Finalize();
    return 0;
  }

  std::vector<double> A(N * M);
  std::vector<double> B(M * P);
  std::vector<double> C(N * P, 0);
  std::vector<double> C_ref(N * P, 0); // 参考答案

  init_matrix(A, N, M);
  init_matrix(B, M, P);
  matmul_baseline(A, B, C_ref, N, M, P);

  if (mode == "baseline")
  {
    auto start = std::chrono::high_resolution_clock::now();

    matmul_baseline(A, B, C, N, M, P);

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;

    std::cout << std::fixed << std::setprecision(9); // 设置9位小数
    std::cout << "[Baseline] Time: " << elapsed.count() << " seconds" << std::endl;
  }
  else if (mode == "openmp")
  {
    auto start = std::chrono::high_resolution_clock::now();

    matmul_openmp(A, B, C, N, M, P);

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;

    std::cout << std::fixed << std::setprecision(9); // 设置9位小数
    std::cout << "[OpenMP] Time: " << elapsed.count() << " seconds" << std::endl;
    std::cout << "[OpenMP] Valid: " << validate(C, C_ref, N, P) << std::endl;
  }
  else if (mode == "block")
  {
    auto start = std::chrono::high_resolution_clock::now();
    matmul_block_tiling(A, B, C, N, M, P);
    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;

    std::cout << std::fixed << std::setprecision(9); // 设置9位小数
    std::cout << "[Block Parallel] Time: " << elapsed.count() << " seconds" << std::endl;
    std::cout << "[Block Parallel] Valid: " << validate(C, C_ref, N, P) << std::endl;
  }
  else if (mode == "other")
  {
    matmul_other(A, B, C, N, M, P);
    std::cout << "[Other] Valid: " << validate(C, C_ref, N, P) << std::endl;
  }
  else
  {
    std::cerr << "Usage: ./main [baseline|openmp|block|mpi]" << std::endl;
  }
  // 需额外增加性能评测代码或其他工具进行评测
  return 0;
}

void init_matrix(std::vector<double> &mat, int rows, int cols)
{
  std::mt19937 gen(42);
  // 生成-100.0到100.0之间的随机浮点数
  std::uniform_real_distribution<double> dist(-100.0, 100.0);
  for (int i = 0; i < rows * cols; ++i)
    mat[i] = dist(gen);
}

bool validate(const std::vector<double> &A, const std::vector<double> &B, int rows, int cols, double tol)
{
  for (int i = 0; i < rows * cols; ++i)
    if (std::abs(A[i] - B[i]) > tol)
      return false;
  return true;
}

void matmul_baseline(const std::vector<double> &A,
                     const std::vector<double> &B,
                     std::vector<double> &C, int N, int M, int P)
{
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < P; ++j)
    {
      C[i * P + j] = 0;
      for (int k = 0; k < M; ++k)
        C[i * P + j] += A[i * M + k] * B[k * P + j];
    }
}

void matmul_openmp(const std::vector<double> &A,
                   const std::vector<double> &B,
                   std::vector<double> &C, int N, int M, int P)
{
  std::cout << "matmul_openmp methods..." << std::endl;
  // 使用OpenMP并行化外层循环
#pragma omp parallel for
  for (int i = 0; i < N; ++i)
  {
    for (int j = 0; j < P; ++j)
    {
      double sum = 0.0;
      for (int k = 0; k < M; ++k)
      {
        sum += A[i * M + k] * B[k * P + j];
      }
      C[i * P + j] = sum;
    }
  }
}

void matmul_block_tiling(const std::vector<double> &A,
                         const std::vector<double> &B,
                         std::vector<double> &C, int N, int M, int P, int block_size)
{
  std::cout << "matmul_block_tiling methods..." << std::endl;
  // 块划分的朴素实现，三重循环外层采用块的遍历
  // 可以进一步并行化：如 #pragma omp parallel for collapse(2)
  for (int ii = 0; ii < N; ii += block_size)
  {
    for (int jj = 0; jj < P; jj += block_size)
    {
      for (int kk = 0; kk < M; kk += block_size)
      {
        // 遍历当前块
        for (int i = ii; i < std::min(ii + block_size, N); ++i)
        {
          for (int j = jj; j < std::min(jj + block_size, P); ++j)
          {
            double sum = 0.0;
            for (int k = kk; k < std::min(kk + block_size, M); ++k)
            {
              sum += A[i * M + k] * B[k * P + j];
            }
            // 注意此处要+=，因为C[i*P+j]可能被多个块累加
            C[i * P + j] += sum;
          }
        }
      }
    }
  }
}

// 方式3: 利用MPI消息传递，实现多进程并行优化 （主要修改函数）
void matmul_mpi(int N, int M, int P)
{
  // 获取当前进程编号(rank)和总进程数(size)
  int rank, size;
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  MPI_Comm_size(MPI_COMM_WORLD, &size);

  // 计算每个进程分配的行数，处理不能整除的情况
  int rows_per_proc = N / size;
  int remainder = N % size;
  // 计算当前进程负责的起始行号
  int start_row = rank * rows_per_proc + std::min(rank, remainder);
  // 计算当前进程实际负责的行数（前remainder个进程多分一行）
  int local_rows = rows_per_proc + (rank < remainder ? 1 : 0);

  // 分配本地A子块、B全体、C子块
  std::vector<double> local_A(local_rows * M);    // 当前进程负责的A子块
  std::vector<double> B(M * P);                   // 所有进程都需要B的全部数据
  std::vector<double> local_C(local_rows * P, 0); // 当前进程计算的C子块

  // 仅主进程(rank==0)需要完整的A、C_ref、C
  std::vector<double> A, C_ref, C;
  if (rank == 0)
  {
    A.resize(N * M);
    C_ref.resize(N * P);
    C.resize(N * P);

    // 主进程初始化A和B
    std::mt19937 gen(42);
    std::uniform_real_distribution<double> dist(-100.0, 100.0);
    for (int i = 0; i < N * M; ++i)
      A[i] = dist(gen);
    for (int i = 0; i < M * P; ++i)
      B[i] = dist(gen);

    // 主进程计算参考结果C_ref（用于正确性验证）
    matmul_baseline(A, B, C_ref, N, M, P);

    // 主进程分发A的子块到各进程
    for (int p = 0; p < size; ++p)
    {
      int s_row = p * rows_per_proc + std::min(p, remainder); // 子块起始行
      int l_rows = rows_per_proc + (p < remainder ? 1 : 0);   // 子块行数
      if (p == 0)
        // 主进程自己直接拷贝
        std::copy(A.begin(), A.begin() + l_rows * M, local_A.begin());
      else
        // 发送A的子块给其他进程
        MPI_Send(A.data() + s_row * M, l_rows * M, MPI_DOUBLE, p, 0, MPI_COMM_WORLD);
    }
  }
  else
  {
    // 其他进程接收A的子块
    MPI_Recv(local_A.data(), local_rows * M, MPI_DOUBLE, 0, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
  }

  // 所有进程广播B矩阵
  MPI_Bcast(B.data(), M * P, MPI_DOUBLE, 0, MPI_COMM_WORLD);

  // 所有进程同步，准备计时
  MPI_Barrier(MPI_COMM_WORLD);
  auto start = std::chrono::high_resolution_clock::now();

  // 各进程本地计算自己的C子块
  for (int i = 0; i < local_rows; ++i)
    for (int j = 0; j < P; ++j)
    {
      double sum = 0.0;
      for (int k = 0; k < M; ++k)
        sum += local_A[i * M + k] * B[k * P + j];
      local_C[i * P + j] = sum;
    }

  // 再次同步，计时结束
  MPI_Barrier(MPI_COMM_WORLD);
  auto end = std::chrono::high_resolution_clock::now();
  std::chrono::duration<double> elapsed = end - start;

  // 主进程收集所有进程的C子块
  if (rank == 0)
  {
    // 计算每个进程的接收数量和偏移量
    std::vector<int> recvcounts(size), displs(size);
    for (int p = 0; p < size; ++p)
    {
      int l_rows = rows_per_proc + (p < remainder ? 1 : 0);
      recvcounts[p] = l_rows * P;                                   // 每个进程C子块元素数
      displs[p] = (p * rows_per_proc + std::min(p, remainder)) * P; // 偏移
    }
    // 收集所有进程的C子块到主进程C
    MPI_Gatherv(local_C.data(), local_rows * P, MPI_DOUBLE, C.data(), recvcounts.data(), displs.data(), MPI_DOUBLE, 0, MPI_COMM_WORLD);

    // 输出性能和正确性
    std::cout << std::fixed << std::setprecision(9);
    std::cout << "[MPI] Time: " << elapsed.count() << " seconds" << std::endl;
    std::cout << "[MPI] Valid: " << validate(C, C_ref, N, P) << std::endl;
  }
  else
  {
    // 其他进程发送自己的C子块到主进程
    MPI_Gatherv(local_C.data(), local_rows * P, MPI_DOUBLE, nullptr, nullptr, nullptr, MPI_DOUBLE, 0, MPI_COMM_WORLD);
  }
}

void matmul_other(const std::vector<double> &A,
                  const std::vector<double> &B,
                  std::vector<double> &C, int N, int M, int P)
{
  std::cout << "Other methods..." << std::endl;
}