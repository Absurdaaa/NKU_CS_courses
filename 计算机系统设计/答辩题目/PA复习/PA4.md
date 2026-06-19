# PA4 — 分时多任务：虚拟内存 + 时钟中断

## 一、虚拟内存（分页机制）

### x86 分页基础

- 页大小：4KB（`0x1000`）
- 虚拟地址 32 位：`[31:22]`=页目录索引，`[21:12]`=页表索引，`[11:0]`=页内偏移
- CR0 寄存器的 PG 位 = 1 时启用分页
- CR3 寄存器存页目录物理地址

### PTE（Protection Extension）

**文件：** `nexus-am/am/arch/x86-nemu/src/pte.c`

**AM 提供的接口：**
```c
void _pte_init(void*(*palloc)(), void(*pfree)(void*));
void _protect(_Protect *p);       // 创建地址空间（分配页目录）
void _release(_Protect *p);       // 释放地址空间
void _map(_Protect *p, void *va, void *pa, int prot); // 建立 va→pa 映射
_RegSet *_umake(_Protect *p, _Area ustack, _Area kstack,
                void *entry, char *const argv[], char *const envp[]);
```

### mm_brk（PA4 中的堆区管理）

**文件：** `nanos-lite/src/mm.c`

PA3 直接返回 0；PA4 需要真正映射物理页：
```c
int mm_brk(uint32_t new_brk) {
  // 从旧 brk 到 new_brk 逐页分配物理内存并 _map()
}
```

## 二、上下文切换（分时多任务）

### 时钟中断链路

```
硬件定时器触发（100Hz）
  → dev_raise_intr()   [nemu/src/device/timer.c]
    → cpu.INTR = true
      → cpu_exec() 检测到 INTR=true
        → raise_intr(0x20, eip)  [nemu/src/cpu/intr.c]
          → 跳转到 IDT[0x20].offset = vectime
            → asm_trap() 保存现场
              → irq_handle() → do_event()
                → 识别 _EVENT_IRQ_TIME
                  → schedule()  进程调度
                    → 返回新进程的 trap frame 指针
              → 恢复新进程现场 → iret
```

### 进程控制块（PCB）

**文件：** `nanos-lite/src/proc.h` + `nanos-lite/src/proc.c`

```c
typedef struct {
  _RegSet *tf;       // 指向保存的现场（trap frame）
  _Protect as;       // 地址空间
  // ...
} PCB;
```

`schedule()` 在进程间切换，返回下一个进程的 trap frame。

### `_make()` 创建新进程现场

**文件：** `nexus-am/am/arch/x86-nemu/src/asye.c`

```c
_RegSet *_make(_Area stack, void *entry, void *arg) {
  // 在栈上构造一个"假的"trap frame
  // 使得第一次切换到这个进程时，能从 entry 开始执行
  tf->eip = (uintptr_t)entry;
  tf->eflags = 0x202;  // IF=1，允许中断
  tf->cs = 0x8;
}
```

## 三、外部中断（来自外部的声音）

**中断号：** `0x20`（时钟）

**与异常的区别：**
- 异常（exception）：CPU 执行指令时内部产生（除零、无效指令、int指令）
- 外部中断（interrupt）：外部设备触发，CPU 在指令间隙检查 `INTR` 引脚

**PA 中实现：** `cpu.INTR` 标志位，`cpu_exec()` 每条指令后检查。

## 四、Navy-apps 运行仙剑奇侠传

需要的完整支持：
- NEMU：TRM + IOE + ASYE + PTE + 时钟中断
- Nanos-lite：loader(ELF) + 文件系统 + 系统调用 + 虚拟内存管理
- Navy-apps：libc(Newlib) + libos（系统调用封装）

## 五、关键宏汇总（PA4）

| 宏 | 位置 | 作用 |
|----|------|------|
| `HAS_PTE` | `nanos-lite/src/main.c` | 启用分页，调 `init_mm()` → `_pte_init()` |
| `HAS_ASYE` | `nanos-lite/src/main.c` | 启用中断异常处理，调 `init_irq()` |

**注意：没有 `HAS_SCHEDULER` 宏。**  
调度器通过 `load_prog()` 加载多个进程 + `_trap()` 触发第一次调度来启动，不需要单独宏控制。

## 六、分页后的内存访问

**文件：** `nemu/src/memory/memory.c`

```c
// 开启分页后：
paddr_t paddr = page_translate(vaddr);  // 查页表做地址转换
// 未开启时：paddr = vaddr（恒等映射）
```

`vaddr_read/write()` → `paddr_read/write()` → 检查 MMIO → `pmem[]`
