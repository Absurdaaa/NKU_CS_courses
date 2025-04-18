import json
import re
import os

def parse_triplets_file(file_path):
    """解析三元组文件，返回三元组列表"""
    triplets = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 找到第一个和最后一个逗号的位置
            first_comma = line.find(',')
            last_comma = line.rfind(',')
            
            # 确保找到了至少两个逗号，且不是同一个
            if first_comma != -1 and last_comma != -1 and first_comma != last_comma:
                arg1 = line[:first_comma].strip()
                relation = line[first_comma+1:last_comma].strip()
                arg2 = line[last_comma+1:].strip()
                triplets.append((arg1, relation, arg2))
    
    return triplets

def extract_descriptions(file_path, unique_args):
    """从描述文件中提取唯一参数的描述"""
    descriptions = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 仅分割第一个冒号，因为描述内容中可能包含冒号
        parts = line.split(':', 1)
        if len(parts) >= 2:
            arg = parts[0].strip()
            desc = parts[1].strip()
            
            # 如果这个参数在我们关心的唯一参数列表中
            if arg in unique_args:
                descriptions[arg] = desc
    
    # 为未找到描述的参数设置默认描述
    for arg in unique_args:
        if arg not in descriptions:
            descriptions[arg] = f"{arg}的相关概念和特性"
    
    return descriptions

def create_json_data(triplets, descriptions):
    """创建JSON数据结构"""
    # 收集所有唯一的参数
    unique_args = set()
    for arg1, _, arg2 in triplets:
        unique_args.add(arg1)
        unique_args.add(arg2)
    
    # 创建节点列表
    nodes = []
    arg_to_id = {}
    for i, arg in enumerate(sorted(unique_args)):
        desc = descriptions.get(arg, f"{arg}的相关概念和特性")
        nodes.append({
            "id": i,
            "name": arg,
            "desc": desc
        })
        arg_to_id[arg] = i
    
    # 创建链接列表
    links = []
    for arg1, relation, arg2 in triplets:
        if arg1 in arg_to_id and arg2 in arg_to_id:
            links.append({
                "source": arg_to_id[arg1],
                "target": arg_to_id[arg2],
                "relation": relation
            })
    
    return {
        "nodes": nodes,
        "links": links
    }

def main():
    # 文件路径
    triplets_file = 'output/alltuple.txt'
    description_file = 'output/allnode.txt'
    output_file = '/Users/linshangjin/NKU_CS_courses/计算机组成原理/第二次大作业/output/output.json'
    
    # 解析三元组文件
    triplets = parse_triplets_file(triplets_file)
    
    # 收集所有唯一的参数
    unique_args = set()
    for arg1, _, arg2 in triplets:
        unique_args.add(arg1)
        unique_args.add(arg2)
    
    # 提取描述
    descriptions = extract_descriptions(description_file, unique_args)
    
    # 创建JSON数据
    json_data = create_json_data(triplets, descriptions)
    
    # 保存到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    print(f"JSON数据已保存到 {output_file}")
    print(f"共创建了 {len(json_data['nodes'])} 个节点和 {len(json_data['links'])} 个关系")

if __name__ == '__main__':
    main()
