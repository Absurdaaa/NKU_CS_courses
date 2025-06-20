import csv

# 你的 ARM 指令集相关主体名词集合（建议用小写进行匹配）
arm_entities = {
    word.lower() for word in [
        "AArch32", "AArch64", "ARM", "Abort", "Access", "Address", "Architecture", "Behavior",
        "Breakpoint", "Cache", "Case", "Control", "Counter", "Data", "Debug", "Domain", "EL0", "EL1",
        "EL2", "EL3", "Effect", "Encoding", "Entry",  "Exception", "Execution", "Extension",
        "Fault", "Field", "Implementation", "Instruction", "Interface", "Level", "Memory", "Mode",
        "Operation", "Page", "PE", "Range", "Register",  "Set", "Size",
        "Software", "Stage", "State", "Support", "System", "Table", "Translation", "Traps"
    ]
}

def filter_triples(input_csv, output_txt):
    kept = []
    unique_entities = set()  # 用于统计独特实体
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            arg1, rel, arg2 = row[0].strip(), row[1].strip(), row[2].strip()
            if arg1.lower() in arm_entities and arg2.lower() in arm_entities:
                arg1 = arg1.title()
                arg2 = arg2.title()
                kept.append((arg1, rel, arg2))
 
                unique_entities.add(arg1.lower())
                unique_entities.add(arg2.lower())

    # 写入 txt 文件
    with open(output_txt, 'w', encoding='utf-8') as f:
        for arg1, rel, arg2 in kept:
            f.write(f"{arg1},{rel},{arg2}\n")

    print(f"✅ 保留了 {len(kept)} 条三元组，已写入 {output_txt}")
    print(f"✅ 共有 {len(unique_entities)} 个独特实体")

# 示例调用
filter_triples("clean_triples_2.csv", "output/filtered_arm_triples.txt")
