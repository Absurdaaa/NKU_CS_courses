import json

def load_triples_from_txt(path):
    """从txt文件加载三元组"""
    triples = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) == 3:
                triples.append(tuple(part.strip() for part in parts))
    return triples

def convert_triples_to_json(triples):
    """将三元组转换为 {nodes, links} JSON 格式"""
    # 收集所有实体（arg1 和 arg2）
    entity_set = set()
    for h, _, t in triples:
        entity_set.add(h)
        entity_set.add(t)

    # 为每个实体分配唯一 ID
    entity_list = sorted(entity_set)
    entity_to_id = {name: idx for idx, name in enumerate(entity_list)}

    # 构建 nodes
    nodes = [{"id": idx, "name": name, "desc": ""} for name, idx in entity_to_id.items()]

    # 构建 links
    links = []
    for h, r, t in triples:
        if h in entity_to_id and t in entity_to_id:
            links.append({
                "source": entity_to_id[h],
                "target": entity_to_id[t],
                "relation": r
            })

    return {
        "nodes": nodes,
        "links": links
    }

def save_json(data, out_path):
    """保存JSON数据到文件"""
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON 已保存到: {out_path}")

# ======= 主程序入口 =======
if __name__ == "__main__":
    input_txt = "output/filtered_arm_triples.txt"            # 输入三元组文本文件
    output_json = "output/triples_graph.json"   # 输出 JSON 文件

    triples = load_triples_from_txt(input_txt)
    graph = convert_triples_to_json(triples)
    save_json(graph, output_json)
