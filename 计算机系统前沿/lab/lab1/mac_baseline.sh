#!/bin/bash

cd "$(dirname "$0")" || exit 1

# 创建保存结果的目录
mkdir -p ./code/mac_baseline_results/raw
mkdir -p ./code/mac_baseline_results/tmp

# 记录 Mac 测试环境信息
sw_vers > ./code/mac_baseline_results/system_info.txt
system_profiler SPHardwareDataType >> ./code/mac_baseline_results/system_info.txt
system_profiler SPNVMeDataType >> ./code/mac_baseline_results/system_info.txt

# 创建 5G 测试文件
rm -f ./code/mac_baseline_results/tmp/mac_fio_test_file.bin
mkfile 5g ./code/mac_baseline_results/tmp/mac_fio_test_file.bin

# benchmark基准测试
# 顺序读测试：读取 5G 测试文件，输出顺序读原始结果
./tools/fio-3.39/fio --name=seq_read --ioengine=pvsync --rw=read --bs=4k --size=5g --numjobs=1 --iodepth=1 --filename="./code/mac_baseline_results/tmp/mac_fio_test_file.bin" \
--output-format=json --output="./code/mac_baseline_results/raw/seq_read.json"

# 顺序写测试：写入 5G 测试文件，输出顺序写原始结果
./tools/fio-3.39/fio --name=seq_write --ioengine=pvsync --rw=write --bs=4k --size=5g --numjobs=1 --iodepth=1 --filename="./code/mac_baseline_results/tmp/mac_fio_test_file.bin" \
--output-format=json --output="./code/mac_baseline_results/raw/seq_write.json"

# 随机读测试：随机读取 5G 测试文件，输出随机读原始结果
./tools/fio-3.39/fio --name=rnd_read --ioengine=pvsync --rw=randread --bs=4k --size=5g --numjobs=1 --iodepth=1 --filename="./code/mac_baseline_results/tmp/mac_fio_test_file.bin" \
--output-format=json --output="./code/mac_baseline_results/raw/rnd_read.json"

# 随机写测试：随机写入 5G 测试文件，输出随机写原始结果
./tools/fio-3.39/fio --name=rnd_write --ioengine=pvsync --rw=randwrite --bs=4k --size=5g --numjobs=1 --iodepth=1 --filename="./code/mac_baseline_results/tmp/mac_fio_test_file.bin" \
--output-format=json --output="./code/mac_baseline_results/raw/rnd_write.json"
