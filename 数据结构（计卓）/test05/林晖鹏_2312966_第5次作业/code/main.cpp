/*
 *考虑相同的类型行数最多的，然后考虑k的奇偶
 *最多100行，所以最多100种状态
 *状态可以用哈西表示，比如二进制之类
 */
#include <iostream>
#include <list>
using namespace std;
int N, M, K;

// 定义哈希表大小
const int TABLE_SIZE = 100;
// 定义键值对的结构体
struct KeyValuePair
{
    int key;
    int value;
    KeyValuePair(const int &k, int v) : key(k), value(v) {}
};
class HashTable
{
private:
    // 哈希表数组，每个元素是一个链表，存储键值对
    list<KeyValuePair> table[TABLE_SIZE];
    int MaxAns;

    // 哈希函数，将字符串键映射到表的索引
    int hashFunction(const int key)
    {
        return key%100;
    }

public:
    HashTable(){
        MaxAns=0;
    }
        // 插入或 更新键值对 到哈希表
        void
        insert(const int key1)
    {
        int index = hashFunction(key1);
        // 遍历链表，检查键是否已存在
        for (list<KeyValuePair>::iterator it = table[index].begin(); it != table[index].end(); it++)
        {
            KeyValuePair &pair1 = *it;
            if (pair1.key == key1)
            {
                pair1.value++; // 更新现有键的值
                if (pair1.value > MaxAns)
                {
                    MaxAns = pair1.value;
                    cout<<MaxAns<<" update"<<endl;
                }
                // printTable();
                return;
            }
        }
        // 如果键不存在，则插入新的键值对
        table[index].push_back(KeyValuePair(key1, 1));
        MaxAns = MaxAns==0?1:MaxAns;
        //cout << MaxAns << " update" << endl;
        // cout<<"插入新值"<<endl;
        // printTable();
    }

    // // 查找键对应的值
    // int search(const int key)
    // {
    //     int index = hashFunction(key);
    //     // 遍历链表，查找键
    //     for (list<KeyValuePair>::iterator it = table[index].begin(); it != table[index].end(); it++)
    //     {
    //         KeyValuePair pair = *it;
    //         if (pair.key == key)
    //         {
    //             return pair.value;
    //         }
    //     }
    //     return -1; // 未找到键
    // }

    // 打印哈希表
    void printTable()
    {
        for (int i = 0; i < TABLE_SIZE; i++)
        {
            if (table[i].size()==0)
            {
                //cout<<"continue"<<endl;
                continue;
                }
                for (list<KeyValuePair>::iterator it = table[i].begin(); it != table[i].end(); it++)
                {
                    KeyValuePair pair = *it;
                    cout << "[" << pair.key << ": " << pair.value << "]->";
                }
            cout<<endl;
        }
    }
    int ans(){
        return MaxAns;
    }
};


int main()
{
    HashTable Hash;
    cin >> N >> M >> K;
    int p = K % 2;
    for (int i = 1, x = 0; i <= N; i++)
    {
        int tow = 1;
        int k = 0; // 记录1的个数
        int num = 0; //二进制转十进制
        for (int j = 1; j <= M; j++)
        {
            cin >> x;
            num += tow * x;
            tow *= 2;
            k += x;
        }
        k = M - k; // 变成0的个数
        if (k % 2 == p && k<=K)
        { // 如果奇偶和k的一样，则计入v
            Hash.insert(num);
        }
    }
    //Hash.printTable();
    cout<< Hash.ans() << endl;
    return 0;
}