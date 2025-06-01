#include <iostream>
#include <fstream>  
#include <string> 
#include <vector>
#include "Save_class.h"

using namespace std;

Save wordSQL;

int main(int argc,char **argv){
    for (int i=1;i<argc;i++){
        wordSQL.read(argv[i],i);
        wordSQL.Print(i-1);
    }
    
    //std::cout<<wordSQL.get_num()<<endl;
    return 0;
}





