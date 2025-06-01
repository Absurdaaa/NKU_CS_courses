#include"Save_class.h"

bool operator==(const dict_word&w1,const dict_word&w2){
        if(w1.index==w2.index&&w1.w==w2.w)return true;
        return false;
    }
bool operator<(const dict_word&w1,const dict_word&w2){
    return w1.w < w2.w;
    }
Save::Save(){
        all_word_num=0;
        d_word_num=0;
    }

    //Save类的成员函数
int Save::Insert(string w,int whichinput,int line,int column){
    all_word_num++;
    //查找是否已记录
    int index=Find(w);
    //如果未记录
    if(index==-1){
        index=d_word_num++;
        word new_w(w,index);
        words.push_back(new_w);
        words[index].Index=index;
        words[index].num=1;
        words[index].w=w;
        words[index].L.add(whichinput,line,column);
        
        numindex[1][1]++;//频次唯一的单词数加一
        numindex[0][0]++;//频次为0的单词排位加一
        if(numindex[1][0]==0)numindex[1][0]=1;

        //放进字典里面
        dict_word new_dict_word(w,index);
        vector<dict_word>::iterator it=lower_bound(dict.begin(),dict.end(),new_dict_word);
        dict.insert(it,new_dict_word);
        //更新字典序排名
        update_dict_Sort(new_dict_word);
    }
    else{//如果已记录
        words[index].num++;
        words[index].L.add(whichinput,line,column);

        // 更新频次排名
        numindex[words[index].num-1][1]-=1;
        numindex[words[index].num-1][0]+=1;
        numindex[words[index].num][1]+=1;
        if(numindex[words[index].num][0]==0){
            numindex[words[index].num][0]=1;
        }

        //更新排名，不必须，可以实时查找
        //而且没有意义，因为原本相同排名的函数，都变大了一，但是要遍历查找，不如直接sort，所以没意义
        //words[index].num_Sort=numindex[words[index].num][0];

    }
    //所有单词数加一
    all_word_num++;
    return index;
}

int Save::get_num(){
    return all_word_num;
}

int Save::Find(string w){
    int index=0;
    // 遍历查找
    for(vector<word>::iterator it=words.begin();!words.empty()&&it!=words.end();it++){
        if(it->w==w){return index;}
        index++;
    }
    return -1;
}

bool cmp_w(dict_word&w1,dict_word&w2){
    return bool(w1.w<w2.w);
}

void Save::update_dict_Sort(dict_word&w){
    vector<dict_word>::iterator it=lower_bound(dict.begin(),dict.end(),w);
    int new_num_Sort=distance(dict.begin(),it)+1;
    //只修改这个排名后的单词的排名
    for(;it!=dict.end();it++){
        int index=it->index;
        words[index].dict_Sort=new_num_Sort;
        new_num_Sort+=1;
    }
    return;
}

void Save::Print(int whichinput){
    string filename = "out" + to_string(whichinput+1) + ".txt";
        ofstream outFile(filename);
    if (!outFile) {
        cerr << "无法打开文件!" << endl;
        return; // 退出程序，返回错误
    }

    // 使用迭代器遍历 dict 并写入文件
    for (vector<dict_word>::iterator it = dict.begin(); it != dict.end(); it++) {
        outFile << it->w << ";"; // 写入字典的单词
        outFile << words[it->index].num << ";"; // 写入对应的 num
        // 这里使用一个简单的方法将 Print 的内容写入文件
        // 你可能需要修改 Print 方法来支持文件输出
        outFile << words[it->index].L.Print() ; // Print 返回一个字符串
        outFile << endl; // 换行
    }
    }

//读取文本
void Save::read(string path,int whichinput){
    //读取文件
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
                //std::cout<<w<<endl;
                //记录单词
                this->Insert(w,whichinput,count,i);
                //找下一个单词
                i=j;
            }
        }
    }
}