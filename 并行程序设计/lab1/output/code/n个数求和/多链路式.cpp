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

      sum = 0;
      int sum1 = 0, sum2 = 0;
      int i = 0;
      for (i = 0; i < n - 1; i += 2)
      {
        sum1 = sum1 + a[i];
        sum2 = sum2 + a[i + 1];
      }
      if (i == n - 3)
      {
        sum = sum + a[n - 1];
      }
      sum = sum1 + sum2;

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
0 9322191 5.36355e-08
10 8779819 5.69488e-08
20 7081198 7.06095e-08
30 5987211 8.35113e-08
40 5242765 9.53695e-08
50 4604109 1.08599e-07
60 4147416 1.20557e-07
70 3752711 1.33237e-07
80 3437611 1.4545e-07
90 3152877 1.58585e-07
100 2929773 1.70662e-07
200 1689979 2.95862e-07
300 1188700 4.20628e-07
400 913426 5.4739e-07
500 742758 6.73167e-07
600 630848 7.92585e-07
700 545499 9.16592e-07
800 478774 1.04434e-06
900 429271 1.16477e-06
1000 386566 1.29344e-06
2000 197689 2.52923e-06
3000 132634 3.76979e-06
4000 99909 5.00456e-06
5000 80118 6.24082e-06
*/