# TB缓存与JIT沙盒实现说明

> 文件：`nemu/src/monitor/cpu-exec.c`

---

## 一、Translation Block（TB）缓存

### 是什么

把一段连续执行的指令序列（一个 "基本块"）的元数据缓存起来。
下次执行到同一地址时，直接用缓存的元数据重放，跳过重新取指的开销。

### 数据结构

```c
typedef struct {
  vaddr_t   pc;          // 指令地址
  uint16_t  opcode;      // opcode（供exec_wrapper_cached使用）
  uint8_t   len;         // 指令字节数
  uint8_t   bytes[8];    // 原始机器码字节（JIT用）
  vaddr_t   next_eip;    // 执行后的下一条EIP
} TBInstr;

typedef struct {
  bool     valid;                    // 本槽是否有效
  vaddr_t  start_eip;               // 块起始EIP
  int      nr_instr;                 // 块内指令数
  TBInstr  instr[TB_MAX_INSTR];     // 最多32条指令的元数据
  // JIT相关字段（ENABLE_JIT_SANDBOX时才有）
  void    (*jit_fn[TB_MAX_INSTR])(); // 编译好的JIT函数指针
  uint8_t  *jit_buf[TB_MAX_INSTR];  // JIT代码的内存页
} TBEntry;

static TBEntry tb_cache[TB_CACHE_SIZE]; // 256个槽的哈希表
```

### 工作流程

```
cpu_exec执行一条指令：
  ┌─ tb_lookup(eip) → 命中？
  │   命中：直接遍历TBEntry.instr[]，调exec_wrapper_cached(opcode)
  │         跳过取指，速度更快
  └─ 未命中：正常exec_wrapper()执行
            + tb_record_step()把该指令记录到tb_building
            + 遇到"块结束"条件时tb_commit()把块存入缓存
```

### 块结束条件（`tb_force_block_end`）

```c
// 条件跳转指令（0x70~0x7F）强制结束块：
// 因为跳转目标不确定，不能把跳转后的指令也纳入同一个块
bool tb_force_block_end(uint16_t opcode) {
  uint8_t op = opcode & 0xff;
  return (op >= 0x70 && op <= 0x7f);  // jcc 系列
}

// 以及块内指令数达到 TB_MAX_INSTR（32条）时也结束
```

### 不可缓存的指令

```c
bool tb_cacheable_instr(vaddr_t pc) {
  return vaddr_read(pc, 1) != 0x66;  // operand-size前缀指令不缓存
}
```

---

## 二、JIT 沙盒（JIT Sandbox）

### 是什么

在 TB 缓存的基础上更进一步：把热点指令翻译成**宿主机原生 x86 机器码**，
直接由宿主机 CPU 执行，完全绕过 NEMU 的解释执行，速度接近原生。

### 目标范围

只对 PAL（仙剑）的特定函数做 JIT，精确到地址范围：

```c
bool jit_cacheable_pc(vaddr_t pc) {
  // PAL_MKF* 系列函数（解压缩热点）
  return pc >= 0x08064304u && pc < 0x0806457cu;
}
```

### 实现原理

对于每条可 JIT 的指令，在宿主机可执行内存（`mmap`）里生成一段原生代码：

```
x86客户指令：sub eax, ecx
      ↓ tb_try_build_jit() 生成宿主机代码
宿主机代码：
  push ecx_val    ; 把源寄存器值压栈
  push eax_val    ; 把目的寄存器值压栈  
  call jit_helper_sub_rr  ; 调C函数完成运算+更新EFLAGS
  add esp, 8
  ret
```

生成的函数通过`tb->jit_fn[i]` 保存，执行时直接 `tb->jit_fn[i]()` 调用，
不再走 NEMU 的 `exec_wrapper` 解释路径。

### 支持的指令（已实现 JIT 翻译）

| opcode | 指令形式 | helper函数 |
|--------|---------|-----------|
| 0x29/0x2B | `sub r,r` / `sub r,m` / `sub m,r` | `jit_helper_sub_rr/mem` |
| 0x39/0x3B | `cmp r,r` / `cmp r,m` / `cmp m,r` | `jit_helper_cmp_rr/mem` |
| 0x50~0x57 | `push r32` | `jit_helper_push_reg` |
| 0x58~0x5F | `pop r32` | `jit_helper_pop_reg` |
| 0x68 | `push imm32` | `jit_helper_push_imm` |
| 0x6A | `push imm8` | `jit_helper_push_imm` |
| 0x83 | `add/sub/cmp/and/or r,imm8`（符号扩展）| `jit_helper_grp1_83_reg` |
| 0x85 | `test r,r` | `jit_helper_test_rr` |
| 0x89 | `mov r→r` / `mov r→[mem]` | `jit_helper_mov_rr` / `jit_helper_mov_store` |
| 0x8B | `mov [mem]→r` | `jit_helper_mov_load` |
| 0xB8+r | `mov r,imm32` | 直接emit x86 `mov [addr],imm32` |
| 0xC1 | `shl/shr/sar r,imm8` | `jit_helper_shift_imm` |
| 0xC3 | `ret` | `jit_helper_ret` |
| 0xC9 | `leave` | `jit_helper_leave` |

### 为什么只需要实现这些指令？

**原因1：Amdahl's Law（JIT只需要覆盖热点）**

JIT仅对 `0x08064304~0x0806457c` 这段地址生效，对应 PAL 的 `PAL_MKF*` 系列解压缩函数（`DecompressChunk`）。用 `perf` 分析仙剑运行时，这段函数占了绝大部分CPU时间。

即使JIT只覆盖这一个函数，根据 Amdahl's Law，整体性能提升已经接近上限——优化那些本来就占用不了多少时间的代码意义不大。

**原因2：解压缩函数的指令分布**

解压缩/数据处理的热点代码特征：
- 大量整数运算（add/sub/cmp/test）
- 大量位移操作（shr/shl/sar）
- 频繁访存（mov r,m / mov m,r）
- 简单的控制流（push/pop/call/ret）

以上恰好就是已实现的指令集合。

**原因3：jcc 不需要JIT**

条件跳转（0x70~0x7F）会强制结束 TB 块，所以 jcc 由 TB 缓存机制处理，不进入 JIT 路径。

**遇到不支持的指令：**
```c
munmap(buf, 4096);  // 释放已分配的可执行内存
return false;       // 回退到 TB 缓存的普通解释执行路径
```

---

## 三、两者的关系

```
无优化（默认）：
  eip → exec_wrapper()（取指+译码+执行）逐条解释

TB缓存：
  eip → tb_lookup → 命中 → exec_wrapper_cached()（跳过取指）
                  → 未命中 → exec_wrapper() + 记录

JIT沙盒（在TB基础上）：
  eip → tb_lookup → 命中 → jit_fn[i]()（原生代码，最快）
                         → 无JIT则 exec_wrapper_cached()
```

## 四、开启方式

```c
// nemu/src/monitor/cpu-exec.c 顶部
#define ENABLE_TB_CACHE   1  // 第一步：开TB缓存
#define ENABLE_JIT_SANDBOX 1 // 第二步：开JIT（依赖TB_CACHE）
```

重新编译后运行 benchmark 对比开关前后的跑分差异。
