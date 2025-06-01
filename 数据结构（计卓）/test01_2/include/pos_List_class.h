#ifndef POS_LIST_CLASS_H  // 防止头文件被多次包含
#define POS_LIST_CLASS_H

#include <iostream>
#include <string> 
using namespace std;

// 位置
struct pos{
    int whichinput;
    int line;
    int column;
    pos* next;
};

class pos_List{
    public:
    int pos_num;
    pos*head;
    pos*tail;
    pos_List();
    void add(int whichinput,int line,int column);
    string Print();
};


#endif 