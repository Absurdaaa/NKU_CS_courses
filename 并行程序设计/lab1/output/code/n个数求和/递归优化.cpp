#include <iostream>
#include <time.h>
using namespace std;

#define MAX_N 5000
double get_elapsed_time(timespec start, timespec end)
{
  return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

void recursion(int n, int a[])
{
  if (n == 1 || n == 0)
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

      recursion(n, a);
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
0 9493446 5.26679e-08
10 6770573 7.3849e-08
20 4948435 1.01042e-07
30 4168210 1.19956e-07
40 3279711 1.52452e-07
50 2858024 1.74946e-07
60 2521040 1.98331e-07
70 2175131 2.29871e-07
80 1934122 2.58515e-07
90 1783273 2.80383e-07
100 1614765 3.09643e-07
200 857410 5.83152e-07
300 583361 8.57103e-07
400 440853 1.13417e-06
500 356612 1.40208e-06
600 296505 1.68631e-06
700 255156 1.95959e-06
800 222780 2.24438e-06
900 198829 2.51473e-06
1000 179115 2.79151e-06
2000 89636 5.57813e-06
3000 59670 8.37943e-06
4000 44715 1.11821e-05
5000 35793 1.39695e-05
*/