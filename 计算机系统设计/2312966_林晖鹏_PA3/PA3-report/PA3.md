# PA3 实验报告

## 1. 实验目标

PA3 的主题是“穿越时空的旅程”，目标是把 NEMU、AM、Nanos-lite 和 Navy-apps 串起来，让系统不再只运行裸机程序，而是能够在 Nanos-lite 上加载并执行用户程序。

当前阶段首先需要完成和理解以下内容：

- 理解 `Nanos-lite` 的启动流程。
- 理解用户程序如何从 `navy-apps` 编译生成，并被打包进 `ramdisk`。
- 实现最小化的 raw program loader。
- 将 `ramdisk` 中的第一个用户程序 `dummy` 加载到正确内存位置。
- 验证 CPU 已经能够跳转到用户程序开始执行。

本阶段的第一个检查点不是直接跑通系统调用，而是看到 `dummy` 执行到一条尚未实现的 `int 0x80` 指令。若能够到达这一现象，就说明 `loader` 已经成功完成了“装载并跳转”这一任务。

## 2. 实现内容

### 2.1 编译第一个用户程序 `dummy`

在 PA3 中，首先需要把 `navy-apps/tests/dummy/dummy.c` 编译成运行在 `Nanos-lite` 上的用户程序。

一开始我在目录：

```text
/home/linshangjin/code/ics2017/navy-apps/tests/dummy
```

下直接执行：

```bash
make
```

此时构建系统尝试生成的是：

```text
build/dummy-native
```

并在链接阶段报错：

```text
undefined reference to '_syscall_'
```

这说明当时程序被编译到了 `native` 目标，而不是 `PA3` 所需要的 x86 用户程序目标，因此构建方向是错误的。

之后改为显式指定 ISA：

```bash
make ISA=x86
```

运行结果中可以看到：

```text
+ LD /home/linshangjin/code/ics2017/navy-apps/tests/dummy/build/dummy-x86
```

这说明 `dummy.c` 已经成功被编译为 x86 用户程序，生成的可执行文件为：

```text
/home/linshangjin/code/ics2017/navy-apps/tests/dummy/build/dummy-x86
```

该文件将作为 `PA3` 中由 `Nanos-lite` 加载执行的第一个用户程序。

### 2.2 更新 `ramdisk`

在生成 `dummy-x86` 之后，需要把它重新打包进 `Nanos-lite` 的 `ramdisk` 中。

操作目录：

```text
/home/linshangjin/code/ics2017/nanos-lite
```

执行命令：

```bash
make update
```

运行结果中可以看到关键命令：

```text
objcopy -S --set-section-flags .bss=alloc,contents -O binary /home/linshangjin/code/ics2017/navy-apps/tests/dummy/build/dummy-x86 build/ramdisk.img
```

这说明刚刚生成的 `dummy-x86` 已经被转换并写入：

```text
build/ramdisk.img
```

因此，后续 `loader()` 只需要从 `ramdisk` 中读取该用户程序，并将其复制到约定的入口地址 `0x4000000` 即可。

需要注意的是，只要 `ramdisk` 中的用户程序发生变化，就必须重新在 `nanos-lite` 目录下执行一次：

```bash
make update
```

否则运行时加载到的仍然是旧版本程序。

### 2.3 实现 raw program loader

`PA3` 的第一个代码任务是在 `Nanos-lite` 中实现最小化的 raw program loader。

涉及文件：

```text
nanos-lite/src/loader.c
nanos-lite/src/ramdisk.c
```

当前阶段的约定非常简单：

- `ramdisk` 中只有一个用户程序。
- 用户程序从 `ramdisk` 偏移 `0` 开始存放。
- 用户程序需要被加载到内存地址 `0x4000000`。

因此 `loader()` 的最小实现逻辑就是：

1. 调用 `get_ramdisk_size()` 获取 `ramdisk` 总大小。
2. 调用 `ramdisk_read(DEFAULT_ENTRY, 0, get_ramdisk_size())`，把整个用户程序复制到 `0x4000000`。
3. 返回 `0x4000000` 作为程序入口。

本次在 `loader.c` 中补上的实现如下：

```c
#include "common.h"

#define DEFAULT_ENTRY ((void *)0x4000000)

void ramdisk_read(void *buf, off_t offset, size_t len);
size_t get_ramdisk_size();

uintptr_t loader(_Protect *as, const char *filename) {
  ramdisk_read(DEFAULT_ENTRY, 0, get_ramdisk_size());
  return (uintptr_t)DEFAULT_ENTRY;
}
```

这一步不涉及文件系统，也不涉及 ELF 解析，而是按照指导书要求，直接把 `ramdisk` 中唯一的用户程序整体搬运到固定入口地址。

### 2.4 运行验证

为了验证 `loader` 是否生效，需要在 `nanos-lite` 目录下运行：

```bash
make ARCH=x86-nemu run
```

这里不能直接使用 `make run`，因为当前工程默认会按 `native` 目标构建，导致跑到错误的平台上。

运行后，`NEMU` 会先进入 monitor，此时需要在提示符下输入：

```text
c
```

继续执行用户程序。

本次继续执行后，终端输出为：

```text
[src/ramdisk.c,26,init_ramdisk] ramdisk info: start = 0x100cec, end = 0x1052c8, size = 17884 bytes
invalid opcode(eip = 0x04001f98): cd 80 5b 5d c3 66 90 90 ...
```

其中机器码：

```text
cd 80
```

正对应 x86 的：

```text
int 0x80
```

这正是当前阶段应当看到的现象，说明：

- `ramdisk` 已经被正确初始化。
- `dummy` 已经被 `loader` 正确复制到 `0x4000000` 附近的用户程序地址空间。
- CPU 已经成功跳转到 `dummy` 并开始执行。
- 当前失败点已经推进到下一阶段，也就是异常、中断和系统调用机制尚未实现。

因此可以认为：**任务 1：实现 raw program loader 已经完成。**

## 3. 关键代码说明

### 3.1 为什么 `loader` 只需要整体复制

当前阶段的用户程序只有一个，即 `dummy`。在 `make update` 之后，构建系统已经把 `dummy-x86` 整体转换成裸二进制并写入 `ramdisk.img`。

因此这一阶段并不需要：

- 遍历文件表
- 查找文件名
- 解析 ELF
- 按段装载程序

只需要把 `ramdisk` 中从偏移 `0` 开始的全部内容复制到指定入口地址即可。

这也是为什么当前 `loader()` 的实现非常短，但仍然是正确的。因为指导书在这一阶段故意把问题简化成“只有一个 raw program”。

### 3.2 为什么看到 `int 0x80` 就说明 `loader` 成功

本阶段的目标并不是立即实现系统调用，而是先验证用户程序是否已经被成功装载并跳转执行。

`dummy` 在运行过程中会执行：

```text
int 0x80
```

如果 `loader` 没有成功，常见现象应当是：

- 跳转到错误地址
- 直接取到非法指令
- 根本进入不了 `dummy`

而现在的现象是：

- 错误位置在 `0x04001f98`
- 指令字节正好是 `cd 80`

这说明 CPU 已经在正确的用户程序代码区执行，只是执行到系统调用入口时，由于异常机制还未实现，才报出了 `invalid opcode`。

因此，“停在未实现的 `int 0x80`”恰恰是本阶段 `loader` 正确工作的证明。

## 4. 测试与运行结果

本阶段使用的主要测试步骤如下：

1. 在 `navy-apps/tests/dummy` 下执行：

```bash
make ISA=x86
```

确认用户程序 `dummy-x86` 成功生成。

2. 在 `nanos-lite` 下执行：

```bash
make update
```

确认 `dummy-x86` 已经被重新写入 `ramdisk.img`。

3. 在 `nanos-lite` 下执行：

```bash
make ARCH=x86-nemu run
```

并在 `NEMU` monitor 中输入：

```text
c
```

4. 最终观察到：

```text
invalid opcode(eip = 0x04001f98): cd 80 ...
```

说明 `loader` 已经成功完成装载与跳转，系统已经推进到下一阶段的异常/系统调用实现。

## 5. 加入 ASYE 的推进情况

在确认 `loader` 已经正确工作之后，下一步开始按照指导书加入 ASYE 支持，目的是让 `Nanos-lite` 在启动时初始化中断描述符表 `IDT`，并为后续的 `int 0x80` 系统调用建立异常入口。

### 5.1 准备 IDT

