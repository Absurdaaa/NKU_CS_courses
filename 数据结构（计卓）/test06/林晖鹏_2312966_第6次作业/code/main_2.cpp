#include <iostream>
#include <vector>
#include <string>
#include <vector>
#include <algorithm>
#include <fstream>
#include <list>
using namespace std;
void InputTxt(string path, vector<string> &v)
{
    ifstream infile(path);
    // 读取每一行，然后不断往系统塞入单词
    int count = 0; // 行数
    string line;
    while (getline(infile, line))
    {
        count++;
        for (int i = 0; i < line.length(); i++)
        {
            // 寻找单词的开头
            if ((char(line[i]) >= 'a' && char(line[i]) <= 'z') || (char(line[i]) >= 'A' && char(line[i]) <= 'Z'))
            {
                int j;
                // 寻找单词的结尾
                for (j = i; j < line.length(); j++)
                {
                    if (!(char(line[j]) >= 'a' && char(line[j]) <= 'z') && !(char(line[j]) >= 'A' && char(line[j]) <= 'Z'))
                    {
                        break;
                    }
                }
                // if(j==line.length()&&i){break;}
                // 截取单词
                string w = line.substr(i, j - i);
                // 如果是s,排除“'s”的情况
                //  if(w.length()==1&&w=="s"){continue;}
                // 改变大小写
                transform(w.begin(), w.end(), w.begin(), ::tolower);
                v.push_back(w);
                i = j;
            }
        }
    }
}

