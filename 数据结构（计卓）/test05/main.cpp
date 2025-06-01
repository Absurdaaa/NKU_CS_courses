/*
*考虑相同的类型行数最多的，然后考虑k的奇偶 
*最多100行，所以最多100种状态
*状态可以用哈西表示，比如二进制之类 
*/
#include<iostream>
#include<vector>
using namespace std;
int N,M,K;
int ans;
vector<pair<long long,int> >v;
vector<pair<long long, int> >::iterator Find(
    vector<pair<long long, int> >::iterator beg,
    vector<pair<long long, int> >::iterator end,
    long long num, bool &b);
bool operator<(pair<long long, int> p1, pair<long long, int> p2)
{
    return p1.first<p2.first;
}
int main()
{
    cin>>N>>M>>K;
    int p=K%2;
    for(int i=1;i<=N;i++){
        long long x=0;
        int tow=1;
        int k = 0; // 记录1的个数
        long long num=0;          
        for(int j=1;j<=M;j++){
            cin>>x;
            num+=tow*x;
            tow*=2;
            k+=x;
        }
        k=M-k; //变成0的个数
        if(k%2==p){       //如果奇偶和k的一样，则计入v
            bool b=0;
            vector<pair<long long, int> >::iterator it = Find(v.begin(), v.end(), num, b);
            if(it!=v.end()&&b==1){
                (*it).second++;
                ans = ans < (*it).second ? (*it).second :ans;
            }
            else if(b==0){
                //这里直接插入，未来修改为有序插入，根据num排序
                v.insert(it,make_pair(num,1));
            }
        }
    }
    cout<<ans<<endl;
    return 0;
}
vector<pair<long long, int> >::iterator Find(
    vector<pair<long long, int> >::iterator beg,
    vector<pair<long long, int> >::iterator end,
    long long num,
    bool &b)
{
    vector<pair<long long, int> >::iterator it = beg;
    //这里用的查找，未来改成二分查找
    for (;it!=end;it++){
        if((*it).first == num){
            return it;
        }
    }
    return end;
}