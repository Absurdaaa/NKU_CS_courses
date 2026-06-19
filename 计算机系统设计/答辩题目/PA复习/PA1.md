# PA1 — 最简单的计算机：TRM + 简易调试器

## 一、TRM 结构

**图灵机（TRM）最小组成：**
- 存储器：`nemu/src/memory/memory.c` 中的大数组 `pmem`
- PC（EIP）+ 通用寄存器：`nemu/include/cpu/reg.h` 中的 `CPU_state` 结构体
- 加法器：在 PA2 中实现
- 工作方式：`cpu_exec()` → `exec_wrapper()` 不断循环

**TRM 工作循环（核心）：**
```
取指(IF) → 译码(ID) → 执行(EX) → 更新 EIP
```

## 二、寄存器结构体（重要考点）

**文件：** `nemu/include/cpu/reg.h`

x86 寄存器特点：EAX/AX/AH/AL 等物理上共享存储，用**匿名 union** 实现：
```c
typedef struct {
  union {
    union {
      uint32_t _32;
      uint16_t _16;
      uint8_t  _8[2];
    } gpr[8];  // EAX=0, ECX=1, EDX=2, EBX=3, ESP=4, EBP=5, ESI=6, EDI=7
  };
  vaddr_t eip;
  // EFLAGS, IDTR 等在 PA2/PA3 中添加
} CPU_state;
```

`reg_test()` 在 `nemu/src/cpu/reg.c` 中对寄存器实现做正确性检测。

## 三、NEMU 启动流程（宏调用链）

```
main()
└── init_monitor()          // nemu/src/monitor/monitor.c
    ├── reg_test()          // 测试寄存器实现
    ├── load_img()          // 把客户程序加载到 pmem[0x100000]
    ├── restart()           // cpu.eip = 0x100000
    └── welcome()
└── ui_mainloop()           // nemu/src/monitor/debug/ui.c
    └── 等待用户输入命令
        └── cmd_c() → cpu_exec(-1)   // -1 转成 uint64_t 极大值 → 一直跑
            └── exec_wrapper()       // 每次执行一条指令
```

**`cpu_exec(-1)` 为什么能一直跑：**  
参数类型是 `uint64_t`，`-1` 转换后变成 `0xFFFFFFFFFFFFFFFF`，约等于无限次循环。

**退出循环的条件：**
1. 达到循环次数
2. 客户程序执行了 `nemu_trap` 指令（机器码 `0xd6`）→ 输出 `HIT GOOD TRAP`

## 四、简易调试器命令

**文件：** `nemu/src/monitor/debug/ui.c`

| 命令 | 函数 | 说明 |
|------|------|------|
| `c` | `cmd_c()` | `cpu_exec(-1)` |
| `si [N]` | `cmd_si()` | `cpu_exec(N)`，默认 N=1 |
| `info r` | `cmd_info()` → `print_reg()` | 打印所有寄存器 |
| `info w` | `cmd_info()` → `print_wp()` | 打印监视点 |
| `p EXPR` | `cmd_p()` → `expr()` | 表达式求值 |
| `x N EXPR` | `cmd_x()` | 扫描内存（起始地址=EXPR值，输出N个4字节） |
| `w EXPR` | `cmd_w()` | 设置监视点 |
| `d N` | `cmd_d()` → `delete_wp(N)` | 删除编号N的监视点 |
| `q` | `cmd_q()` → 返回 -1 | 退出 |

用 `readline()` 读命令，支持历史记录（上下方向键）。

## 五、表达式求值

**文件：** `nemu/src/monitor/debug/expr.c`

**两步流程：**
1. **词法分析**：`make_token()` 用正则表达式识别 token，存入 `tokens[]` 数组
2. **递归求值**：`eval(p, q)` 对 tokens[p..q] 递归求值

**dominant operator（主运算符）查找规则：**
- 不在括号内
- 优先级最低
- 多个同优先级取最右边（左结合）

**指针解引用 vs 乘法区分：**  
看 `*` 前一个 token 的类型：若是数字/右括号/寄存器 → 乘法；否则 → 解引用。

**调试表达式扩展（完整 BNF）：**
```
expr ::= number
       | reg               ($eax)
       | expr +|-|*|/ expr
       | expr ==|!= expr
       | expr &&||| expr
       | -expr             (负号)
       | *expr             (指针解引用，用 vaddr_read())
       | (expr)
```
所有结果统一为 `uint32_t`。

## 六、监视点

**文件：** `nemu/include/monitor/watchpoint.h` + `nemu/src/monitor/debug/watchpoint.c`

**数据结构：** 链表 + 池（pool）
```c
typedef struct watchpoint {
  int NO;
  struct watchpoint *next;
  char expr[...];    // 监视的表达式字符串
  uint32_t val;      // 上一次的值
} WP;

static WP wp_pool[NR_WP];  // 静态池，NR_WP=32
WP *head, *free_;          // head: 使用中; free_: 空闲
```

**`static` 关键字的意义：** 限制变量作用域在本文件内（文件作用域），防止外部访问。

**工作原理：**  
`cpu_exec()` 每执行一条指令后，遍历 `head` 链表，对每个监视点重新 `eval()` 表达式，若值改变则设 `nemu_state = NEMU_STOP`。

**断点本质：** 用 `int3` 指令（opcode `0xCC`，1字节）替换原指令首字节实现 → "偷龙转凤"。

## 七、死循环检测（有点难度）

**文件：** `nemu/src/monitor/cpu-exec.c`

**宏开关：** `ENABLE_LOOP_DETECTOR`（默认 0，改为 1 开启）

**检测原理：** 用滑动窗口记录最近 N 条指令的 EIP，若同一地址重复出现超过阈值，判定为死循环。

**出现循环会怎样：** NEMU 会继续执行（无法自动检测），直到：
- 触发 `HIT BAD TRAP` / 段错误
- 或用户按 Ctrl+C 中断
- 或开启了 `ENABLE_LOOP_DETECTOR`

## 八、调试宏（`nemu/include/debug.h`）

```c
Log(...)    // 带文件名/行号/函数名的 printf
Assert(cond, ...) // 条件不满足时输出信息并 assert fail
panic(...)  // 无条件终止程序（= Assert(0, ...)）
```
