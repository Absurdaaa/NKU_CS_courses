#ifndef WORD_CLASS_H  // 防止头文件被多次包含
#define WORD_CLASS_H

#include <iostream>
#include <string> 
#include "pos_List_class.h"
using namespace std;


class word{
    public:
    //频次
    int num;
    //系统中的索引
    int Index;
    //频次排名
    int num_Sort;
    //字典序排名
    int dict_Sort;
    //单词字符串
    string w;
    //位置链表
    pos_List L;
    //构造函数
    word(string w1,int Index1=0,int num_sort1=0,int dict_sort1=0);
    // 修改频次排名
    void change_num_Sort(int num);
};

#endif 