这一阶段主要完成了以下工作：

- 在 `NEMU` 的 `cpu` 结构体中加入 `CS` 和 `IDTR`
- 实现 `lidt` 指令
- 在 `restart()` 中将 `CS` 初始化为 `0x8`
- 在 `nanos-lite/src/main.c` 中打开 `HAS_ASYE`

这样做的目的，是为了让系统启动后能够执行：

```text
init_irq() -> _asye_init()
```

从而完成 `IDT` 初始化和事件处理函数注册。

### 5.2 实现 `int/raise_intr/iret` 的最小骨架

为继续推进系统调用异常链路，又补上了以下内容：

- 在 `nemu/src/cpu/exec/system.c` 中实现 `int`
- 在 `nemu/src/cpu/intr.c` 中实现 `raise_intr()`
- 在 `nemu/src/cpu/exec/system.c` 中实现 `iret`

当前实现中：

- `int` 指令会调用 `raise_intr()`，而不是在 helper 内直接手写整套中断逻辑
- `raise_intr()` 会根据 `IDTR` 和中断号定位门描述符
- 然后按顺序把 `EFLAGS`、`CS` 和返回地址压栈
- 最后设置跳转目标，让 CPU 进入对应异常入口
- `iret` 负责把 `eip/cs/eflags` 从栈中恢复

### 5.3 当前验证结果

重新执行：

```bash
make ARCH=x86-nemu run
```

并在 `NEMU` monitor 中输入：

```text
c
```

在最开始补上 `CS`、`IDTR`、`lidt`、`HAS_ASYE` 之后，终端输出先推进为：

```text
[src/main.c,20,main] 'Hello World!' from Nanos-lite
[src/main.c,21,main] Build time: ...
[src/ramdisk.c,26,init_ramdisk] ramdisk info: ...
[src/main.c,28,main] Initializing interrupt/exception handler...
invalid opcode(eip = 0x00100af5): 0f 01 18 ...
```

其中：

```text
0f 01 18
```

对应的正是 `lidt` 指令编码。

这说明当前系统已经不再直接停在用户程序中的 `cd 80`，而是已经成功推进到了异常机制初始化阶段，开始执行 `init_irq()` 和 `_asye_init()` 相关路径。  
换句话说，`loader -> 进入 Nanos-lite -> 打开 HAS_ASYE -> 尝试初始化 IDT` 这一条链已经被打通。

目前新的阻塞点变成了：

- `lidt` 所在这条初始化路径仍需继续检查和完善

因此当前阶段可以确认：

- 系统已经成功越过了“用户程序执行到 `int 0x80` 就停住”的旧检查点
- 异常处理链路已经开始生效
- 后续需要继续围绕 `lidt`、异常入口和系统调用分发做进一步完善

### 5.4 修正 `lidt/int/iret` 的入口挂接后继续验证

继续排查后发现，虽然已经在 `system.c` 中实现了 `lidt`、`int` 和 `iret` 的 helper，但 `NEMU` 的 opcode table 里并没有把这些 helper 真正挂接上去：

- `0x0f 0x01 /3` 对应的 `lidt` 没有接到 `gp7`
- `0xcd` 对应的 `int imm8` 没有挂到 `int`
- `0xcf` 对应的 `iret` 也没有挂到 `iret`

此外，`all-instr.h` 中也缺少这几个 helper 的声明，因此即便修改了 opcode table，编译阶段仍然会报 `exec_lidt / exec_int / exec_iret` 未声明。

将这些入口全部补齐之后，再次运行：

```bash
make ARCH=x86-nemu run
```

并在 `NEMU` monitor 中输入：

```text
c
```

终端输出继续推进为：

```text
invalid opcode(eip = 0x00100b12): 60 54 e8 03 ff ff ff 83 ...
```

其中：

```text
60
```

对应的正是 x86 的：

```text
pusha
```

这一步非常关键，因为它说明当前系统已经不再停在：

- 用户程序中的 `int 0x80`
- 也不再停在 `lidt`

而是进一步推进到了：

- `trap.S` 中系统调用异常入口附近的保存现场阶段

结合 `trap.S` 的实现：

```asm
vecsys:  pushl $0;  pushl $0x80; jmp asm_trap
asm_trap:
  pushal
```

可以判断当前新的 `invalid opcode 0x60` 正对应 `pushal/pusha`。  
这说明：

- `int 0x80` 已经被 NEMU 正确识别
- `raise_intr()` 已经完成了基本的中断入口跳转
- CPU 已经成功进入 `vecsys()` 对应的异常入口
- 当前新的阻塞点变成了 `pusha` 尚未实现

因此可以认为：**中断机制的基本跳转链路已经建立成功。**

### 5.5 实现 `pusha` 后推进到 `do_event()`

在进入 `vecsys()` 之后，新的阻塞点是：

```text
invalid opcode(eip = 0x00100b12): 60 54 e8 03 ff ff ff 83 ...
```

其中 `0x60` 对应 `pusha/pushal`。  
根据 `trap.S` 中的实现：

```asm
asm_trap:
  pushal
  pushl %esp
  call irq_handle
```

可以判断此时系统已经进入异常入口，只是因为 `pushal` 尚未实现，导致 trap frame 还不能继续构造。

因此继续补上了：

- `pusha`
- `popa`
- `0x60 / 0x61` 在 opcode table 中的挂接
- 对应 helper 的声明

其中 `pusha` 的实现特别注意了一个细节：  
压入栈中的 `esp` 必须是执行 `pusha` 之前的旧值，而不能是前面几次 `push` 之后已经改变过的值。

完成这一部分后，重新运行：

```bash
make ARCH=x86-nemu run
```

并在 `NEMU` monitor 中输入：

```text
c
```

终端输出推进为：

```text
[src/irq.c,5,do_event] system panic: Unhandled event ID = 3
nemu: HIT BAD TRAP at eip = 0x00100032
```

这说明系统已经完成了如下推进：

- `int 0x80`
- `raise_intr()`
- 跳入 `vecsys()`
- 执行 `asm_trap`
- `pushal` 保存通用寄存器
- `pushl %esp` 传递 trap frame
- `irq_handle()`
- 最终进入 `nanos-lite/src/irq.c` 中的 `do_event()`

也就是说，异常现场已经成功传到了 C 代码中。  
当前新的问题变成了：`do_event()` 读到的事件号是 `3`，而不是后续期望的系统调用事件编号。这通常说明 trap frame 中字段的解释顺序还没有完全对齐，因此下一步需要继续：

- 重新组织 `_RegSet`
- 让它与 `trap.S` 的压栈顺序完全一致
- 再实现系统调用参数宏 `SYSCALL_ARGx`

### 5.6 重组 `_RegSet` 后事件号对齐到指导书现象

继续对照 `trap.S` 的压栈过程：

```asm
vecsys:  pushl $0;  pushl $0x80; jmp asm_trap
asm_trap:
  pushal
  pushl %esp
  call irq_handle
```

可以知道传给 `irq_handle()` 的 trap frame 在内存中的顺序必须和以下内容严格一致：

- `pushal` 保存的 8 个通用寄存器
- `irq`
- `error_code`
- `eip`
- `cs`
- `eflags`

因此重新组织了：

```text
nexus-am/am/arch/x86-nemu/include/arch.h
```

中的 `_RegSet` 成员顺序，并同时补上了系统调用参数宏：

- `SYSCALL_ARG1(r) -> eax`
- `SYSCALL_ARG2(r) -> ebx`
- `SYSCALL_ARG3(r) -> ecx`
- `SYSCALL_ARG4(r) -> edx`

重新运行：

```bash
make ARCH=x86-nemu run
```

并在 `NEMU` monitor 中输入：

```text
c
```

终端输出变为：

```text
[src/irq.c,5,do_event] system panic: Unhandled event ID = 8
nemu: HIT BAD TRAP at eip = 0x00100032
```

这与指导书中给出的参考现象一致，说明：

- trap frame 的布局已经和 `trap.S` 成功对齐
- `irq_handle()` 已经能够从 `_RegSet` 中正确读出事件号
- 异常现场从汇编入口传递到 `do_event()` 这一整条链已经跑通

因此当前可以确认：  
**加入 ASYE、建立 IDT、实现 `int/raise_intr/iret/pusha`、并让 trap frame 传递到 `do_event()` 这一阶段已经完成。**

### 5.7 实现系统调用分发与最小返回路径

