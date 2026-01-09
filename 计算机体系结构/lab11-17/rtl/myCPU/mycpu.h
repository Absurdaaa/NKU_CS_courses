`ifndef MYCPU_H
    `define MYCPU_H

    `define BR_BUS_WD           35

    `define PFS_TO_FS_BUS_WD    65
    `define FS_TO_DS_BUS_WD     97
    // ds_to_es: 增加 TLBR/TLBWI/TLBP 3 个指令位
    `define DS_TO_ES_BUS_WD     214
    // es_to_ms / ms_to_ws: 透传 3 个 TLB 指令位 + tlbp {found,index}
    `define ES_TO_MS_BUS_WD     171
    `define MS_TO_WS_BUS_WD     132
    `define WS_TO_RF_BUS_WD     41
    `define ES_FWD_BLK_BUS_WD   42
    `define MS_FWD_BLK_BUS_WD   42

    // CP0 addr = {rd[15:11], sel[2:0]}
    `define CP0_INDEX_ADDR       8'h00  // Index,  rd=0  sel=0
    `define CP0_ENTRYLO0_ADDR    8'h10  // EntryLo0, rd=2 sel=0
    `define CP0_ENTRYLO1_ADDR    8'h18  // EntryLo1, rd=3 sel=0
    `define CP0_ENTRYHI_ADDR     8'h50  // EntryHi,  rd=10 sel=0

    `define EX_INT              5'h00
    `define EX_ADEL             5'h04
    `define EX_ADES             5'h05
    `define EX_SYS              5'h08
    `define EX_BP               5'h09
    `define EX_RI               5'h0a
    `define EX_OV               5'h0c
    `define EX_NO               5'h1f

    `define EX_ENTRY            32'h_bfc00380

`endif
