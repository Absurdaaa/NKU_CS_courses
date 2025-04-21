import re
import csv
import spacy
from collections import Counter
import time

import PyPDF2

def pdf_to_text(pdf_path, txt_path, batch_size=10):
  try:
    # 打开 PDF 文件
    with open(pdf_path, 'rb') as pdf_file:
      reader = PyPDF2.PdfReader(pdf_file)
      total_pages = len(reader.pages)
      print(f"PDF 文件共有 {total_pages} 页。")

      # 分批读取并写入文本文件
      with open(txt_path, 'w', encoding='utf-8') as txt_file:
        for start_page in range(0, total_pages, batch_size):
          end_page = min(start_page + batch_size, total_pages)
          print(f"正在处理第 {start_page + 1} 到第 {end_page} 页...")
          for page_num in range(start_page, end_page):
            page = reader.pages[page_num]
            txt_file.write(page.extract_text())
            txt_file.write("\n")
      print(f"转换完成，文本已保存到 {txt_path}")
  except Exception as e:
    print(f"发生错误: {e}")

# 加载英文 NLP 模型
nlp = spacy.load("en_core_web_sm")
nlp.max_length = 30_000_000  # 设置最大长度为 30M 字符（适配你的输入）

# 常见代词（可自行扩展）
# 再删去一些常见无用词
PRONOUNS = {
    "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them",
    "this", "that", "these", "those",
    "my", "your", "his", "its", "our", "their",
    "mine", "yours", "hers", "ours", "theirs"
}

def is_pronoun(word):
    return word.lower().strip() in PRONOUNS

def is_valid_entity(entity):
    if not entity:
        return False
    entity = entity.strip()
    if len(entity) < 2:
        return False
    if all(c in "!@#$%^&*()_+=-[]{};:'\",.<>?/\\|`~" for c in entity):
        return False
    if re.fullmatch(r"[#=;0-9\s]+", entity):
        return False
    if len(re.findall(r'[a-zA-Z]', entity)) < 2:
        return False
    if is_pronoun(entity):
        return False
    return True

def clean_text(text):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if len(line) < 10:
            continue
        if 'copyright' in line.lower() or '©' in line:
            continue
        if re.fullmatch(r'[\W\d\s]+', line):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)

def extract_triples(text):
    triples = []
    doc = nlp(text)
    for sent in doc.sents:
        subj, verb, obj = None, None, None
        for token in sent:
            if "subj" in token.dep_ and subj is None:
                subj = token
            elif token.pos_ == "VERB" and verb is None:
                verb = token
            elif "obj" in token.dep_ and obj is None:
                obj = token
        if subj and verb and obj:
            arg1, rel, arg2 = subj.text, verb.text, obj.text
            if is_valid_entity(arg1) and is_valid_entity(arg2):
                triples.append((arg1.strip(), rel.strip(), arg2.strip()))
    return triples

def split_large_text(text, chunk_size=500_000):
    """将大文本按字符分块"""
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]



def process_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    cleaned = clean_text(raw_text)
    chunks = split_large_text(cleaned)
    total_chunks = len(chunks)

    all_triples = []
    total_extracted = 0

    print(f"开始处理，共 {total_chunks} 个分块，每块约 50 万字符")

    for i, chunk in enumerate(chunks):
        start_time = time.time()
        triples = extract_triples(chunk)
        all_triples.extend(triples)
        total_extracted += len(triples)
        duration = time.time() - start_time

        print(f"  ➤ 第 {i+1}/{total_chunks} 块处理完毕：提取 {len(triples)} 个三元组，累计 {total_extracted}，耗时 {duration:.2f} 秒")

    print(f"\n✅ 所有分块处理完毕，总共提取三元组：{total_extracted}")
    return all_triples



def filter_and_export(triples, out_csv='clean_triples.csv', top_k=50):
    triples = list(set(triples))  # 去重
    entity_counter = Counter()
    for arg1, _, arg2 in triples:
        entity_counter[arg1.lower()] += 1
        entity_counter[arg2.lower()] += 1

    top_entities = set(e for e, _ in entity_counter.most_common(top_k))
    filtered_triples = [
        (a, r, b) for (a, r, b) in triples
        if a.lower() in top_entities and b.lower() in top_entities
    ]

    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['arg1', 'relation', 'arg2'])
        writer.writerows(filtered_triples)

    print(f"总抽取三元组数：{len(triples)}")
    print(f"保留高频实体（Top {top_k}）三元组数：{len(filtered_triples)}")
    print(f"结果已保存至 {out_csv}")

if __name__ == "__main__":

    pdf_path = "Architecture Reference Manual ArmV8.pdf"  # 替换为你的 PDF 文件路径
    txt_path = "Architecture Reference Manual ArmV8_output.txt"          # 替换为输出的文本文件路径
    pdf_to_text(pdf_path, txt_path, batch_size=20)
      
  
    import argparse
    parser = argparse.ArgumentParser(description="三元组抽取 Pipeline（英文）")
    parser.add_argument("input_txt", help="输入文本文件（英文）路径")
    parser.add_argument("--topk", type=int, default=100, help="保留高频实体数量")
    parser.add_argument("--out", type=str, default="clean_triples_2.csv", help="输出 CSV 文件名")
    args = parser.parse_args()

    triples = process_file(args.input_txt)
    filter_and_export(triples, args.out, args.topk)
