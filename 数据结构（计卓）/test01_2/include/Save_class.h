#ifndef SAVE_CLASS_H  // 防止头文件被多次包含
#define SAVE_CLASS_H

#include "word_class.h"
#include <iostream>
#include <string> 
#include <vector>
#include <algorithm>
#include <fstream>
using namespace std;

/*
    可改进的地方：
    1. 可以Index[27]记录每个瘦子们第一个出现的索引位置，这样更新字典序的时候不需要遍历字典序前面的单词
    2. 载入单词的时候要查找是否存在，一方面可以考虑哈希表，另一方面也可以运用上面1中的字典序快速寻找
    已改进 3. 更新排名时可以实时查找，所以word类里面可以不用记录排名
*/

struct dict_word{
    string w;
    int index;
    dict_word(string word,int Index){
        w=word;
        index=Index;
    }
    
};

//字典序比较函数
bool cmp_w(dict_word&w1,dict_word&w2);
bool operator==(const dict_word&w1,const dict_word&w2);
bool operator<(const dict_word&w1,const dict_word&w2);

//构建系统类
class Save{
    private:
    int all_word_num;//所有单词数
    int d_word_num;//不重复单词数
    vector<word>words;

    //字典，用于字典排名
    vector<dict_word>dict;

    // 暂未开发
    //记录vector中首字母开头的第一个索引，0就是还没有这个字母的单词载入
    //int Index[27];

    //最大排名
    //int biggestNum;
    // [0]记录排名;
    // [1]记录这个频次的单词有几个
    int numindex[1000000][2];
    
    public:
    friend bool operator==(const dict_word&w1,const dict_word&w2);
    friend bool operator<(const dict_word&w1,const dict_word&w2);
    Save();
    //单词载入系统
    int Insert(string w,int whichinput,int line,int column);
    //获取单词数
    int get_num();
    // 查找单词是否已存在
    int Find(string w);

    
    //更新所有字典序排名,参数为修改的单词，因为只修改后面的单词排名
    void update_dict_Sort(dict_word&w);

    //打印储存的数据
    void Print(int whichinput);

    //读取文本
    void read(string path,int whichinput);
};


#endif 