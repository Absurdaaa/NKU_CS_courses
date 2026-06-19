# PA5 — 从一到无穷大：程序与性能

> PA5 = 浮点数支持（Binary Scaling）+ NEMU 性能优化（TB缓存 + JIT）

---

## 一、浮点数支持：Binary Scaling

### 为什么不用 float？

x87 浮点指令细节复杂，根据 KISS 法则，用**整数模拟浮点**更简单。

### FLOAT 类型定义

用 32 位整数表示实数，定点格式：

```
位31      位30~16       位15~0
[sign] [integer 15位] [fraction 16位]
小数点固定在第15和第16位之间
```

实数 `a` 的 FLOAT 表示：`A = (int32_t)(a * 2^16)`

例：`1.2 → 1.2 * 65536 = 78643 = 0x13333`

### 四则运算规则

| 运算 | 方法 |
|------|------|
| 加法 `A+B` | 直接整数加（`(a+b)*2^16`） |
| 减法 `A-B` | 直接整数减 |
| 乘法 `A*B` | 整数乘后**右移16位**（`A*B/2^16`）|
| 除法 `A/B` | 先**左移16位**再整数除（`(A<<16)/B`）|
| 关系运算 | 直接整数比较（保序性保证正确）|

### 需要实现的函数

```c
// navy-apps/apps/pal/include/FLOAT.h
int32_t F2int(FLOAT a);       // FLOAT → int（右移16位）
FLOAT   int2F(int a);         // int → FLOAT（左移16位）
FLOAT   F_mul_int(FLOAT a, int b);  // 直接整数乘
FLOAT   F_div_int(FLOAT a, int b);  // 直接整数除

// navy-apps/apps/pal/src/FLOAT/FLOAT.c
FLOAT   f2F(float a);              // float字面量 → FLOAT
FLOAT   F_mul_F(FLOAT a, FLOAT b); // 乘后右移16位
FLOAT   F_div_F(FLOAT a, FLOAT b); // 左移16位后除
FLOAT   Fabs(FLOAT a);             // 绝对值
```

实现正确后，仙剑奇侠传可以正常战斗。

---

## 二、NEMU 性能优化

### 性能分析工具：perf

```bash
perf record nemu/build/nemu nanos-lite/build/nanos-lite-x86-nemu.bin
perf report  # 查看热点函数
```

### 两级优化

| 优化 | 宏开关 | 思路 |
|------|--------|------|
| **TB缓存** | `ENABLE_TB_CACHE` | 缓存指令块元数据，跳过重复取指 |
| **JIT沙盒** | `ENABLE_JIT_SANDBOX` | 热点指令→宿主机原生x86代码直接执行 |

详细实现见 [TB_JIT实现说明.md](TB_JIT实现说明.md)。

### 宏开关位置

```c
// nemu/src/monitor/cpu-exec.c
#define ENABLE_TB_CACHE    0  // 改1开启TB缓存
#define ENABLE_JIT_SANDBOX 0  // 改1开启JIT（依赖TB_CACHE）
```

### 跑分方法

注释掉 `nemu/include/common.h` 中的 `DEBUG` 和 `DIFF_TEST`，然后：

```bash
cd nexus-am/apps/dhrystone && make ARCH=x86-nemu run
```

跑分以 i7-6700@3.40GHz 为参照，100000分=与参照机相当。
