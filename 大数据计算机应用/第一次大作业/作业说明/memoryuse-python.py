# 仅供运行时测试使用，与最终测试时使用的代码可能存在不同
# 可能需要修改部分代码以适应不同的测试环境

default_script_path="pagerank.py"

import psutil
import subprocess
import time
import sys
import os

def monitor_memory(script_path, *args):
    cmd = [sys.executable, script_path] + list(args)
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
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {os.path.basename(script_path)}\n")
        f.write(f"Maximum: {max_memory:.2f} MB\n")
        f.write(f"Time: {run_time:.2f} s\n\n")
    
    return max_memory, run_time

def main():
    total_memory=0
    epochs=10
    for i in range(epochs):
        if len(sys.argv) > 1:
            script_path = sys.argv[1]
            args = sys.argv[2:]
        else:
            script_path = default_script_path
            args = []
        
        if not os.path.exists(script_path):
            print(f"path '{script_path}' invalid")
            sys.exit(1)
        
        max_memory, run_time = monitor_memory(script_path, *args)
        total_memory+=max_memory
    
    outfile=open("memory_usage_avg.txt", "a", encoding='utf-8')
    print(f"file: {script_path} avg maximum mem: {total_memory/epochs:.2f} MB",file=outfile)
    outfile.close()

if __name__ == "__main__":
    main()