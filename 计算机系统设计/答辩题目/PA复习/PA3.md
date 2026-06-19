# PA3 — 异常控制流：中断机制 + 系统调用 + 文件系统

## 一、特权级制度

i386 有 ring 0~3，PA 只用 ring 0（操作系统）和 ring 3（用户进程）。  
PA 中为简化，**所有进程都运行在 ring 0**，不实现保护检查。

## 二、中断/异常机制（重要考点）

### IDT（中断描述符表）

**门描述符（PA 简化版，8字节）：**
```
高4字节: OFFSET[31:16] | P | Don't care
低4字节: Don't care    | OFFSET[15:0]
```
P=1 表示有效，OFFSET 是处理函数地址。

**IDTR 寄存器：** 存 IDT 首地址 + 长度，由 `lidt` 指令设置。

### 触发异常时硬件做的事（`raise_intr()`）

**文件：** `nemu/src/cpu/intr.c`

```c
void raise_intr(uint8_t NO, vaddr_t ret_addr) {
  // 1. 依次压栈 EFLAGS, CS, EIP（返回地址）
  rtl_push(&cpu.eflags);
  t0 = cpu.cs;
  rtl_push(&t0);
  rtl_push(&ret_addr);
  // 2. 关中断（IF=0）
  cpu.IF = 0;
  // 3. 从 IDTR.base + NO*8 读出门描述符，提取 handler 地址
  vaddr_t gate_addr = cpu.idtr.base + NO * 8;
  uint32_t handler = (gate_lo & 0x0000ffff) | (gate_hi & 0xffff0000);
  // 4. 跳转到 handler
  decoding.jmp_eip = handler;
  decoding.is_jmp = 1;
}
```

**`int` 指令：** 调用 `raise_intr(imm8, next_eip)`，`next_eip` 是 int 指令**下一条**指令的地址。

### 异常处理完整链路（重要考点）

```
用户程序 int $0x80
  → NEMU exec_int()
    → raise_intr(0x80, ret_addr)
      → 压栈 EFLAGS/CS/EIP，跳转到 IDT[0x80].offset
        → vecsys()   [nexus-am/am/arch/x86-nemu/src/trap.S]
          → asm_trap()
            → pusha（保存通用寄存器，构造 trap frame）
              → pushl %esp（把 trap frame 指针压栈）
                → call irq_handle()  [nexus-am/am/arch/x86-nemu/src/asye.c]
                  → 构造 _Event，调用注册的事件处理函数 H()
                    → do_event()  [nanos-lite/src/irq.c]
                      → do_syscall()  [nanos-lite/src/syscall.c]
                        → 处理系统调用，设置返回值到 r->eax
              ← 返回 trap frame 指针
          ← popa（恢复通用寄存器，eax已含返回值）
          ← iret（从栈上恢复 EIP/CS/EFLAGS，回到用户程序）
```

### trap frame（陷阱帧）结构

**文件：** `nexus-am/am/arch/x86-nemu/include/arch.h` 中的 `_RegSet`

trap frame 在栈上从高地址到低地址排列：
```
[高地址]
  EIP      ← 硬件压入（int指令下一条地址）
  CS       ← 硬件压入
  EFLAGS   ← 硬件压入
  irq      ← vecsys 压入（中断号 0x80）
  error    ← vecsys 压入（错误码，占位）
  EAX      ← pusha 压入
  ECX      ←
  EDX      ←
  EBX      ←
  ESP      ←
  EBP      ←
  ESI      ←
  EDI      ← pusha 压入
[低地址]  ← esp 指向这里（传给 irq_handle 的指针）
```

**`pushl %esp` 的作用：** 把当前 esp（指向 trap frame 起始）压栈，作为 `irq_handle()` 的参数，让 C 函数能访问整个现场。

### `iret` 指令

从栈上依次弹出 EIP、CS、EFLAGS，恢复执行现场。  
**文件：** `nemu/src/cpu/exec/system.c`

### 宏 `HAS_ASYE` 开启后调用链

