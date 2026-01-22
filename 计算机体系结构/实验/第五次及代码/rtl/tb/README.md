# tb/ 目录说明

本目录下是用于定位/回归 TLB 集成边界的 **CPU 级** testbench（直接例化 `mycpu_core`，并提供简化 SRAM 时序模型）。

## 用例列表

- `cpu_tlb_hazard_tb.v`
  - 目的：验证 `TLBWI/TLBR` 在 WB 提交后的 flush+重取 + outstanding discard，以及 `TLBP` 与在途 `MTC0(EntryHi)` 的阻塞。
  - 期望：仿真结束打印 `[TB][PASS] cpu_tlb_hazard_tb`。

- `cpu_tlb_suite_tb.v`
  - 目的：覆盖更多语义与边界：偶/奇页选择、G 位忽略 ASID、TLBR 回读一致性、TLBR->TLBP 紧邻序列、TLBP miss 的 Index.P=1、以及取指侧 s0 的 TLB 翻译（跳转到 kuseg 代码页执行）。
  - 期望：仿真结束打印 `[TB][PASS] cpu_tlb_suite_tb` 并输出各 RES 值。

- `cpu_tlb_vd_tb.v`
  - 目的：检查 **V/D 位在“未实现异常”策略下**的安全处理：
    - tag 匹配但 `V=0` 时不应进行地址翻译（退化为不翻译/视作 miss）
    - store 且 `D=0` 时不应进行地址翻译（退化为不翻译/视作 miss）
  - 期望：仿真结束打印 `[TB][PASS] cpu_tlb_vd_tb`。

## 在 Vivado/xsim 里运行（示例）

1. 把 `rtl/myCPU/*.v` 与 `rtl/tb/*.v` 加入仿真源。
2. 选择对应的 tb 顶层（例如 `cpu_tlb_suite_tb`）。
3. 运行 `run all`，观察控制台 PASS/FAIL 打印。

> 注：tb 默认假设 reset 向量 `0xBFC0_0000` 通过直映规则到物理 `0x1FC0_0000`。