在事件号已经能够正确读出为指导书期望的 `8` 之后，下一步继续完成最小的系统调用闭环。

这一阶段补上的内容包括：

1. 在 `nanos-lite/src/irq.c` 中识别 `_EVENT_SYSCALL`，并把它转交给 `do_syscall()`
2. 在 `nanos-lite/src/syscall.c` 中补上：
   - `SYSCALL_ARG1~4` 的实际取值使用
   - `SYS_none`
   - `SYS_exit`
3. 在 `nemu/src/cpu/exec/data-mov.c` 中补上 `popa`，保证异常返回路径完整

其中最关键的两个最小系统调用为：

- `SYS_none`
  - 用于 `dummy` 最先测试“用户态进入内核再返回”的最小闭环
  - 按指导书要求返回 `1`
- `SYS_exit`
  - 在用户程序结束时调用 `_halt(status)` 终止运行

完成后重新运行：

```bash
make ARCH=x86-nemu run
```

并在 `NEMU` monitor 中输入：

```text
c
```

终端输出推进为：

```text
nemu: HIT GOOD TRAP at eip = 0x00100032
```

这说明以下整条链已经跑通：

- 用户程序执行 `int 0x80`
- `NEMU` 通过 `raise_intr()` 进入异常入口
- `vecsys()` 和 `asm_trap()` 构造 trap frame
- `irq_handle()` 把事件传递给 `do_event()`
- `do_event()` 识别系统调用事件
- `do_syscall()` 处理 `SYS_none`
- 返回用户程序继续执行
- 最终 `SYS_exit` 成功使程序正常结束

因此到这一步可以确认：

- `PA3.1` 的最小系统调用闭环已经完成
- `dummy` 已经能够在 `Nanos-lite` 上正常运行并以 `HIT GOOD TRAP` 结束

## 8. 实现 `SYS_write` 并切换到 `hello`

在完成 `PA3.1` 之后，下一步开始实现 `write()` 系统调用，并将 `Nanos-lite` 上运行的用户程序从 `dummy` 切换为 `hello`。

### 8.1 编译 `hello` 用户程序

首先进入：

```text
/home/linshangjin/code/ics2017/navy-apps/tests/hello
```

执行：

```bash
make ISA=x86
```

运行结果中可以看到：

```text
+ LD /home/linshangjin/code/ics2017/navy-apps/tests/hello/build/hello-x86
```

说明 `hello.c` 已经成功编译成面向 x86 的用户程序。

### 8.2 实现 `SYS_write`

为了让 `hello` 中的：

```c
write(1, "Hello World!\n", 13);
```

真正生效，需要同时修改内核和用户态封装两侧。

涉及文件：

```text
nanos-lite/src/syscall.c
navy-apps/libs/libos/src/nanos.c
```

在内核侧，本次先实现最小版本的 `SYS_write`：

- 若文件描述符 `fd` 为 `1` 或 `2`
- 就把缓冲区内容逐字节输出到串口 `_putc()`
- 返回实际写入的字节数 `len`

这已经足够支持 `hello` 程序的标准输出。

在用户态封装侧，原先 `_write()` 还是未实现状态，会直接：

```c
_exit(SYS_write);
```

这显然不是真正的系统调用封装。  
因此改为：

```c
return _syscall_(SYS_write, fd, (uintptr_t)buf, count);
```

这样用户程序调用 `write()` 时，参数就会通过：

- `eax`：系统调用号
- `ebx`：文件描述符
- `ecx`：缓冲区地址
- `edx`：写入长度

进入内核处理。

### 8.3 切换 `ramdisk` 中的唯一用户程序

在这一阶段，`nanos-lite/Makefile` 中 `ramdisk` 的生成规则仍然指向 `dummy`：

```make
OBJCOPY_FILE = $(NAVY_HOME)/tests/dummy/build/dummy-x86
```

为了让系统真正运行 `hello`，需要把它改为：

```make
OBJCOPY_FILE = $(NAVY_HOME)/tests/hello/build/hello-x86
```

这样在执行 `make update` 时，写入 `ramdisk.img` 的就是 `hello` 而不再是 `dummy`。

### 8.4 更新 `ramdisk` 并重新运行

修改完成后，在 `nanos-lite` 目录下执行：

```bash
make update
make ARCH=x86-nemu run
```

进入 `NEMU` monitor 后输入：

```text
c
```

实际运行结果为：

```text
[src/main.c,20,main] 'Hello World!' from Nanos-lite
[src/main.c,21,main] Build time: ...
[src/ramdisk.c,26,init_ramdisk] ramdisk info: ...
[src/main.c,28,main] Initializing interrupt/exception handler...
Hello World!
Hello World for the 2th time
Hello World for the 3th time
Hello World for the 4th time
...
```

这说明：

- `hello-x86` 已经被成功打包进 `ramdisk`
- `loader` 已经成功装载新的用户程序
- `write()` 系统调用已经能够正常把字符串输出到串口
- 用户程序可以持续运行并反复打印内容

因此可以确认：  
**`SYS_write` 的最小实现已经完成，`hello` 程序已经能够在 `Nanos-lite` 上正常输出。**
## 6. 思考题

### 6.1 对比异常与函数调用

函数调用和异常处理都会导致控制流发生跳转，但它们保存现场的范围并不相同。

函数调用时，调用者和被调用者之间是一种“合作关系”。双方都遵守既定的 calling convention，因此哪些寄存器由调用者保存、哪些寄存器由被调用者保存，都是事先约定好的。也正因为如此，函数调用通常只需要保存：

- 返回地址
- 调用约定中要求保护的寄存器
- 必要时再额外保存局部变量相关状态

而异常处理不同。异常发生时，CPU 是在“打断”当前程序的正常执行。此时异常处理代码并不知道：

- 用户程序当前执行到了哪一条指令
- 哪些通用寄存器里放着仍然有用的数据
- 当前标志位寄存器 `EFLAGS` 处于什么状态
- 这次异常是由什么原因触发的

因此，为了保证异常处理结束之后还能完整恢复现场，必须保存的信息会更多，至少包括：

- `EIP`
- `CS`
- `EFLAGS`
- 异常号 `irq`
- 错误码 `error_code`
- 通用寄存器现场

从本质上看，函数调用是程序主动、受约束地切换到另一个过程；而异常处理是系统被动、异步地接管当前执行流。正因为异常是“被打断”的场景，所以它必须保存比普通函数调用更完整的现场。

### 6.2 trap.S 中 `pushl %esp` 的作用

`trap.S` 中有一行看起来比较奇怪的代码：

```asm
pushl %esp
call irq_handle
```

乍看之下，它像是在把栈顶指针自己再压一遍，好像没有实际意义。但结合前后的代码就可以理解，它其实是在做一件很普通的事情：**把当前 trap frame 的首地址作为参数传给 C 函数 `irq_handle()`**。

在 `vecsys()` 和 `asm_trap()` 中，栈上已经依次保存了：

- 硬件自动压入的 `EFLAGS`、`CS`、`EIP`
- `vecsys` 手动压入的 `error_code` 和 `irq`
- `pushal` 保存的全部通用寄存器

当执行完 `pushal` 之后，此时 `%esp` 正好指向这整块 trap frame 的起始位置。  
再执行：

```asm
pushl %esp
```

就相当于把“这块 trap frame 的地址”压栈。随后：

```asm
call irq_handle
```

按照普通的 C 函数调用约定，这个被压栈的地址就会作为第一个参数传给 `irq_handle(_RegSet *tf)`。

因此，这里的 `pushl %esp` 并不诡异，它本质上就是：

- 利用当前 `%esp` 已经指向 trap frame
- 把 trap frame 的地址作为参数传入 C 代码

也就是说，`irq_handle()` 拿到的 `tf`，其实就是“当前异常现场的指针”。

### 6.3 为什么 `push imm8` 需要符号扩展

在阅读 `trap.S` 时还会注意到，`vecsys()` 中有：

```asm
pushl $0
pushl $0x80
```

这里提醒了一个容易忽略的细节：`push imm8` 在 x86 中需要做符号扩展。

原因是 `push` 在 32 位模式下压栈的单位始终是 4 字节，即使立即数只有 8 位，CPU 在真正压栈前也会先把它扩展成 32 位数，再写入栈中。  
如果不做符号扩展，那么：

- 对正数可能暂时看不出问题
- 但对于像 `-1` 这样的立即数，就会把 `0xff` 错当成 `0x000000ff`

这会直接影响：

