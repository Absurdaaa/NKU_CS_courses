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
0 9745512 5.13057e-08
10 2152335 2.32306e-07
20 556201 8.98957e-07
30 279591 1.78833e-06
40 150417 3.3241e-06
50 101494 4.92644e-06
60 68342 7.31623e-06
70 51851 9.64313e-06
80 38899 1.2854e-05
90 31395 1.59266e-05
100 24930 2.00567e-05
200 6254 7.99572e-05
300 2782 0.00017979
400 1565 0.00031954
500 1001 0.0004999
600 695 0.000719518
700 511 0.000980344
800 390 0.00128218
900 308 0.00162782
1000 248 0.00201689
2000 62 0.00810585
3000 28 0.0185179
4000 16 0.032963
5000 10 0.0505505
6000 7 0.0721705
7000 6 0.0981169
8000 4 0.127863
9000 4 0.162006
10000 3 0.198019
*/
