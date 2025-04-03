# 仅供运行时测试使用，与最终测试时使用的代码可能存在不同
# 可能需要修改部分代码以适应不同的编译器
# 目前为 g++ 编译器

import psutil
import subprocess
import time
import sys
import os

def compile_cpp(cpp_file, output_file=None, compiler="g++", compile_flags='',optimize_flag='-O2'):
    if output_file is None:
        output_file = os.path.splitext(cpp_file)[0] + ".exe"
    
    compile_flags_list = compile_flags.split()
    compile_cmd = [compiler] + compile_flags_list + [cpp_file, "-o", output_file]
    
    if optimize_flag:
        compile_cmd.append(optimize_flag)
    
    try:
        result = subprocess.run(compile_cmd, check=True, capture_output=True, text=True)
        print("compile successfully!")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"error:\n{e.stderr}")
        sys.exit(1)

def monitor_memory(executable_path, *args):
    cmd = [executable_path] + list(args)
    start_time = time.time()
    process = subprocess.Popen(cmd)
    p = psutil.Process(process.pid)
    max_memory = 0
    try:
        while process.poll() is None:
            try:
                memory_info = p.memory_info()
                memory_used = memory_info.rss / (1024 * 1024)
                
                max_memory = max(max_memory, memory_used)
                
                print(f"\r memory used:{memory_used:.2f} MB, Maximum: {max_memory:.2f} MB", end="")
                
                time.sleep(0.1)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                break
    except KeyboardInterrupt:
        print("\n KeyboardInterrupt")
        process.kill()
    
    process.wait()
    
    end_time = time.time()
    run_time = end_time - start_time
    
    print(f"\n Time elapsed: {run_time:.2f} s")
    print(f"Maximum: {max_memory:.2f} MB")
    
    with open("memory_usage_log.txt", "a", encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {os.path.basename(executable_path)}\n")
        f.write(f"Maximum: {max_memory:.2f} MB\n")
        f.write(f"Time: {run_time:.2f} 秒\n\n")
    
    return max_memory, run_time

def main():
    cpp_file,prog_args='',''
    if len(sys.argv) < 2:
        cpp_file='pagerank.cpp'
        prog_args=''
    
    else:
        cpp_file = sys.argv[1]
        prog_args = sys.argv[2:]
    
    if not os.path.exists(cpp_file):
        print(f"path '{cpp_file}' invalid")
        sys.exit(1)
        
    compiler = os.environ.get("CXX", "g++")
    compile_flags = os.environ.get("CXXFLAGS", "-fopenmp -mavx2")
    
    executable = compile_cpp(cpp_file, compiler=compiler, compile_flags=compile_flags)
    
    total_memory = 0
    epochs = 10
    
    for i in range(epochs):
        max_memory, run_time = monitor_memory(executable, *prog_args)
        total_memory += max_memory
        
    avg_memory = total_memory / epochs
    with open("memory_usage_log.txt", "a", encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {os.path.basename(cpp_file)} - avg ({epochs} epoches)\n")
        f.write(f"avg mm used: {avg_memory:.2f} MB\n\n")

if __name__ == "__main__":
    main()