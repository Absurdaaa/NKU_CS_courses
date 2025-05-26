#include <iostream>
#include <cmath>
#include <vector>

using namespace std;

// 均方误差
double RMSE(const vector<double> &A, const vector<double> &B, int rows, int cols)
{
  double sum = 0.0;
  for (int i = 0; i < rows * cols; ++i)
    sum += (A[i] - B[i]) * (A[i] - B[i]);
  return sqrt(sum / (rows * cols));
}

// 最大绝对误差(Maximum Absolute Error)
double MAE(const vector<double> &A, const vector<double> &B, int rows, int cols)
{
  double max_error = 0.0;
  for (int i = 0; i < rows * cols; ++i)
  {
    double error = std::abs(A[i] - B[i]);
    if (error > max_error)
    {
      max_error = error;
    }
  }
  return max_error;
}

// 平均绝对误差(Mean Absolute Error)
double meanAbsoluteError(const vector<double> &A, const vector<double> &B, int rows, int cols)
{
  double sum = 0.0;
  for (int i = 0; i < rows * cols; ++i)
  {
    sum += std::abs(A[i] - B[i]);
  }
  return sum / (rows * cols);
}

// 相对误差(Relative Error) - Frobenius范数形式
double relativeError(const vector<double> &A, const vector<double> &B, int rows, int cols)
{
  double error_sum = 0.0;
  double norm_sum = 0.0;

  for (int i = 0; i < rows * cols; ++i)
  {
    error_sum += (A[i] - B[i]) * (A[i] - B[i]);
    norm_sum += A[i] * A[i];
  }

  return sqrt(error_sum / norm_sum);
}
