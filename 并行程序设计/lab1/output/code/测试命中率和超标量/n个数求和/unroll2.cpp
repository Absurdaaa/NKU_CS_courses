#include <iostream>
#include <time.h>
using namespace std;
#define MAX_N 5000
int main()
{
  int sum;
  int a[MAX_N];

  // 初始化,1000起步
  for (int i = 0; i < MAX_N; i++)
  {
    a[i] = i;
  }
  int n = MAX_N;
  sum = 0;
  int sum1 = 0, sum2 = 0;
  int i = 0;
  for (i = 0; i < n - 1; i += 2)
  {
    sum1 = sum1 + a[i];
    sum2 = sum2 + a[i + 1];
  }
  if (i == n - 3)
  {
    sum = sum + a[n - 1];
  }
  sum = sum1 + sum2;
  return 0;
}

/*

 Performance counter stats for './a':

         1,324,748      l1d_cache
            24,710      l1d_cache_refill
           164,953      l2d_cache
            22,222      l2d_cache_refill
         2,996,362      cycles
         3,473,826      instructions                     #    1.16  insn per cycle

       0.001723482 seconds time elapsed

       0.001712000 seconds user
       0.000000000 seconds sys
*/