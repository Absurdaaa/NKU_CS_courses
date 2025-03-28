
#include <iostream>
#include <time.h>
using namespace std;

double get_elapsed_time(timespec start, timespec end)
{
  return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

// 提高精度

int main()
{
  int sum[1000];
  // 矩阵b
  int b[1000][1000];
  // 向量a
  int a[1000];
  int step = 10;
  long counter = 0;

  // clock_t start, finish;
  struct timeval start, end;
  // 初始化,1000起步
  for (int i = 0; i < 1000; i++)
  {
    for (int j = 0; j < 1000; j++)
      b[i][j] = i * 1000 + j;
    a[i] = i;
  }

  for (int n = 0; n <= 1000; n += step)
  {
    // 清空 sum 数组
    for (int i = 0; i < n; i++)
      sum[i] = 0;

    // 记录开始时间
    timespec start_time, end_time;
    clock_gettime(CLOCK_MONOTONIC, &start_time);

    int counter = 0;

    // 运行直到时间达到 10ms
    while (true)
    {
      counter++;

      for (int i = 0; i < n; i++)
      {
        sum[i] = 0.0;
        int j = 0;
        for (j = 0; j < n - 3; j += 4)
        {
          sum[i] += b[j][i] * a[j];
          sum[i] += b[j + 1][i] * a[j + 1];
          sum[i] += b[j + 2][i] * a[j + 2];
          sum[i] += b[j + 3][i] * a[j + 3];
        }
        if (j == n - 5)
          sum[i] += b[n - 1][i] * a[n - 1];
        else if (j == n - 6)
          sum[i] += b[n - 1][i] * a[n - 1] + b[n - 2][i] * a[n - 2];
        else if (j == n - 7)
          sum[i] += b[n - 1][i] * a[n - 1] + b[n - 2][i] * a[n - 2] + b[n - 3][i] * a[n - 3];
      }

      clock_gettime(CLOCK_MONOTONIC, &end_time);
      if (get_elapsed_time(start_time, end_time) >= 0.1)
        break; // 至少 0.1s
    }

    double total_time = get_elapsed_time(start_time, end_time);
    cout << n << " " << total_time / counter << endl;

    if (n == 100)
      step = 100;
  }
  return 0;
}

/*
0 5.11236e-08
10 2.71117e-07
20 1.09207e-06
30 2.20534e-06
40 4.14637e-06
50 6.23459e-06
60 1.01002e-05
70 1.32768e-05
80 1.79232e-05
90 2.20441e-05
100 2.79492e-05
200 0.000114033
300 0.000258984
400 0.000476281
500 0.000758691
600 0.0011071
700 0.00152472
800 0.00193284
900 0.00253402
1000 0.00348793
*/