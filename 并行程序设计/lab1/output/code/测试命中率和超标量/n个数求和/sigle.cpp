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
  for (int i = 0; i < n; i++)
  {
    sum = sum + a[i];
  }
  return 0;
}

/*

 Performance counter stats for './a':

         1,329,898      l1d_cache
            24,894      l1d_cache_refill
           162,030      l2d_cache
            21,687      l2d_cache_refill
         2,974,984      cycles
         3,480,060      instructions                     #    1.17  insn per cycle

       0.001753902 seconds time elapsed

       0.001743000 seconds user
       0.000000000 seconds sys


*/