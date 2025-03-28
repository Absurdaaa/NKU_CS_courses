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
    sum =0;

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
        sum = sum+a[i];
      }

      clock_gettime(CLOCK_MONOTONIC, &end_time);
      if (get_elapsed_time(start_time, end_time) >= 0.1)
        break; // 至少 10ms
    }

    double total_time = get_elapsed_time(start_time, end_time);
    cout << n << " " << counter << " " << total_time / counter << endl;

    if (n == 100)
      step = 100;
    if (n == 1000)
      step = 1000;
  }
  return 0;
}

/*
0 9739314 5.13383e-08
10 7877428 6.34725e-08
20 5756775 8.68542e-08
30 4547572 1.09949e-07
40 3753713 1.33201e-07
50 3197762 1.56359e-07
60 2782538 1.79692e-07
70 2463285 2.02981e-07
80 2210154 2.26229e-07
90 2004838 2.49397e-07
100 1833112 2.7276e-07
200 989420 5.05347e-07
300 677707 7.37782e-07
400 515414 9.70095e-07
500 413778 1.20838e-06
600 347676 1.43812e-06
700 299386 1.67009e-06
800 262836 1.90233e-06
900 234325 2.1338e-06
1000 211280 2.36654e-06
2000 106816 4.68098e-06
3000 71434 6.99954e-06
4000 53688 9.31308e-06
5000 42977 1.16342e-05
*/