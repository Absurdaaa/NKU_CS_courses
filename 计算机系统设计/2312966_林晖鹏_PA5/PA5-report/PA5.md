# PA5 过程记录

## 1. PA5 起步：先把指导书重新整理成实现主线

这一轮没有一上来就改代码，而是先把 `PA5实验指导.pdf` 重新读了一遍，并整理成了：

- [08-PA5-程序与性能.md](/Users/linshangjin/Desktop/PA/PA指导书/08-PA5-程序与性能.md)

这一步的目的是先确认 `PA5` 真正要做的事情是什么，避免继续沿用 `PA4` 的思路误改。

整理后的结论是：

1. `PA5` 真正需要落代码的核心是 `FLOAT / binary scaling`
2. 后半部分的 `Amdahl's law`、`perf`、`JIT`、`TB`、`RTL` 更偏性能分析和设计理解
3. `PA5` 本身并不要求继续做多进程或分时展示，因此 `PA4` 留下来的 `pal + hello + videotest` 并不是这次实验的主线

这个判断对后面排查性能和验证战斗都很重要。

---

## 2. 先同步代码状态：单独拉一份本地 `pa5` 工作区

一开始本地的 [ics2017](/Users/linshangjin/Desktop/PA/ics2017) 还停留在 `pa4` 分支，而且工作区里已经有很多 `PA4` 的未提交改动。如果直接在这份代码上切 `pa5`，风险很大，容易把两次实验的状态混在一起。

因此这一步没有直接覆盖本地原工作区，而是：

1. 先确认远端虚拟机上的 `~/code/ics2017` 当前分支是 `pa5`
2. 再把远端整份仓库同步到本地一个新目录：

```text
/Users/linshangjin/Desktop/PA/ics2017-pa5
```

这样做之后：

- 原来的 `ics2017` 仍然保留 `PA4` 状态
- 新的 `ics2017-pa5` 单独对应 `PA5`
- 后面所有 `FLOAT` 修改和验证都在 `ics2017-pa5` 上进行

这一步完成后，本地 `pa5` 代码和远端 `pa5` 代码进入了可对齐状态。

---

## 3. 定位 PA5 真实需要补的代码：`FLOAT.h` 和 `FLOAT.c`

根据指导书，`PA5` 需要补的函数集中在：

- [FLOAT.h](/Users/linshangjin/Desktop/PA/ics2017-pa5/navy-apps/apps/pal/include/FLOAT.h)
- [FLOAT.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/navy-apps/apps/pal/src/FLOAT/FLOAT.c)

一开始这两个文件里的实现都是空壳，核心函数全部停在：

```c
assert(0);
```

具体要补的函数是：

- `F2int()`
- `int2F()`
- `F_mul_int()`
- `F_div_int()`
- `f2F()`
- `F_mul_F()`
- `F_div_F()`
- `Fabs()`

这一步先没有去碰 `NEMU`、`AM`、`Nanos-lite`，而是集中把 `PAL` 里的定点数支持补齐。原因很直接：指导书前半部分真正需要写代码的核心就是这一块。

---

## 4. 实现 `binary scaling`

### 4.1 先补最基础的缩放关系

在 [FLOAT.h](/Users/linshangjin/Desktop/PA/ics2017-pa5/navy-apps/apps/pal/include/FLOAT.h) 里，先补了两个基础常量：

```c
#define FLOAT_FRAC_BITS 16
#define FLOAT_SCALE (1 << FLOAT_FRAC_BITS)
```

后面的所有实现都围绕这个固定缩放因子 `2^16` 展开。

然后依次补了：

```c
static inline int F2int(FLOAT a) {
  int64_t mag = (a < 0) ? -(int64_t)a : (int64_t)a;
  int ret = (int)(mag >> FLOAT_FRAC_BITS);
  return (a < 0) ? -ret : ret;
}

static inline FLOAT int2F(int a) {
  return (FLOAT)(a << FLOAT_FRAC_BITS);
}

static inline FLOAT F_mul_int(FLOAT a, int b) {
  return (FLOAT)((int64_t)a * b);
}

static inline FLOAT F_div_int(FLOAT a, int b) {
  assert(b != 0);
  return a / b;
}
```

这里的实现思路是：

- `int2F()` 直接左移 16 位
- `F2int()` 再右移 16 位，但要注意负数截断
- `F_mul_int()` / `F_div_int()` 走整数快捷路径，不必先把 `int` 转成 `FLOAT`

### 4.2 再补 `F_mul_F()`、`F_div_F()`、`f2F()`、`Fabs()`

在 [FLOAT.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/navy-apps/apps/pal/src/FLOAT/FLOAT.c) 里，首先补的是：

```c
FLOAT F_mul_F(FLOAT a, FLOAT b) {
  return (FLOAT)(((int64_t)a * b) / FLOAT_SCALE);
}
```

这对应指导书里的关系：

```text
(a * 2^16) * (b * 2^16) = (a * b) * 2^32
```

因此乘完之后必须再除一次 `2^16`。

`Fabs()` 最简单，直接按补码整数取绝对值：

```c
FLOAT Fabs(FLOAT a) {
  return (a < 0) ? -a : a;
}
```

最需要小心的是 `f2F()`。指导书明确要求：

```text
不能直接引入 x87 浮点指令
```

因此这里没有直接写浮点算术，而是通过位级方式解析 `float`：

```c
union {
  float f;
  uint32_t u;
} conv = { .f = a };
```

然后从二进制表示里拆出：

- 符号位
- 指数
- 尾数

最后按 `FLOAT = real * 2^16` 的含义重新拼回定点结果。

### 4.3 中途修了一次：`F_div_F()` 不能直接用 64 位整除

一开始 `F_div_F()` 的实现是：

```c
return (FLOAT)(((int64_t)a * FLOAT_SCALE) / b);
```

逻辑上没问题，但远端重新编译 `pal-x86` 时直接报出：

```text
undefined reference to `__divdi3'
```

这说明：

- 目标是 32 位环境
- 链接阶段缺少 64 位整除运行库支持

所以这一版实现虽然“数学上是对的”，但“工程上在当前环境里不能用”。

后面改成了手写长除法：

```c
static uint32_t udiv64by32(uint64_t dividend, uint32_t divisor) {
  uint64_t quotient = 0;
  uint64_t remainder = 0;

  assert(divisor != 0);

  for (int i = 47; i >= 0; i--) {
    remainder = (remainder << 1) | ((dividend >> i) & 1u);
    quotient <<= 1;
    if (remainder >= divisor) {
      remainder -= divisor;
      quotient |= 1;
    }
  }

  assert((quotient >> 32) == 0);
  return (uint32_t)quotient;
}
```

然后 `F_div_F()` 改成：

```c
FLOAT F_div_F(FLOAT a, FLOAT b) {
  uint32_t ua = (a < 0) ? -(uint32_t)a : (uint32_t)a;
  uint32_t ub = (b < 0) ? -(uint32_t)b : (uint32_t)b;
  FLOAT ret;

  assert(b != 0);

  ret = (FLOAT)udiv64by32((uint64_t)ua << FLOAT_FRAC_BITS, ub);
  return ((a < 0) ^ (b < 0)) ? -ret : ret;
}
```

这样既保持了 `FLOAT` 除法语义，又绕开了 `__divdi3` 链接问题。

---

## 5. 本地数值验证

在真正同步远端之前，先在本地做了几组轻量验证。

### 5.1 对照指导书例子

本地小测试结果：

```text
f2F(1.2)=0x13333
f2F(5.6)=0x59999
f2F(-1.2)=0xfffecccd
int2F(3)=0x30000
F2int(int2F(3))=3
F_mul_F(2,3)=6
F_div_F(7,2)=3
Fabs(-1.2)=0x13333
```

其中前三项正好和指导书给出的例子一致，说明：

- `f2F()` 没写反
- 符号位和缩放位数正确
- 负数补码处理正确

### 5.2 补充验证 `Fsqrt()` 和 `Fpow()`

虽然这两个函数原本就在框架代码里，但它们依赖的底层 `FLOAT` 运算刚刚被补齐，因此又额外测了一次：

```text
Fsqrt(4)=0x20000 int=2
Fsqrt(2)=0x16a0a
Fpow(8,0)=0x20000 int=2
F_div_int(Fsqrt(4),2)=0x10000
```

---

## 6. 先把 `PA4` 留下来的多进程影响收掉

`PA5` 的目标是验证 `FLOAT` 和后面的性能分析，不需要继续保留 `pal + hello + videotest` 这套分时展示。前面如果直接沿用 `PA4` 的状态，`pal` 在远端会非常卡，前面的剧情都推进得很慢，更别说进入战斗验证。

因此先把 [main.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nanos-lite/src/main.c) 改回单进程，只保留：

```c
load_prog("/bin/pal");
```

这样做的目的不是“偷懒”，而是把 `PA5` 收敛回真正需要分析的场景：

- 只有 `pal`
- 没有 `hello` 的额外输出
- 没有 `videotest` 和 `F12` 切换
- 后面 `perf` 的热点也更集中在 `NEMU` 本身

远端重新运行后，日志里只剩 `/bin/pal`，说明这一步已经生效。

---

## 7. 第一轮 `perf`：先看启动阶段热点在哪里

远端安装好 `perf` 之后，先做了第一轮约 `25s` 的采样，命令思路是：

```bash
printf "c\n" | timeout 25s perf record -F 99 -g \
  ./nemu/build/nemu ./nanos-lite/build/nanos-lite-x86-nemu.bin
```

然后导出文本报告：

```bash
perf report --stdio --sort symbol
```

这一轮采样覆盖的还不是战斗阶段，而是 `pal` 的启动和资源加载阶段。运行日志里主要是：

- `VIDEO_Init success`
- `PAL_InitResources success`
- 各种 `*.mkf`、`*.dat` 资源文件读取

第一轮热点大致是：

- `is_mmio`：`18.40%`
- `page_translate.part.1`：`13.83%`
- `paddr_read`：`12.52%`
- `__memcpy_sse2_unaligned`：`11.17%`
- `paddr_write`：`9.09%`
- `vaddr_read`：`6.60%`

这一轮给出的结论很明确：

1. 当前瓶颈主要不在 `pal` 的上层游戏逻辑，而在 `NEMU` 的访存辅助路径。
2. 分页打开后，一次客户程序访存会经过：

```text
vaddr_read / vaddr_write
-> page_translate
-> paddr_read / paddr_write
-> is_mmio
```

3. 启动阶段还存在大量数据搬运，所以 `__memcpy_sse2_unaligned` 也比较高。

也就是说，后面真正值得优先优化的，不是 `pal` 自己，而是 `NEMU` 里的地址翻译和物理访存相关代码。

---

## 8. 第一轮优化：`is_mmio()` 快路径和 `A/D` 位条件回写

### 8.1 给 `is_mmio()` 加快路径

在 [mmio.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nemu/src/device/io/mmio.c) 里，原来的 `is_mmio()` 每次都会线性扫描映射表：

```c
int is_mmio(paddr_t addr) {
  int i;
  for (i = 0; i < nr_map; i ++) {
    if (addr >= maps[i].low && addr <= maps[i].high) {
      return i;
    }
  }
  return -1;
}
```

当前实验场景里 MMIO 区域很少，这样每次都完整扫描，开销不划算。因此这里补成了：

```c
int is_mmio(paddr_t addr) {
  if (nr_map == 0) {
    return -1;
  }

  if (nr_map == 1) {
    return (addr >= maps[0].low && addr <= maps[0].high) ? 0 : -1;
  }

  for (int i = 0; i < nr_map; i++) {
    if (addr >= maps[i].low && addr <= maps[i].high) {
      return i;
    }
  }
  return -1;
}
```

改完之后：

- 没有 MMIO 时直接返回
- 只有一个 MMIO 区间时只做一次区间判断
- 只有多于一个区间时才走原来的扫描路径

### 8.2 `page_translate()` 只在位真的变化时才写回

在 [memory.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nemu/src/memory/memory.c) 里，原来的代码每次地址翻译都会无条件写回 PDE/PTE：

```c
pde.accessed = 1;
paddr_write(..., pde.val);

