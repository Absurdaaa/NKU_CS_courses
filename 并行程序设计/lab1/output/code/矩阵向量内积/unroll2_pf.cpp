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
        int j=0;
        for (j = 0; j < n-1; j+=2)
        {
          sum[i] += b[j][i] * a[j];
          sum[i] += b[j+1][i] * a[j+1];
          
        }
        if(j==n-3)sum[i]+=b[n-1][i]*a[n-1];
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
0 5.11872e-08
10 3.2239e-07
20 1.11754e-06
30 2.42518e-06
40 4.29602e-06
50 7.27211e-06
60 1.02961e-05
70 1.39413e-05
80 1.88053e-05
90 2.34227e-05
100 2.85524e-05
200 0.000115163
300 0.000266276
400 0.000482735
500 0.000788889
600 0.00117785
700 0.00159189
800 0.00203801
900 0.00279807
1000 0.00362578
*/