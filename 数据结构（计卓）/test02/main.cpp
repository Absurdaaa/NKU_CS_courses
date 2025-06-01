#include<iostream>
#include<string>
#include "Huffman.cpp"
using namespace std;

Huffman hfm;
string file_path;
string output_name;
string output_code_name ;
int main()
{
    file_path = "inputfile1_ascii.txt";
    output_name = "output1.txt";

    hfm.build_tree(file_path);
    hfm.run_tree(hfm.head);
    hfm.Print(output_name);
    
    file_path = "inputfile2_ascii.txt";
    output_code_name = "code_file2.dat";
    hfm.code(file_path, output_code_name);

    file_path = "code_file2.dat";
    output_name = "decode_file2.txt";
    hfm.decode(file_path, output_name);
    cout<<"success"<<endl;

    return 0;
}