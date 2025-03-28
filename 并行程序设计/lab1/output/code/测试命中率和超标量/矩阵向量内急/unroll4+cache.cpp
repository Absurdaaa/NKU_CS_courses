#include <iostream>
#include <time.h>
using namespace std;
#define MAX_N 10000

int main()
{
  int sum[MAX_N];
  // 矩阵b
  int(*b)[MAX_N] = new int[MAX_N][MAX_N];
  // 记得最后要 delete[] b;
  // 向量a
  int a[MAX_N];

  for (int i = 0; i < MAX_N; i++)
  {
    for (int j = 0; j < MAX_N; j++)
      b[i][j] = i * MAX_N + j;
    a[i] = i;
  }

  int n = MAX_N;
  // 清空 sum 数组
  for (int i = 0; i < n; i++)
    sum[i] = 0;

  for (int i = 0; i < n; i++)
  {
    // sum[i] = 0.0;
    int j = 0;
    for (j = 0; j < n - 3; j += 4)
    {
      sum[j] += b[i][j] * a[i];
      sum[j + 1] += b[i][j + 1] * a[i];
      sum[j + 2] += b[i][j + 2] * a[i];
      sum[j + 3] += b[i][j + 3] * a[i];
    }
    if (j == n - 5)
      sum[n - 1] += b[i][n - 1] * a[i];
    else if (j == n - 6)
    {
      sum[n - 2] += b[i][n - 2] * a[i];
      sum[n - 1] += b[i][n - 1] * a[i];
    }
    else if (j == n - 7)
    {
      sum[n - 3] += b[i][n - 3] * a[i];
      sum[n - 2] += b[i][n - 2] * a[i];
      sum[n - 1] += b[i][n - 1] * a[i];
    }
  }

  // cout<<sum<<endl;
  delete[] b;
  return 0;
}

/*
 Performance counter stats for './a':

     2,213,553,380      l1d_cache
         5,220,093      l1d_cache_refill
        44,556,512      l2d_cache
         1,713,303      l2d_cache_refill
     1,596,901,699      cycles
     5,395,924,842      instructions                     #    3.38  insn per cycle

       0.585350217 seconds time elapsed

       0.462404000 seconds user
       0.102327000 seconds sys

*/