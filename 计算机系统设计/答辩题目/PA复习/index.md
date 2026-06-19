# PA 复习索引

> 代码根目录：`/Users/linshangjin/Desktop/PA/ics2017/`

## 各 PA 笔记

| 文件 | 内容 |
|------|------|
| [PA0.md](PA0.md) | 环境配置、Docker、Git 工作流 |
| [PA1.md](PA1.md) | TRM、简易调试器、表达式求值、监视点 |
| [PA2.md](PA2.md) | 指令实现（取指译码执行）、RTL、IOE（串口/VGA/键盘/时钟） |
| [PA3.md](PA3.md) | 异常控制流、中断机制、系统调用、文件系统 |
| [PA4.md](PA4.md) | 虚拟内存（分页）、分时多任务、外部中断 |

---

## 高频考点速查

### 宏开关 → 调用链

| 宏 | 位置 | 开启后效果 |
|----|------|-----------|
| `HAS_IOE` | `nemu/include/common.h` | `init_device()` 初始化串口/VGA/键盘/时钟 |
| `HAS_ASYE` / `HAS_ASYE` 在 nanos-lite | `nanos-lite/src/main.c` 中 `#define HAS_ASYE` | 调用 `init_irq()` → `_asye_init()` → 准备 IDT，注册事件处理函数 |
| `DIFF_TEST` | `nemu/include/common.h` | 启动 QEMU，`difftest_step()` 每条指令后对比寄存器 |
| `DEBUG` | `nemu/include/common.h` | 开启 `Log()` 等调试宏输出 |
| `ENABLE_LOOP_DETECTOR` | `nemu/src/monitor/cpu-exec.c` | 死循环检测（默认 0，改为 1 开启） |

### 关键代码位置

| 功能 | 文件 | 函数/符号 |
|------|------|----------|
| CPU 主循环 | `nemu/src/monitor/cpu-exec.c` | `cpu_exec()` |
| 指令译码执行入口 | `nemu/src/cpu/exec/exec.c` | `exec_wrapper()` → `exec_real()` → `idex()` |
| opcode 查找表 | `nemu/src/cpu/exec/exec.c` | `opcode_table[512]` |
| call/ret/jmp 实现 | `nemu/src/cpu/exec/control.c` | `make_EHelper(call/ret/jmp)` |
| 中断触发 | `nemu/src/cpu/intr.c` | `raise_intr()` |
| 串口 | `nemu/src/device/serial.c` | `serial_io_handler()` / `init_serial()` |
| VGA | `nemu/src/device/vga.c` | `init_vga()` / `update_screen()` |
| 调试器 UI | `nemu/src/monitor/debug/ui.c` | `ui_mainloop()` |
| 表达式求值 | `nemu/src/monitor/debug/expr.c` | `expr()` / `make_token()` |
| 监视点 | `nemu/src/monitor/debug/watchpoint.c` | `new_wp()` / `free_wp()` |
| 异常处理（AM层） | `nexus-am/am/arch/x86-nemu/src/asye.c` | `irq_handle()` / `_asye_init()` |
| 陷阱帧构造 | `nexus-am/am/arch/x86-nemu/src/trap.S` | `asm_trap()` |
| 系统调用分发 | `nanos-lite/src/syscall.c` | `do_syscall()` |
| 事件分发 | `nanos-lite/src/irq.c` | `do_event()` |
| 文件系统 | `nanos-lite/src/fs.c` | `fs_open/read/write/close/lseek()` |
| loader | `nanos-lite/src/loader.c` | `loader()` |
