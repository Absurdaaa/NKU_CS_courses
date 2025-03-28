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
    for (int j = 0; j < n; j++)
    {
      sum[i] += b[i][j] * a[i];
    }
  }

  // cout<<sum<<endl;
  delete[] b;
  return 0;
}
/*

 Performance counter stats for './a':

     2,514,409,877      l1d_cache
         5,018,967      l1d_cache_refill
        35,162,605      l2d_cache
         1,739,977      l2d_cache_refill
     1,666,655,714      cycles
     5,447,596,673      instructions                     #    3.27  insn per cycle

       0.612140395 seconds time elapsed

       0.485939000 seconds user
       0.104129000 seconds sys




*/