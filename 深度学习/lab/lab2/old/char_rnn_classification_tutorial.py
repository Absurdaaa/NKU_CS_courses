#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
char_rnn_classification_tutorial 的 Python 导出版。
说明：原 notebook 中的英文 markdown 与主要说明性注释已整理为中文；
变量名、函数名以及 PyTorch API 保持英文，以保证代码可运行。
"""

# 字符级 RNN 姓名分类：使用字符序列判断名字所属的语言类别。

# 准备 PyTorch 运行环境，并根据设备情况选择 CPU 或 CUDA。

import torch

# 检查 CUDA 是否可用
device = torch.device('cpu')
if torch.cuda.is_available():
    device = torch.device('cuda')

print('使用的 PyTorch 版本:', torch.__version__, '设备:', device)

# 准备数据：读取 `data/names` 目录中的多语言姓名文件，并做统一字符处理。

import string
import unicodedata

# 使用 "_" 表示词表外字符，也就是模型未显式处理的字符
allowed_characters = string.ascii_letters + " .,;'" + "_"
n_letters = len(allowed_characters)

# 把 Unicode 字符串转换成普通 ASCII 字符串
def unicodeToAscii(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
        and c in allowed_characters
    )

# 本节为原 notebook 的说明文字，这里已整理为 Python 脚本中的中文注释。

print (f"converting 'Ślusàrski' to {unicodeToAscii('Ślusàrski')}")

# 将姓名转换为张量：字符先转成 one-hot，再组合成名字序列张量。

# 根据字符表查找字符索引，例如 "a" 对应 0
def letterToIndex(letter):
    # 如果遇到未知字符，则返回词表外字符的索引
    if letter not in allowed_characters:
        return allowed_characters.find("_")
    else:
        return allowed_characters.find(letter)

# 把一个名字转换成 `<名字长度 x 1 x 字符种类数>` 的张量，
# 也就是由多个 one-hot 字符向量组成的序列
def lineToTensor(line):
    tensor = torch.zeros(len(line), 1, n_letters)
    for li, letter in enumerate(line):
        tensor[li][0][letterToIndex(letter)] = 1
    return tensor

# 下面给出 `lineToTensor()` 在单字符和多字符字符串上的使用示例。

print (f"字符 'a' 会被转换为 {lineToTensor('a')}") #注意张量中的第一个位置被置为 1
print (f"名字 'Ahn' 会被转换为 {lineToTensor('Ahn')}") #注意字符 A 会把对应索引位置置为 1

# 到这里已经完成文本到张量的基础表示，接下来需要把样本整理成 Dataset 以便训练、验证和测试。

from io import open
import glob
import os
import time

import torch
from torch.utils.data import Dataset

class NamesDataset(Dataset):

    def __init__(self, data_dir):
        self.data_dir = data_dir #for provenance of the dataset
        self.load_time = time.localtime #for provenance of the dataset
        labels_set = set() #set of all classes

        self.data = []
        self.data_tensors = []
        self.labels = []
        self.labels_tensors = []

        #read all the ``.txt`` files in the specified directory
        text_files = glob.glob(os.path.join(data_dir, '*.txt'))
        for filename in text_files:
            label = os.path.splitext(os.path.basename(filename))[0]
            labels_set.add(label)
            lines = open(filename, encoding='utf-8').read().strip().split('\n')
            for name in lines:
                self.data.append(name)
                self.data_tensors.append(lineToTensor(name))
                self.labels.append(label)

        #Cache the tensor representation of the labels
        self.labels_uniq = list(labels_set)
        for idx in range(len(self.labels)):
            temp_tensor = torch.tensor([self.labels_uniq.index(self.labels[idx])], dtype=torch.long)
            self.labels_tensors.append(temp_tensor)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        data_item = self.data[idx]
        data_label = self.labels[idx]
        data_tensor = self.data_tensors[idx]
        label_tensor = self.labels_tensors[idx]

        return label_tensor, data_tensor, data_label, data_item

# 在这里把姓名数据加载到 `NamesDataset` 中。

alldata = NamesDataset("data/names")
print(f"已加载 {len(alldata)} 条样本")
print(f"示例样本 = {alldata[0]}")

# 借助 Dataset 可以很方便地把数据划分为训练集和测试集。

train_set, test_set = torch.utils.data.random_split(alldata, [.85, .15], generator=torch.Generator(device=device).manual_seed(2024))

print(f"训练样本数 = {len(train_set)}, 验证样本数 = {len(test_set)}")

# 现在已经得到一个基础数据集，并完成了训练/测试划分。

# 构建网络：这里实现字符级分类 RNN。

import torch.nn as nn
import torch.nn.functional as F

class CharRNN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super(CharRNN, self).__init__()

        self.rnn = nn.RNN(input_size, hidden_size)
        self.h2o = nn.Linear(hidden_size, output_size)
        self.softmax = nn.LogSoftmax(dim=1)

    def forward(self, line_tensor):
        rnn_out, hidden = self.rnn(line_tensor)
        output = self.h2o(hidden[0])
        output = self.softmax(output)

        return output

# 创建 RNN 后，可以指定输入维度、隐藏层维度和输出类别数。

n_hidden = 128
rnn = CharRNN(n_letters, n_hidden, len(alldata.labels_uniq))
print(rnn)

# 接下来把姓名张量送入网络，并通过辅助函数把输出解码成文本标签。

def label_from_output(output, output_labels):
    top_n, top_i = output.topk(1)
    label_i = top_i[0].item()
    return output_labels[label_i], label_i

input = lineToTensor('Albert')
output = rnn(input) #this is equivalent to ``output = rnn.forward(input)``
print(output)
print(label_from_output(output, alldata.labels_uniq))

# 训练部分开始。

# 定义训练函数，使用小批量样本执行前向传播、反向传播和参数更新。

import random
import numpy as np

def train(rnn, training_data, n_epoch = 10, n_batch_size = 64, report_every = 50, learning_rate = 0.2, criterion = nn.NLLLoss()):
    """
    在给定训练数据上按小批量训练若干轮，并按设定间隔汇报损失。
    """
    # 记录损失，便于后续绘图
    current_loss = 0
    all_losses = []
    rnn.train()
    optimizer = torch.optim.SGD(rnn.parameters(), lr=learning_rate)

    start = time.time()
    print(f"训练数据集大小 = {len(training_data)}")

    for iter in range(1, n_epoch + 1):
        rnn.zero_grad() # 清空梯度

        # 构造若干个小批量
        # 由于名字长度不同，这里没有直接使用标准 dataloader 批处理张量
        batches = list(range(len(training_data)))
        random.shuffle(batches)
        batches = np.array_split(batches, len(batches) //n_batch_size )

        for idx, batch in enumerate(batches):
            batch_loss = 0
            for i in batch: # 遍历当前小批量中的每个样本
                (label_tensor, text_tensor, label, text) = training_data[i]
                output = rnn.forward(text_tensor)
                loss = criterion(output, label_tensor)
                batch_loss += loss

            # 更新参数
            batch_loss.backward()
            nn.utils.clip_grad_norm_(rnn.parameters(), 3)
            optimizer.step()
            optimizer.zero_grad()

            current_loss += batch_loss.item() / len(batch)

        all_losses.append(current_loss / len(batches) )
        if iter % report_every == 0:
            print(f"{iter} ({iter / n_epoch:.0%}): \t 当前平均批损失 = {all_losses[-1]}")
        current_loss = 0

    return all_losses

# 现在可以按指定轮数和批大小训练模型。

start = time.time()
all_losses = train(rnn, train_set, n_epoch=27, learning_rate=0.15, report_every=5)
end = time.time()
print(f"训练耗时 {end-start}s")

# 绘制结果：观察历史损失曲线。

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

plt.figure()
plt.plot(all_losses)
plt.show()

# 评估结果：通过混淆矩阵查看各类别的预测情况。

def evaluate(rnn, testing_data, classes):
    confusion = torch.zeros(len(classes), len(classes))

    rnn.eval() #set to eval mode
    with torch.no_grad(): # 评估阶段不记录梯度
        for i in range(len(testing_data)):
            (label_tensor, text_tensor, label, text) = testing_data[i]
            output = rnn(text_tensor)
            guess, guess_i = label_from_output(output, classes)
            label_i = classes.index(label)
            confusion[label_i][guess_i] += 1

    # 按行归一化混淆矩阵
    for i in range(len(classes)):
        denom = confusion[i].sum()
        if denom > 0:
            confusion[i] = confusion[i] / denom

    # 设置绘图对象
    fig = plt.figure()
    ax = fig.add_subplot(111)
    cax = ax.matshow(confusion.cpu().numpy()) #numpy uses cpu here so we need to use a cpu version
    fig.colorbar(cax)

    # 设置坐标轴
    ax.set_xticks(np.arange(len(classes)), labels=classes, rotation=90)
    ax.set_yticks(np.arange(len(classes)), labels=classes)

    # 强制每个刻度都显示标签
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))

    # 原 notebook 中用于文档缩略图控制，这里保留为普通注释
    plt.show()



evaluate(rnn, test_set, classes=alldata.labels_uniq)

# 从混淆矩阵的非主对角区域可以看出模型容易混淆的语言。

# 练习与拓展：可以尝试更大的网络、不同超参数，或者替换成 LSTM、GRU。
