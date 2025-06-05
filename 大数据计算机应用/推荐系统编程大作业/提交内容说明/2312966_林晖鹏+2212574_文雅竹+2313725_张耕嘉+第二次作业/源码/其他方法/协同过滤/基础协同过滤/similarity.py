import numpy as np

def cosine_similarity(vec1, vec2):
    """计算两个向量的余弦相似度"""
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    return np.dot(vec1, vec2) / (norm1 * norm2 + 1e-8)

def pearson_similarity(vec1, vec2):
    """计算两个向量的皮尔逊相关系数"""
    mean1 = np.mean(vec1)
    mean2 = np.mean(vec2)
    centered_vec1 = vec1 - mean1
    centered_vec2 = vec2 - mean2
    numerator = np.dot(centered_vec1, centered_vec2)
    denominator = np.sqrt(np.sum(centered_vec1 ** 2)) * np.sqrt(np.sum(centered_vec2 ** 2))
    return numerator / (denominator + 1e-8)

def manhattan_similarity(vec1, vec2):
    """计算两个向量的曼哈顿距离相似度"""
    distance = np.sum(np.abs(vec1 - vec2))
    return 1 / (1 + distance)

def euclidean_similarity(vec1, vec2):
    """计算两个向量的欧几里得距离相似度"""
    distance = np.sqrt(np.sum((vec1 - vec2) ** 2))
    return 1 / (1 + distance)

def jaccard_similarity(vec1, vec2):
    """计算两个向量的杰卡德相似度（适用于二值向量）（集合相似度）"""
    intersection = np.sum(np.minimum(vec1, vec2))
    union = np.sum(np.maximum(vec1, vec2))
    return intersection / (union + 1e-8)