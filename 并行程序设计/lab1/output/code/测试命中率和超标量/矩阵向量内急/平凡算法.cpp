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
          sum[j] += b[i][j] * a[j];
        }
      }
      
    // cout<<sum<<endl;
  delete[] b;
  return 0;
}

/*
 Performance counter stats for './a':

     2,510,352,249      l1d_cache
         5,159,026      l1d_cache_refill
        59,737,908      l2d_cache
         1,699,741      l2d_cache_refill
     1,714,686,566      cycles
     5,434,378,023      instructions                     #    3.17  insn per cycle

       0.609295817 seconds time elapsed

       0.493586000 seconds user
       0.101649000 seconds sys


   Performance counter stats for './a':

         1,551,191      l1d_cache
            29,728      l1d_cache_refill
           216,336      l2d_cache
            26,132      l2d_cache_refill
       204,077,833      cycles
       404,228,333      instructions                     #    1.98  insn per cycle

       0.068899580 seconds time elapsed

       0.068966000 seconds user
       0.000000000 seconds sys


 Performance counter stats for './a':

         1,246,806      l1d_cache
            24,580      l1d_cache_refill
           161,288      l2d_cache
            21,887      l2d_cache_refill
         2,911,147      cycles
         3,315,403      instructions                     #    1.14  insn per cycle

       0.001722523 seconds time elapsed

       0.000868000 seconds user
       0.000868000 seconds sys

 Performance counter stats for './a':

         1,251,928      l1d_cache
            24,303      l1d_cache_refill
           161,786      l2d_cache
            20,025      l2d_cache_refill
         2,754,737      cycles
         3,324,533      instructions                     #    1.21  insn per cycle

       0.001523567 seconds time elapsed

       0.001578000 seconds user
       0.000000000 seconds sys

*/