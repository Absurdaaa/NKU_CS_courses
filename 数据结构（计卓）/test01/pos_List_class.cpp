#include "pos_List_class.h"




pos_List::pos_List(){
        pos_num=0;
        head=NULL;
        tail=NULL;
    }
//pos_List类的成员函数
void pos_List::add(int whichinput,int line,int column){
    //初始化新位置
    pos* new_pos=new pos;
    new_pos->line=line;
    new_pos->whichinput=whichinput;
    new_pos->column=column+1;
    new_pos->next=NULL;
    if(head==NULL){
        head=new_pos;
        tail=new_pos;
    }
    else{
        tail->next=new_pos;
        tail=new_pos;
    }
    return;
}

string pos_List::Print(){
    pos*p=head;
    string ans;
    while(p!=NULL){
        ans+="("+to_string(p->whichinput)+","+to_string(p->line)+","+to_string(p->column)+")"+";";
        p=p->next;
    }
    //cout<<ans<<endl;
    return ans;
}