- trap frame 中 `irq` 或错误码的值
- 后续 `irq_handle()` 对事件类型的判断

因此实现 `push imm8` 时，必须按照 x86 语义对立即数先进行符号扩展，再执行压栈。

## 7. 当前进度与后续计划

截至目前，PA3 的第一项任务已经完成，即：

- 成功编译第一个用户程序 `dummy`
- 成功更新 `ramdisk`
- 成功实现 `loader`
- 成功验证用户程序已经开始执行

接下来将继续实现：

- IDTR
- `lidt`
- `int`
- `raise_intr`
- `iret`
- 系统调用参数传递

目标是让当前停在 `int 0x80` 的执行路径能够继续向前推进，最终完成异常、中断和系统调用机制的最小闭环。

## 9. 实现 `SYS_brk` 与用户层 `_sbrk`

在 `SYS_write` 跑通之后，继续阅读指导书可以发现，`hello` 虽然已经能输出，但此时 `printf()` 仍然很可能是退化成“逐字符调用 `write()`”的方式在工作。根本原因是用户层的堆区管理还没有打通。

### 9.1 为什么还需要 `SYS_brk`

`malloc()/free()` 负责管理用户程序堆区里的内存块，但“堆区到底能有多大”这件事，本质上还是在调整用户程序可用的地址空间范围，因此需要通过系统调用向操作系统申请。

在 `Navy-apps` 的 `newlib` 中，`malloc()` 最终会用到 `sbrk()`。而 `sbrk()` 又会继续调用 `libos` 里的 `_sbrk()` 来请求调整 program break。  
如果 `_sbrk()` 总是失败，那么 `printf()` 在第一次尝试申请格式化缓冲区时就拿不到堆空间，只能退化成逐字符输出。

因此，这一步需要同时补齐两侧逻辑：

- 在 `Nanos-lite` 中实现 `SYS_brk`
- 在用户层 `libos` 中实现 `_sbrk()`

### 9.2 `SYS_brk` 的最小实现

当前 `Nanos-lite` 仍然是单任务操作系统，并没有真正的进程地址空间隔离。因此这一阶段不需要真的维护一套复杂的堆区分配机制，只需要让 `SYS_brk` **总是返回成功** 即可。

我在 `nanos-lite/src/syscall.c` 中加入了如下分支：

```c
case SYS_brk:
  /* 现在还是单任务系统，空闲内存先都默认给用户程序用。
   * 所以 brk 这里先一律返回成功，后面真做内存保护再收紧。
   */
  r->eax = 0;
  break;
```

这样做的含义是：

- 用户程序可以先默认认为堆区扩展总是成功
- 当前阶段先把“用户层能正常用 `malloc()/printf()`”这条链打通
- 真正的内存保护与多任务管理留到后续实验再做

### 9.3 用户层 `_sbrk()` 的实现

用户层 `_sbrk()` 的逻辑则需要自己维护当前的 `program break` 位置。

根据指导书，程序刚启动时，`program break` 应当位于链接器提供的 `_end` 符号处，因此实现思路如下：

1. 第一次调用 `_sbrk()` 时，将静态变量 `program_break` 初始化为 `&_end`
2. 根据参数 `increment` 计算新的 `program break`
3. 通过 `SYS_brk` 请求内核设置新的 `program break`
4. 若成功，则更新记录值，并返回旧的 `program break`
5. 若失败，则返回 `(void *)-1`

我在 `navy-apps/libs/libos/src/nanos.c` 中实现为：

```c
void *_sbrk(intptr_t increment){
  extern char _end;
  static uintptr_t program_break = 0;

  if (program_break == 0) {
    // 第一次进来时，堆顶就从链接脚本给的 _end 开始记。
    program_break = (uintptr_t)&_end;
  }

  uintptr_t old_break = program_break;
  uintptr_t new_break = program_break + increment;
  int ret = _syscall_(SYS_brk, new_break, 0, 0);

  if (ret == 0) {
    program_break = new_break;
    return (void *)old_break;
  }

  return (void *)-1;
}
```

这里有一个调试细节需要特别注意：  
在 `_sbrk()` 里不能直接用 `printf()` 打印调试信息。因为 `printf()` 自己又会尝试申请缓冲区，最后还会再次调用 `_sbrk()`，从而造成死递归。若真要调试，更稳妥的办法是先 `sprintf()` 到本地缓冲区，再通过 `write()` 输出。

### 9.4 运行结果与现象分析

完成上述实现后，重新编译并运行 `hello`，程序依然能够稳定输出：

```text
Hello World!
Hello World for the 2th time
Hello World for the 3th time
...
```

这说明：

- `SYS_brk` 已经不会阻塞用户程序继续运行
- `_sbrk()` 不再像框架代码那样无条件失败
- `hello` 在 `Nanos-lite` 上的运行链路仍然保持正常

从指导书的角度看，这一步的关键目标并不是让输出内容发生变化，而是补齐堆区扩展这条系统调用路径，使 `newlib` 后续需要堆区支持的库函数不再一开始就失败。

如果需要进一步严格观察 `printf()` 是否已经从“逐字符 `write()`”切换为“格式化完成后一次性 `write()`”，可以临时在 `sys_write()` 中加 `Log()` 统计每次写入的长度；不过最终提交版本不一定需要保留这类调试输出。

### 9.5 缓冲区与系统调用开销的验证

指导书特别强调了缓冲区的意义：  
如果每输出 1 个字符都要陷入一次内核，那么输出一整行字符串就会产生很多次系统调用，开销非常大；而如果先把格式化结果放到用户层缓冲区里，再通过一次 `write()` 统一交给内核，就能显著减少系统调用次数。

为了验证这一点，我在 `nanos-lite/src/syscall.c` 的 `SYS_write` 分支中临时加入了：

```c
Log("sys_write(fd=%d, len=%d)", fd, len);
```

这样重新运行 `hello` 之后，就可以直接从日志里观察每次 `write()` 的长度。

判断标准如下：

- 如果还是逐字符输出，那么日志会频繁出现很多 `len = 1`
- 如果堆区和缓冲区已经开始正常工作，那么执行 `printf()` 时更可能看到一次 `len > 1` 的 `write()`，说明格式化后的整段字符串被一次性交给了内核

这一步的实验意义不是修改 `hello` 的输出内容，而是通过观察系统调用粒度，验证 `sbrk()/malloc()/printf()/write()` 这条链是否已经比之前更高效。

本次实际运行时，我观察到如下输出：

```text
[src/syscall.c,28,do_syscall] sys_write(fd=1, len=13)
Hello World!
[src/syscall.c,28,do_syscall] sys_write(fd=1, len=29)
```

这组现象的含义非常明确：

- 第一条 `len=13` 对应的是 `hello.c` 中最开始那次显式调用：
  ```c
  write(1, "Hello World!\n", 13);
  ```
  也就是说，这一行本来就是一次性输出 13 个字符。

- 后面的 `len=29` 则更关键。它说明后续的 `printf("Hello World for the %dth time\n", i++)` 并没有退化成很多次 `len=1` 的字符级 `write()`，而是先在用户层把整条格式化字符串准备好，再通过一次 `write()` 统一交给内核。

因此可以判断：

- `SYS_brk` 与用户层 `_sbrk()` 已经生效
- `malloc()`/缓冲区申请不再一开始就失败
- `printf()` 已经能够利用缓冲区降低系统调用次数

从系统调用开销的角度看，这说明现在输出一整行字符串时，不再需要为每个字符都单独陷入一次内核，而是可以通过一次系统调用完成整段内容的输出，这正是 batching 和缓冲区存在的意义。

### 9.6 在 GNU/Linux 上粗略测试 `write()` 系统调用开销

为了更直观地理解“为什么 batching 能显著降低开销”，我又编写了一个简单的测试程序，对不同 `write()` 粒度下的耗时做了粗略对比。

#### 9.6.1 实验设计

这个小程序的目标非常单纯：固定总输出量，然后只改变“每次 `write()` 写多少字节”，看看系统调用次数和总耗时会发生什么变化。

实验设计如下：

测试方法是固定总输出量为 `1048576` 字节（1 MB），然后分别控制每次 `write()` 的块大小为：

- `1` 字节
- `1024` 字节
- `4096` 字节

并将输出重定向到 `/dev/null`，尽量避免终端显示本身干扰测试结果。

这样设计的原因是：

