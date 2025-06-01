#include<iostream>
#include<vector>
#include<algorithm>
using namespace std;
int N;
int mp[1005][1005];
vector<pair<int,int> >v0;//放上下左右没有液体的金属坐标，一开始都在这个
vector<pair<int, int> > v1;
vector<pair<int, int> > v2;
void Print(){
    for(int i=1;i<=N;i++){
        for(int j=1;j<=N;j++){
            cout<<mp[i][j]<<" ";
        }
        cout<<endl;
    }
}

class Deque{//简单模拟队列
    public:
    int size;
    vector<pair<int,int> >v;
    //v的begin是队尾，end是队头
    Deque(){
        size=0;
    }
    void Push(pair<int,int> p){
        v.insert(v.begin()+size,p);
        size++;
    }
    void Pop(){
        if(size==0){cout<<"队列里没有元素了."<<endl;return;}
        v.erase(v.begin());
        size--;
    }
    pair<int,int> Top(){
        return *v.begin();
    }
};

//灌入液体
void intowater_BFS(int i,int j,int k){//k是时刻，周围液体初始化时刻是0
    if(mp[i][j]==-1){
        return;
    }
    mp[i][j]=k;
    Deque dq;
    dq.Push(make_pair(i,j));
    while(dq.size!=0){
        int x = dq.Top().first;
        int y = dq.Top().second;
        
        int deriction[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for(int p=0;p<4;p++){
            int nextx = x +deriction[p][0];
            int nexty = y+ deriction[p][1];
            if (mp[nextx][nexty] == -2)
            {
                mp[nextx][nexty]=k;
                if (nextx != 0 || nextx != N + 1 || nexty != 0 || nexty != N + 1)
                { // 如果不是边界就放进队列里面
                    dq.Push(make_pair(nextx, nexty));
                }
            }
            else if(mp[nextx][nexty]==-1){//如果是金属块
                vector<pair<int, int> >::iterator it = find(v0.begin(), v0.end(), make_pair(nextx, nexty));
                if(it==v0.end()){//没找到
                    it = find(v1.begin(), v1.end(), make_pair(nextx, nexty));
                    if(it==v1.end())continue;
                    v2.push_back(*it);
                    v1.erase(it);
                }
                else{
                    v1.push_back(*it);
                    v0.erase(it);
                }
            }
        }
        dq.Pop();
    }
}

// 更新周围金属块的状态,用于一个金属块变液体之后
int update(int k)
{
    if (v0.size() == 0 && v1.size() == 0 && v2.size() == 0)//所有都融化了
    {
        return k;
    }
    int deriction[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
    Deque dq;
    dq.v = v2;
    dq.size = v2.size();
    int size=dq.size;
    for (vector<pair<int, int> >::iterator it = v2.begin(); it != v2.end(); it++)
    {
        mp[(*it).first][(*it).second] = k + 1;
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
                continue;                                                 // 如果不是金属块就跳过
            if (mp[nextx][nexty] == -2)intowater_BFS(nextx, nexty, k + 1);//遇到中空

            vector<pair<int, int> >::iterator it = find(v0.begin(), v0.end(), make_pair(nextx, nexty));
            if (it == v0.end())
            { // 没找到
                it = find(v1.begin(), v1.end(), make_pair(nextx, nexty));
                if (it == v1.end())continue;
                v2.push_back(*it);
                v1.erase(it);
            }
            else
            {
                v1.push_back(*it);
                v0.erase(it);
            }
        }
        dq.Pop();
    }
    //Print();
    return update(k + 1);
}

int main(){
    cin>>N;
    //由于金属有可能在边界，边界外面应该是算没有液体的。
    //这里假设金属不在边界，如果在的话，
    for(int i=1;i<=N;i++){
        char a;
        for(int j=1;j<=N;j++){
            cin>>a;
            if(a=='_'){mp[i][j]=-2;}
            else if(a=='#'){
                mp[i][j]=-1;
                v0.push_back(make_pair(i,j));
                }
            //mp的数字代表变成液体的时间，-1则为没变成液体
        }
    }
    
    //处理上下左右四个边界,灌入液体
    for(int i=1;i<=N;i++){
        intowater_BFS(i,1,0);
        intowater_BFS(i, N, 0);
        intowater_BFS(1, i, 0);
        intowater_BFS(N, i, 0);
    }
    //Print();
    int ans=update(0);
    cout<<ans<<endl;
    return 0;
}