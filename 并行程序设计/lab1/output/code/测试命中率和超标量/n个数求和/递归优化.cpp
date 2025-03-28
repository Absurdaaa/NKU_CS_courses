#include <iostream>
#include <time.h>
using namespace std;
#define MAX_N 5000

void recursion(int n, int a[])
{
  if (n <= 1)
  {
    return;
  }
  else
  {
    for (int i = 0; i < n / 2; i++)
      a[i] += a[n - i - 1];
    n = n / 2;
    recursion(n, a);
  }
}

int main()
{
  int sum = 0;
  int a[MAX_N];
  int n = MAX_N;

  recursion(n, a);
  sum = a[0];
  return 0;
}

/*

 Performance counter stats for './a':

         1,337,590      l1d_cache
            24,564      l1d_cache_refill
           159,577      l2d_cache
            19,875      l2d_cache_refill
         3,138,417      cycles
         3,503,516      instructions                     #    1.12  insn per cycle

       0.001727162 seconds time elapsed

       0.000000000 seconds user
       0.001835000 seconds sys

*/