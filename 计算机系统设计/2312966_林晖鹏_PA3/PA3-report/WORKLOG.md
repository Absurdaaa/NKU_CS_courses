# PA3 Worklog

## Environment

- Local workspace: `/Users/linshangjin/Desktop/PA`
- Local code repo: `/Users/linshangjin/Desktop/PA/ics2017`
- VM host: `172.16.31.137`
- VM code repo: `/home/linshangjin/code/ics2017`
- Handout: `/Users/linshangjin/Desktop/PA/PA指导书/04-PA3-异常控制流与操作系统.md`

## Session Notes

### 2026-05-22

- 目标：开始完成 PA3，并持续记录可以直接复用到实验报告里的过程材料。
- 用户确认虚拟机 IP 已从 `172.16.31.136` 变为 `172.16.31.137`。
- 已验证可以通过 SSH 连接虚拟机，并确认以下目录仍然存在：
  - `/home/linshangjin/code/ics2017`
  - `/home/linshangjin/code/PA报告`
  - `/home/linshangjin/code/PA指导书`
- 已阅读 `PA3` 指导书，确定当前第一阶段目标为：
  - 编译第一个用户程序 `dummy`
  - 实现 `loader`
  - 之后继续实现异常、中断和系统调用链路

### 编译 dummy 的过程

- 操作目录：`~/code/ics2017/navy-apps/tests/dummy`
- 第一次执行命令：`make`
- 现象：
  - 构建目标变成了 `dummy-native`
  - 链接阶段报错：`undefined reference to '_syscall_'`
- 分析：
  - 这说明当时编译到了错误的平台目标
  - 生成的不是 `PA3` 所需要的 x86 用户程序

- 第二次执行命令：`make ISA=x86 APP=dummy`
- 目的：
  - 显式指定编译方向，尝试把用户程序切到 x86 目标

- 最终成功执行命令：`make ISA=x86`
- 运行结果：
  - 成功链接生成 `/home/linshangjin/code/ics2017/navy-apps/tests/dummy/build/dummy-x86`
- 结论：
  - `dummy.c` 已经被成功编译为面向 x86 的用户程序
  - 该文件将作为 `Nanos-lite` 在 PA3 中加载和执行的第一个用户程序

### 更新 ramdisk

- 操作目录：`~/code/ics2017/nanos-lite`
- 执行命令：`make update`
- 运行结果：
  - 构建系统执行了 `objcopy .../dummy/build/dummy-x86 build/ramdisk.img`
  - 同时更新了 `src/files.h` 和 `src/syscall.h`
- 结论：
  - 刚刚生成的 `dummy-x86` 已经被打包进 `nanos-lite/build/ramdisk.img`
  - 后续 `loader()` 的任务，就是把这个用户程序从 ramdisk 复制到 `0x4000000` 并跳转执行

### 任务 1：实现 raw program loader

- 修改文件：`nanos-lite/src/loader.c`
- 修改内容：
  - 调用 `get_ramdisk_size()` 获取 ramdisk 大小
  - 调用 `ramdisk_read(DEFAULT_ENTRY, 0, get_ramdisk_size())`
  - 返回 `0x4000000` 作为入口地址
- 说明：
  - 当前阶段按照指导书要求，将 ramdisk 中唯一的用户程序整体搬运到 `0x4000000`
  - 暂时不涉及文件系统，也不涉及 ELF 解析

### 运行验证

- 为避免 `nanos-lite` 默认按 `native` 编译，运行时使用了：
  - `make ARCH=x86-nemu run`
- 运行现象：
  - `nanos-lite` 与 `nemu` 均完成了编译和链接
  - `NEMU` 成功启动并加载镜像 `nanos-lite-x86-nemu.bin`
  - 但在进入运行后，`make run` 以 `Segmentation fault (core dumped)` 结束
- 当前结论：
  - `loader.c` 已经补上，并且能够通过编译，参与后续镜像构建
  - 但目前还没有看到指导书中预期的“未实现的 int 指令”
  - 当前阻塞已经从 `loader` 的缺失，推进到了 `NEMU` 运行期异常，需要继续排查

## 下一步

1. 检查 `NEMU` 运行期段错误发生在什么位置。
2. 只在 `TODO` 明确落点内继续修改代码。
3. 继续推进 PA3.1，直到看到用户程序执行到未实现的 `int` 指令。
