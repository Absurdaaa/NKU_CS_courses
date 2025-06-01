#include<iostream>
#include<vector>
#include <string>
#include <vector>
#include <algorithm>
#include <fstream>
#include<list>
using namespace std;
void InputTxt(string path,vector<string>&v){
    ifstream infile(path);
    //读取每一行，然后不断往系统塞入单词
    int count=0;//行数
    string line;
    while(getline(infile,line)){
        count++;
        for(int i=0;i<line.length();i++){
            //寻找单词的开头
            if((char(line[i])>='a'&&char(line[i])<='z')||(char(line[i])>='A'&&char(line[i])<='Z')){
                int j;
                //寻找单词的结尾
                for(j=i;j<line.length();j++){
                    if(!(char(line[j])>='a'&&char(line[j])<='z')&&!(char(line[j])>='A'&&char(line[j])<='Z')){
                        break;
                    }
                }
                //if(j==line.length()&&i){break;}
                //截取单词
                string w=line.substr(i,j-i);
                //如果是s,排除“'s”的情况
                // if(w.length()==1&&w=="s"){continue;}
                //改变大小写
                transform(w.begin(), w.end(), w.begin(), ::tolower);
                v.push_back(w);
                i = j;
            }
        }
    }
}

class Hash{
    public:
    Hash(int n){
        Max_Size=n;
        table = new list<string>[Max_Size];
    }
    ~Hash()
    {
        delete[] table;
    }

    void Insert(string s)
    {
        int key = HashFunc(s);
        list<string> &ls = table[key];
        // cout<<key<<endl;
        // cout<<ls.size()<<endl;
        for (list<string>::iterator it = ls.begin(); it != ls.end(); it++)
        {
            // cout<<*it<<endl;
            // cout<<s<<endl;
            if (*it == s)
            {
                return;
            }
        }
        // 这里可以改成按大小有序插入
        ls.push_back(s);
    }

    int Search(string s,bool&b)
    {
        b=1;
        int times = 1;
        int key = HashFunc(s);
        list<string> &ls = table[key];
        for (list<string>::iterator it = ls.begin(); it != ls.end(); it++)
        {
            
            if (*it == s)
            {
                //cout << "查到单词" << s << " 查找" << times << "次" << endl;
                return times;
            }
            times++;
        }
        // 这里可以改成按大小有序插入
        //cout << "查找不到单词" << s << " 查找" << 1 << "次" << endl;
        b=0;
        return times;
    }
    void Print(){
        int max = 0;
        int num[6];
        for (int i = 0; i < 6; i++)
            num[i] = 0;
        for (int i = 0; i < Max_Size; i++)
        {
            // cout<<table[i].size()<<endl;
            max = max > table[i].size() ? max : table[i].size();
            num[table[i].size()]++;
        }
        cout << "最长链为" << max << endl;
        for(int i=1;i<5;i++){
            cout<<"长度为"<<i<<"的链有"<<num[i]<<endl;
        }
        
    }

    private:
    int Max_Size;
    list<string> *table;
    //哈希函数
    long long HashFunc(string s)
    {
        long long num=0;
        int g=1;
        for(int i=0;i<s.length();i++){
            num+=(s[i]-'a')*g;
            num = num%Max_Size;
            g*=31;
        }
        if(num%Max_Size<0){
            num+=Max_Size;
        }
        return num%Max_Size;
    }
};
string path_in,path_search;
vector<string>vec;
double average = 0;
int fail=0;
int main(){
    //构建哈希表文件路径
    path_in = "input.txt";
    InputTxt(path_in, vec);
    Hash hash(vec.size());
    for(vector<string>::iterator it=vec.begin();it!=vec.end();it++){
        hash.Insert(*it);
    }

    path_search = "search.txt";
    vec.clear();
    InputTxt(path_search, vec);
    for (vector<string>::iterator it = vec.begin(); it != vec.end(); it++)
    {
        bool b=0;
        average+=hash.Search(*it,b);
        if(!b)fail++;
    }
    if(vec.size()==0)return 0;
    average = average/vec.size();
    cout<<"平均查找次数为"<<average<<endl;
    cout << "查找失败的次数" << fail << endl;
    hash.Print();
    return 0;
}