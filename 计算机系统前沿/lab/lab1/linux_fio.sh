# benchmark基准测试
fio --name=seq_read --ioengine=pvsync --rw=read --bs=4k --size=5G --numjobs=1 --iodepth=1 --filename="./fio_test_file" \
> ./benchmark/seq_read_result.txt

fio --name=seq_write --ioengine=pvsync --rw=write --bs=4k --size=5G --numjobs=1 --iodepth=1 --filename="./fio_test_file" \
> ./benchmark/seq_write_result.txt


fio --name=rnd_read --ioengine=pvsync --rw=randread --bs=4k --size=5G --numjobs=1 --iodepth=1 --filename="./fio_test_file" \
> ./benchmark/rnd_read_result.txt


fio --name=rnd_write --ioengine=pvsync --rw=randwrite --bs=4k --size=5G --numjobs=1 --iodepth=1 --filename="./fio_test_file" \
> ./benchmark/rnd_write_result.txt



#!/bin/bash

# 测试文件路径
TEST_FILE="./fio_test_file"
RESULT_FILE="./cmp/fio_combined_results.txt"

# 清空文件，确保每次测试前文件为空
dd if=/dev/zero of=$TEST_FILE bs=1M count=5120 oflag=direct
> $RESULT_FILE  # 清空结果文件

# 测试块大小（bs）列表
BLOCK_SIZES=("4k" "8k" "16k" "32k" "64k" "128k")

# 并发线程数和队列深度组合
NUMJOBS=("1" "4" "8")
IODEPTH=("1" "16" "64")

# I/O 引擎类型
IOENGINES=("pvsync" "libaio" "io_uring" "mmap")

# 1. 块大小（bs）变化测试
echo "Starting block size tests..." | tee -a $RESULT_FILE

for bs in "${BLOCK_SIZES[@]}"; do
    echo "Running test with block size: $bs" | tee -a $RESULT_FILE
    fio --name=seq_read_bs_$bs --ioengine=pvsync --rw=read --bs=$bs --size=5G --numjobs=1 --iodepth=1 --filename=$TEST_FILE | tee -a $RESULT_FILE
    fio --name=seq_write_bs_$bs --ioengine=pvsync --rw=write --bs=$bs --size=5G --numjobs=1 --iodepth=1 --filename=$TEST_FILE | tee -a $RESULT_FILE
    fio --name=rnd_read_bs_$bs --ioengine=pvsync --rw=randread --bs=$bs --size=5G --numjobs=1 --iodepth=1 --filename=$TEST_FILE | tee -a $RESULT_FILE
    fio --name=rnd_write_bs_$bs --ioengine=pvsync --rw=randwrite --bs=$bs --size=5G --numjobs=1 --iodepth=1 --filename=$TEST_FILE | tee -a $RESULT_FILE
done

# 2. 并发线程数和队列深度（numjobs & iodepth）测试
echo "Starting numjobs and iodepth tests..." | tee -a $RESULT_FILE

for numjobs in "${NUMJOBS[@]}"; do
    for iodepth in "${IODEPTH[@]}"; do
        echo "Running test with numjobs=$numjobs and iodepth=$iodepth" | tee -a $RESULT_FILE
        fio --name=seq_read_numjobs_${numjobs}_iodepth_${iodepth} --ioengine=pvsync --rw=read --bs=4k --size=5G --numjobs=$numjobs --iodepth=$iodepth --filename=$TEST_FILE | tee -a $RESULT_FILE
        fio --name=seq_write_numjobs_${numjobs}_iodepth_${iodepth} --ioengine=pvsync --rw=write --bs=4k --size=5G --numjobs=$numjobs --iodepth=$iodepth --filename=$TEST_FILE | tee -a $RESULT_FILE
        fio --name=rnd_read_numjobs_${numjobs}_iodepth_${iodepth} --ioengine=pvsync --rw=randread --bs=4k --size=5G --numjobs=$numjobs --iodepth=$iodepth --filename=$TEST_FILE | tee -a $RESULT_FILE
        fio --name=rnd_write_numjobs_${numjobs}_iodepth_${iodepth} --ioengine=pvsync --rw=randwrite --bs=4k --size=5G --numjobs=$numjobs --iodepth=$iodepth --filename=$TEST_FILE | tee -a $RESULT_FILE
    done
done

# 3. I/O 引擎（ioengine）对比测试
echo "Starting I/O engine tests..." | tee -a $RESULT_FILE

for ioengine in "${IOENGINES[@]}"; do
    echo "Running test with ioengine: $ioengine" | tee -a $RESULT_FILE
    fio --name=seq_read_ioengine_$ioengine --ioengine=$ioengine --rw=read --bs=4k --size=5G --numjobs=1 --iodepth=1 --filename=$TEST_FILE | tee -a $RESULT_FILE
    fio --name=seq_write_ioengine_$ioengine --ioengine=$ioengine --rw=write --bs=4k --size=5G --numjobs=1 --iodepth=1 --filename=$TEST_FILE | tee -a $RESULT_FILE
    fio --name=rnd_read_ioengine_$ioengine --ioengine=$ioengine --rw=randread --bs=4k --size=5G --numjobs=1 --iodepth=1 --filename=$TEST_FILE | tee -a $RESULT_FILE
    fio --name=rnd_write_ioengine_$ioengine --ioengine=$ioengine --rw=randwrite --bs=4k --size=5G --numjobs=1 --iodepth=1 --filename=$TEST_FILE | tee -a $RESULT_FILE
done

echo "All tests completed!" | tee -a $RESULT_FILE