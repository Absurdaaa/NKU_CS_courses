### 我们这里提供两种方法的编译指令：（具体看实验报告）
* 方法一（稀疏矩阵优化）：
```
g++  -std=c++17  -O2 ./pagerank2.cpp -o ./pagerank1.exe
```

* 方法二（分块矩阵优化）：
```
g++  -std=c++17  -O2 ./pagerank2.cpp -o ./pagerank2.exe
```