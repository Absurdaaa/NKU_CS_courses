import numpy as np
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

# 初始化转移矩阵
def build_transition_matrix(edges, nodes, node_index):
    N = len(nodes)# 节点个数
    M = np.zeros((N, N))
    # 构建转移矩阵 M，行表示出发点，列表示终点
    for u, v in edges:
        i = node_index[u]
        j = node_index[v]
        M[i, j] = 1
    # 归一化：将每一行除以该行的和，注意处理死节点（没有出边的节点）
    for i in range(N):
        row_sum = M[i].sum()
        if row_sum != 0:
            M[i] /= row_sum
        else:
            # 如果没有出边，则均匀分布到所有节点上
            # 黑洞！！！
            M[i] = np.ones(N) / N
    return M.T  # 转置后方便用列向量表示概率

def pagerank(M, damping=0.85, tol=1e-6, max_iter=10000):
    N = M.shape[0]
    # 初始化概率向量
    pr = np.ones(N) / N
    teleport = np.ones(N) / N
    for _ in range(max_iter):
        # (1 - damping) * teleport 是为了防止蜘蛛网问题，让它有一定概率随机走到任意节点，跑出蜘蛛网
        pr_new = damping * (M @ pr) + (1 - damping) * teleport
        if np.linalg.norm(pr_new - pr, ord=1) < tol:
            print(f"迭代第{_}次之后，PageRank 收敛")
            return pr_new
        pr = pr_new
    return pr

@profile
def main():
    file_path = "Data.txt"
    edges, nodes, node_index = build_graph(file_path)
    M = build_transition_matrix(edges, nodes, node_index)
    pr_values = pagerank(M)
    
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
    with open("Res11.txt", "w") as f:
        for i in range(len(sorted_node_pr)):
            node, pr = sorted_node_pr[i]
            f.write(f"{node} {pr:.8f}\n")
    
if __name__ == "__main__":

  import time
  start_time = time.time()
  main()
  end_time = time.time()
  print(f"执行时间: {end_time - start_time:.2f} 秒")

