# PA2 — 冯诺依曼计算机系统：指令实现 + IOE

## 一、指令执行流程（重要考点）

**文件：** `nemu/src/monitor/cpu-exec.c` → `nemu/src/cpu/exec/exec.c`

```
cpu_exec(n)
└── exec_wrapper()          // nemu/src/cpu/exec/exec.c
    ├── 保存 eip 到 decoding.seq_eip
    └── exec_real(&eip)
        ├── instr_fetch()   // 取指：读 eip 处1字节 = opcode
        ├── set_width()     // 根据 opcode_table 设置操作数宽度
        └── idex(eip, &opcode_table[opcode])
            ├── e->decode(eip)   // 译码：填充 decoding.src/dest/src2
            └── e->execute(eip)  // 执行：用 RTL 指令实现语义
    └── update_eip()        // 更新 EIP（顺序 or 跳转）
```

**`update_eip()` 逻辑：**
```c
if (decoding.is_jmp)
    cpu.eip = decoding.jmp_eip;   // 跳转
else
    cpu.eip = decoding.seq_eip;   // 顺序下一条
```

## 二、opcode_table（译码查找表）

**文件：** `nemu/src/cpu/exec/exec.c`

```c
typedef struct {
  DHelper decode;    // 译码函数指针
  EHelper execute;   // 执行函数指针
  int width;         // 操作数宽度（0=按前缀决定）
} opcode_entry;

opcode_entry opcode_table[512];  // 前256项单字节，后256项0F前缀双字节
```

**填写方式：**
```c
IDEXW(G2E, add, 1)  // 译码:G2E, 执行:add, 宽度:1字节
IDEX(E2G, mov)      // 宽度由前缀决定
EX(call)            // 只有执行函数（译码在 decode_J 里）
EMPTY               // 未实现 → exec_inv() → panic
```

**宏定义：**
```c
make_EHelper(name)  // 定义 exec_name(vaddr_t *eip)
make_DHelper(name)  // 定义 decode_name(vaddr_t *eip)
```

## 三、关键指令实现

### call 指令（`nemu/src/cpu/exec/control.c`）

**考点：call 做了什么？**
1. 把**下一条指令地址（返回地址）压栈** `rtl_push(eip)`
2. 跳转到目标地址 `decoding.is_jmp = 1`

```c
make_EHelper(call) {
  rtl_push(eip);          // 把 eip（即返回地址）压栈
  decoding.is_jmp = 1;    // 设置跳转标志
  // 跳转目标已由 decode_J 算好，存在 decoding.jmp_eip
}
```

**考点：call 的目标地址放哪里？**  
存在 `decoding.jmp_eip`，由 `decode_J()` 在译码阶段算出（当前 EIP + 偏移量）。

### ret 指令

```c
make_EHelper(ret) {
  rtl_pop(&decoding.jmp_eip);  // 从栈顶弹出返回地址
  decoding.is_jmp = 1;
}
```

### jmp / jcc 指令

```c
make_EHelper(jmp) {
  decoding.is_jmp = 1;  // 目标已在 decoding.jmp_eip
}

make_EHelper(jcc) {
  uint8_t subcode = decoding.opcode & 0xf;
  rtl_setcc(&t2, subcode);  // 根据条件码设 t2=0/1
  decoding.is_jmp = t2;     // 条件成立才跳
}
```

**考点：指令地址（EIP）放在哪里？**  
- 顺序执行：`decoding.seq_eip`（取指后自动递增）
- 跳转目标：`decoding.jmp_eip`
- 最终由 `update_eip()` 决定写入 `cpu.eip`

## 四、RTL（寄存器传输语言）

**文件：** `nemu/include/cpu/rtl.h`

**RTL 基本指令（不需要临时寄存器）：**
```c
rtl_li(&dest, imm)          // 立即数写入
rtl_add/sub/and/or/xor...   // 算术/逻辑运算
rtl_lm(&dest, addr, len)    // 内存读
rtl_sm(addr, &src, len)     // 内存写
rtl_lr_l/w/b(&dest, reg)    // 通用寄存器读
rtl_sr_l/w/b(reg, &src)     // 通用寄存器写
```

**RTL 伪指令（用基本指令实现）：**
```c
rtl_push(&src)   // ESP-4, 写内存
rtl_pop(&dest)   // 读内存, ESP+4
rtl_mv(&dest, &src)
rtl_sext(&dest, &src, width)  // 符号扩展
```

**RTL 临时寄存器：** `t0, t1, t2, t3`（`uint32_t`），`tzero`（只读0）

## 五、AM 模型

```
AM = TRM + IOE + ASYE + PTE + MPE
```

| 模块 | 功能 | PA 阶段 |
|------|------|---------|
| TRM | 基本计算、内存、`_putc`、`_halt` | PA1/PA2 |
| IOE | 串口/时钟/键盘/VGA | PA2 |
| ASYE | 中断异常处理 | PA3 |
| PTE | 虚拟内存/分页 | PA4 |

