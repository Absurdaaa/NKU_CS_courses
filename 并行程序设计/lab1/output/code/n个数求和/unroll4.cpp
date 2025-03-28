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
  int a[MAX_N];
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
      sum = 0;
      int sum1 = 0, sum2 = 0,sum3=0,sum4=0;
      int i=0;
      for (i = 0; i < n-3; i += 4)
      {
        sum1 = sum1 + a[i];
        sum2 = sum2 + a[i+1];
        sum3 = sum3 + a[i+2];
        sum4 = sum4 + a[i+3];
      }
      if(i == n-5)sum+=a[n-1];
      else if(i == n-6)sum+= a[n-1]+a[n-2];
      else if (i == n - 7)
        sum += a[n - 1] + a[n - 2]+a[n-3];
      sum = sum1 + sum2 +sum3+sum4;

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
  return 0;
}

/*
0 9511057 5.25704e-08
10 8920083 5.60533e-08
20 7815661 6.39741e-08
30 7141615 7.00122e-08
40 6284447 7.95615e-08
50 5821962 8.58817e-08
60 5217879 9.58244e-08
70 4877762 1.02506e-07
80 4477979 1.11658e-07
90 4221106 1.18452e-07
100 3904535 1.28056e-07
200 2395490 2.08726e-07
300 1724578 2.89926e-07
400 1348979 3.70651e-07
500 1103350 4.53166e-07
600 937470 5.3335e-07
700 812921 6.15066e-07
800 725993 6.88712e-07
900 649978 7.69257e-07
1000 589125 8.48717e-07
2000 302743 1.65157e-06
3000 203935 2.45177e-06
4000 153707 3.25296e-06
5000 124923 4.00247e-06
*/