pte.accessed = 1;
if (is_write) {
  pte.dirty = 1;
}
paddr_write(..., pte.val);
```

这样会带来很多额外的 `paddr_write()`，即使：

- `accessed` 早就已经是 `1`
- `dirty` 也早就已经是 `1`

所以这里改成了“只有状态真正从 `0 -> 1` 时才回写”，例如：

```c
if (pde.accessed == 0) {
  pde.accessed = 1;
  paddr_write(pdir_base + pde_index * 4, 4, pde.val);
}

if (pte.accessed == 0 || (is_write && pte.dirty == 0)) {
  pte.accessed = 1;
  if (is_write) {
    pte.dirty = 1;
  }
  paddr_write(ptab_base + pte_index * 4, 4, pte.val);
}
```

### 8.3 本地小测试

为了避免直接上远端试错，这两处改动先做了轻量测试：

- `mmio fast-path test passed`
- `page_translate writeback test passed`

测试目的主要是确认两件事：

1. 对外可见行为不变
2. 冗余写回和冗余路径确实减少

---

## 9. 第二轮 `perf`：局部优化有效，但瓶颈还在访存路径

第一轮优化之后，又做了一轮新的 `perf`。与最初结果对比，比较明显的变化是：

- `paddr_write`：`9.09% -> 7.78%`
- `page_translate.part.1`：`13.83% -> 13.44%`
- `paddr_read`：`12.52% -> 11.65%`

说明这轮优化不是白做，特别是：

- `A/D` 位条件回写确实减少了很多无意义页表写回
- `paddr_write` 的占比肉眼可见地降下来了

但与此同时，`is_mmio` 仍然很高，仍然接近 `19%`。  
这意味着：

1. `A/D` 位条件回写只是去掉了访存链上的一部分额外负担
2. 当前真正更顽固的热点，依然是“每次物理访存都要付出的 MMIO 判断成本”

这一轮之后，优化方向就更清楚了：后面应该继续压低访存路径里的固定成本，而不是去怀疑 `pal` 自己的逻辑。

---

## 10. 继续压热路径：跳过无效 watchpoint 检查，并关掉高频日志

### 10.1 没有 watchpoint 时，直接跳过 `check_watchpoints()`

在 [cpu-exec.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nemu/src/monitor/cpu-exec.c) 里，原来每条指令后都会调用：

```c
if (check_watchpoints()) {
  ...
}
```

即使当前根本没有任何 watchpoint，也要做一次函数调用和遍历。

因此这里先在 [watchpoint.h](/Users/linshangjin/Desktop/PA/ics2017-pa5/nemu/include/monitor/watchpoint.h) 中补声明：

```c
bool has_watchpoints();
```

再在 [watchpoint.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nemu/src/monitor/debug/watchpoint.c) 中实现：

```c
bool has_watchpoints() {
  return head != NULL;
}
```

最后把 `cpu_exec()` 改成：

```c
if (has_watchpoints()) {
  if (check_watchpoints()) {
    nemu_state = NEMU_STOP;
    printf("Watchpoints were triggered.\n");
  }
}
```

这样在正常运行 `pal` 时，如果根本没有设置监视点，就完全不需要为这条调试路径付费。

### 10.2 去掉高频日志

为了让 `perf` 更接近真实热点，也顺手去掉了几类会大量刷屏的日志：

- [fs.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nanos-lite/src/fs.c) 里的 `Pathname`
- [irq.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nanos-lite/src/irq.c) 里的 `do_event time`
- [proc.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nanos-lite/src/proc.c) 里的 `schedule[...]`
- [syscall.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nanos-lite/src/syscall.c) 里的 `SYS_write(...)`
- [exec.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nemu/src/cpu/exec/exec.c) 里的 `exec_wrapper irq[...]`

这些日志在调试时有用，但在性能测试阶段会额外放慢程序推进，尤其是 `pal` 启动阶段本身就伴随大量资源读取。

### 10.3 单进程时直接返回，不再做多余调度

既然这轮 `PA5` 已经收敛成单进程 `pal`，那么在 [proc.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nanos-lite/src/proc.c) 里，也没有必要继续保留多进程切换路径。

因此补了：

```c
if (nr_proc == 1) {
  return current->tf;
}
```

这样在只有 `pal` 的情况下：

- 只保存当前 trap frame
- 直接恢复当前进程
- 不再做无意义的进程轮转和页表切换

这一步虽然不是第一热点，但逻辑上更贴合 `PA5` 当前场景，也减少了不必要的额外路径。

---

## 11. 构建和采样过程中的一次排查：旧二进制导致结果失真

中间有一段时间，虽然源码已经更新了，但跑出来的新 `perf` 结果还是能看到大量旧日志，例如：

- `Pathname:`
- `schedule[...]`
- `do_event time[...]`
- `exec_wrapper irq[...]`

后来重新核对发现，问题不在源码，而在构建流程：

1. 前面同步代码时，远端误留下了几份重复源码，导致 `NEMU` 一度出现重复定义链接错误。
2. `nanos-lite` 的 `build/ramdisk.img` 会被 `clean` 删除，而 `update` 目标又要求 `build/` 目录先存在。
3. 结果就是：有时源码改了，但真正用于采样的二进制并没有成功重建。

这段排查最终确认后，远端重新做了完整流程：

```bash
cd ~/code/ics2017/nemu
make clean
make -j"$(nproc)"