// 判断一个字符是否是元音
bool isVowel(char c)
{
    c = tolower(c); // 转换为小写，统一处理
    return (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u');
}
// 拆分单词为音节
int splitIntoSyllables(vector<string> &vec, vector<string> &vec2)
{
    int max_len=0;//记录最大音节的长度
    for (vector<string>::iterator it=vec.begin();it!=vec.end();it++){
        string currentSyllable = "";
        string word = *it;

        for (int i = 0; i < word.length(); i++)
        {
            char c = word[i];
            if (isVowel(c))
            {
                if (!currentSyllable.empty())
                {
                    vec2.push_back(currentSyllable); // 添加前一个音节
                    max_len = max_len > currentSyllable.length() ? max_len : currentSyllable.length();
                }
                currentSyllable = c; // 当前元音作为新的音节开始
            }
            else
            {
                currentSyllable += c; // 当前辅音加入当前音节
            }
        }

        if (!currentSyllable.empty())
        {
            vec2.push_back(currentSyllable); // 添加最后一个音节
        }
    }
    return max_len;
}

struct Key_value {
    string str;
    int hashvalue;
    Key_value(string s,int h){
        str=s;
        hashvalue=h;
    }
};
class Hash
{
public:
    Hash(int n)
    {
        Max_Size = n;
        table = new list<Key_value>[Max_Size];
    }
    ~Hash()
    {
        delete[] table;
    }

    void Insert(string s)
    {
        int key = HashFunc(s);
        list<Key_value> &ls = table[key];
        // cout<<key<<endl;
        // cout<<ls.size()<<endl;
        for (list<Key_value>::iterator it = ls.begin(); it != ls.end(); it++)
        {
            // cout<<*it<<endl;
            // cout<<s<<endl;
            if ((*it).str == s)
            {
                return;
            }
        }
        // 这里可以改成按大小有序插入
        ls.push_back(Key_value(s,0));
    }

    int Search(string s,int &times)//返回哈希值
    {
        times = 1;
        int key = HashFunc(s);
        list<Key_value> &ls = table[key];
        for (list<Key_value>::iterator it = ls.begin(); it != ls.end(); it++)
        {
            
            if ((*it).str == s)
            {
                // cout << "查到单词" << s << " 查找" << times << "次" << endl;
                return (*it).hashvalue;
            }
            times++;
        }
        // 这里可以改成按大小有序插入
        // cout << "查找不到单词" << s << " 查找" << 1 << "次" << endl;
        return -1;
    }
    
    void givehash(){//给音节排哈希表
        int hashvalue=0;
        for(int i=0;i<Max_Size;i++){
            list<Key_value> &ls = table[i];
            for (list<Key_value>::iterator it = ls.begin(); it != ls.end(); it++){
                (*it).hashvalue = hashvalue;
                hashvalue++;
            }
        }
        num = hashvalue-1;
    }
private:
    int num;
    int Max_Size;
    list<Key_value> *table;
    // 哈希函数
    long long HashFunc(string s)
    {
        long long num = 0;
        int g = 1;
        for (int i = 0; i < s.length(); i++)
        {
            num += (s[i] - 'a') * g;
            num = num % Max_Size;
            g *= 31;
        }
        if (num % Max_Size < 0)
        {
            num += Max_Size;
        }
        return num % Max_Size;
    }
};

class Hash2
{
public:
    Hash *hash;
    Hash2(int n,int n2)
    {
        Max_Size = n;
        table = new list<string>[Max_Size];
        hash =new Hash(n2);
    }
    ~Hash2()
    {
        delete[] table;
    }

    void Insert(string s)
    {
        int t;
        int key = HashFunc(s,t);
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
    void Print()
    {
        int max = 0;
        int num[6];
        for(int i=0;i<6;i++)num[i]=0;
        for (int i = 0; i < Max_Size; i++)
        {
            // cout<<table[i].size()<<endl;
            max = max > table[i].size() ? max : table[i].size();
            num[table[i].size()]++;
        }
        cout << "最长链为" << max << endl;
        for (int i = 1; i < 5; i++)
        {
            cout << "长度为" << i << "的链有" << num[i] << endl;
        }
    }

    int Search(string s,bool &fail)
    {
        fail=1;
        int times = 1;
        int key = HashFunc(s,times);
        if(key==-1){
            fail = 0;
            return times;
        }
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
        //这里可以改成按大小有序插入
        //cout << "查找不到单词" << s << " 查找" << 1 << "次" << endl;
        fail=0;
        return times;
    }

private:
    int Max_Size;
    list<string> *table;

    // 拆分单词为音节
    vector<string> splitIntoSyllables(const string &word)
    {
        vector<string> syllables;
        string currentSyllable = "";

        for (int i = 0; i < word.length(); i++)
        {
            char c = word[i];

            if (isVowel(c))
            {
                if (!currentSyllable.empty())
                {
                    syllables.push_back(currentSyllable); // 添加前一个音节
                }
                currentSyllable = c; // 当前元音作为新的音节开始
            }
            else
            {
                currentSyllable += c; // 当前辅音加入当前音节
            }
        }

        if (!currentSyllable.empty())
        {
            syllables.push_back(currentSyllable); // 添加最后一个音节
        }

        return syllables;
    }
    // 哈希函数
    long long HashFunc(string s,int &t)
    {
        long long num = 0;
        int g = 1;
        vector<string>vec = splitIntoSyllables(s);
        for (vector<string>::iterator it=vec.begin();it!=vec.end();it++)
        {
            if (this->hash->Search(*it, t)==-1){
                return -1;//没有这个音节
            }
            num += (this->hash->Search(*it, t)) * g;
            num = num % Max_Size;
            g *= 131;
        }
        if (num % Max_Size < 0)
        {
            num += Max_Size;
        }
        return num % Max_Size;
    }
    
};

string path_in, path_search;
vector<string> vec;
vector<string> vec2;
double average = 0;
double fail=0;
int main()
{
    // 构建哈希表文件路径
    path_in = "input.txt";
    InputTxt(path_in, vec);
    int max_len = splitIntoSyllables(vec,vec2);
    //cout<<max_len<<endl;
    Hash2 hash(vec.size(),vec2.size());
    for (vector<string>::iterator it = vec2.begin(); it != vec2.end(); it++)
    {
        hash.hash->Insert(*it);//插入音节构造哈希
    }
    hash.hash->givehash();//初始化哈希值
    for (vector<string>::iterator it = vec.begin(); it != vec.end(); it++)
    {
        hash.Insert(*it);//插入单词
    }
    path_search = "search.txt";
    vec.clear();
    InputTxt(path_search, vec);
    for (vector<string>::iterator it = vec.begin(); it != vec.end(); it++)
    {
        bool b=0;
        average += hash.Search(*it,b);
        if(!b){fail++;}
    }
    if (vec.size() == 0)
        return 0;
    average = average / vec.size();
    cout << "平均查找次数为" << average << endl;
    
    cout<<"查找失败的次数"<<fail<<endl;
    
    hash.Print();
        return 0;
}
