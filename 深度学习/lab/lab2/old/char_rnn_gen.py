#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
char_rnn_gen 的 Python 导出版。
说明：原 notebook 中的英文 markdown 与主要说明性注释已整理为中文；
变量名、函数名以及 PyTorch API 保持英文，以保证代码可运行。
"""

# 字符级 RNN 姓名生成：根据给定语言类别和起始字母生成名字。

from io import open
import glob
import os
import unicodedata
import string

all_letters = string.ascii_letters + " .,;'-"
n_letters = len(all_letters) + 1 # 额外加一个 EOS 结束标记

def findFiles(path): return glob.glob(path)

# 把 Unicode 字符串转换成普通 ASCII 字符串
def unicodeToAscii(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
        and c in all_letters
    )

# 读取文件并按行切分
def readLines(filename):
    with open(filename, encoding='utf-8') as some_file:
        return [unicodeToAscii(line.strip()) for line in some_file]

# 构建 `category_lines` 字典，保存每个类别对应的名字列表
category_lines = {}
all_categories = []
for filename in findFiles('data/names/*.txt'):
    category = os.path.splitext(os.path.basename(filename))[0]
    all_categories.append(category)
    lines = readLines(filename)
    category_lines[category] = lines

n_categories = len(all_categories)

if n_categories == 0:
    raise RuntimeError('未找到数据。请确认已经下载 data.zip，'
        '并将其解压到当前目录。')

print('# 类别数:', n_categories, all_categories)
print(unicodeToAscii("O'Néàl"))

# 构建网络：在基础 RNN 上加入类别条件信息，使模型能够按语言生成名字。

import torch
import torch.nn as nn

class RNN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super(RNN, self).__init__()
        self.hidden_size = hidden_size
        

    def forward(self, category, input, hidden):
        pass

    def initHidden(self):
        return torch.zeros(1, self.hidden_size)

# 训练部分开始。

import random

# 从列表中随机取一个元素
def randomChoice(l):
    return l[random.randint(0, len(l) - 1)]

# 随机获取一个类别，并在该类别中随机取一个名字
def randomTrainingPair():
    category = randomChoice(all_categories)
    line = randomChoice(category_lines[category])
    return category, line

# 在每个时间步，网络输入类别、当前字符和隐藏状态，输出下一个字符及新的隐藏状态。

# 把类别转换成 one-hot 向量
def categoryTensor(category):
    li = all_categories.index(category)
    tensor = torch.zeros(1, n_categories)
    tensor[0][li] = 1
    return tensor

# 把输入名字转换成 one-hot 矩阵（不包含结束标记 EOS）
def inputTensor(line):
    tensor = torch.zeros(len(line), 1, n_letters)
    for li in range(len(line)):
        letter = line[li]
        tensor[li][0][all_letters.find(letter)] = 1
    return tensor

# 目标序列使用 LongTensor 表示：从第二个字符一直到 EOS
def targetTensor(line):
    letter_indexes = [all_letters.find(line[li]) for li in range(1, len(line))]
    letter_indexes.append(n_letters - 1) # EOS 结束标记
    return torch.LongTensor(letter_indexes)

# 为了方便训练，这里定义一个随机样本函数，直接返回训练所需的张量。

# 根据随机的类别与名字构造类别、输入和目标张量
def randomTrainingExample():
    category, line = randomTrainingPair()
    category_tensor = categoryTensor(category)
    input_line_tensor = inputTensor(line)
    target_line_tensor = targetTensor(line)
    return category_tensor, input_line_tensor, target_line_tensor

# 训练网络：在名字生成任务中，每个时间步都要预测下一个字符，因此每一步都会产生损失。

criterion = nn.NLLLoss()

learning_rate = 0.0005

def train(category_tensor, input_line_tensor, target_line_tensor):
    target_line_tensor.unsqueeze_(-1)
    hidden = rnn.initHidden()

    rnn.zero_grad()

    loss = torch.Tensor([0]) # 这里也可以直接写成 `loss = 0`

    for i in range(input_line_tensor.size(0)):
        output, hidden = rnn(category_tensor, input_line_tensor[i], hidden)
        l = criterion(output, target_line_tensor[i])
        loss += l

    loss.backward()

    for p in rnn.parameters():
        p.data.add_(p.grad.data, alpha=-learning_rate)

    return output, loss.item() / input_line_tensor.size(0)

# 为了统计训练耗时，这里定义一个辅助函数把秒数转换成人类可读的字符串。

import time
import math

def timeSince(since):
    now = time.time()
    s = now - since
    m = math.floor(s / 60)
    s -= m * 60
    return '%dm %ds' % (m, s)

# 训练流程与常规神经网络类似：反复调用训练函数，并周期性打印损失。

rnn = RNN(n_letters, 128, n_letters)

n_iters = 100000
print_every = 5000
plot_every = 500
all_losses = []
total_loss = 0 # 每经过 `plot_every` 次迭代后重置

start = time.time()

for iter in range(1, n_iters + 1):
    output, loss = train(*randomTrainingExample())
    total_loss += loss

    if iter % print_every == 0:
        print('%s (%d %d%%) %.4f' % (timeSince(start), iter, iter / n_iters * 100, loss))

    if iter % plot_every == 0:
        all_losses.append(total_loss / plot_every)
        total_loss = 0

# 绘制损失曲线以观察模型的学习过程。

import matplotlib.pyplot as plt

plt.figure()
plt.plot(all_losses)

# 采样生成：给定类别和起始字母，重复预测下一个字符直到生成结束标记。

max_length = 20

# 按给定类别和起始字母进行一次采样
def sample(category, start_letter='A'):
    with torch.no_grad():  # 采样阶段不需要跟踪梯度历史
        category_tensor = categoryTensor(category)
        input = inputTensor(start_letter)
        hidden = rnn.initHidden()

        output_name = start_letter

        for i in range(max_length):
            output, hidden = rnn(category_tensor, input[0], hidden)
            topv, topi = output.topk(1)
            topi = topi[0][0]
            if topi == n_letters - 1:
                break
            else:
                letter = all_letters[topi]
                output_name += letter
            input = inputTensor(letter)

        return output_name

# 针对同一类别和多个起始字母生成多个样本
def samples(category, start_letters='ABC'):
    for start_letter in start_letters:
        print(sample(category, start_letter))

samples('Russian', 'RUS')

samples('German', 'GER')

samples('Spanish', 'SPA')

samples('Chinese', 'CHI')
