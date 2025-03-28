#include <iostream>
#include <time.h>
using namespace std;

#define MAX_N 5000
double get_elapsed_time(timespec start, timespec end)
{
  return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

// 提高精度

int main()
{
  int sum;
  int(*a) = new int[MAX_N];
  int step = 10;

  // clock_t start, finish;
  struct timeval start,
      end;
  // 初始化,1000起步
  for (int i = 0; i < MAX_N; i++)
  {
    a[i] = i;
  }

  for (int n = 0; n <= MAX_N; n += step)
  {
    // 清空 sum
    sum = 0;

    // 记录开始时间
    timespec start_time, end_time;
    clock_gettime(CLOCK_MONOTONIC, &start_time);

    int counter = 0;

    // 一直循环运行，运行直到时间总达到 10ms，在求平均数，这样能稳定很多
    while (true)
    {
      counter++;

      for (int m = n; m > 1; m = (m + 1) / 2)
      { // 向上取整
        for (int i = 0; i < m / 2; i++)
        {
          a[i] += a[m - i - 1]; // 前半部分 += 后半部分
        }
      }
      sum = a[0];

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
  delete a;
  return 0;
}

/*
0 9755722 5.1252e-08
10 5624747 8.88929e-08
20 3560721 1.40421e-07
30 2610391 1.91542e-07
40 1972889 2.53435e-07
50 1620066 3.0863e-07
60 1373415 3.64056e-07
70 1179036 4.24075e-07
80 1030037 4.8542e-07
90 927573 5.39041e-07
100 834096 5.99452e-07
200 420965 1.18775e-06
300 281534 1.77599e-06
400 210935 2.37041e-06
500 168726 2.96339e-06
600 140511 3.55844e-06
700 120569 4.14703e-06
800 105234 4.75135e-06
900 94046 5.31658e-06
1000 84446 5.92099e-06
2000 42117 1.18718e-05
3000 28094 1.77979e-05
4000 21039 2.37664e-05
5000 16783 2.97934e-05
*/