cd ~/code/ics2017/nanos-lite
make ARCH=x86-nemu clean
mkdir -p build
make ARCH=x86-nemu update
make ARCH=x86-nemu -j"$(nproc)"
```

这一步完成后，运行日志才真正体现出最新代码状态：

- 高频日志大幅减少
- 单进程 `pal` 初始化链更干净
- 采样结果终于能对应当前源码

这一段虽然不是功能实现本身，但对后面写报告很重要：它说明性能对比一定要建立在“源码和二进制一致”的前提上，否则结论会失真。

---

## 12. 第四轮 `perf`：第一次拿到与当前源码一致的干净结果

### 12.1 运行现象

这次重新完整编译后，再做了一轮新的 `perf` 采样，对应文件已经归档到：

- [pa5-pal-opt4.run.log](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/opt4/pa5-pal-opt4.run.log)
- [pa5-pal-opt4.perf.report.txt](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/opt4/pa5-pal-opt4.perf.report.txt)
- [pa5-pal-opt4.perf.report.symbol.txt](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/opt4/pa5-pal-opt4.perf.report.symbol.txt)

这一次运行日志和前几轮相比明显干净很多，只剩：

- `game start!`
- `VIDEO_Init success`
- 资源加载过程
- `PAL_InitResources success`

而前面那些高频调试日志已经基本不见了。

### 12.2 新的热点分布

这次的主要热点是：

- `is_mmio`：`18.39%`
- `paddr_read`：`18.10%`
- `page_translate.part.1`：`15.46%`
- `vaddr_read`：`9.72%`
- `exec_real`：`6.71%`
- `read_ModR_M`：`5.41%`

有两个变化非常重要：

1. `check_watchpoints` 已经不再作为主要独立热点出现  
   说明“没有 watchpoint 时直接跳过”的优化确实生效了。

2. `__memcpy_sse2_unaligned` 从前几轮的明显热点降到了很低  
   这和日志减少、采样更干净是对应的，也说明之前一部分噪声被剥掉了。

### 12.3 这轮结果说明了什么

到这一步，热点已经更加集中地落在真正的访存路径上：

```text
vaddr_read
-> page_translate
-> paddr_read
-> is_mmio
```

因此现在可以更有把握地说：

1. 之前那轮 `A/D` 位条件回写优化是有效的，但它只是削掉了附加开销。
2. 当前最大的结构性瓶颈，仍然是 `NEMU` 解释执行中的访存辅助路径。
3. `is_mmio` 和 `paddr_read` 都接近 `18%`，说明每次物理访存的固定成本依旧很高。

这和 PA5 指导书后半部分引出 `basic block`、`TB`、`JIT` 的思路是吻合的：如果想进一步明显提速，就不能只靠零散的小补丁，最终还是要想办法减少解释执行和访存辅助路径的重复成本。

---

## 13. 当前阶段可以给出的优化建议

结合现在已经做过的修改和 `opt4` 的结果，后面如果还要继续优化，最有价值的方向是：

1. 继续压 `is_mmio()` 的调用成本  
   当前虽然已经加了快路径，但每次物理访存仍然要调用它。后面可以考虑进一步做成更直接的普通内存快路径。

2. 继续减少 `page_translate()` 的重复工作  
   例如进一步考虑页表访问缓存，而不是每次都完整走两级页表。

3. 如果需要写报告中的“更大方向”，可以把 `basic block`、`TB`、`JIT` 写成结构性优化思路  
   当前实验还没真正实现这些大改动，但从热点结果看，它们的设计动机已经非常清楚。

目前这份 `PA5` 过程记录已经保留了：

- 初始实现
- 本地验证
- 两轮以上 `perf`
- 每次优化的原因
- 最后一轮干净采样的真实结论

后面如果继续推进战斗验证或继续做性能优化，可以直接在这份材料上往后追加。

这说明：

- `Fsqrt()` 能正常迭代收敛
- `Fpow()` 当前被当作立方根使用时也能跑通

---

## 6. 同步远端并重新编译

本地验证通过后，把：

- `navy-apps/apps/pal/include/FLOAT.h`
- `navy-apps/apps/pal/src/FLOAT/FLOAT.c`

同步到了远端虚拟机的：

```text
~/code/ics2017
```

然后在远端执行：

```bash
cd ~/code/ics2017/nanos-lite
export NEMU_HOME=~/code/ics2017/nemu
export AM_HOME=~/code/ics2017/nexus-am
export NAVY_HOME=~/code/ics2017/navy-apps
make ARCH=x86-nemu update
```

第一次重编时，`pal-x86` 在链接阶段因为 `__divdi3` 失败；修掉 `F_div_F()` 之后再次执行，`make update` 通过，`pal-x86` 成功链接。

这一步的结论是：

- `FLOAT` 的功能实现已经能在远端真实编译环境里通过
- 这不是只停留在本地小样例上的逻辑正确

---

## 7. 远端运行验证：至少能越过 PAL 初始化

远端编译通过之后，继续在虚拟机上做了一次真实运行验证。  
早期日志中已经能看到：

```text
VIDEO_Init success
PAL_InitGolbals success
PAL_InitFont success
PAL_InitUI success
PAL_InitText success
PAL_InitInput success
PAL_InitResources success
```

并且还能继续读取：

```text
/share/games/pal/*.mkf
```

这说明：

- 这次 `FLOAT` 补全没有把 `PAL` 的启动链打坏
- 程序至少能稳定越过最早的初始化阶段

不过这一步还不能直接宣称“战斗完全验证通过”，因为当时的主要问题已经变成：

```text
远端运行太卡，剧情推进很慢，短时间内进不了战斗
```

也就是说，后面阻塞验证的主要矛盾，已经从“浮点数是不是坏了”转成了“整体执行速度太慢”。

---

## 8. PA5 不应继续沿用 PA4 的多进程负担

在继续排查之前，先重新对照指导书确认了一次边界：

```text
PA5 本身不要求继续做 pal + hello + videotest 的分时展示
```

但远端 `pa5` 代码当时继承了 `PA4` 的状态，仍然在：

- 加载 `/bin/hello`
- 加载 `/bin/videotest`
- 保留 `current_game`
- 保留优先级调度

这会明显拖慢 `pal`。

所以后面把 `nanos-lite/src/main.c` 收敛回了单进程：

```c
load_prog("/bin/pal");
_trap();
```

去掉了：

- `/bin/hello`
- `/bin/videotest`

这样之后：

- 日志里只看到 `/bin/pal`
- `schedule()` 只会反复返回 `pal`
- 不再被 `hello` 的输出和 `videotest` 的切换干扰

这一步的目标不是“做性能优化”，而是先把 `PA5` 收敛回指导书真正关心的单进程场景。

---

## 9. 为什么开始做热点分析

到这一步时，问题已经很明确：

```text
FLOAT 功能已经补上
编译也能通过
PAL 初始化也能继续推进
但远端运行很卡，推进剧情太慢，不方便短时间内进入战斗做最终验证
```

因此开始转入指导书后半部分提到的热点分析。

这里不是立刻盲目改代码，而是先问一个更实际的问题：

```text
当前到底慢在什么地方
```

---

## 10. 配置并使用 `perf`

在远端虚拟机上先确认了：

```text
perf version 4.15.18
```

然后又发现一个权限问题：  
直接运行 `perf record` 会报：

```text
perf_event_open(...): Permission denied
kernel.perf_event_paranoid = 3
```

说明：

- 虽然 `perf` 已经装好
- 但普通用户还不能直接采样

后面通过调整：

```bash
sudo sysctl -w kernel.perf_event_paranoid=-1
sudo sysctl -w kernel.kptr_restrict=0
```

才让 `perf record` 真正可用。

---

## 11. 第一次热点采样

真正跑起来的采样命令是：

```bash
printf "c\n" | timeout 25s perf record -F 99 -g -o /tmp/pa5-pal.perf.data \
  ./nemu/build/nemu ./nanos-lite/build/nanos-lite-x86-nemu.bin \
  > /tmp/pa5-pal-run.log 2>&1
```

然后导出文本报告：

```bash
perf report --stdio -i /tmp/pa5-pal.perf.data --sort comm,dso,symbol \
  > /tmp/pa5-pal.perf.report.txt

perf report --stdio -i /tmp/pa5-pal.perf.data --sort symbol \
  > /tmp/pa5-pal.perf.report.symbol.txt
```

这次采样结果是：

```text
[ perf record: Captured and wrote 0.180 MB /tmp/pa5-pal.perf.data (2364 samples) ]
```

说明这次采样是真正成功了，不再是前面那种 0 字节空文件。

---

## 12. 热点分析结果

这次 25 秒采样覆盖的还是 `PAL` 启动和资源加载阶段，而不是战斗阶段。  
从运行日志看，当时程序主要还在：

- 读取 `/bin/pal`
- 初始化 `VIDEO`
- 读取 `fbp.mkf / mgo.mkf / ball.mkf / data.mkf ...`
- 初始化字体、UI、文本和资源

热点主要集中在这些符号上：

- `is_mmio`：约 `18.40%`
- `page_translate.part.1`：约 `13.83%`
- `paddr_read`：约 `12.52%`
- `paddr_write`：约 `9.09%`
- `vaddr_read`：约 `6.60%`
- `exec_real`：约 `4.19%`
- `read_ModR_M`、`decode_mov_G2E`、`decode_mov_E2G` 等译码路径也占了一部分
- `__memcpy_sse2_unaligned`：约 `11.17%`

这里最重要的结论有两条：

### 12.1 热点集中在访存和分页辅助路径

`is_mmio`、`page_translate`、`paddr_read`、`paddr_write`、`vaddr_read` 这一组热点说明：

```text
当前性能瓶颈主要来自访存路径过长
```

也就是客户程序的一次内存访问，在 NEMU 里会继续触发：

- 页表遍历
- MMIO 判断
- 物理内存读写

这和 `PA5` 指导书后半部分对“解释执行天然很慢”的分析是吻合的。

进一步对照代码之后，又发现了两个非常具体的问题：

1. `is_mmio()` 本身是线性扫描  
   当前实现位于 `nemu/src/device/io/mmio.c`，每次物理访存都会扫描整个 `maps[]` 表：

```c
int is_mmio(paddr_t addr) {
  int i;
  for (i = 0; i < nr_map; i ++) {
    if (addr >= maps[i].low && addr <= maps[i].high) {
      return i;
    }
  }
  return -1;
}
```

但在当前实验环境里，`MMIO` 实际上非常少，启动阶段最主要的是 `VGA` 显存这一项。  
这意味着：

```text
很多本来就是普通内存的访问
也要先走一遍通用 MMIO 查找逻辑
```

这正好解释了为什么 `is_mmio` 会在热点里排到非常靠前。

2. `page_translate()` 会无条件回写 PDE/PTE  
   当前实现在每次地址翻译时都会：

```c
pde.accessed = 1;
paddr_write(..., pde.val);

pte.accessed = 1;
if (is_write) {
  pte.dirty = 1;
}
paddr_write(..., pte.val);
```

这会带来一个额外问题：

```text
即使 accessed 已经是 1
即使 dirty 已经是 1
仍然会再做一次 paddr_write()
```

这样又进一步放大了：

- `paddr_write`
- `paddr_read`
- `is_mmio`

这些访存相关热点。

### 12.2 启动阶段还有明显的数据搬运开销

`__memcpy_sse2_unaligned` 也占了比较高的比例，说明：

```text
PAL 启动阶段的大量资源加载和数据搬运也是热点来源
```

换句话说，这次采样结果并没有把热点指向某个“上层游戏逻辑函数”，而是把热点指向了：

- 解释执行本身
- 访存辅助路径
- 启动资源搬运

这也是为什么当前运行会明显偏慢。

---

## 13. 根据热点分析得到的第一轮优化思路

这次分析之后，没有立刻去碰更大的设计，比如 `TB`、`basic block` 或 `JIT`，而是先挑了两处“当前代码里就能看见、而且收益方向明确”的点：

### 13.1 给 `is_mmio()` 增加快路径

优化目标：

```text
在 MMIO 映射很少时，不要每次都走完整的线性扫描
```

因为当前实验场景下：

- `nr_map == 0` 时可以直接返回 `-1`
- `nr_map == 1` 时只需要一次区间判断

因此这一处属于“保持行为不变，但减少无意义查找开销”的优化。

### 13.2 让 `page_translate()` 只在 A/D 位发生变化时才回写

优化目标：

```text
避免每次地址翻译都无条件写回 PDE/PTE
```

正确语义其实只是：

- 第一次访问时把 `accessed` 置 1
- 第一次写入时把 `dirty` 置 1

如果这些位本来就已经是 `1`，再次回写不会改变外部可见结果，只会增加额外的物理写操作。

因此这一处属于“保持翻译结果和页表状态语义不变，但减少重复写回”的优化。

---

## 14. 继续尝试两版 `is_mmio()` 优化

前面的 `opt4` 已经把热点收敛得比较清楚了：

- `is_mmio`
- `paddr_read`
- `page_translate.part.1`

其中 `is_mmio` 仍然在 `18%` 左右。于是这里继续尝试两种更直接的优化思路，并通过远端重新编译和 `perf` 对比来决定保留哪一版。

### 14.1 方案 A：按区间排序，再用二分查找

第一版思路比较保守：仍然保留“区间数组”这个数据结构，但把映射表按 `low` 有序维护，然后把原来的线性扫描：

```c
for (i = 0; i < nr_map; i ++) {
  if (addr >= maps[i].low && addr <= maps[i].high) {
    return i;
  }
}
```

改成：

1. `add_mmio_map()` 插入时按 `low` 排序
2. `is_mmio()` 查询时用二分查找

核心代码如下：

```c
static void insert_mmio_map_sorted(MMIO_t map) {
  int i = nr_map;
  while (i > 0 && maps[i - 1].low > map.low) {
    maps[i] = maps[i - 1];
    i--;
  }
  maps[i] = map;
}

int is_mmio(paddr_t addr) {
  if (nr_map == 0) return -1;
  if (nr_map == 1) {
    return (addr >= maps[0].low && addr <= maps[0].high) ? 0 : -1;
  }

  int left = 0, right = nr_map - 1;
  while (left <= right) {
    int mid = left + (right - left) / 2;
    if (addr < maps[mid].low) {
      right = mid - 1;
    } else if (addr > maps[mid].high) {
      left = mid + 1;
    } else {
      return mid;
    }
  }
  return -1;
}
```

本地先做了一个很小的行为测试，覆盖：

- 无 MMIO 映射
- 单个映射
- 多个映射乱序插入
- 命中和未命中

测试输出：

```text
scheme A mmio test passed
```

然后把这版同步到远端，重编后采了一轮新的 `perf`，归档到：

- [pa5-pal-optA.run.log](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/optA/pa5-pal-optA.run.log)
- [pa5-pal-optA.perf.report.symbol.txt](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/optA/pa5-pal-optA.perf.report.symbol.txt)

这一轮的主要热点是：

- `is_mmio`：`18.40%`
- `paddr_read`：`17.99%`
- `page_translate.part.1`：`15.02%`
- `vaddr_read`：`8.91%`
- `exec_real`：`7.04%`

和 `opt4` 比较：

- `is_mmio` 基本持平
- `paddr_read`、`page_translate.part.1`、`vaddr_read` 有一点下降

这一版说明：排序+二分查找在当前规模下收益不算大，但至少没有把性能拉坏，属于小幅正向。

### 14.2 方案 B：页级直接查表

第二版思路更激进：既然物理地址空间固定是 `128MB`，那就直接按页粒度建立：

```text
page_no -> mmio_map_id
```

查询时先用：

```c
page = addr >> 12;
```

直接找到这一页对应的 MMIO 编号，再做一次最终区间确认。

核心代码是：

```c
#define PMEM_SIZE (128 * 1024 * 1024)
#define MMIO_PAGE_COUNT (PMEM_SIZE >> 12)

static int16_t mmio_page_map[MMIO_PAGE_COUNT];

static void mark_mmio_pages(int map_no, paddr_t low, paddr_t high) {
  uint32_t start_page = low >> 12;
  uint32_t end_page = high >> 12;
  for (uint32_t page = start_page; page <= end_page; page++) {
    mmio_page_map[page] = map_no;
  }
}

int is_mmio(paddr_t addr) {
  if (nr_map == 0) return -1;
  if (nr_map == 1) {
    return (addr >= maps[0].low && addr <= maps[0].high) ? 0 : -1;
  }

  uint32_t page = addr >> 12;
  if (page >= MMIO_PAGE_COUNT) return -1;

  int map_no = mmio_page_map[page];
  if (map_no >= 0 && addr >= maps[map_no].low && addr <= maps[map_no].high) {
    return map_no;
  }
  return -1;
}
```

本地也做了小测试，覆盖：

- 单页 MMIO
- 跨页 MMIO
- 非 MMIO 页

测试输出：

```text
scheme B mmio page-map test passed
```

同步远端后采得一轮新的 `perf`，归档到：

- [pa5-pal-optB.run.log](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/optB/pa5-pal-optB.run.log)
- [pa5-pal-optB.perf.report.symbol.txt](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/optB/pa5-pal-optB.perf.report.symbol.txt)

这一轮的主要热点是：

- `is_mmio`：`18.67%`
- `paddr_read`：`16.88%`
- `page_translate.part.1`：`16.23%`
- `vaddr_read`：`8.58%`
- `exec_real`：`8.01%`

这一版的特点是：

- `paddr_read` 和 `vaddr_read` 略有下降
- 但 `is_mmio` 和 `page_translate.part.1` 都没有下降
- `exec_real` 还略有上升

整体看并没有比方案 A 更稳。

### 14.3 这两版怎么选

把三轮结果放在一起看：

| 版本 | is_mmio | paddr_read | page_translate | vaddr_read | 结论 |
| --- | --- | --- | --- | --- | --- |
| `opt4` 基线 | `18.39%` | `18.10%` | `15.46%` | `9.72%` | 当前稳定基线 |
| `optA` 排序+二分 | `18.40%` | `17.99%` | `15.02%` | `8.91%` | 小幅正向 |
| `optB` 页级查表 | `18.67%` | `16.88%` | `16.23%` | `8.58%` | 波动更大，不够稳 |

从这组数据看：

1. `is_mmio()` 在当前实验规模下不是“单纯把查询结构换复杂”就能大幅优化掉的。
2. 方案 A 虽然收益不大，但逻辑简单，副作用也小。
3. 方案 B 虽然看起来更像 O(1) 查询，但实际在这份 `PA5` 的场景下没有表现出更好的整体收益。

因此最后保留的是：

```text
方案 A：按区间排序 + 二分查找
```

远端当前源码也已经切回这一版。

---

## 15. 尝试实现一个最小 TB 原型

在 `optA` 之后，热点还是明显集中在：

- `is_mmio`
- `paddr_read`
- `page_translate.part.1`
- `exec_real`

这说明只做局部访存优化，收益已经开始变小。按照指导书后半部分的思路，下一步就该考虑 `TB/basic block` 这一类更接近执行模型的优化。

不过这里没有直接去做真正的 `JIT`，而是先实现了一个最小可行的 `TB` 原型，目标是：

1. 保留每条客户指令真实执行的语义
2. 不生成宿主机代码
3. 先缓存“已经走过的 basic block 的 opcode 序列和下一条 PC”
4. 命中时跳过重复的 opcode 取指和表查询

### 15.1 原型设计

这里把 `TB` 简化成一个 direct-mapped cache。每个 block 记录：

```c
typedef struct {
  vaddr_t pc;
  uint16_t opcode;
  vaddr_t next_eip;
} TBInstr;

typedef struct {
  bool valid;
  vaddr_t start_eip;
  int nr_instr;
  TBInstr instr[TB_MAX_INSTR];
} TBEntry;
```

含义分别是：

- `pc`：这一条客户指令的起始地址
- `opcode`：已经解析出来的 opcode 编号
- `next_eip`：上一次真实执行完这条指令后，下一条指令落到哪里

也就是说，这里缓存的不是“执行结果”，而是“这段 basic block 上一次的执行轨迹”。

### 15.2 回放时做了什么

在 [cpu-exec.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nemu/src/monitor/cpu-exec.c) 中，先按 `cpu.eip` 查 cache：

```c
static inline TBEntry *tb_lookup(vaddr_t eip) {
  TBEntry *tb = &tb_cache[tb_hash(eip)];
  return (tb->valid && tb->start_eip == eip) ? tb : NULL;
}
```

命中后，并不是“直接跳过执行”，而是：

```c
exec_wrapper_cached(tb->instr[i].opcode, false);
```

也就是复用已经缓存下来的 opcode，跳过原来 `exec_real()` 里那一步：

- 从内存取 opcode 字节
- 查 opcode table

但仍然保留：

- 操作数译码
- 真实执行
- `page_translate()`
- `paddr_read()/paddr_write()`
- 中断检查
- watchpoint 检查
- `device_update()`

所以这版 `TB` 更准确地说是：

```text
basic block 的 opcode/控制流缓存
```

而不是真正意义上的 `JIT`。

### 15.3 为什么还要排除 `0x66` 前缀指令

第一次把这个原型推到远端做 smoke test 时，程序很快就在分页访存里崩掉。后面排查发现，原因出在：

- `0x66` 这种 operand-size prefix 指令

普通执行时，`decoding.opcode` 最终只留下“真实 opcode”，前缀本身不会保留在缓存记录里。这样一来，TB 回放时就会丢掉原来的 operand-size 语义，进而把指令解释错。

所以这里先做了一个保守处理：

```c
static inline bool tb_cacheable_instr(vaddr_t pc) {
  return vaddr_read(pc, 1) != 0x66;
}
```

如果一条指令以 `0x66` 开头，就不把它记进 TB。这样虽然牺牲了一部分命中率，但能先保证原型的正确性。

### 15.4 远端验证

修正 `0x66` 问题之后，远端重新做了 smoke run，`pal` 可以稳定推进到：

- `VIDEO_Init success`
- `PAL_InitResources success`

说明这版 TB 原型至少没有立刻破坏最基本的运行链。

随后又做了一轮新的 `perf`，结果归档到：

- [pa5-pal-tb.run.log](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/tb/pa5-pal-tb.run.log)
- [pa5-pal-tb.perf.report.symbol.txt](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/tb/pa5-pal-tb.perf.report.symbol.txt)

### 15.5 TB 原型的 perf 结果

这一轮的主要热点是：

- `paddr_read`：`18.62%`
- `is_mmio`：`18.33%`
- `page_translate.part.1`：`12.47%`
- `vaddr_read`：`6.77%`
- `exec_wrapper_cached`：`6.15%`
- `cpu_exec`：`5.41%`
- `exec_real`：`1.56%`

和 `optA` 相比，最明显的变化是：

- `exec_real`：`7.04% -> 1.56%`
- `page_translate.part.1`：`15.02% -> 12.47%`
- `vaddr_read`：`8.91% -> 6.77%`

这说明：

1. TB 原型确实减少了“重复 opcode 取指和表查询”这一部分成本
2. 解释执行链条里的前端开销被压下去了一截
3. 但真正最重的热点仍然是：
   - `is_mmio`
   - `paddr_read`
   - `page_translate`

也就是说，这版 TB 原型已经开始触碰指导书里说的“解释执行为什么慢”这个核心问题，但它还没有改变：

```text
客户程序每次访存仍然要走完整的地址翻译和物理访存路径
```

所以收益是有的，但还不够颠覆性。

### 15.6 再补一个更直接的性能指标：吞吐量

前面的 `perf` 结果说明的是“热点结构变了什么”，但还不够直接回答“到底快了多少”。因此这里又补了一个更容易写进报告的指标：

```text
固定执行相同数量的客户指令，记录 wall time，再换算成 guest instructions/s
```

为了保证对比更公平，这里没有拿非常早的 `0553aed` 去比较，而是选了：

- `pre-TB`：最近一个还没有 `exec_wrapper_cached/TB cache` 的提交  
  `3ff5c9d`
- `TB`：当前带 TB 原型的版本

两边运行的都是同一份 `nanos-lite/build/nanos-lite-x86-nemu.bin`，只替换 `NEMU` 可执行文件。测试命令思路是：

```text
si 20000000
```

也就是固定执行 `20,000,000` 条客户指令，然后退出。

实测结果如下：

| 版本 | 第一次耗时 | 第二次耗时 | 平均耗时 | 吞吐量 |
| --- | --- | --- | --- | --- |
| `TB` | `2.13s` | `2.04s` | `2.085s` | `20,000,000 / 2.085 ≈ 9.59 M instr/s` |
| `pre-TB` | `2.40s` | `2.43s` | `2.415s` | `20,000,000 / 2.415 ≈ 8.28 M instr/s` |

按平均值计算，TB 原型带来的吞吐量提升大约是：

```text
(9.59 - 8.28) / 8.28 ≈ 15.8%
```

这个数字和前面的 `perf` 结果是能对上的：

- `exec_real` 明显下降
- `vaddr_read/page_translate` 也有下降
- 但访存链仍然是主要瓶颈，所以没有出现成倍提升

因此可以比较稳地写成：

```text
当前实现的最小 TB 原型，在 PAL 启动阶段可以带来约 15% 左右的吞吐量提升。
```

### 15.7 再做一个小探究：TB 大小设成多少更合适

指导书在讲 `TB/basic block` 时，专门强调了一个问题：

```text
每次编译多少条客户指令比较合适？
```

这个问题完全可以结合当前原型做一个小探究。  
这里把 [cpu-exec.c](/Users/linshangjin/Desktop/PA/ics2017-pa5/nemu/src/monitor/cpu-exec.c) 里的：

```c
#define TB_MAX_INSTR 32
```

改成可编译期覆盖，然后在远端分别测试：

- `TB_MAX_INSTR = 1`
- `TB_MAX_INSTR = 4`
- `TB_MAX_INSTR = 8`
- `TB_MAX_INSTR = 16`
- `TB_MAX_INSTR = 32`
- `TB_MAX_INSTR = 64`

测试方法和前面吞吐量一样，仍然固定：

```text
si 20000000
```

每个点跑两次，记录 wall time，再换算成 `guest instructions/s`。

实测结果如下：

| `TB_MAX_INSTR` | 第一次耗时 | 第二次耗时 | 平均耗时 | 吞吐量 |
| --- | --- | --- | --- | --- |
| `1` | `2.04s` | `2.01s` | `2.025s` | `9.88 M instr/s` |
| `4` | `1.87s` | `2.09s` | `1.980s` | `10.10 M instr/s` |
| `8` | `2.05s` | `1.94s` | `1.995s` | `10.03 M instr/s` |
| `16` | `2.00s` | `1.94s` | `1.970s` | `10.15 M instr/s` |
| `32` | `1.96s` | `2.03s` | `1.995s` | `10.03 M instr/s` |
| `64` | `1.92s` | `1.97s` | `1.945s` | `10.28 M instr/s` |

结果文件已经归档到：

- [pa5_tb_size_results.txt](/Users/linshangjin/Desktop/PA/PA报告/PA5-report/perf/tb/pa5_tb_size_results.txt)

从这组数据可以看到两点：

1. `TB_MAX_INSTR = 1` 明显更差  
   这和指导书里的分析是一致的：如果一个 TB 只对应一条客户指令，那么每执行完一条指令就要重新查一次 cache，冗余检查太多。

2. `16 ~ 64` 区间差距不大  
   说明在当前这个比较粗糙的 TB 原型里，block 变大以后确实能多摊掉一些前端开销，但收益已经不像从 `1` 提到 `4` 那样明显。

当前这组实验里，`64` 的吞吐量最高，大约是：

```text
10.28 M instr/s
```

不过 `16`、`32`、`64` 之间的差距都不算很大，这说明：

- TB 大小不是越大越会无限变好
- 当前主要瓶颈仍然在访存链
- block 大小调参只能继续榨出一小部分收益

综合考虑之后，这里没有把源码默认值改成 `64`，而是继续保留：

```c
#define TB_MAX_INSTR 32
```

原因主要有三点：

1. `32` 和 `64` 的差距不大，没有拉开到必须修改默认值的程度
2. 当前实现仍然只是一个比较保守的 TB 原型，保留 `32` 更稳妥
3. 这组实验更重要的意义在于说明“TB 大小存在合适区间”，而不是机械追逐这一组数据里的局部最优值

如果把这个探究写成一句更适合放进报告里的结论，可以写成：

```text
在当前 PAL 启动阶段 workload 下，TB_MAX_INSTR 从 1 提升到 16 以上后，
吞吐量会稳定高于单指令 TB；继续增大到 64 仍有小幅收益，但 16、32、64
之间差距已经明显缩小，说明 TB 大小存在一个“足够大即可”的区间，而不是越大越好。
```

### 15.8 如何评价这版 TB

如果从“PA5 是否有必要做到这里”来看，这个 TB 原型已经足够作为一个亮点：

- 它不是空谈 `TB/JIT`
- 确实动到了执行模型
- 也确实在 `perf` 上看到了收益

但同时也要明确它的限制：

1. 这不是真正的 JIT
2. 它没有生成宿主机代码
3. 它对 `0x66` 前缀做了保守回避
4. 它仍然没有绕开访存链的主要成本

所以更合适的表述应该是：

```text
本次实现的是一个 basic block/TB cache 原型，用来验证“减少解释执行前端重复工作”
这条思路是否有效；真正完整的 JIT/TB 体系仍然需要更复杂的前端和后端设计。
```

### 15.9 最小 JIT 沙盒先在 `jitmini` 上验证

在完成 TB 原型之后，这里继续往前走了一步：不是直接把 `pal` 整体切到 JIT，而是先做了一个最小 JIT 沙盒。原因很直接，`pal` 的真实执行路径里很快就会遇到访存、条件跳转、系统调用和分页相关逻辑；如果一上来就在完整 workload 上做 JIT，很难判断问题到底出在哪一层。

因此先增加了一个极小测试程序 `jitmini`，只保留几条最简单的指令，例如：

- `nop`
- `mov imm32, r32`
- `mov r32, r32`

然后在 `nemu/src/monitor/cpu-exec.c` 中加入一个默认关闭的 JIT 沙盒，只给这几类指令生成很短的宿主机 x86 代码。生成方式没有去碰复杂的寄存器分配，而是直接把客户机寄存器 `cpu.gpr[]` 里的值搬到内存中对应的位置。这样做的目的不是追求性能，而是先验证“生成宿主机代码并执行”这条链能不能通。

这一步在远端是成功的。打开 `JIT_SANDBOX_TEST` 后，`jitmini` 可以跑到 `GOOD TRAP`，而且日志里出现了：

```text
[jit-sandbox] first hit at eip=0x00100011, built=22
```

这说明两件事：

1. 最小 JIT 代码确实已经被构建出来
2. 运行时也确实命中过一次 JIT 生成的宿主机代码，而不是始终退回解释器

因此，这个沙盒至少证明了：在当前 32 位环境下，做一个最小的宿主机代码生成原型是可行的。

### 15.10 尝试把 JIT 推到 `pal`，并逐步收缩范围

有了 `jitmini` 之后，下一步才开始把同一套沙盒小心地推向 `pal`。这里没有直接追求“大范围覆盖”，而是按下面的顺序逐步收缩：

1. 一开始只支持最简单的 `mov/nop`
2. 然后限制 JIT 只允许命中用户代码区，不再碰低地址内核路径
3. 再把 `esp/ebp` 相关寄存器全部排除，避免破坏栈帧建立
4. 之后继续把 `_write`、`__swbuf`、`strlen`、`SDL_SetPalette`、`SDL_CreateRGBSurface`、`get_display_info` 这些辅助路径排除掉
5. 最后把范围继续缩到 `PAL_MKFGetChunkCount/Size/ReadChunk` 这类真实但相对简单的资源读取函数

中间每缩一轮，都在远端重新编译并短跑一次。前面几轮虽然可以穿过 `PAL_InitResources`，但后面都会在更深处撞到：

```text
PDE for vaddr 0xe7c53ef2 is not present
```

这个现象说明：JIT 不是完全跑不起来，而是某一处状态一致性仍然被破坏了，最后在分页访问时体现成错误地址。

不过在继续收缩之后，最终拿到了一个比较干净的结果：把白名单控制在

```c
0x08064304 <= pc < 0x08064494
```

也就是只覆盖：

- `PAL_MKFGetChunkCount`
- `PAL_MKFGetChunkSize`
- `PAL_MKFReadChunk`

这时远端日志里已经能稳定看到：

```text
[jit-sandbox] first hit at eip=0x08064331, built=1
[jit-sandbox] hit #1 eip=0x08064331 opcode=89 len=2 bytes=89 d0
```

并且同一轮运行仍然能继续推进到：

- `PAL_InitGolbals success`
- `PAL_InitFont success`
- `PAL_InitUI success`
- `PAL_InitText success`
- `PAL_InitInput success`
- `PAL_InitResources success`

这一轮没有再在初始化阶段崩掉。也就是说，JIT 在 `pal` 上并不是完全失败，而是已经能在真实 workload 的一小段资源读取逻辑上稳定命中。

从这个结果看，当前最合适的结论不是“已经做出了完整 JIT”，而是：

1. `jitmini` 证明了最小宿主机代码生成链是可行的
2. `pal` 上的大范围 JIT 仍然会破坏更复杂的状态一致性
3. 但把范围收缩到 `PAL_MKFGetChunkCount/Size/ReadChunk` 之后，已经能在真实程序上拿到稳定命中

如果把这部分写成一句更适合正式报告的结论，可以写成：

```text
在 PA5 后半部分进一步尝试了一个最小 JIT 沙盒。完整的 pal 工作负载在大范围 JIT 下
仍然会因为状态一致性问题而失稳，但通过逐步收缩白名单，最终已经能够在
PAL_MKFGetChunkCount/Size/ReadChunk 这一类真实资源读取函数上稳定命中 JIT，
说明“在真实 workload 上局部落地 JIT”这条方向是可行的，只是继续扩大覆盖范围仍需
更严格地处理寄存器、控制流和访存语义。
```

### 15.11 `TB only` 和 `TB + narrow JIT` 的吞吐量对比

前面的实验已经说明：`pal` 上的局部 JIT 不是完全没用上，但这还不等于它已经带来了整体性能提升。因此这里又补了一组更直接的吞吐量对比：

```text
固定执行 20,000,000 条客户指令，比较 TB only 和 TB + narrow JIT 的 wall time
```

测试条件保持和前面一致：

- `TB_MAX_INSTR = 32`
- 仍然运行同一份 `nanos-lite/build/nanos-lite-x86-nemu.bin`
- `TB only` 与 `TB + narrow JIT` 都各跑两次
- `narrow JIT` 仍然只覆盖：
  - `PAL_MKFGetChunkCount`
  - `PAL_MKFGetChunkSize`
  - `PAL_MKFReadChunk`

实测结果如下：

| 模式 | 第一次耗时 | 第二次耗时 | 平均耗时 | 吞吐量 |
| --- | --- | --- | --- | --- |
| `TB only` | `2.02s` | `1.98s` | `2.00s` | `20,000,000 / 2.00 = 10.00 M instr/s` |
| `TB + narrow JIT` | `2.07s` | `2.16s` | `2.115s` | `20,000,000 / 2.115 ≈ 9.46 M instr/s` |

按平均值计算，这一版 `narrow JIT` 相比 `TB only` 的变化大约是：

```text
(9.46 - 10.00) / 10.00 ≈ -5.4%
```

也就是说，在当前这个极窄覆盖范围下，局部 JIT 虽然已经能稳定命中真实函数，但总体吞吐量反而略低于只使用 TB 的版本。

这个结果并不奇怪，主要原因有两点：

1. 当前 JIT 覆盖范围非常小  
   它只命中 `PAL_MKFGetChunkCount/Size/ReadChunk` 里极少数简单指令，摊薄不了太多前端成本。

2. 现在的 JIT 仍然只是一个验证性质的原型  
   每条指令后仍然要回到原有框架里做状态检查、设备更新和中断相关处理，JIT 命中带来的收益还不足以覆盖额外的构建和切换成本。

因此，这组数据更适合写成下面这个结论：

```text
局部 JIT 命中已经发生，但在覆盖范围很窄时，宿主机代码执行带来的收益还不足以转化成整体吞吐量提升。
如果后面继续扩大 JIT 的有效覆盖范围，或者进一步降低 JIT 框架本身的额外成本，才有可能在真实 workload 上看到净收益。
```

### 15.12 继续扩大白名单之后，为什么还是没有更多收益

在拿到上面这组吞吐量结果之后，这里又继续往前试了两步：

1. 先把白名单从
   - `PAL_MKFGetChunkCount`
   - `PAL_MKFGetChunkSize`
   - `PAL_MKFReadChunk`

   扩到再包含：
   - `PAL_MKFGetDecompressedSize`

2. 再进一步把范围扩大到包含：
   - `PAL_MKFDecompressChunk`

这两轮都保持了同样的原则：

- `ENABLE_JIT_SANDBOX` 默认仍然关闭
- 只在远端短跑验证时临时打开
- 每次结束后都立即恢复到稳定版本

实际现象有一点很值得记录：即使把白名单继续扩大到 `PAL_MKFDecompressChunk`，8 秒短跑里日志仍然只稳定出现同一个命中点：

```text
[jit-sandbox] first hit at eip=0x08064331, built=4
[jit-sandbox] hit #1 eip=0x08064331 opcode=89 len=2 bytes=89 d0
```

也就是说，白名单放宽了，但“真正能被 JIT 编译并执行的客户指令”并没有明显增加。

这个现象说明，当前阶段的限制已经不再主要来自“PC 范围太窄”，而更可能来自下面这个问题：

```text
当前 JIT 沙盒支持的指令种类仍然太少，因此即使白名单继续放宽，
真正满足条件、能被翻译成宿主机代码的客户指令仍然很有限。
```

换句话说，现在继续单纯扩大 PC 范围，收益已经开始变小；如果还想让 `pal` 上的 JIT 进一步扩展，更值得做的事情就不是继续改白名单，而是补更多安全的指令形式，例如：

- 少量更稳的寄存器算术
- 部分不涉及栈指针的 `xor/test`
- 更严格受控的简单移位或比较

因此，这一步实验其实把方向收束得更清楚了：

1. 白名单本身不是唯一瓶颈
2. 继续扩范围之前，更应该先补可安全 JIT 的指令类型
3. 只有“命中范围”和“可编译指令种类”同时扩大，局部 JIT 才有可能真正转化成吞吐量收益

### 15.13 再补一种新指令：`test r32, r32`

在上一步之后，这里没有继续盲目扩大白名单，而是先补了一类新的、相对安全的指令：

```text
test r32, r32
```

选择它的原因是：

1. 它不会写回通用寄存器
2. 只需要更新标志位
3. 和之前直接去碰更激进的 `xor reg, reg` 相比，风险更低

这次做法仍然比较保守：只支持寄存器到寄存器形式，并且在 JIT helper 里显式维护：

- `ZF`
- `SF`
- `CF = 0`
- `OF = 0`

补完之后再次在当前 `PAL_MKF*` 白名单上做远端短跑，日志里已经能看到明显更多的 JIT 命中点，例如：

```text
[jit-sandbox] first hit at eip=0x0806430e, built=5
[jit-sandbox] hit #1 eip=0x0806430e opcode=85 len=2 bytes=85 db
[jit-sandbox] hit #3 eip=0x080643f1 opcode=85 len=2 bytes=85 ff
[jit-sandbox] hit #4 eip=0x080643f9 opcode=85 len=2 bytes=85 f6
[jit-sandbox] hit #5 eip=0x08064400 opcode=85 len=2 bytes=85 db
[jit-sandbox] hit #7 eip=0x08064454 opcode=85 len=2 bytes=85 db
```

而且这轮运行仍然能稳定推进到：

- `PAL_InitGolbals success`
- `PAL_InitFont success`
- `PAL_InitUI success`
- `PAL_InitText success`
- `PAL_InitInput success`
- `PAL_InitResources success`

这说明补 `test` 之后，JIT 在 `pal` 这段真实代码上的命中已经不再只是单个 `mov`，而是开始覆盖更多判断逻辑。

### 15.14 补 `test` 之后的吞吐量变化

命中点变多之后，又重新做了一组和前面相同的吞吐量测试：

```text
si 20000000
```

实测结果如下：

| 模式 | 第一次耗时 | 第二次耗时 | 平均耗时 | 吞吐量 |
| --- | --- | --- | --- | --- |
| `TB only` | `2.06s` | `1.99s` | `2.025s` | `20,000,000 / 2.025 ≈ 9.88 M instr/s` |
| `TB + narrow JIT (+ test)` | `2.08s` | `2.08s` | `2.08s` | `20,000,000 / 2.08 ≈ 9.62 M instr/s` |

按平均值计算，这一版相比 `TB only` 仍然是：

```text
(9.62 - 9.88) / 9.88 ≈ -2.6%
```

不过和前一轮 `-5.4%` 相比，损失已经缩小了。这说明：

1. 增加一种新的安全指令后，JIT 覆盖率确实提高了
2. 提高覆盖率以后，整体效果也在向更好的方向移动
3. 只是当前这点覆盖范围仍然不够大，还没有正式跨过“净收益为正”的门槛

因此，这一步的意义在于：

```text
它证明了继续补安全指令种类是有价值的。虽然还没有让局部 JIT 超过 TB only，
但已经把吞吐量差距从约 -5.4% 缩小到约 -2.6%，说明方向是对的。
```

### 15.15 再往前走一步：补 `83` 组里的 `add/sub/cmp imm8`

在 `test` 之后，下一步没有直接去碰更重的访存或调用指令，而是先补了 `83` 这组里最常见、也最保守的几种寄存器形式：

- `/0 add imm8`
- `/5 sub imm8`
- `/7 cmp imm8`

这样做的原因是：

1. 它们仍然只在寄存器层面工作
2. 相比 `push/pop/call`，语义边界更清楚
3. 在白名单这段 `PAL_MKF*` 代码里，`83` 的 miss 数量已经不低，值得先补

补完之后再次统计，已经能看到：

```text
opcode 83 hits=2
opcode 83 miss=39
```

也就是说，这一批 `83` 指令已经开始命中，只是覆盖率还不够高。

### 15.16 再补 `8d` 和 `8b`

继续看未命中统计，会发现：

- `8d miss` 很高
- `8b miss` 更高

这两类指令虽然比单纯寄存器运算复杂一些，但仍然有一部分是可以保守支持的：

1. `8d`
   - 这是 `lea`
   - 本质上只是地址计算，不真正访问内存
   - 因此比较适合先做成 JIT helper

2. `8b`
   - 这里只先补了最保守的一半：`mov r32, [mem]`
   - 仍然不碰 `89` 的写内存版本
   - helper 里通过现有的 `vaddr_read()` 读取客户机虚拟地址

补完这两类之后，白名单里的命中统计已经明显变化：

```text
[jit-sandbox] summary built=102 executed=46
[jit-sandbox] opcode 83 hits=2
[jit-sandbox] opcode 85 hits=14
[jit-sandbox] opcode 89 hits=2
[jit-sandbox] opcode 8b hits=21
[jit-sandbox] opcode 8d hits=7
```

同时：

```text
opcode 8d miss=4
```

和之前相比，`8d` 基本已经从“高 miss”变成了“高 hit”；`8b` 也开始大量命中。

这一步非常关键，因为它说明局部 JIT 已经不再只是覆盖几条简单的判断和寄存器搬运，而是开始真正碰到：

- 栈上局部变量的读取
- 地址计算
- 资源处理逻辑里的实际数据访问

### 15.17 补到 `8b` 之后，局部 JIT 首次转成正收益

在 `8b` 和 `8d` 都补上之后，又重新做了一组和前面完全相同的吞吐量测试，仍然固定：

```text
si 20000000
```

实测结果如下：

| 模式 | 第一次耗时 | 第二次耗时 | 平均耗时 | 吞吐量 |
| --- | --- | --- | --- | --- |
| `TB only` | `2.12s` | `2.15s` | `2.135s` | `20,000,000 / 2.135 ≈ 9.37 M instr/s` |
| `TB + narrow JIT (+ test/+83/+8d/+8b)` | `2.05s` | `2.09s` | `2.07s` | `20,000,000 / 2.07 ≈ 9.66 M instr/s` |

按平均值计算，这一版相比 `TB only` 的变化已经变成：

```text
(9.66 - 9.37) / 9.37 ≈ +3.1%
```

这说明一个很重要的转折点：

1. 局部 JIT 已经不再只是“能命中但拖后腿”
2. 继续补安全指令种类之后，它第一次在吞吐量上超过了 `TB only`
3. 虽然这个收益还不算大，但已经证明“扩大有效覆盖范围”确实能够把局部 JIT 从负收益拉到正收益

如果要把这一步写成一句最浓缩的结论，可以写成：

```text
在逐步补齐 test、83、8d 和 8b 这几类安全指令之后，局部 JIT 在 pal 的资源处理路径上
已经从“可命中但负收益”演变为“可命中且带来约 3% 的净吞吐量提升”，说明这种逐步扩大
覆盖范围的策略是有效的。
```

### 15.18 一次性补一批栈相关指令：`push/pop`、`push imm`、`leave`

前面几轮统计里，剩余 miss 已经非常集中，最突出的就是：

- `50/53/55/56/57`：`push reg`
- `5b/5d/5e/5f`：`pop reg`
- `6a`：`push imm8`
- `c9`：`leave`

这一类指令虽然会改栈，但还没有真正碰到控制流跳转；和 `call/ret` 相比，风险明显小一档。因此这里做了一轮更激进的扩展，不再只补一条新指令，而是把这一批栈相关 opcode 一次性补上。

对应 helper 大致如下：

```c
static void jit_helper_push_reg(uint32_t src_reg) {
  cpu.gpr[R_ESP]._32 -= 4;
  vaddr_write(cpu.gpr[R_ESP]._32, 4, cpu.gpr[src_reg]._32);
}

static void jit_helper_pop_reg(uint32_t dst_reg) {
  uint32_t old_esp = cpu.gpr[R_ESP]._32;
  uint32_t value = vaddr_read(old_esp, 4);
  cpu.gpr[R_ESP]._32 = old_esp + 4;
  if (dst_reg != R_ESP) {
    cpu.gpr[dst_reg]._32 = value;
  }
}

static void jit_helper_leave(void) {
  uint32_t old_ebp = cpu.gpr[R_EBP]._32;
  cpu.gpr[R_ESP]._32 = old_ebp;
  cpu.gpr[R_EBP]._32 = vaddr_read(old_ebp, 4);
  cpu.gpr[R_ESP]._32 = old_ebp + 4;
}
```

然后在 `tb_try_build_jit()` 里一次性接通：

- `0x50 ~ 0x57`
- `0x58 ~ 0x5f`（保守起见仍然不支持 `pop esp`）
- `0x6a`
- `0x68`
- `0xc9`

这轮仍然遵循同样的调试方式：先在远端打开 JIT 窄白名单做 8 秒短跑，只要 `PAL_InitResources success` 之前被打坏，就立刻回退。实际现象是稳定通过，而且命中日志明显变厚了：

```text
[jit-sandbox] hit #1 eip=0x08064304 opcode=55 len=1 bytes=55
[jit-sandbox] hit #2 eip=0x08064307 opcode=53 len=1 bytes=53
[jit-sandbox] hit #5 eip=0x08064312 opcode=50 len=1 bytes=50
[jit-sandbox] hit #6 eip=0x08064313 opcode=6a len=2 bytes=6a 00
[jit-sandbox] hit #7 eip=0x08064315 opcode=6a len=2 bytes=6a 00
```

这次的统计摘要里，和这一批新扩展直接相关的命中已经变成：

```text
opcode 50 hits=11
opcode 51 hits=1
opcode 53 hits=15
opcode 55 hits=6
opcode 56 hits=12
opcode 57 hits=5
opcode 5b hits=1
opcode 5d hits=1
opcode 5e hits=1
opcode 5f hits=1
opcode 6a hits=23
opcode c9 hits=2
```

这说明 JIT 已经不只是覆盖一小段判断和寄存器搬运，而是开始碰到更真实的函数栈帧建立、参数压栈以及函数尾部恢复。

### 15.19 补完这批栈相关指令之后的吞吐量

为了判断这次“一次性多补一些”到底只是命中增加，还是能够继续转化成吞吐量收益，这里又对 `TB only` 和当前这版 `TB + narrow JIT` 做了一轮相同条件的对比：

- 固定执行 `si 20000000`
- 每个版本各跑两次
- 记录 wall time

结果如下：

| 配置 | 第 1 次 | 第 2 次 | 平均值 | 吞吐量 |
| --- | --- | --- | --- | --- |
| `TB only` | `2.07s` | `2.03s` | `2.05s` | `20,000,000 / 2.05 ≈ 9.76 M instr/s` |
| `TB + narrow JIT (+ push/pop/6a/c9)` | `2.05s` | `2.05s` | `2.05s` | `20,000,000 / 2.05 ≈ 9.76 M instr/s` |

这组数据说明：

1. 这批栈相关指令已经能够稳定命中，并且没有把 `pal` 初始化主线打坏。
2. 但在当前这版实现下，新增覆盖范围带来的收益基本被 JIT 自身的额外开销抵消，最终与 `TB only` 几乎持平。
3. 因此这一轮更像是一次“覆盖范围扩大成功”，而不是一次明显的吞吐量提升。

换句话说，`push/pop/leave` 这一类会改栈的指令并不是完全不能做；只要范围收得够窄、helper 写得够保守，它们也能稳定地落在 `pal` 的真实路径上。但如果后面想继续拿到更显著的性能收益，单纯继续补这类栈操作已经不够了，下一步更值得去碰的是：

- 仍然高 miss 的 `c7`
- 以及真正更关键但更危险的 `call/ret`

### 15.20 顺手修掉 `c7` 的漏判，并验证它是否真的带来收益

上一轮摘要里还有一个很扎眼的现象：

```text
opcode c7 miss=6
```

这条指令本来已经尝试支持过，但统计始终没有出现命中。继续往下检查后，发现问题不在 helper 本身，而在 EA 解析函数的判定条件：原来的 `jit_decode_ea()` 默认要求“地址计算部分吃完整条指令长度”，而 `c7 /0` 后面还会跟一个 `imm32`，因此它会被误判成解析失败。

这里没有重写一套新解析器，而是在现有 helper 上加了一个带尾部长度参数的版本：

```c
static bool jit_decode_ea_tail(const TBInstr *ins, int tail_bytes,
    uint8_t *reg, uint8_t *rm, uint8_t *mod,
    uint32_t *base_reg, uint32_t *index_reg, uint32_t *scale, int32_t *disp) {
  ...
  return pos + tail_bytes == ins->len;
}
```

然后 `c7` 改成使用 `tail_bytes = 4`，也就是把最后那 4 个字节的立即数单独留出来。

修完之后重新在远端跑同样的 `si 20000000`，统计里终于出现了：

```text
opcode c7 hits=4
```

同时原来的 `c7 miss=6` 已经消失，说明这条指令不再是“看起来支持了、实际上根本命不中”的状态。

接着又补了一组吞吐量对比：

| 配置 | 第 1 次 | 第 2 次 | 平均值 | 吞吐量 |
| --- | --- | --- | --- | --- |
| `TB only` | `2.00s` | `1.96s` | `1.98s` | `20,000,000 / 1.98 ≈ 10.10 M instr/s` |
| `TB + narrow JIT (+ c7)` | `1.95s` | `2.02s` | `1.985s` | `20,000,000 / 1.985 ≈ 10.08 M instr/s` |

这组数据说明：

1. `c7` 的确已经从 miss 变成了可命中的 JIT 指令。
2. 但单靠这 4 次新增命中，还不足以把整体吞吐量继续往上推。
3. 从结果上看，它基本和 `TB only` 持平，仍然属于“覆盖范围扩大成功，但性能收益还不明显”的一轮。

因此，到这一阶段可以把结论收束成一句话：

```text
局部 JIT 在 pal 上已经能够稳定覆盖一批真实的栈、访存和立即数写入指令，
但如果想继续把吞吐量明显拉高，下一步就不能再只补这种局部小指令，而必须开始触碰
更关键的控制流路径。
```

### 15.22 按全局高频结果继续扩 `89`

上一节的全局统计里，最醒目的结果是：

```text
opcode 89  占 25.06%
```

这说明如果还想继续扩 JIT，`89` 一定是最值得继续追的一类指令。前面虽然已经支持了一部分 `89`，但统计里仍然能看到不少 miss。继续排查后发现，真正卡住的一大块并不是寻址形式本身，而是之前对寄存器使用做得太保守：

- `89/8b` 的寄存器到寄存器形式里，原来会直接拒绝 `esp/ebp`
- `89` 的写内存形式里，原来对源寄存器也套了同样的限制

这种限制在最早验证阶段是合理的，因为它能降低风险；但到了后面，它已经开始直接吃掉高频真实路径里的命中机会。

所以这里做了一个比较明确的调整：

1. `89/8b` 的寄存器到寄存器形式不再直接用“读绝对地址再写绝对地址”的方式处理，而是统一走 helper：

```c
static void jit_helper_mov_rr(uint32_t dst_reg, uint32_t src_reg) {
  cpu.gpr[dst_reg]._32 = cpu.gpr[src_reg]._32;
}
```

2. `89` 的写内存形式也去掉了对源寄存器的 `jit_safe_reg()` 限制。

这样做之后，远端重新跑 `si 20000000` 的摘要里，`89` 的命中已经从原来的很低水平明显增加到：

```text
opcode 89 hits=9
```

这说明扩 `89` 这一步本身是有效的，也和前面的全局频率统计相互印证：既然它在真实初始化阶段就是第一高频，那么继续把它的 JIT 覆盖做完整，确实能立刻换来更多命中。

### 15.23 做一个更受控的 `jcc` 原型：先支持短跳转 `74/75/77/7f`

在全局统计里，真正的另一类大头不是栈操作，而是条件控制流：

- `75`
- `7f`
- `74`
- `77`

所以这里没有再去碰 `call/ret`，而是先做一个更保守的 `jcc` 原型，只支持：

- `0x74` `je/jz`
- `0x75` `jne/jnz`
- `0x77` `ja`
- `0x7f` `jg`

对应 helper 的思路非常直接：

```c
static void jit_helper_jcc_short(uint32_t op, uint32_t fallthrough, uint32_t target) {
  bool take = false;
  switch (op & 0xff) {
    case 0x74: take = cpu.ZF; break;
    case 0x75: take = !cpu.ZF; break;
    case 0x77: take = (!cpu.CF && !cpu.ZF); break;
    case 0x7f: take = (!cpu.ZF && (cpu.SF == cpu.OF)); break;
  }
  cpu.eip = take ? target : fallthrough;
}
```

这里特意没有试图把分支直接编译成宿主机跳转，而是仍然通过 helper 来决定下一条 `eip`，这样风险更低。

不过第一次接上以后，摘要里并没有立刻出现 `jcc` 命中。继续排查后发现，问题不在 helper，而在 TB 的构造策略：

- 原来 TB 只会在“分支真的跳走”时结束 block
- 如果某次 `jcc` 没跳，它就会被继续吞进 block 中间
- 这样就不满足当前 JIT 原型“只有 block 末尾的 `jcc` 才允许接管 `eip`”的前提

所以这里又补了一条很小但很关键的规则：

```c
static inline bool tb_force_block_end(uint16_t opcode) {
  uint8_t op = opcode & 0xff;
  return (op >= 0x70 && op <= 0x7f);
}
```

也就是说，遇到短条件跳转时，不管这次是否真的改变了控制流，都先把 block 截断。

这一步补上之后，`jcc` 原型终于开始真正命中。远端摘要里已经出现：

```text
opcode 74 hits=7
```

这说明“在局部真实 workload 上让条件跳转进入 JIT”这条路已经不是停留在设计层，而是确实跑起来了。

### 15.24 扩 `89` 和 `jcc` 之后的吞吐量

最后又做了一组新的吞吐量对比，条件仍然保持一致：

- 固定执行 `si 20000000`
- 比较 `TB only` 和当前这版 `TB + narrow JIT`

实测结果如下：

| 配置 | 第 1 次 | 第 2 次 | 平均值 | 吞吐量 |
| --- | --- | --- | --- | --- |
| `TB only` | `2.01s` | `2.01s` | `2.01s` | `20,000,000 / 2.01 ≈ 9.95 M instr/s` |
| `TB + narrow JIT (+ wider 89 + jcc)` | `2.01s` | `2.01s` | `2.01s` | `20,000,000 / 2.01 ≈ 9.95 M instr/s` |

这组结果的含义是：

1. `89` 扩完整和 `jcc` 原型都已经真的命中了。
2. 但当前命中的数量和覆盖范围，还不足以把整体吞吐量再明显往上推。
3. 因此这一轮最重要的成果，不是“又快了多少”，而是：
   - 已经证明高频 `mov` 和短条件跳转可以稳定接入当前这套局部 JIT
   - 下一步如果还想继续追性能，就要继续扩大 `jcc` 覆盖，或者开始真正碰 `call/ret`

### 15.25 继续扩大 `jcc`，并开始碰最小 `call/ret`

前一轮里，`74` 已经开始命中，说明“短条件跳转进入 JIT”这条路是走得通的。接下来就按同一思路，把剩下几条高频短跳转也一起接上：

- `72`：`jb/jc`
- `76`：`jbe`
- `78`：`js`

对应 helper 只是继续补条件判断，不改变整体策略：仍然由 helper 来决定下一条 `eip`，而不是直接生成宿主机分支跳转。

在这个基础上，又继续往前碰了一步控制流：加了一个最小的 `call/ret` 原型，只支持：

- `e8 rel32`
- `c3 ret`

而且都只允许出现在 block 末尾，避免在 block 中间接管控制流。实现也保持最保守的形式：

```c
static void jit_helper_call_rel32(uint32_t fallthrough, uint32_t target) {
  cpu.gpr[R_ESP]._32 -= 4;
  vaddr_write(cpu.gpr[R_ESP]._32, 4, fallthrough);
  cpu.eip = target;
}

static void jit_helper_ret(void) {
  uint32_t old_esp = cpu.gpr[R_ESP]._32;
  cpu.eip = vaddr_read(old_esp, 4);
  cpu.gpr[R_ESP]._32 = old_esp + 4;
}
```

这里对 `call` 还额外加了一层限制：目标地址必须仍然落在当前 `jit_cacheable_pc()` 的白名单范围里，否则直接回退。

远端短跑和 `si 20000000` 摘要都通过之后，新的命中统计已经出现了：

```text
opcode 72 hits=2
opcode 74 hits=7
opcode 76 hits=1
opcode 78 hits=2
opcode c3 hits=2
opcode e8 hits=1
```

这说明两个重要的事情：

1. `jcc` 不再只是支持了一个 `74`，而是已经在真实路径里覆盖到一小组条件跳转。
2. `call/ret` 也已经不是完全碰不得，在严格限制范围和 block 边界后，最小形式是可以命中的。

### 15.26 补完更多 `jcc` 和最小 `call/ret` 之后的吞吐量

为了判断这一步到底有没有继续换来性能收益，这里又做了一组同样条件的吞吐量对比：

- 固定执行 `si 20000000`
- 比较 `TB only` 和当前这版 `TB + narrow JIT`

结果如下：

| 配置 | 第 1 次 | 第 2 次 | 平均值 | 吞吐量 |
| --- | --- | --- | --- | --- |
| `TB only` | `2.00s` | `2.06s` | `2.03s` | `20,000,000 / 2.03 ≈ 9.85 M instr/s` |
| `TB + narrow JIT (+ more jcc + call/ret)` | `2.05s` | `2.03s` | `2.04s` | `20,000,000 / 2.04 ≈ 9.80 M instr/s` |

这组数据仍然没有出现进一步的明显加速，基本可以视作与 `TB only` 持平，甚至略慢一点点。这里更合理的解读不是“这一步没意义”，而是：

1. 当前这版 `jcc/call/ret` 还只是非常保守的 helper 形式
2. 命中虽然发生了，但每次命中带来的收益还不足以抵掉额外的框架开销
3. 这一步最大的价值是把局部 JIT 的能力边界继续往前推，而不是立刻换取大幅吞吐量提升

换句话说，到这个位置已经可以比较清楚地看出：

- 在 `pal` 这类真实 workload 上，局部 JIT 从 `mov/test` 逐步推进到栈操作、条件跳转、`call/ret`
- 这一条路在功能上是走得通的
- 但如果想继续把吞吐量明显拉高，后面就不能再只靠“helper 化地补几条指令”，而要开始考虑更大范围的 block 级优化或更直接的 codegen 方式

### 15.27 为什么 helper 式 JIT 的收益开始变小

做到这一轮之后，现象已经非常一致：

1. JIT 覆盖范围确实在扩大  
   从最早的 `mov/test`，到后面的 `8b/8d/83/c1`、栈操作、条件跳转，再到最小 `call/ret`，说明这条实现路线在功能上是能一步一步推进的。

2. 但吞吐量并没有随着“支持的 opcode 越来越多”而持续提升  
   有几轮已经接近 `TB only` 持平，最后这轮 `jcc + call/ret` 甚至略慢一点点。

这说明问题已经不在“还能不能再补几条指令”，而在当前 JIT 的结构本身。这里可以把原因拆成四条。

#### 15.27.1 当前 JIT 仍然 heavily 依赖 C helper

现在这版 JIT 虽然会生成宿主机代码，但生成出来的大部分内容，本质上仍然只是：

- 压几个立即数
- `call` 一个 C helper
- helper 再去读写 `cpu.gpr[]`
- helper 里再调用 `vaddr_read/vaddr_write`
- 最后回到原框架

也就是说，它减少了一部分“前端解释开销”，但还没有把真正重的执行路径搬出 C helper。

因此，从宿主机角度看，这更像：

```text
解释器前端 + 少量机器码包装 + 大量 helper 调用
```

而不是真正意义上的“直接运行编译后的 block”。

#### 15.27.2 每条客户指令后仍然要回到原来的执行框架

当前设计里，即使某条指令命中了 JIT，执行完之后仍然要继续走：

- `cpu.eip` 更新
- watchpoint 检查
- `device_update()`
- 中断轮询
- block 边界判断

这意味着 JIT 命中的收益被拆得很碎。  
即使成功把一条客户指令变成了宿主机代码执行，它后面仍然要立刻回到原来的调度框架里交接一次。

所以现在这版更像是：

```text
单条指令 JIT
```

而不是：

```text
整个 block 在宿主机上连续跑完
```

这也是为什么它在功能上能逐步扩展，但在性能上很难突然出现明显跃升。

#### 15.27.3 最重的热点仍然在访存链，而不是前端 dispatch

前面的 `perf` 已经反复说明，最重的热点始终是：

- `is_mmio`
- `paddr_read`
- `page_translate`
- `vaddr_read`

这些路径的共同特点是：

- 它们属于访存和分页辅助链
- 和是否把 opcode 前端 JIT 化，并不是一一对应的关系

换句话说，就算当前 JIT 已经让某些 `mov/cmp/jcc` 不再走完整解释器前端，只要最后还是要：

- 读内存
- 查页表
- 判断 MMIO
- 做物理读写

真正的大头就还在那里。

这也是为什么：

- `TB` 能先带来一波较明显收益
- 后面局部 JIT 再继续补 opcode 时，收益却开始变平

因为它优化掉的是“越来越薄的一层”，而不是那条最重的访存主链。

#### 15.27.4 白名单和保守约束保证了正确性，也限制了收益上限

为了不把现在已经能运行的 `pal` 打坏，这次 JIT 一直是按很保守的方式扩：

- 限定 PC 白名单
- 只允许部分 opcode
- `jcc/call/ret` 只允许出现在 block 末尾
- 目标地址还要受额外约束

这些约束非常必要，因为它们保证了实验可以一步一步向前推进。  
但它们也意味着：

- 命中范围天然受限
- 很多真正高频但危险的路径还是回退到 TB

所以当前这版 JIT 的真实定位，更准确地说是：

```text
一个能在 pal 真实 workload 上局部生效、并逐步扩展能力边界的探索性 JIT 原型
```

而不是：

```text
一个已经足以接管大部分热点路径的高收益 JIT
```

#### 15.27.5 当前阶段可以得出的结论

把这些现象放在一起，最合理的结论是：

1. 当前 helper 式 JIT 的价值，主要在于验证“JIT 这条路在真实 workload 上走得通”。
2. 它已经成功把局部能力边界推进到了条件跳转和最小 `call/ret`。
3. 但继续只靠“增加 helper 支持的 opcode 种类”，性能收益已经接近饱和。
4. 如果后面真的还想让 JIT 带来更明显的提速，下一步就不应该再只是补零散指令，而应该考虑：
   - 更大粒度的 block 连续执行
   - 减少 helper 往返
   - 更直接的宿主机 codegen
   - 或者从访存路径本身入手

换成一句最简洁的表述就是：

```text
当前这版 JIT 已经证明了“局部即时编译”在 pal 上可行，但它仍然 heavily 依赖 helper、
并且无法绕开访存主链，因此继续扩大 opcode 覆盖后，性能提升很快进入平台期。
```

### 15.28 再做一次 `perf`，把当前 JIT 和前面的结果放在一起看

为了把当前阶段的判断再压实一次，这里又补了一轮新的 `perf` 采样，并且不是只看一种配置，而是并排看三组结果：

1. 早期干净基线 `opt4`
2. 当前代码、`JIT` 关闭，仅保留 `TB`
3. 当前代码、`JIT` 打开

三轮采样的工作负载仍然一致：都是 `pal` 的初始化阶段，也就是运行到 `PAL_InitResources success` 附近这段时间。

把关键热点放在一起对比，可以得到下面这张简化表：

| 配置 | `is_mmio` | `paddr_read` | `page_translate` | `vaddr_read` | `exec_real/exec_wrapper_cached` |
| --- | --- | --- | --- | --- | --- |
| 早期 `opt4` | `18.39%` | `18.10%` | `15.46%` | `9.72%` | `exec_real 6.71%` |
| 当前 `TB only` | `19.60%` | `16.29%` | `14.54%` | `7.88%` | `exec_wrapper_cached 7.35%`, `exec_real 0.78%` |
| 当前 `JIT on` | `17.68%` | `18.17%` | `14.23%` | `7.93%` | `exec_wrapper_cached 6.34%`, `exec_real 1.10%` |

从这张表里可以直接读出三点。

#### 15.28.1 和最早阶段相比，前端解释开销已经被压下去了

早期 `opt4` 时，`exec_real` 还有：

```text
6.71%
```

而到了当前阶段：

- `TB only` 下 `exec_real` 只剩 `0.78%`
- `JIT on` 下 `exec_real` 也只有 `1.10%`

这说明从最早的纯解释执行，到后面的 `TB`，再到现在的局部 `JIT`，**前端 dispatch/解释成本确实已经被连续压掉了一大块**。这和前面吞吐量实验里 `TB` 能明显带来一轮收益的现象是一致的。

#### 15.28.2 当前 JIT 再往前走时，最大热点仍然没有离开访存链

不管是 `TB only` 还是 `JIT on`，最重的几项始终还是：

- `is_mmio`
- `paddr_read`
- `page_translate`
- `vaddr_read`

也就是说，**当前阶段最重的时间消耗依然集中在虚拟地址访问、页表遍历、MMIO 判断和物理内存读写上**。

这也解释了为什么：

- 局部 JIT 能继续命中更多 opcode
- 但整体吞吐量却没有继续明显拉开

因为它优化掉的是前端的一层，而最重的大头仍然在访存辅助链上。

#### 15.28.3 当前 JIT 的效果主要体现在“继续压前端”，而不是改写主瓶颈

把当前 `TB only` 和 `JIT on` 放在一起看，能看到几处很细的变化：

- `is_mmio`：`19.60% -> 17.68%`
- `page_translate`：`14.54% -> 14.23%`
- `exec_wrapper_cached`：`7.35% -> 6.34%`

这些变化方向说明：

1. 当前 `JIT` 确实还在继续压“前端解释/TB 调度”这层成本。
2. 但它没有从根本上改变整个系统最重的那条访存路径。
3. 因此它带来的收益会越来越接近平台期，而不会再像最早从解释器到 `TB` 那样出现一次明显跃升。

如果要把这一轮 `perf` 对比压成一句结论，可以写成：

```text
从当前阶段的 perf 对比看，TB 和局部 JIT 已经把前端解释开销明显压低；
但系统的主热点仍然长期停留在 is_mmio、paddr_read、page_translate 和 vaddr_read
这条访存链上，因此继续扩大 helper 式 JIT 的 opcode 覆盖后，性能收益开始趋于平台。
```

### 15.21 做一次更正式的 opcode 频率统计：覆盖整个 `pal` 初始化阶段

前面所有 JIT 命中统计都有一个天然局限：它们只反映当前白名单覆盖到的 `PAL_MKF*` 局部路径。为了判断“真正高频的客户指令到底是什么”，这里又临时做了一轮更正式的全局统计。

这次没有再依赖 JIT 摘要，而是在 `NEMU` 里临时加了一组全局 opcode 计数钩子：

1. 在 `exec_wrapper()` 和 `exec_wrapper_cached()` 里，每执行一条客户指令就累计一次 opcode。
2. 在串口输出路径里监视文本行。
3. 一旦检测到：

```text
PAL_InitResources success
```

就立刻输出 top opcode 统计，并停止运行。

这样得到的统计范围就不再是 JIT 白名单，而是：

```text
从 pal 启动到 PAL_InitResources success 的整个初始化阶段
```

这轮统计时保持：

- `ENABLE_JIT_SANDBOX = 0`
- 只打开临时的 opcode profile

最终得到的结果如下：

```text
[opcode-profile] total=4265104
[opcode-profile] rank=1  opcode=89    count=1068922 ratio=25.06%
[opcode-profile] rank=2  opcode=39    count=570863  ratio=13.38%
[opcode-profile] rank=3  opcode=8b    count=467027  ratio=10.95%
[opcode-profile] rank=4  opcode=83    count=348772  ratio=8.18%
[opcode-profile] rank=5  opcode=75    count=303354  ratio=7.11%
[opcode-profile] rank=6  opcode=7f    count=241531  ratio=5.66%
[opcode-profile] rank=7  opcode=42    count=240822  ratio=5.65%
[opcode-profile] rank=8  opcode=8a    count=229566  ratio=5.38%
[opcode-profile] rank=9  opcode=88    count=227727  ratio=5.34%
[opcode-profile] rank=10 opcode=74    count=51457   ratio=1.21%
[opcode-profile] rank=11 opcode=c7    count=43447   ratio=1.02%
[opcode-profile] rank=12 opcode=77    count=36365   ratio=0.85%
[opcode-profile] rank=13 opcode=05    count=32773   ratio=0.77%
[opcode-profile] rank=14 opcode=8d    count=25640   ratio=0.60%
[opcode-profile] rank=15 opcode=40    count=20431   ratio=0.48%
[opcode-profile] rank=16 opcode=80    count=20303   ratio=0.48%
[opcode-profile] rank=17 opcode=85    count=19910   ratio=0.47%
[opcode-profile] rank=18 opcode=0f b6 count=18779   ratio=0.44%
[opcode-profile] rank=19 opcode=53    count=17484   ratio=0.41%
[opcode-profile] rank=20 opcode=55    count=17005   ratio=0.40%
```

这组结果非常重要，因为它把“真正高频的客户指令”画得很清楚：

1. 最重的是 `89`
   - 占到了整个初始化阶段的四分之一以上
   - 说明大量时间花在寄存器/内存写回路径上

2. `39`、`83`、`75`、`7f`、`74`
   - 这组组合表明初始化阶段里大量存在
     - 比较
     - 小算术
     - 条件跳转
   - 也就是说，控制流判断在真实 workload 中是绝对主力

3. `8b`、`8a`、`88`
   - 说明读内存、按字节搬运数据这件事也非常频繁

4. 栈操作虽然能命中很多次，但从全局频率看并不是主角
   - `53`、`55` 只在 top20 的尾部
   - 这解释了为什么补完一大批 `push/pop` 之后，覆盖范围增加了，但吞吐量没有明显再上去

因此，如果把这轮统计转成后续 JIT 的决策结论，可以写成：

```text
从 pal 初始化阶段的全局 opcode 统计看，真正高频的客户指令集中在
mov、cmp、group1 小算术以及条件跳转上，而不是此前较容易处理的 push/pop。
这说明后续如果想让 JIT 继续带来明显收益，下一步的重点应当放在控制流相关
指令和更高频的访存/写回路径上。
```

---

## 16. 当前阶段结论

到现在为止，`PA5` 已经可以确认完成的部分有：

1. `FLOAT / binary scaling` 相关函数已经全部补齐
2. 本地数值样例与指导书示例一致
3. 远端真实编译通过
4. `PAL` 已经能够真正进入战斗并继续运行
5. `PA5` 场景已经收敛回单进程 `pal`
6. 已经完成多轮 `perf` 热点采样，并得到可写进报告的结果
7. 已经完成 `is_mmio`、A/D 位回写、TB、TB 大小探究等多轮性能实验
8. 已经实现一个最小 JIT 沙盒，并在 `jitmini` 与 `pal` 的局部真实函数上得到稳定命中

当前仍然没有完全做完的部分主要是：

1. `pal` 上更大范围的 JIT 覆盖
2. 把 JIT 从局部真实函数继续推进到更复杂的控制流和访存路径

---

## 17. 后续可以继续补的内容

后面如果继续推进，这份记录还可以继续补：

1. `JIT 继续扩范围`
- 是否先从 `PAL_MKFReadChunk` 向上扩大到更多资源相关函数
- 是否继续避开解压、分页和系统调用路径

2. `吞吐量对比`
- 是否专门记录局部 JIT 命中前后的吞吐量变化
- 是否补一组“TB only / TB + narrow JIT”对比数据

3. `热点分析写入正式报告`
- 采样命令
- 运行环境
- 热点函数占比
- 对性能瓶颈的解释

---

## 18. perf 结果归档

为了方便后续写正式报告，这次已经把两轮 `perf` 的文本结果都同步保存到了本地：

### 16.1 第一轮优化前

目录：

```text
PA报告/PA5-report/perf/before/
```

文件：

- `pa5-pal-run.log`
- `pa5-pal.perf.report.txt`
- `pa5-pal.perf.report.symbol.txt`

### 16.2 第二轮优化后

目录：

```text
PA报告/PA5-report/perf/after/
```

文件：

- `pa5-pal-opt.run.log`
- `pa5-pal-opt.perf.report.txt`
- `pa5-pal-opt.perf.report.symbol.txt`

### 17.3 最新干净基线

目录：

```text
PA报告/PA5-report/perf/opt4/
```

文件：

- `pa5-pal-opt4.run.log`
- `pa5-pal-opt4.perf.report.txt`
- `pa5-pal-opt4.perf.report.symbol.txt`

### 17.4 方案 A：排序 + 二分

目录：

```text
PA报告/PA5-report/perf/optA/
```

文件：

- `pa5-pal-optA.run.log`
- `pa5-pal-optA.perf.report.symbol.txt`

### 17.5 方案 B：页级查表

目录：

```text
PA报告/PA5-report/perf/optB/
```

文件：

- `pa5-pal-optB.run.log`
- `pa5-pal-optB.perf.report.symbol.txt`

### 18.6 TB 原型

目录：

```text
PA报告/PA5-report/perf/tb/
```

文件：

- `pa5-pal-tb.run.log`
- `pa5-pal-tb.perf.report.symbol.txt`

这样后面写报告时，不需要再回远端重复采集，可以直接对照这两轮结果做“优化前后对比分析”。
