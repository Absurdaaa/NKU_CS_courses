#include "word_class.h"

//构造函数
   word::word(string w1,int Index1,int num_sort1,int dict_sort1){
        this->w=w1;
        this->Index=Index1;
        this->num_Sort=num_sort1;
        this->dict_Sort=dict_sort1;
        num=1;
    }
    // 修改频次排名
    void word::change_num_Sort(int num){
        this->num_Sort=num;
    }