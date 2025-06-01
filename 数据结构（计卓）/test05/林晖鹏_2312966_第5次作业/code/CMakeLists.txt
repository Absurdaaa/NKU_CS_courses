cmake_minimum_required(VERSION 3.10)   # 指定最低 CMake 版本

project(test05)          # 定义项目名称和版本

# 设置 C++ 标准为 C++11
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# set(CMAKE_C_COMPILER "/usr/local/bin/gcc-14")   # 修改为你的 gcc 路径
# set(CMAKE_CXX_COMPILER "/usr/local/bin/g++-14")  # 修改为你的 g++ 路径

# 添加头文件搜索路径
include_directories(${PROJECT_SOURCE_DIR}/include)

# 添加源文件
# add_library(printhello.cpp)        # 创建一个库目标 MyLib
add_executable(test05 main.cpp )  # 创建一个可执行文件目标 Main

# 链接库到可执行文件
# target_link_libraries(main)