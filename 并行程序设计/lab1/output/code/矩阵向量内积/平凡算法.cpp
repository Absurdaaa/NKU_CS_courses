#include <iostream>
#include <time.h>
using namespace std;
#define MAX_N 10000

double get_elapsed_time(timespec start, timespec end)
{
  return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

// 提高精度

int main()
{
  int sum[MAX_N];
  // 矩阵b
  int(*b)[MAX_N] = new int[MAX_N][MAX_N];
  // 记得最后要 delete[] b;
  // 向量a
  int a[MAX_N];
  int step = 10;
  long counter = 0;

  // clock_t start, finish;
  struct timeval start, end;
  // 初始化,1000起步
  for (int i = 0; i < MAX_N; i++)
  {
    for (int j = 0; j < MAX_N; j++)
      b[i][j] = i * MAX_N + j;
    a[i] = i;
  }

  for (int n = 0; n <= MAX_N; n += step)
  {
    // 清空 sum 数组
    for (int i = 0; i < n; i++)
      sum[i] = 0;

    // 记录开始时间
    timespec start_time, end_time;
    clock_gettime(CLOCK_MONOTONIC, &start_time);

    int counter = 0;

    // 一直循环运行，运行直到时间总达到 10ms，在求平均数，这样能稳定很多
    while (true)
    {
      counter++;

      for (int i = 0; i < n; i++)
      {
        for (int j = 0; j < n; j++)
        {
          sum[j] += b[i][j] * a[j];
        }
      }

      clock_gettime(CLOCK_MONOTONIC, &end_time);
      if (get_elapsed_time(start_time, end_time) >= 0.5)
        break; // 至少 10ms
    }

    double total_time = get_elapsed_time(start_time, end_time);
    cout << n << " " << counter << " " << total_time / counter << endl;

    if (n == 100)
      step = 100;
    if (n == 1000)
      step = 1000;
  }
  delete[] b;
  return 0;
}

/*
0 1787726 5.5937e-08
10 188056 5.3703e-07
20 63061 1.58577e-06
30 34593 2.8908e-06
40 25040 3.99388e-06
50 16145 6.19388e-06
60 11252 8.88743e-06
70 8286 1.20699e-05
80 6081 1.64469e-05
90 5016 1.99394e-05
100 4045 2.47227e-05
200 917 0.000109149
300 238 0.000422399
400 178 0.000564759
500 121 0.000827444
600 111 0.000908147
700 82 0.00123322
800 62 0.00161795
900 50 0.00202916
1000 41 0.00248184
*/

/*
0 9827416 5.08781e-08
10 1769878 2.82505e-07
20 501635 9.96741e-07
30 229804 2.17577e-06
40 130436 3.83331e-06
50 83493 5.98857e-06
60 58483 8.5495e-06
70 42619 1.17321e-05
80 32715 1.52835e-05
90 25876 1.9323e-05
100 20930 2.38896e-05
200 5245 9.53314e-05
300 2325 0.000215087
400 1299 0.000384988
500 832 0.000601324
600 578 0.000866371
700 427 0.00117222
800 331 0.00151334
900 263 0.00190739
1000 213 0.00235326
2000 54 0.00940963
3000 24 0.0210968
4000 14 0.037812
5000 9 0.0587405
6000 6 0.0850843
7000 5 0.116714
8000 4 0.153435
9000 3 0.194184
10000 3 0.238889
*/