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
    sum = 0;
    int n = MAX_N;
    // 一直循环运行，运行直到时间总达到 10ms，在求平均数，这样能稳定很多
    int sum1 = 0, sum2 = 0, sum3 = 0, sum4 = 0;
    int i = 0;
    for (i = 0; i < n - 3; i += 4)
    {
      sum1 = sum1 + a[i];
      sum2 = sum2 + a[i + 1];
      sum3 = sum3 + a[i + 2];
      sum4 = sum4 + a[i + 3];
    }
    if (i == n - 5)
      sum += a[n - 1];
    else if (i == n - 6)
      sum += a[n - 1] + a[n - 2];
    else if (i == n - 7)
      sum += a[n - 1] + a[n - 2] + a[n - 3];
    sum = sum1 + sum2 + sum3 + sum4;
  return 0;
}

/*
 Performance counter stats for './a':

         1,334,084      l1d_cache
            25,127      l1d_cache_refill
           166,812      l2d_cache
            20,485      l2d_cache_refill
         2,732,709      cycles
         3,474,360      instructions                     #    1.27  insn per cycle

       0.001468688 seconds time elapsed

       0.000770000 seconds user
       0.000770000 seconds sys

*/