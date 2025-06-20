import csv
from collections import Counter

# 停用代词（可自行补充）
PRONOUNS = {
    "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them",
    "this", "that", "these", "those",
    "my", "your", "his", "its", "our", "their",
    "mine", "yours", "hers", "ours", "theirs"
}

# 工具函数：是否是代词
def is_pronoun(word):
    return word.lower().strip() in PRONOUNS

# 保存三元组
triples = []

with open('relation.tsv', 'r') as infile:
    reader = csv.reader(infile, delimiter='\t')
    for row in reader:
        if len(row) >= 18:
            arg1 = row[15].strip().lower()
            rel = row[16].strip().lower()
            arg2 = row[17].strip().lower()

            if is_pronoun(arg1) or is_pronoun(arg2):
                continue  # 跳过代词

            triples.append((arg1, rel, arg2))

# 去重
unique_triples = list(set(triples))

# 统计实体频率
entity_counter = Counter()
for arg1, _, arg2 in unique_triples:
    entity_counter[arg1] += 1
    entity_counter[arg2] += 1

# 取前100个高频实体
top_entities = set([entity for entity, _ in entity_counter.most_common(100)])

# 保留 arg1 和 arg2 都在 top_entities 的三元组
filtered_triples = [
    (arg1, rel, arg2) for (arg1, rel, arg2) in unique_triples
    if arg1 in top_entities and arg2 in top_entities
]

# 保存到 CSV
with open('top100_triples.csv', 'w', newline='') as outfile:
    writer = csv.writer(outfile)
    writer.writerow(['arg1', 'relation', 'arg2'])
    writer.writerows(filtered_triples)

print(f"总三元组数（去重后）：{len(unique_triples)}")
print(f"保留高频实体三元组数：{len(filtered_triples)}")