- 固定总输出量，可以保证不同测试之间的数据规模一致
- 改变 `chunk` 大小，本质上就是改变系统调用次数
- 重定向到 `/dev/null`，可以尽量把观察重点放在 `write()` 本身的开销上，而不是终端渲染速度上

因此，这个实验虽然很简单，但已经足够用来说明“逐字符 `write()`”和“批量 `write()`”在开销上的数量级差异。

#### 9.6.2 测试程序实现

本次用于测试的程序如下：

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static long long now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

int main(int argc, char *argv[]) {
  size_t total = 1024 * 1024;
  size_t chunk = 1;

  if (argc >= 2) {
    total = strtoull(argv[1], NULL, 10);
  }
  if (argc >= 3) {
    chunk = strtoull(argv[2], NULL, 10);
  }

  if (chunk == 0 || total == 0) {
    fprintf(stderr, "usage: %s [total_bytes] [chunk_size]\\n", argv[0]);
    return 1;
  }

  char *buf = malloc(chunk);
  if (buf == NULL) {
    perror("malloc");
    return 1;
  }
  memset(buf, 'A', chunk);

  size_t written = 0;
  long long start = now_ns();

  while (written < total) {
    size_t this_time = chunk;
    if (this_time > total - written) {
      this_time = total - written;
    }

    ssize_t ret = write(STDOUT_FILENO, buf, this_time);
    if (ret < 0) {
      perror("write");
      free(buf);
      return 1;
    }
    written += (size_t)ret;
  }

  long long end = now_ns();
  double ms = (end - start) / 1000000.0;

  dprintf(STDERR_FILENO,
    "\\n[bench] total=%zu bytes, chunk=%zu bytes, calls=%zu, time=%.3f ms\\n",
    total, chunk, (total + chunk - 1) / chunk, ms);

  free(buf);
  return 0;
}
```

这段程序的核心思路是：

- 用 `clock_gettime(CLOCK_MONOTONIC, ...)` 记录开始和结束时间
- 固定总写出字节数 `total`
- 通过 `chunk` 控制每次 `write()` 的大小
- 最终输出总调用次数和总耗时

其中：

- `chunk=1` 对应“接近逐字符输出”的极端情况
- `chunk=1024` 和 `chunk=4096` 则更接近带缓冲区的批量输出

#### 9.6.3 实验结果与分析

本次在 Ubuntu（GNU/Linux）环境下实际测得结果如下：

```text
[bench] total=1048576 bytes, chunk=1 bytes, calls=1048576, time=1790.584 ms
[bench] total=1048576 bytes, chunk=1024 bytes, calls=1024, time=1.258 ms
[bench] total=1048576 bytes, chunk=4096 bytes, calls=256, time=0.266 ms
```

从结果可以清楚看出：

- 当 `chunk=1` 时，需要执行 `1048576` 次 `write()`，耗时约 `1790.584 ms`
- 当 `chunk=1024` 时，只需要 `1024` 次 `write()`，耗时下降到 `1.258 ms`
- 当 `chunk=4096` 时，只需要 `256` 次 `write()`，耗时进一步下降到 `0.266 ms`

也就是说，在这组粗测中：

- 逐字符 `write()` 的耗时远高于批量 `write()`
- 单次写入越大，系统调用次数越少，总耗时也越低

这与前面在 `Nanos-lite` 中观察到的现象是相互印证的：  
一旦 `printf()` 能够先在用户层缓冲区中组织好完整字符串，再通过一次 `write()` 输出，就能显著减少用户态和内核态之间的切换次数，从而降低系统调用带来的额外开销。

因此，缓冲区并不只是“为了写代码方便”才存在，它本质上是一种典型的 batching 技术，用更少的系统调用完成更多的数据传输工作。

#### 9.6.4 与参考文章的对比

指导书中提到可以将实验结果与 Arkanis 在 2017 年发表的文章《Measurements of system call performance and overhead》进行对比。该文的核心结论之一是：

- 系统调用相较普通函数调用存在明显额外开销
- 对小粒度 I/O，使用库函数缓冲区进行 batching 是非常有价值的

文章中关于 `fread()/fwrite()` 的讨论表明：当库函数先把小块数据积累到缓冲区中，再用较少次数的系统调用统一处理时，性能会明显优于每次只处理很小一段数据的情况。

我这次的粗测虽然不是对文章原实验的完全复现，但趋势是一致的，而且更直观：

- `chunk=1` 时，需要执行 `1048576` 次 `write()`，耗时 `1790.584 ms`
- `chunk=1024` 时，只需要 `1024` 次 `write()`，耗时 `1.258 ms`
- `chunk=4096` 时，只需要 `256` 次 `write()`，耗时 `0.266 ms`

这说明：

- 系统调用次数一旦下降，总耗时会显著下降
- batching 的收益在“原本非常碎片化的输出场景”里尤其明显

因此，不管是在 GNU/Linux 还是在本次 `Nanos-lite` 的实验环境中，缓冲区的意义都是一致的：  
**尽可能把很多小输出合并成更少次数、更大粒度的系统调用，从而降低用户态和内核态切换带来的额外成本。**

## 10. 实现简易文件系统并运行 `text`

在完成 `SYS_write`、`SYS_brk` 和 `_sbrk()` 之后，PA3 的主线继续推进到简易文件系统。指导书给出的目标是：

- 在 `nanos-lite/src/fs.c` 中实现最小文件系统接口
- 在系统调用层和 `libos` 层接上 `open/read/write/lseek/close`
- 让 `loader` 不再硬编码从 `ramdisk` 偏移 `0` 读程序，而是通过文件名加载
- 最终将用户程序切换为 `/bin/text`，看到 `PASS!!!`

### 10.1 文件系统骨架实现

我首先在 `fs.h` 中补齐了文件系统接口声明：

- `fs_open()`
- `fs_read()`
- `fs_write()`
- `fs_lseek()`
- `fs_close()`
- `fs_filesz()`

随后在 `fs.c` 中实现了一个最小可用的文件表模型。每个文件记录包含：

- 文件名
- 文件大小
- 在 `ramdisk` 中的偏移
- 当前打开偏移 `open_offset`

实现思路如下：

- `fs_open()`：按文件名在 `file_table` 中线性查找，并将 `open_offset` 置零
- `fs_read()`：从当前偏移读取，且不能越过文件末尾
- `fs_write()`：对普通文件写入 `ramdisk`，对 `stdout/stderr` 直接调用 `_putc()`
- `fs_lseek()`：根据 `SEEK_SET/SEEK_CUR/SEEK_END` 计算新的偏移
- `fs_close()`：当前阶段直接返回 `0`
- `fs_filesz()`：返回文件大小

这一步的本质是先把“固定文件表 + 固定大小文件 + 顺序读写”这条最小链打通，不去引入目录、动态创建文件等复杂机制。

### 10.2 系统调用层与 `libos` 对接

文件系统接口补好之后，还需要让用户程序真的能够通过系统调用访问这些文件。

为此，我在 `nanos-lite/src/syscall.c` 中补上了：

- `SYS_open`
- `SYS_read`
- `SYS_write`
- `SYS_lseek`
- `SYS_close`

它们分别直接转发到：

- `fs_open()`
- `fs_read()`
- `fs_write()`
- `fs_lseek()`
- `fs_close()`

与此同时，在 `navy-apps/libs/libos/src/nanos.c` 中，原来那些直接 `_exit(SYS_xxx)` 的占位实现也被替换成真正的系统调用封装，使得 `fopen()/fread()/fseek()/fclose()/fprintf()` 之类的库函数终于能够落到内核实现上。

### 10.3 让 `loader` 按文件名加载程序

在 raw loader 阶段，`loader()` 只是从 `ramdisk` 偏移 `0` 处整块复制程序。  
但文件系统完成后，这种方式就不够用了，因为此时 `ramdisk` 中不再只有一个程序，而是整个 `fsimg`。

因此我把 `loader()` 改成了：

1. `fs_open(filename, 0, 0)`
2. `fs_filesz(fd)`
3. `fs_read(fd, DEFAULT_ENTRY, size)`
4. `fs_close(fd)`

这样之后，切换用户程序就不再依赖手工修改 `ramdisk` 的起始偏移，而只需要传入不同的文件名即可。

当前在 `main.c` 中，我把主程序入口切换为：

```c
loader(NULL, "/bin/text");
```

这样本阶段就会直接验证 `text` 这条路径。

### 10.4 切换到 `fsimg` 构建模式

由于文件系统阶段不再是“把一个单独程序 objcopy 进 `ramdisk`”的模式，因此我也修改了 `nanos-lite/Makefile` 中的 `update` 规则，使其从原来的：

- `update-ramdisk-objcopy`

切换为：

- `update-ramdisk-fsimg`

这样在执行：

```bash
make ARCH=x86-nemu update
```

时，系统会：

- 在 `navy-apps` 中构建完整 `fsimg`
- 将 `fsimg` 中的所有文件拼接成新的 `ramdisk.img`
- 自动生成 `nanos-lite/src/files.h`

这一步是后续文件系统正常工作的关键，因为 `file_table` 中的普通文件记录正是从 `files.h` 自动生成出来的。

### 10.5 运行 `text` 验证文件系统

完成上述修改后，我在虚拟机中执行：

```bash
cd ~/code/ics2017/nanos-lite
make ARCH=x86-nemu update
make ARCH=x86-nemu run
```

在 `NEMU` monitor 中输入：

```text
c
```

继续执行后，终端输出为：

```text
PASS!!!
nemu: HIT GOOD TRAP at eip = 0x00100032
```

这说明：

- `/bin/text` 已经通过文件系统被 `loader()` 正确加载
- `fopen()` 已经能够通过 `SYS_open` 打开 `/share/texts/num`
- `fseek()` / `ftell()` / `fread()` / `fprintf()` 等所依赖的底层 `read/write/lseek/close` 已经打通
- 文件读写偏移管理是正确的
- 程序最终通过全部断言，打印 `PASS!!!`

因此可以认为：

- **任务 7：实现简易文件系统** 已完成
- **任务 8：让 loader 使用文件系统** 已完成
- **任务 9：运行 `text` 验证完整文件系统链路** 已完成

截图建议：

- 最适合放报告的截图就是包含下面两行的终端画面：
  ```text
  PASS!!!
  nemu: HIT GOOD TRAP
  ```

这张图可以直接作为“简易文件系统与 `text` 验证通过”的证据。

## 11. 实现设备文件 `/dev/fb`、`/proc/dispinfo` 与 `/dev/events`

在完成普通文件系统之后，下一步就是把 IOE 也统一抽象到文件接口下，也就是指导书中“Everything is a file”这一部分。

这一阶段对应的三个特殊文件分别是：

- `/dev/fb`：frame buffer，抽象显存
- `/proc/dispinfo`：屏幕大小信息
- `/dev/events`：时钟与按键事件

### 11.1 `/dev/fb` 与 `/proc/dispinfo`

按照指导书要求，我在 `init_fs()` 中为 `/dev/fb` 初始化了大小：

```text
screen_width * screen_height * sizeof(uint32_t)
```

这样用户程序就可以把整个屏幕看成一段可 `lseek + write` 的字节序列。

与此同时，我在 `init_device()` 中提前构造了 `/proc/dispinfo` 的内容，格式为：

```text
WIDTH:400
HEIGHT:300
```

然后在：

- `dispinfo_read()`
- `fs_read()`
- `fs_write()`

中对 `/proc/dispinfo` 和 `/dev/fb` 做了专门重定向，使得它们虽然不在 `ramdisk` 中拥有真实文件实体，但对用户程序来说看起来仍然像普通文件一样可被访问。

其中 `fb_write()` 的实现思路是：

1. 根据写入偏移 `offset` 计算当前像素在屏幕上的 `(x, y)` 位置
2. 将待写入像素按行拆开
3. 调用 AM 提供的 `_draw_rect()` 完成实际绘制

### 11.2 为什么第一次 `bmptest` 没有出图

最开始我直接切到 `/bin/bmptest` 进行验证，但窗口中没有出现图片。  
后来排查发现，原因并不在 `fs.c` 或 `fb_write()`，而在于更底层的 `x86-nemu` IOE 仍然是骨架状态：

- `_draw_rect()` 只是往 framebuffer 填测试值
- `_draw_sync()` 为空实现
- NEMU 的 `vga` 设备虽然有窗口，但显存写入后没有真正触发刷新

因此我继续补齐了两侧底层支持：

- 在 `nexus-am/am/arch/x86-nemu/src/ioe.c` 中实现真正的 `_draw_rect()`
- 在 `nemu/src/device/vga.c` 中让显存写入能够触发窗口刷新

这之后再次运行 `bmptest`，终于在 NEMU 窗口中看到了 `ProjectN` Logo，说明 framebuffer 这一条链已经真正打通。

本次对应截图为：

- `pa3-bmptest-projectn-logo.png`

它可以直接作为 `/dev/fb` 与 `/proc/dispinfo` 实现成功的证据。

### 11.3 `/dev/events` 的实现与验证

对于输入设备，我按照指导书中的事件文本格式实现了 `/dev/events`：

- `t 1234`
- `kd A`
- `ku A`

其策略是：

- 若有按键事件，优先返回按键事件
- 若当前没有按键，则返回时钟事件

这一部分在 `events_read()` 中完成。

运行 `/bin/events` 后，终端中已经能够稳定看到：

```text
receive event: t 615
```

这说明：

- `/dev/events`
- `fs_read()`
- `fopen("/dev/events")`
- `fgetc()`
- 用户态 `printf()`

这条“时间事件”链已经完整跑通。

### 11.4 键盘事件的底层验证

在继续验证按键事件时，我发现单纯从用户态现象不太容易直接判断问题位于哪一层，因此又在 `NEMU` 的键盘设备中增加了轻量调试输出。

最终在终端中观察到：

```text
[kbd] down scancode=4 am=32811
[src/device.c,22,events_read] events_read got key = 32811
[kbd] up scancode=4 am=43
[src/device.c,22,events_read] events_read got key = 43
[kbd] down scancode=7 am=32813
[kbd] up scancode=7 am=45
```

这说明：

- NEMU 图形窗口已经能够收到主机键盘事件
- SDL 事件已经进入 `NEMU` 键盘设备
- 按键扫描码已经被成功翻译成 AM 约定的按键编码
- `events_read()` 已经能够通过 `_read_key()` 实际读到键盘事件

因此，虽然 `events` 测试程序这一次截图中主要明确展示了时间事件，而没有直接拍到 `receive event: kd/ku ...` 的最终用户态输出，但**键盘事件链路至少已经确认成功推进到了 `events_read()` 这一层**。

这张终端截图建议命名为：

- `pa3-events-keyboard-debug.png`

它可以作为“按键事件已经进入 NEMU 键盘设备”的验证材料。

### 11.5 本阶段结论

截至目前，这一部分可以比较稳妥地总结为：

- `/dev/fb` 已经可用，`bmptest` 成功显示 `ProjectN` Logo
- `/proc/dispinfo` 已经可用，图形程序能够正确获取屏幕大小
- `/dev/events` 的时间事件链已经完整跑通
- 键盘事件已经确认进入 NEMU 键盘设备、完成 AM 编码转换，并被 `events_read()` 实际读到

也就是说，“一切皆文件”这条主线已经基本建立起来，后续运行 `pal` 所需要的图形和输入基础已经具备。

## 12. 当前进度

截至目前，PA3 已经完成并验证了以下内容：

- 实现 raw program loader，并成功装载 `dummy`
- 打通 `int 0x80 -> raise_intr() -> vecsys() -> asm_trap -> irq_handle() -> do_event()` 这条异常/系统调用入口链
- 实现 `pusha/popa` 与 trap frame 对齐，成功达到 `Unhandled event ID = 8` 的指导书检查点
- 实现最小系统调用分发，跑通 `SYS_none` 和 `SYS_exit`，成功得到 `HIT GOOD TRAP`
- 实现 `SYS_write`，并切换到 `hello` 程序运行
- 实现 `SYS_brk` 与用户层 `_sbrk()`，补齐堆区扩展路径
- 实现简易文件系统，接通 `open/read/write/lseek/close`
- 让 `loader` 按文件名加载用户程序
- 成功运行 `/bin/text`，得到 `PASS!!!`
- 实现 `/dev/fb` 与 `/proc/dispinfo`，成功显示 `ProjectN` Logo
- 实现 `/dev/events` 的时间事件，并确认键盘事件已被 `events_read()` 实际读到

接下来的主线任务就从“最小系统调用闭环”进入到：

- 将 `/home/linshangjin/code/pal.zip` 中的仙剑资源解包到 `navy-apps/fsimg/share/games/pal/`
- 切换入口程序，尝试运行 `/bin/pal`
- 继续收尾设备文件与图形输入链在 `pal` 场景下的完整验证

## 13. 运行 `pal` 过程中的排障与修复

在进入 `pal` 之后，我一开始的判断其实是不够准确的。最初看到现象是：

- 资源文件全部加载成功
- `PAL_InitResources success`
- 屏幕能够进入第一帧、第二帧
- 但程序始终卡在开场阶段，画面无法继续推进

当时我先怀疑的是：

- `pal.zip` 资源文件不完整
- `/dev/fb` 画面还没有真正显示出来
- `/dev/events` 没有把按键和时间事件继续送到用户态

但随着日志逐步补齐，我发现这些猜测并不成立：

- 资源文件可以全部正常读取
- `bmptest` 已经能正确显示 `ProjectN Logo`
- `events_read()` 已经能够读到时间事件和键盘事件

因此，这里的问题已经不是“框架根本没搭起来”，而是**我自己的 PA3 改动中，有一些和 `pal` 的运行时语义不完全匹配**。

### 13.1 先缩小排查范围

为了避免继续在无关模块里兜圈子，我重新梳理了 `pal` 真正依赖的链路，只保留和 `pal` 直接相关的几个层次：

- `nanos-lite/src/device.c`
- `nanos-lite/src/fs.c`
- `navy-apps/libs/libndl/src/ndl.c`
- `navy-apps/apps/pal/src/hal/hal.c`
- `navy-apps/apps/pal/src/device/input.c`
- `navy-apps/apps/pal/src/main.c`
- `navy-apps/apps/pal/src/misc/rngplay.c`
- `nexus-am/am/arch/x86-nemu/src/ioe.c`
- `nemu/src/device/vga.c`

也就是说，这一阶段我不再重新怀疑：

- 中断机制
- `loader`
- `SYS_brk`
- 普通文件系统主线

因为这些内容在前面已经分别通过：

- `dummy`
- `hello`
- `text`
- `bmptest`

验证过了。

### 13.2 第一个真实问题：`vga` 过度刷新

在继续定位时，我先把注意力放到图形路径上，因为这时已经能确认：

- `pal` 资源已经加载完成
- `VIDEO_UpdateScreen()` 之前的逻辑可以走到
- 画面能够进入前几帧，但推进得非常慢

进一步检查后，我发现真正的第一个问题出在：

```text
nemu/src/device/vga.c
```

我之前为了让图像尽快显示出来，曾经把显存写入和 SDL 刷新绑得太紧，导致：

- `/dev/fb` 每写一小段
- `NEMU` 就整屏刷新一次

而 `pal` 的一帧画面又会触发很多次 `/dev/fb` 写入，于是最终效果就变成：

- 每一帧被拆成大量整屏刷新
- 性能极差
- 看起来像“卡在前几帧”

我把这里改成“显存只负责写入，窗口刷新仍然走原有的定时刷新路径”之后，运行速度明显提升，这说明：

> `vga` 过度刷新并不是猜测，而是一个已经被确认的真实 bug。

### 13.3 第二个判断：问题集中在事件与时间推进链

继续往下排查时，我发现：

- `PAL_RNGPlay` 可以进入
- `VIDEO_UpdateScreen()` 前后的日志都能打出来
- `redraw[2]` 开始已经出现了非黑像素

这说明程序并不是完全没有继续执行，而是：

> 能跑到商标动画/开场动画的前几帧，然后在某个等待事件或时间推进的位置停住。

这时我重新收束排查范围，重点只盯住和 `pal` 当前卡住现象直接相关的链路：

- `nanos-lite/src/device.c`
- `navy-apps/libs/libndl/src/ndl.c`
- `nexus-am/am/arch/x86-nemu/src/ioe.c`

这条链上，也就是：

- `/dev/events`
- `libndl`
- `NDL_WaitEvent()`
- `PAL_PollEvent()`

而不是继续去怀疑：

- 资源包
- 普通文件读写
- `pal` 自己的主循环逻辑

也就是说，问题已经不再是“程序本体是否能运行”，而是：

> 事件和时间推进这条底层语义，在我当前的实现里是否足够稳定，能不能支撑 `pal` 这种连续动画场景。

### 13.4 最终修复策略

在这一阶段，我决定不再继续到处零散补丁，而是换一种更稳的办法：

> 只保留“为了运行 `pal` 直接相关”的文件，把这一小段链路整理成同一套一致的实现。

具体来说，我只重新整理下面这些与 `pal` 直接相关的文件：

- `nanos-lite/src/device.c`
- `nanos-lite/src/fs.c`
- `navy-apps/libs/libndl/src/ndl.c`
- `navy-apps/apps/pal/src/hal/hal.c`
- `navy-apps/apps/pal/src/device/input.c`
- `navy-apps/apps/pal/src/main.c`
- `navy-apps/apps/pal/src/misc/rngplay.c`
- `nexus-am/am/arch/x86-nemu/src/ioe.c`
- `nemu/src/device/vga.c`

这样做的理由是：

- 不去大范围推翻整套 PA3 实现
- 只收窄到 `pal` 真正依赖的那一小段链路
- 避免把已经验证通过的部分重新弄坏

在整理这些文件时，还出现了一个很典型的小问题：

- `fs.c` 中一度写成了 `ssize_t fs_read/fs_write`
- 而我当前仓库的 `fs.h` 声明是 `size_t fs_read/fs_write`

因此重新整理后会触发编译错误。我随后把 `fs.c` 的返回类型改回和当前头文件一致，这才完成了和现有工程的兼容。

### 13.5 这次排障给我的反思

这次 `pal` 卡住的问题，给我的最大提醒不是“某一行代码写错了”，而是：

1. 出现复杂运行时问题时，不能继续靠猜  
   一开始我在“黑屏”“是不是太卡”“是不是资源包有问题”之间来回怀疑，效率其实不高。

2. 要先确认问题发生在哪一层  
   这次真正有效的推进，是把问题压缩成：
   - `vga` 刷新
   - `/dev/events`
   - `libndl`
   - `PAL_PollEvent`

3. 当排查范围已经足够小的时候，最好把同一条链路上的实现一次性整理干净  
   尤其是像 `pal` 这种强依赖图形、事件和时间推进配合的程序，与其继续在很多地方加临时补丁，不如把和它直接相关的那几层统一收束成一套一致实现。

因此，这一阶段的修 bug 过程，本质上不是“重新实现仙剑”，而是：

> 重新审视自己在 `pal` 运行链路上做过的修改，把真正会影响运行时语义的地方找出来，并集中修到同一条链上。

## 14. 必答题：仙剑奇侠传中文件读写的具体过程

这一题真正想说明的是：在 `PA3` 里，用户程序虽然写的是标准 C 库函数或者 `NDL` 接口，但最后都能一路落到 `Nanos-lite`、`AM` 和 `NEMU` 上。  
换句话说，仙剑奇侠传并不是“直接操作硬件”，而是依次通过：

```text
pal -> 库函数/NDL -> libos -> Nanos-lite -> AM -> NEMU
```

这一整条链，来完成存档读取和屏幕更新。

### 14.1 通过 `fread()` 读取游戏存档的过程

在仙剑中，读档发生在：

```text
navy-apps/apps/pal/src/global/global.c
```

中的 `PAL_LoadGame()`。  
这里会先打开对应存档文件，然后调用：

```c
fread(...)
```

把存档内容读到内存缓冲区中。

这一步表面上只是一次普通的 C 标准库文件读取，但实际往下会经过很多层。

#### 1. 用户程序层：`pal`

`PAL_LoadGame()` 站在游戏程序的角度，只认为自己是在读一个普通文件：

- 先 `fopen()`
- 再 `fread()`

也就是说，仙剑本身并不关心这个文件在 ramdisk 里，还是在真实磁盘里，它只使用标准文件接口。

#### 2. C 标准库层：`newlib`

`fread()` 是 `newlib` 提供的标准库函数。  
它内部不会直接操作 `Nanos-lite`，而是会继续调用更底层的文件读接口，例如：

- `read()`
- 或对应的系统封装 `_read()`

因此，`fread()` 的作用更像是：

- 处理缓冲区
- 处理“读多少字节”
- 维护 `FILE*` 的内部状态

真正的数据来源，还要继续往下交给操作系统。

#### 3. 用户态运行时层：`libos`

在：

```text
navy-apps/libs/libos/src/nanos.c
```

中，`_read()` 的实现最终会调用：

```c
_syscall_(SYS_read, fd, (uintptr_t)buf, count)
```

这里做的事情是：

1. 把系统调用号 `SYS_read` 放到 `%eax`
2. 把参数 `fd`、`buf`、`count` 放到 `%ebx/%ecx/%edx`
3. 执行 `int $0x80`

从这一刻开始，控制权从用户程序陷入 `Nanos-lite`。

#### 4. 操作系统层：`Nanos-lite`

系统调用进入：

```text
nanos-lite/src/syscall.c
```

中的 `do_syscall()`。  
当系统调用号是 `SYS_read` 时，`Nanos-lite` 会进一步调用：

```c
fs_read(fd, buf, len)
```

也就是说，在 `Nanos-lite` 看来，用户程序并不是在“读档”，而是在“从某个文件描述符里读一段字节序列”。

#### 5. 文件系统层：`fs.c`

在：

```text
nanos-lite/src/fs.c
```

中，`fs_read()` 会根据 `fd` 去查文件表：

- 这个 `fd` 对应哪个文件
- 文件当前的 `open_offset` 是多少
- 这次最多还能读多少字节

如果它是普通文件，那么就会调用：

```c
ramdisk_read(buf, disk_offset + open_offset, len)
```

然后更新：

```c
file_table[fd].open_offset += len;
```

也就是说，文件系统层真正做的事情是：

1. 根据文件描述符定位文件
2. 计算文件中的偏移
3. 从 ramdisk 对应位置把字节拷出来
4. 把这些字节交还给用户程序提供的缓冲区

#### 6. `ramdisk` 层

`ramdisk` 本质上就是一段已经被打包进镜像的字节数组。  
因此 `ramdisk_read()` 并不神秘，它本质就是一次“从内核维护的字节序列中拷贝数据”。

对于仙剑读档来说，这意味着：

- 存档文件的实体并不来自真实磁盘
- 而是来自当前镜像中的文件系统映像

但对 `pal` 来说，这一点是完全透明的。

#### 7. 整体串起来看

因此，仙剑读取存档的完整路径可以概括为：

```text
PAL_LoadGame()
-> fread()
-> _read()
-> _syscall_(SYS_read)
-> do_syscall()
-> fs_read()
-> ramdisk_read()
```

所以虽然游戏代码里看到的是标准库函数 `fread()`，但真正完成“从文件里取出字节”的，是 `Nanos-lite` 的文件系统和 ramdisk。

### 14.2 通过 `NDL_DrawRect()` 更新屏幕的过程

在仙剑中，画面更新最终会走到：

```text
navy-apps/apps/pal/src/hal/hal.c
```

中的 `redraw()`。

`redraw()` 的职责是：

1. 读取当前 8-bit 索引色画面
2. 根据调色板把每个像素索引转换成真正的 32-bit RGB 值
3. 调用 `NDL_DrawRect()` 把像素写入画布
4. 再调用 `NDL_Render()` 把画布内容真正提交到屏幕

因此，仙剑并不是直接操作 VGA 显存，而是先通过 `NDL` 这一层做统一封装。

#### 1. 用户程序层：`pal`

在 `redraw()` 中，`pal` 会遍历当前的 8-bit 画面缓冲：

- `vmem` 里存的是颜色索引
- `palette[]` 里存的是索引对应的 RGB 颜色

它先把索引色转换成 32-bit 像素，然后调用：

```c
NDL_DrawRect(fb, 0, 0, W, H);
NDL_Render();
```

也就是说，在用户程序看来，它只是把一帧像素交给 `NDL` 来显示。

#### 2. 多媒体库层：`libndl`

在：

```text
navy-apps/libs/libndl/src/ndl.c
```

中：

- `NDL_DrawRect()` 先把要显示的像素写进内部 `canvas`
- `NDL_Render()` 再把整张 `canvas` 一行一行写到 `/dev/fb`

关键代码逻辑是：

```c
fseek(fbdev, offset, SEEK_SET);
fwrite(..., fbdev);
fflush(fbdev);
```

这里的 `fbdev` 就是：

```c
fopen("/dev/fb", "w")
```

打开得到的文件流。

所以从 `NDL` 的角度来看，屏幕就是一个可以写入的特殊文件。

#### 3. 用户态运行时层：`libos`

`fseek()` 和 `fwrite()` 最终会落到：

- `_lseek()`
- `_write()`

这些函数在：

```text
navy-apps/libs/libos/src/nanos.c
```

里会继续转成系统调用：

```c
_syscall_(SYS_lseek, ...)
_syscall_(SYS_write, ...)
```

也就是说，`NDL_Render()` 不是直接碰设备，而是让操作系统去处理 `/dev/fb` 的定位和写入。

#### 4. 操作系统层：`Nanos-lite`

`Nanos-lite` 在：

```text
nanos-lite/src/syscall.c
```

里接到：

- `SYS_lseek`
- `SYS_write`

之后，分别转发给：

```c
fs_lseek(...)
fs_write(...)
```

这里最关键的是：  
`/dev/fb` 并不是普通文件，所以不会走到 `ramdisk_write()`，而是会在文件系统层被识别成特殊文件。

#### 5. 文件系统层：`fs.c`

在：

```text
nanos-lite/src/fs.c
```

中，`fs_write()` 会判断当前 `fd` 是否是：

```c
FD_FB
```

如果是，就调用：

```c
fb_write(buf, open_offset, len)
```

这里 `open_offset` 就对应了用户程序通过 `lseek()` 设置好的文件偏移。  
因此，对 `/dev/fb` 来说：

- 文件偏移本质上就是“像素在线性显存中的位置”

#### 6. 设备层：`fb_write()`

在：

```text
nanos-lite/src/device.c
```

中，`fb_write()` 会把线性偏移还原成屏幕上的坐标：

1. 先根据 `offset` 算出当前对应第几行、第几列
2. 再调用：

```c
_draw_rect(...)
```

把这一段像素真正交给 AM 层处理

也就是说，`/dev/fb` 虽然表面上是“文件写入”，但在这里已经被重新解释成：

- 往屏幕某个坐标位置写像素

#### 7. AM 层：`_draw_rect()`

在：

```text
nexus-am/am/arch/x86-nemu/src/ioe.c
```

中，`_draw_rect()` 会把像素逐行拷贝到 framebuffer 对应的内存区域：

```c
dest = fb + y * _screen.width + x;
memcpy(...)
```

这里的 `fb` 本质上是映射到 `NEMU` VGA 设备的显存区域。

因此，AM 的作用就是把来自 `Nanos-lite` 的“画矩形请求”翻译成“往模拟显存写一段像素”。

#### 8. NEMU 层：VGA 设备

在：

```text
nemu/src/device/vga.c
```

中，NEMU 维护了图形窗口和对应的纹理/显存映射。  
当显存内容被更新后，定时刷新路径会调用：

```c
update_screen()
```

把显存内容同步到 SDL 窗口中，最终用户才在 NEMU 图形窗口里看到画面。

也就是说，最后这一步完成的是：

- 把“客户机中的显存内容”
- 映射成“宿主机 SDL 窗口中的图像”

#### 9. 整体串起来看

因此，仙剑更新屏幕的完整路径可以概括为：

```text
redraw()
-> NDL_DrawRect()
-> NDL_Render()
-> fwrite("/dev/fb")
-> _write()
-> _syscall_(SYS_write)
-> do_syscall()
-> fs_write()
-> fb_write()
-> _draw_rect()
-> NEMU VGA
-> SDL 窗口显示
```

### 14.3 这道题真正体现的思想

把上面两条链放在一起看，会发现一个很有意思的共性：

- 读存档时，仙剑使用的是 `fread()`
- 画屏幕时，仙剑最终也是通过文件接口去写 `/dev/fb`

前者面对的是普通文件，后者面对的是特殊设备文件，但在用户程序眼里，它们都只是：

- 打开
- 读取/写入
- 按偏移访问

这正是 `PA3` 想让我们体会到的核心思想：

> “一切皆文件”

也就是说，`Nanos-lite` 向用户程序暴露的不是各种零散硬件接口，而是统一的文件抽象。  
于是：

- 存档可以像普通文件一样读
- 屏幕可以像文件一样写
- 事件可以像文件一样读

而仙剑奇侠传也正是在这套统一抽象之上，才能在 `Nanos-lite + AM + NEMU` 这套环境中顺利运行。
