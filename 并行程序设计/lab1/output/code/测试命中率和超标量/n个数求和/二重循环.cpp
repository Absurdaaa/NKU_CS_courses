#include <iostream>
#include <time.h>
using namespace std;
#define MAX_N 5000
int main()
{
  int sum=0;
  int a[MAX_N];
  int n = MAX_N;

  for (int m = n; m > 1; m = (m + 1) / 2)
  { // 向上取整
    for (int i = 0; i < m / 2; i++)
    {
      a[i] += a[m - i - 1]; // 前半部分 += 后半部分
    }
  }
  sum = a[0];
  return 0;
}

/*

  Performance counter stats for './a':

         1,327,899      l1d_cache
            24,451      l1d_cache_refill
           158,054      l2d_cache
            20,122      l2d_cache_refill
         2,935,584      cycles
         3,491,168      instructions                     #    1.19  insn per cycle

       0.001577426 seconds time elapsed

       0.001657000 seconds user
       0.000000000 seconds sys


*/