```
nanos-lite main()
└── init_irq()
    └── _asye_init(do_event)   [nexus-am/am/arch/x86-nemu/src/asye.c]
        ├── 初始化 idt 数组（设置 IDT 的各个门描述符）
        │   ├── idt[0x80] = vecsys (系统调用)
        │   ├── idt[0x81] = vectrap
        │   └── idt[0x20] = vectime (时钟中断)
        ├── set_idt(idt, sizeof(idt))  → lidt 指令设置 IDTR
        └── H = do_event  （注册事件处理函数）
```

## 三、系统调用

### `_syscall_()` 调用约定

**文件：** `navy-apps/libs/libos/src/nanos.c`

```c
// 参数：eax=调用号, ebx=arg1, ecx=arg2, edx=arg3
// 返回值：eax
asm volatile("int $0x80" : "=a"(ret) : "a"(type), "b"(a0), "c"(a1), "d"(a2));
```

### 系统调用分发

**文件：** `nanos-lite/src/syscall.c` → `do_syscall()`

```c
switch (a[0]) {   // a[0] = eax = 系统调用号
  case SYS_none:  r->eax = 1; break;
  case SYS_exit:  _halt(a[1]); break;
  case SYS_write: r->eax = fs_write(a[1], (void*)a[2], a[3]); break;
  case SYS_open:  r->eax = fs_open(...); break;
  case SYS_read:  r->eax = fs_read(...); break;
  case SYS_brk:   r->eax = mm_brk(a[1]); break;
  // ...
}
```

### SYS_write（标准输出）

`fd=1(stdout)` 或 `fd=2(stderr)` → 调用 `_putc()` 逐字符输出到串口。

### SYS_brk（堆区管理）

`_sbrk()` 在用户层管理 program break（heap 末尾地址），通过 `SYS_brk` 请求 OS 扩展堆。  
PA3 单任务：`SYS_brk` 直接返回 0（总成功）。  
PA4 分页后：`mm_brk()` 需要真正映射物理页。

## 四、文件系统

**文件：** `nanos-lite/src/fs.c`

### 简易文件系统特点
- 文件数量固定，大小固定
- 不能创建新文件，没有目录
- 文件在 ramdisk 中连续存放
- 文件描述符 = 文件记录表下标（前3个固定为 stdin/stdout/stderr）

### 文件记录表 `file_table`

```c
// nanos-lite/src/files.h（自动生成）
static Finfo file_table[] = {
  [FD_STDIN]  = {"stdin",  0, 0, 0},
  [FD_STDOUT] = {"stdout", 0, 0, 0},
  [FD_STDERR] = {"stderr", 0, 0, 0},
  // 特殊文件:
  {"/dev/fb",        ...},
  {"/proc/dispinfo", ...},
  // 普通文件（由 make update 生成）:
  {"/bin/hello", size, offset, 0},
  ...
};
```

### 文件操作

```c
int fs_open(const char *name, int flags, int mode);  // 返回fd（文件记录表下标）
int fs_read(int fd, void *buf, size_t len);
int fs_write(int fd, const void *buf, size_t len);
int fs_lseek(int fd, size_t offset, int whence);
int fs_close(int fd);  // 简化：总是返回0
```

偏移量 `open_offset` 在 `Finfo` 结构体中维护。

### 特殊文件

| 文件 | 操作 | 实现位置 |
|------|------|---------|
| `/dev/fb` | write | `fb_write()` → `_draw_rect()` 写 VGA 显存 |
| `/proc/dispinfo` | read | `dispinfo_read()` → 返回屏幕宽高字符串 |

### loader 使用文件系统

```c
// nanos-lite/src/loader.c
// 用 fs_open("/bin/hello") → fs_read() → 加载到 0x4000000
uintptr_t loader(PCB *pcb, const char *filename) {
  int fd = fs_open(filename, 0, 0);
  // 读取并加载到目标地址...
  return entry;
}
```

## 五、一切皆文件

Unix 哲学：键盘/显示器/管道/socket 都是字节序列，统一用文件接口操作。

**Nanos-lite 实现：**
- 串口 → `stdout`/`stderr`（fd=1/2），写时调用 `_putc()`
- VGA 显存 → `/dev/fb`，写时调用 `fb_write()` → `_draw_rect()`
- 屏幕信息 → `/proc/dispinfo`，读时返回 `"WIDTH:400\nHEIGHT:300\n"`
- 键盘/时钟 → `/dev/events`（PA3 阶段3实现）
