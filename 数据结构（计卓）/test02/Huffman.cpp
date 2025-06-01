#include<iostream>
#include<fstream>
#include<vector>
#include<algorithm>
#include <bitset>
#include <string>
using namespace std;

class point{
public:
    unsigned char a;
    int ascii;             //ascii码
    int num;                //出现次数
    point *left;
    point *right;
    string code_asscii;     //编码
    

    point()
    {
        a='\0';
        ascii = -1;
        num=0;
        left = nullptr;
        right = nullptr;
        code_asscii="";
    }

    //纯次数节点的构造函数
    point(int n){
        num=n;
        a = '\0';
        ascii=-1;
        left = nullptr;
        right = nullptr;
        code_asscii = "";
    }
    
    //字符节点的构造函数
    point(char a,int n){
        this->a=a;
        ascii=int(a);
        num=n;
        left = nullptr;
        right = nullptr;
        code_asscii = "";
    }
    
    bool operator>(const point&p2){
    return this->num>p2.num;
    }
};


class Huffman
{
public:
    point *head;    //根节点
    int num_ascii[129];//保存字符出现次数
    string code_asscii[129];//保存编码，遍历树时生成
    Huffman();
    int len;
    int maxnum;

    //输入文件名读取文件搭建树
    void build_tree(string file_name);
    //遍历树得到编码
    void run_tree(point *p);
    //打印结果
    void Print(string output_name);
    //编码
    void code(string file_name, string code_file_name);
    //解码
    void decode(string file_name, string output_name);

    private :
        // 二分查找
        vector<point>::iterator binary_search(vector<point> &vec, int size, int num);
};

Huffman::Huffman(){
    for(int i=0;i<129;i++){
        num_ascii[i]=0;
        code_asscii[i]="";
    }
    head=nullptr;
}

bool cmp(point &p1, point &p2)
{
    return p1.num<p2.num;
}

//二分查找
vector<point>::iterator Huffman::binary_search(vector<point> &v, int size, int num){
    int low=0;
    int high=size-1;
    int mid=0;
    vector<point>::iterator it=v.begin();
    
    while (low <= high)
    {
        mid=low+(high-low)/2; // 防止溢出
        if(low==high){
            it=v.begin()+low;
            return it;
        }
        else if(v[mid].num<num){low=mid+1;}
        else if (v[mid].num >= num){high = mid - 1;}
    }
    return v.begin() + low;
}

void Huffman::build_tree(string file_name)
{
    //读取文件
    ifstream infile(file_name);
    string line;
    //读取每个符号的频次
    while(getline(infile,line)){
        for(int i=0;i<line.length();i++){
            num_ascii[int(line[i])]++;
        }
        num_ascii[int('\n')]++;
    }

    vector<point>point_sort;
    // 设立子叶;
    for (int i = 1; i < 128;i++){
        //对于次数为0的字符，不创建子叶
        // if(num_ascii[i]==0){
        //     point *new_point = new point(char(i),0);
        //     continue;
        // };
        point * new_point =new point(char(i),num_ascii[i]);
        //放进容器里面
        point_sort.push_back(*new_point);
    }
    sort(point_sort.begin(),point_sort.end(),cmp);
    
    int size=point_sort.size();
    while(size>1){
        point *p1=new point(point_sort.front());
        point_sort.erase(point_sort.begin());
        point *p2 = new point(point_sort.front());
        point_sort.erase(point_sort.begin());
        //创建次数节点
        point* p3=new point(p1->num+p2->num);
        //构造树
        p3->left=p1;
        p3->right=p2;
        cout<<p2->ascii<<p1->ascii<<endl;
        
        //二分查找插入地方
        if(point_sort.empty()){
            point_sort.push_back(*p3);
            break;
        }
        vector<point>::iterator it = binary_search(point_sort,size-2,p3->num);
        point_sort.insert(it+1,*p3);
        size--;
    }
    
    head=&(point_sort.front());
    point_sort.pop_back();
}

void Huffman::run_tree(point*p){
    if(p->ascii!=-1){
        code_asscii[p->ascii]=p->code_asscii;
        return;
    }

    if (p->left != nullptr)
    {
        point *p1 = p->left;
        p1->code_asscii = p->code_asscii + '0';
        run_tree(p1);
    }

    if (p->right != nullptr)
    {
        point *p2 = p->right;
        p2->code_asscii = p->code_asscii + '1';
        run_tree(p2);
    }
}

