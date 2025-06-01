#include <iostream>
#include <vector>
#include <algorithm>
#include <cstdlib>
#include <chrono> // 引入chrono库
#include <ctime>
using namespace std;
int N;
int mp[1005][1005];
vector<pair<int, int> > v2;
int v[1005][1005];
int num=0;
void Print()
{
    for (int i = 1; i <= N; i++)
    {
        for (int j = 1; j <= N; j++)
        {
            cout << mp[i][j] << " ";
        }
        cout << endl;
    }
}

class Deque
{ // 简单模拟队列
public:
    int size;
    vector<pair<int, int> > v;
    // v的begin是队尾，end是队头
    Deque()
    {
        size = 0;
    }
    void Push(pair<int, int> p)
    {
        v.insert(v.begin() + size, p);
        size++;
    }
    void Pop()
    {
        if (size == 0)
        {
            cout << "队列里没有元素了." << endl;
            return;
        }
        v.erase(v.begin());
        size--;
    }
    pair<int, int> Top()
    {
        return *v.begin();
    }
};

// 灌入液体
void intowater_BFS(int i, int j, int k)
{ // k是时刻，周围液体初始化时刻是0
    if (mp[i][j] == -1)
    {
        return;
    }
    if (mp[i][j] != -2)return;
        mp[i][j] = k;
    Deque dq;
    dq.Push(make_pair(i, j));
    while (dq.size != 0)
    {
        int x = dq.Top().first;
        int y = dq.Top().second;
        int deriction[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int p = 0; p < 4; p++)
        {
            int nextx = x + deriction[p][0];
            int nexty = y + deriction[p][1];
            if (mp[nextx][nexty] == -2)
            {
                mp[nextx][nexty] = k;
                if (nextx != 0 || nextx != N + 1 || nexty != 0 || nexty != N + 1)
                { // 如果不是边界就放进队列里面
                    dq.Push(make_pair(nextx, nexty));
                }
            }
            else if (mp[nextx][nexty] == -1)
            { // 如果是金属块
                v[nextx][nexty]++;
                if(v[nextx][nexty]==2){v2.push_back(make_pair(nextx,nexty));}
            }
            
        }
        dq.Pop();
    }
}

// 更新周围金属块的状态,用于一个金属块变液体之后
int update(int k)
{
    if (num == 0) // 所有都融化了
    {
        return k;
    }
    int deriction[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
    Deque dq;
    dq.v = v2;
    dq.size = v2.size();
    int size = dq.size;
    for (vector<pair<int, int> >::iterator it = v2.begin(); it != v2.end(); it++)
    {
        mp[(*it).first][(*it).second] = k + 1;
        num--;
    }
    v2.clear();
    for (int i = 0; i < size; i++)
    {
        pair<int, int> p = dq.Top();
        int x = p.first;
        int y = p.second;

        for (int p = 0; p < 4; p++)
        {
            int nextx = x + deriction[p][0];
            int nexty = y + deriction[p][1];
            if (mp[nextx][nexty] != -1 && mp[nextx][nexty] != -2)
                continue; // 如果不是金属块就跳过
            if (mp[nextx][nexty] == -2)
                intowater_BFS(nextx, nexty, k + 1); // 遇到中空

            v[nextx][nexty]++;
            if (v[nextx][nexty] == 2)
            {
                v2.push_back(make_pair(nextx, nexty));
            }
        }
        dq.Pop();
    }
    //Print();
    return update(k + 1);
}

int main()
{
    std::chrono::high_resolution_clock::time_point start = std::chrono::high_resolution_clock::now();

    cin >> N;
    
    // 设置矩阵的大小
    const int rows = 1000;
    const int cols = 1000;

    // 初始化随机数生成器
    std::srand(std::time(nullptr));

    // 填充矩阵
    for (int i = 1; i <= rows; ++i)
    {
        for (int j = 1; j <= cols; ++j)
        {
            // 确保边界上的元素是'_'
            if (i == 1 || i == rows  || j == 1 || j == cols )
            {
                mp[i][j] = -2;
            }
            else
            {
                // 内部元素随机选择'#'或'_'
                mp[i][j] = (std::rand() % 2 == 0) ? -1: -2;
                if (mp[i][j] == -1)
                    num++;
            }
        }
    }

    
    // 由于金属有可能在边界，边界外面应该是算没有液体的。
    // 这里假设金属不在边界，如果在的话，
    // for (int i = 1; i <= N; i++)
    // {
    //     char a;
    //     for (int j = 1; j <= N; j++)
    //     {
    //         cin >> a;
    //         if (a == '_')
    //         {
    //             mp[i][j] = -2;
    //         }
    //         else if (a == '#')
    //         {
    //             mp[i][j] = -1;
    //             num++;
    //         }
    //         // mp的数字代表变成液体的时间，-1则为没变成液体
    //     }
    // }

    // 处理上下左右四个边界,灌入液体
    for (int i = 1; i <= N; i++)
    {
        intowater_BFS(i, 1, 0);
        intowater_BFS(i, N, 0);
        intowater_BFS(1, i, 0);
        intowater_BFS(N, i, 0);
    }
    //Print();
    int ans = update(0);
    cout << ans << endl;

    std::chrono::high_resolution_clock::time_point end = std::chrono::high_resolution_clock::now();

    // 计算程序运行时间（单位：秒）
    std::chrono::duration<double> duration = end - start;

    // 输出程序执行的时间
    std::cout << "程序执行时间: " << duration.count() << " 秒" << std::endl;
    return 0;
}