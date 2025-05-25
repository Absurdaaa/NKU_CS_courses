mpic++ -fopenmp -mavx2 -mfma -o outputfile sourcefile.cpp

# ./outputfile baseline >>all_result.out

# ./outputfile openmp >>all_result.out

# ./outputfile block >>all_result.out

# ./outputfile simd >>all_result.out

# mpirun --allow-run-as-root -np 4 ./outputfile mpi >>all_result.out

# # dcu
hipcc sourcefile_dcu.cpp -o outputfile_dcu

# ./outputfile_dcu >>all_result.out

#!/bin/bash

# 清空日志文件
> resource_usage.log

echo "===== Baseline ====="           >> resource_usage.log
/usr/bin/time -v ./outputfile baseline     2>> resource_usage.log

echo "===== OpenMP ====="             >> resource_usage.log
/usr/bin/time -v ./outputfile openmp       2>> resource_usage.log

echo "===== Block Parallel ====="     >> resource_usage.log
/usr/bin/time -v ./outputfile block        2>> resource_usage.log

echo "===== SIMD ====="               >> resource_usage.log
/usr/bin/time -v ./outputfile simd         2>> resource_usage.log

echo "===== MPI ====="                >> resource_usage.log
/usr/bin/time -v mpirun --allow-run-as-root -np 4 ./outputfile mpi 2>> resource_usage.log

# DCU部分
echo "===== HIP/DCU (before) ====="   >> resource_usage.log
rocm-smi --showuse --showmeminfo vram --showtemp >> resource_usage.log

echo "===== HIP/DCU ====="            >> resource_usage.log
/usr/bin/time -v ./outputfile_dcu 2>> resource_usage.log

echo "===== HIP/DCU (after) ====="    >> resource_usage.log
rocm-smi --showuse --showmeminfo vram --showtemp >> resource_usage.log

echo "资源占用情况已全部记录在 resource_usage.log"