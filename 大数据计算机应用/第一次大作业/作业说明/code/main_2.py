import numpy as np
from scipy import sparse
from memory_profiler import profile


def build_graph(file_path):
    # 读取文件并构建节点集与边列表
    edges = []
    nodes = set()
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 2:
                print("Invalid line format:", line)
                continue
            u, v = parts
            edges.append((u, v))
            # 添加节点到集合中
            nodes.update([u, v])
    # 排序节点并建立索引
    nodes = sorted(list(nodes))
    node_index = {node: idx for idx, node in enumerate(nodes)}
    return edges, nodes, node_index

def build_transition_matrix(edges, nodes, node_index):
    N = len(nodes)
    # 使用COO格式初始化稀疏矩阵（适合构建阶段）
    row_indices = []
    col_indices = []
    data = []
    
    # 统计每个节点的出度
    out_degrees = np.zeros(N)
    for u, v in edges:
        i = node_index[u]
        j = node_index[v]
        out_degrees[i] += 1
    
    # 构建稀疏矩阵的数据
    for u, v in edges:
        i = node_index[u]
        j = node_index[v]
        if out_degrees[i] > 0:
            row_indices.append(j)  # 转置后的行（原列）
            col_indices.append(i)  # 转置后的列（原行）
            data.append(1.0 / out_degrees[i])
    
    
    death = np.zeros(N, dtype=np.float32)
    # 处理死节点（没有出边的节点）
    for i in range(N):
        if out_degrees[i] == 0:
            death[i] = 1
    
    # 创建稀疏矩阵（已转置）
    M = sparse.csr_matrix((data, (row_indices, col_indices)), shape=(N, N))
    return M,death

def pagerank(M, death, damping=0.85, tol=1e-6, max_iter=10000):
    N = M.shape[0]
    # 初始化概率向量
    pr = np.ones(N, dtype=np.float32) / N
    teleport = np.ones(N, dtype=np.float32) / N
    
    for iter_count in range(max_iter):
        # 稀疏矩阵乘法
        pr_new = damping * (M @ pr) +damping/N *(death @ pr)  + (1 - damping) * teleport
        
        # 计算收敛程度
        err = np.linalg.norm(pr_new - pr, ord=1)
        pr = pr_new
        
        if err < tol:
            print(f"迭代第{iter_count}次之后，PageRank 收敛")
            return pr
            
    print(f"警告：达到最大迭代次数{max_iter}，但未收敛")
    return pr

@profile
def main():
    file_path = "Data.txt"
    edges, nodes, node_index = build_graph(file_path)
    M,death = build_transition_matrix(edges, nodes, node_index)
    pr_values = pagerank(M,death)
    
    # 将节点与对应的 PageRank 值组合成元组列表
    node_pr = list(zip(nodes, pr_values))
    # 按照 PageRank 值降序排序
    sorted_node_pr = sorted(node_pr, key=lambda x: x[1], reverse=True)
    # 输出排序后的节点和 PageRank 值
    # for node, pr in sorted_node_pr:
    #     print("节点 {} 的 PageRank 值为: {:.6f}".format(node, pr))
    
    for i in range(100):
        node, pr = sorted_node_pr[i]
        print("节点 {} 的 PageRank 值为: {:.6f}".format(node, pr))
    print(pr_values.sum())
    
    # 将 Top-100 节点及其分数写入文件
    with open("Res2.txt", "w") as f:
        for i in range(100):
            node, pr = sorted_node_pr[i]
            f.write(f"{node} {pr:.6f}\n")
    
if __name__ == "__main__":
    main()

