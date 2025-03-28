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

    // 一直循环运行，运行直到时间总达到 10ms，在求平均数，这样能稳定很多
    while (true)
    {
      counter++;

      for (int i = 0; i < n; i++)
      {
        for (int j = 0; j < n; j++)
        {
          sum[i] += b[i][j] * a[i];
        }
      }

      clock_gettime(CLOCK_MONOTONIC, &end_time);
      if (get_elapsed_time(start_time, end_time) >= 0.1)
        break; // 至少 10ms
    }

    double total_time = get_elapsed_time(start_time, end_time);
    cout << n << " " << counter << " " << total_time / counter << endl;

    if (n == 100)
      step = 100;
  }
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
0 9812903 5.09533e-08
10 1879023 2.66096e-07
20 544234 9.18723e-07
30 250652 1.9948e-06
40 142230 3.51545e-06
50 91099 5.48854e-06
60 63497 7.87443e-06
70 47133 1.06085e-05
80 36073 1.38611e-05
90 28456 1.75715e-05
100 23000 2.174e-05
200 5639 8.868e-05
300 2501 0.000199937
400 1399 0.000357452
500 888 0.000563161
600 618 0.00080993
700 452 0.00110701
800 347 0.0014445
900 274 0.00182809
1000 222 0.00225459
2000 56 0.00893587
3000 25 0.0200498
4000 15 0.0356405
5000 10 0.0555366
6000 7 0.0799108
7000 5 0.108686
8000 4 0.14184
9000 3 0.179411
10000 3 0.221104
*/