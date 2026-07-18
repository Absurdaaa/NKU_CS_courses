import random

import numpy as np
import copy
import torch
import torch.nn
import string
import unicodedata
import os
import glob
from torch.nn.utils.rnn import pad_sequence
from io import open
from torch.utils.data import Dataset, DataLoader, random_split, Subset
from sklearn.model_selection import train_test_split

allowed_characters = string.ascii_letters + ',.;' + '_'
n_letters = len(allowed_characters)

def unicodeToAscii(s):
    res = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn' and c in allowed_characters)
    return res

def letterToIndex(letter):
    if letter not in allowed_characters:
        return allowed_characters.find('_')
    else:
        return allowed_characters.find(letter)

def lineToTensor(line):
    tensor = torch.zeros(len(line), 1, n_letters)
    for idx, letter in enumerate(line):
        tensor[idx][0][letterToIndex(letter)] = 1
    return tensor

class NameDataset(Dataset):
    def __init__(self, data_dir):
        self.data = []
        self.data_tensors = []
        self.labels = []
        self.labels_tensors = []

        labels_set = set()

        test_files = glob.glob(os.path.join(data_dir, '*.txt'))
        for file in test_files:
            filename = os.path.basename(file)
            label, ext = os.path.splitext(filename)
            labels_set.add(label)
            lines = open(file, encoding='utf-8').read().strip().split('\n')
            for name in lines:
                ascii_name = unicodeToAscii(name)

                # 后面全部使用转换后的 ascii_name
                self.data.append(ascii_name)
                self.labels.append(label)
                self.data_tensors.append(lineToTensor(ascii_name))

        self.labels_uniq = list(labels_set)
        for i in range(len(self.labels)):
            temp_tensor = torch.tensor(self.labels_uniq.index(self.labels[i]), dtype=torch.long)
            self.labels_tensors.append(temp_tensor)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        data_item = self.data[idx]
        data_label = self.labels[idx]
        data_tensor = self.data_tensors[idx]
        label_tensor = self.labels_tensors[idx]
        return label_tensor, data_tensor, data_label, data_item


def get_train_test_data(dataset, test_size=0.1):
    """
    将 NameDataset 拆分为训练集和测试集，返回的依然是 NameDataset 对象。
    """
    indices = list(range(len(dataset)))

    # 提取用于分层抽样的 labels
    if hasattr(dataset, 'labels'):
        targets = dataset.labels
    else:
        raise AttributeError('dataset 必须提供 labels 属性进行分层抽样')

    train_indices, test_indices = train_test_split(indices, test_size=test_size, stratify=targets, random_state=42)

    # 1. 浅拷贝原数据集，保留 labels_uniq 等非数据属性的映射
    train_dataset = copy.copy(dataset)
    test_dataset = copy.copy(dataset)

    # 2. 根据拆分出来的索引，重新生成并覆盖内部的四个核心数据列表 (Train)
    train_dataset.data = [dataset.data[i] for i in train_indices]
    train_dataset.labels = [dataset.labels[i] for i in train_indices]
    train_dataset.data_tensors = [dataset.data_tensors[i] for i in train_indices]
    train_dataset.labels_tensors = [dataset.labels_tensors[i] for i in train_indices]

    # 3. 根据拆分出来的索引，重新生成并覆盖内部的四个核心数据列表 (Test)
    test_dataset.data = [dataset.data[i] for i in test_indices]
    test_dataset.labels = [dataset.labels[i] for i in test_indices]
    test_dataset.data_tensors = [dataset.data_tensors[i] for i in test_indices]
    test_dataset.labels_tensors = [dataset.labels_tensors[i] for i in test_indices]

    return train_dataset, test_dataset

def collate_fn(batch):
    # 1. 解包 batch
    label_tensors = [item[0] for item in batch]
    # item[1] 的形状是 (seq_len, 1, n_letters)，我们需要去掉那个多余的 1
    # squeeze(1) 后变成 (seq_len, n_letters)
    data_tensors = [item[1].squeeze(1) for item in batch]
    data_labels = [item[2] for item in batch]
    data_items = [item[3] for item in batch]

    # 2. 处理 Labels（把标量堆叠成一个一维张量）
    # 结果形状: (batch_size,)
    label_tensors = torch.stack(label_tensors)

    # 3. 计算 lengths
    # 获取排序/掩码需要的真实长度序列
    lengths = torch.tensor([t.size(0) for t in data_tensors], dtype=torch.long)

    # 4. Pad data_tensors (处理变长序列)
    # 结果形状: (max_seq_len, batch_size, n_letters)
    data_tensors = pad_sequence(data_tensors, batch_first=False, padding_value=0)

    # 注意：这里把 lengths 也一起返回了！字符串直接原样返回
    return label_tensors, data_tensors, lengths, data_labels, data_items


def get_dataloader(dataset, batch_size=4096, shuffle=False):
    return DataLoader(dataset=dataset,
                      batch_size=batch_size,
                      shuffle=shuffle,
                      collate_fn=collate_fn)