**客户程序运行流程：**
```
start.S → _trm_init() → main() → _halt()
(nexus-am/am/arch/x86-nemu/img/boot/start.S)
(nexus-am/am/arch/x86-nemu/src/trm.c)
```

**`nemu_trap` 指令：** 机器码 `0xd6`，`_halt()` 内嵌汇编触发，让 NEMU 知道程序结束。

## 六、串口实现（重要考点）

**文件：** `nemu/src/device/serial.c`

**串口链路（完整调用链）：**
```
用户程序 printf()
  → _putc(ch)             [nexus-am/am/arch/x86-nemu/src/trm.c]
    → out指令写端口 0x3F8 [TRM API]
      → pio_write()        [nemu/src/device/io/port-io.c]
        → serial_io_handler() [nemu/src/device/serial.c]
          → putc(c, stdout) [输出到 NEMU 所在终端]
```

**关键代码：**
```c
#define SERIAL_PORT 0x3F8
void serial_io_handler(ioaddr_t addr, int len, bool is_write) {
  if (is_write && addr == SERIAL_PORT + CH_OFFSET) {
    char c = serial_port_base[CH_OFFSET];
    putc(c, stdout);  // 直接输出到主机 stdout
  }
}
void init_serial() {
  serial_port_base = add_pio_map(SERIAL_PORT, 8, serial_io_handler);
  serial_port_base[LSR_OFFSET] = 0x20;  // 状态寄存器：总是就绪
}
```

**宏 `HAS_IOE` 开启后调用链：**
```
nemu 启动
└── init_monitor()
    └── init_device()       [nemu/src/device/device.c, 需 HAS_IOE]
        ├── init_serial()
        ├── init_timer()
        ├── init_keyboard()
        └── init_vga()      → 创建 SDL 窗口
```

## 七、VGA 实现（重要考点）

**文件：** `nemu/src/device/vga.c`

**VGA 使用内存映射 I/O（MMIO）：**
- 物理地址 `0x40000` 开始的一段内存映射到 VGA 显存
    把地址范围 0x40000~0xBFFFF 标记为"MMIO区域"，访问它不走pmem，改走vmem数组。
- 程序用普通 `mov` 指令写这段内存 = 写 VGA 显存

```c
#define VMEM 0x40000
#define SCREEN_H 300
#define SCREEN_W 400

void init_vga() {
  SDL_Init(SDL_INIT_VIDEO);
  SDL_CreateWindowAndRenderer(SCREEN_W*2, SCREEN_H*2, ...);
  vmem = add_mmio_map(VMEM, 0x80000, vga_vmem_io_handler);
}
void update_screen() {
  SDL_UpdateTexture(texture, NULL, vmem, SCREEN_W * sizeof(uint32_t));
  SDL_RenderCopy(renderer, texture, NULL, NULL);
  SDL_RenderPresent(renderer);
}
```

**VGA 访问链路：**
```
用户程序写地址 0x40000~
  → paddr_write()          [nemu/src/memory/memory.c]
    → is_mmio() 判断是否映射区域
      → mmio_write()        [nemu/src/device/io/mmio.c]
        → 写入 vmem 数组
          → update_screen() 由定时器 50Hz 刷新
```

**AM 中 `_draw_rect()` 实现：**  
`nexus-am/am/arch/x86-nemu/src/ioe.c`  
计算目标像素在显存中的偏移，用 `memcpy` 写入 `(void*)VMEM + offset`。

## 八、端口 I/O vs 内存映射 I/O

| | 端口映射 I/O | 内存映射 I/O |
|--|---|---|
| 指令 | `in`/`out` 专用指令 | 普通 `mov` 等访存指令 |
| 示例设备 | 串口(0x3F8)、键盘(0x60)、时钟(0x48) | VGA 显存(0x40000) |
| 地址空间 | 独立 I/O 空间 | 占用物理内存地址空间 |
| 访问函数 | `pio_read/write()` | `mmio_read/write()` |

## 九、Differential Testing

**原理：** 让 NEMU 和 QEMU 逐条执行同一程序，每条指令后对比寄存器状态。

**宏：** `DIFF_TEST`（在 `nemu/include/common.h` 中定义）

**文件：** `nemu/src/monitor/diff-test/diff-test.c` → `difftest_step()`

**为什么 in/out 跳过对比：** NEMU 串口总就绪，QEMU 串口不一定，行为不同，用 `is_skip_nemu/qemu` 标志跳过。

## 十、死循环相关（考点）

**出现死循环时：**
- NEMU 会一直在 `cpu_exec()` 里循环执行，无法自行发现
- 用户可用 `Ctrl+C` 中断 → 返回 `ui_mainloop()`

**如何判断死循环：**  
`ENABLE_LOOP_DETECTOR = 1`（`nemu/src/monitor/cpu-exec.c`）：  
维护一个滑动窗口（`LOOP_WINDOW_SIZE=32`），记录最近执行的 EIP，若同一 EIP 出现次数超过 `LOOP_REPEAT_THRESHOLD=20`，判定为死循环并输出提示、暂停执行。