// 打印结果
void Huffman::Print(string output_name)
{
    std::ofstream outfile(output_name);
    for(int i=1;i<129;i++){
        outfile << "ascii编码为：" << i << " 出现次数为：" << num_ascii[i]
                << "哈夫曼编码为：" << code_asscii[i] << endl;
    }
}

void Huffman::code(string file_name,string code_file_name){
    // 读取文件
    ifstream infile(file_name);
    std::ofstream outfile(code_file_name, std::ios::binary);
    string line;
    string total="";
    while (getline(infile, line))
    {
        if(total!=""){
            total += code_asscii[int('\n')];
        }
        for (int i = 0; i < line.length(); i++)
        {
            total+=code_asscii[int(line[i])];
        }
        
    }
    std::bitset<8>bitBuffer; // 用于存储当前字节的比特位
    int bitCount = 0;
    len=total.length();
    std::bitset<32> bits(len); // 64位表示 long long
    string l = bits.to_string();
    cout<<l<<endl;
    total=l+total;
    for (int i=0;i<total.length();i++)
    {
        unsigned char bit=total[i];
        // 将每个比特写入缓冲区
        bitBuffer[bitCount] = (bit == '1') ? 1 : 0; // 将比特添加到缓冲区
        bitCount++;

        // 如果缓冲区满了（8个比特），则写入文件
        if (bitCount == 8)
        {
            unsigned char byte = static_cast<unsigned char>(bitBuffer.to_ulong());
            outfile.write(reinterpret_cast<const char *>(&byte), sizeof(byte)); // 写入字节
            bitCount = 0;                                                       // 重置比特计数
        }
    }

    //如果有剩余的比特未写入，处理最后的部分
    if (bitCount > 0)
    {
        unsigned char byte = static_cast<unsigned char>(bitBuffer.to_ulong());
        outfile.write(reinterpret_cast<const char *>(&byte), sizeof(byte));
    }
    // 关闭文件
    infile.close();
    outfile.close();

    std::ofstream outfile2("解码前的01字符串.txt");
    outfile2 << total;
    outfile2.close();
}

void Huffman::decode(string file_name, string output_name){
    ifstream infile(file_name, std::ios::binary);
    std::ofstream outfile(output_name);
    if (!outfile)
    {
        std::cerr << "无法打开输出文件: " << output_name << std::endl;
        return;
    }
    if (!infile)
    {
        std::cerr << "无法打开文件: " << file_name << std::endl;
        return;
    }

    std::string bitString="";
    unsigned char byte;
    // 读取文件直到结尾
    // while (infile.read(reinterpret_cast<char *>(&byte), sizeof(byte)))
    // {
    //     // 如果当前字节是'a'
    //     if (byte == 'a')
    //     {
    //         // 读取'a'后面的所有字节
    //         while (infile.read(reinterpret_cast<char *>(&byte), sizeof(byte)))
    //         {
    //             bitString += byte; // 追加到字符串
    //         }
    //         break; // 读取完'a'后面的内容后退出循环
    //     }

    //     // 只追加数字字符到数字部分
    //     if (std::isdigit(byte))
    //     {
    //         l += byte;
    //     }
    // }
    // cout << l << endl;
    // long long len2 = std::stoll(l);
    int len2;
    string l;
    for(int i=0;i<32;i++){
        infile.read(reinterpret_cast<char *>(&byte), sizeof(byte));
        l+=byte;
    }
    cout<<l<<endl;

    while (infile.read(reinterpret_cast<char *>(&byte), sizeof(byte)))
    {
        for (int i = 0; i<=7 ; ++i)
        {
            bitString += (byte & (1 << i)) ? '1' : '0'; // 逐位检查
        }
    }
    
    std::ofstream outfile2("解码后的01字符串.txt");
    outfile2 << bitString;
    outfile2.close();
    
    point *current = head;
    for(int i=0;i<len;i++){
        char bit=bitString[i];
        point *lastcurrent =current;
            if (bit == '0')
        {
            current=current->left;
        }
        else if(bit=='1'){
            current=current->right;
        }
        else{
            cout<<"WTF!!!"<<endl;
            return;
        }
        if(current==nullptr){
            cout << "WTF!!!" << endl;
            return;
        }
        
        if(current->ascii!=-1){
            outfile << current->a;
            current = head;
        }
    }
    infile.close();
    outfile.close();

}