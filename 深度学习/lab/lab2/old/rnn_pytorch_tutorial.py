#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rnn_pytorch_tutorial 的 Python 导出版。
说明：原 notebook 中的英文 markdown 与主要说明性注释已整理为中文；
变量名、函数名以及 PyTorch API 保持英文，以保证代码可运行。
"""

# RNN 教程：基于字符级循环神经网络进行姓名分类。

# 数据目录 `data/names` 中包含 18 个按语言划分的姓名文本文件。每个文件名对应一种语言，每行一个名字。我们会把它们整理成 “语言 -> 名字列表” 的映射。

from __future__ import unicode_literals, print_function, division
from io import open
import glob
import os

def findFiles(path): return glob.glob(path)

print(findFiles('../data/names/*.txt'))

import unicodedata
import string

all_letters = string.ascii_letters + " .,;'"
n_letters = len(all_letters)

# 把 Unicode 字符串转换成普通 ASCII 字符串
def unicodeToAscii(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
        and c in all_letters
    )

print(unicodeToAscii('Ślusàrski'))

# 构建 `category_lines` 字典，保存每种语言对应的姓名列表
category_lines = {}
all_categories = []

# 读取文件并按行切分
def readLines(filename):
    lines = open(filename, encoding='utf-8').read().strip().split('\n')
    return [unicodeToAscii(line) for line in lines]

for filename in findFiles('../data/names/*.txt'):
    category = os.path.splitext(os.path.basename(filename))[0]
    all_categories.append(category)
    lines = readLines(filename)
    category_lines[category] = lines

n_categories = len(all_categories)

# 现在已经得到 `category_lines`、`all_categories` 和 `n_categories`，分别表示语言到名字列表的映射、语言列表以及类别总数。

print(category_lines['Italian'][:5])

# 将姓名转换为张量：把字符编码成 one-hot 向量，再把整行名字堆叠成序列张量。

import torch

# 根据字符表查找字符索引，例如 "a" 对应 0
def letterToIndex(letter):
    return all_letters.find(letter)

# 演示：把单个字符转换成 `<1 x n_letters>` 张量
def letterToTensor(letter):
    tensor = torch.zeros(1, n_letters)
    tensor[0][letterToIndex(letter)] = 1
    return tensor

# 把一个名字转换成 `<名字长度 x 1 x 字符种类数>` 的张量，
# 也就是由多个 one-hot 字符向量组成的序列
def lineToTensor(line):
    tensor = torch.zeros(len(line), 1, n_letters)
    for li, letter in enumerate(line):
        tensor[li][0][letterToIndex(letter)] = 1
    return tensor

print(letterToTensor('J'))

print(lineToTensor('Jones').size())

# 构建网络：这里实现一个最基础的字符级 RNN，用隐藏状态逐字符处理名字，最终输出语言类别。

# 原 notebook 中此处是一张 RNN 结构示意图，导出为 `.py` 后不再保留图片。

import torch.nn as nn

class RNN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super(RNN, self).__init__()

        self.hidden_size = hidden_size

        self.i2h = nn.Linear(input_size + hidden_size, hidden_size)
        self.i2o = nn.Linear(input_size + hidden_size, output_size)
        self.softmax = nn.LogSoftmax(dim=1)

    def forward(self, input, hidden):
        combined = torch.cat((input, hidden), 1)
        hidden = self.i2h(combined)
        output = self.i2o(combined)
        output = self.softmax(output)
        return output, hidden

    def initHidden(self):
        return torch.zeros(1, self.hidden_size)

n_hidden = 128
rnn = RNN(n_letters, n_hidden, n_categories)

import torch.nn as nn

class LSTM(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super(LSTM, self).__init__()

        self.hidden_size = hidden_size

        self.rnn = nn.LSTM(input_size, hidden_size)
        self.out = nn.Linear(hidden_size, output_size)
        self.softmax = nn.LogSoftmax(dim=-1)

    def forward(self, input, h, c):
#         combined = torch.cat((input, hidden), 1)
        out, (h, c) = self.rnn(input, (h, c))
        output = self.out(out)
        output = self.softmax(output)
        return output, h, c

    def initHidden(self):
        return torch.zeros(1, 1, self.hidden_size), torch.zeros(1, 1, self.hidden_size)

n_hidden = 64
rnn = LSTM(n_letters, n_hidden, n_categories)

# 每一步前向传播都需要当前字符的张量和上一步隐藏状态，输出当前类别分布以及新的隐藏状态。

input = letterToTensor('A')
print(input.size())
hidden = torch.zeros(1, n_hidden)

h, c = rnn.initHidden()
output = rnn(input.unsqueeze(1), h, c)

# 为了提高效率，这里直接使用整行名字张量，再通过切片逐字符送入网络。

input = lineToTensor('Albert')
print(input.size())
hidden = torch.zeros(1, n_hidden)

h, c = rnn.initHidden()
output, h, c = rnn(input, h, c)
print(torch.exp(output))

# 最终输出是一个 `<1 x n_categories>` 的张量，数值越大表示该类别越可能。

# 训练准备：先定义从输出中解码类别、随机采样训练样本等辅助函数。

def categoryFromOutput(output):
    top_n, top_i = output.topk(1)
    category_i = top_i[0].item()
    return all_categories[category_i], category_i

print(categoryFromOutput(output))

# 还需要一个快速获取训练样本的函数，随机返回名字及其所属语言。

import random

def randomChoice(l):
    return l[random.randint(0, len(l) - 1)]

def randomTrainingExample():
    category = randomChoice(all_categories)
    line = randomChoice(category_lines[category])
    category_tensor = torch.tensor([all_categories.index(category)], dtype=torch.long)
    line_tensor = lineToTensor(line)
    return category, line, category_tensor, line_tensor

for i in range(10):
    category, line, category_tensor, line_tensor = randomTrainingExample()
    print('category =', category, '/ line =', line)

# 训练网络：对每个样本逐字符更新隐藏状态，最后用最终输出与真实标签计算损失。

criterion = nn.NLLLoss()

# 一次训练迭代的大致流程包括：准备输入与标签、初始化隐藏状态、逐字符前向传播、计算损失并反向传播。

learning_rate = 0.005 # 学习率过大可能发散，过小则学习过慢

def train(category_tensor, line_tensor):
    h0, c0 = rnn.initHidden()

    rnn.zero_grad()

#     print(line_tensor.size())
#     for i in range(line_tensor.size()[0]):
#         output, hidden = rnn(line_tensor[i], hidden)
    output, h, c = rnn(line_tensor, h0, c0)

    loss = criterion(output[-1], category_tensor)
    loss.backward()

    # 按学习率更新参数
    for p in rnn.parameters():
        p.data.add_(p.grad.data, alpha=-learning_rate)

    return output, loss.item()

# 接下来反复调用训练函数，定期打印当前损失与预测结果，同时记录损失曲线。

import time
import math

n_iters = 300000
print_every = 5000
plot_every = 1000



# 记录损失，便于后续绘图
current_loss = 0
all_losses = []

def timeSince(since):
    now = time.time()
    s = now - since
    m = math.floor(s / 60)
    s -= m * 60
    return '%dm %ds' % (m, s)

start = time.time()

for iter in range(1, n_iters + 1):
    category, line, category_tensor, line_tensor = randomTrainingExample()
    output, loss = train(category_tensor, line_tensor)
    current_loss += loss

    # 打印迭代次数、损失、名字以及预测结果
    if iter % print_every == 0:
        guess, guess_i = categoryFromOutput(output[-1])
        correct = '✓' if guess == category else '✗ (%s)' % category
        print('%d %d%% (%s) %.4f %s / %s %s' % (iter, iter / n_iters * 100, timeSince(start), loss, line, guess, correct))

    # 把当前阶段的平均损失加入历史记录
    if iter % plot_every == 0:
        all_losses.append(current_loss / plot_every)
        current_loss = 0

# 绘制训练结果：使用累计的历史损失观察模型是否在收敛。

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

plt.figure()
plt.plot(all_losses)

# 评估结果：通过混淆矩阵查看各语言之间的分类情况。

# 用混淆矩阵统计各类别的预测情况
confusion = torch.zeros(n_categories, n_categories)
n_confusion = 10000

# 给定一行名字，直接返回模型输出
def evaluate(line_tensor):
    h0, c0 = rnn.initHidden()

#     for i in range(line_tensor.size()[0]):
    output, h, c = rnn(line_tensor, h0, c0)

    return output[-1]

# 遍历一批样本，统计模型的预测结果
for i in range(n_confusion):
    category, line, category_tensor, line_tensor = randomTrainingExample()
    output = evaluate(line_tensor)
    guess, guess_i = categoryFromOutput(output)
    category_i = all_categories.index(category)
    confusion[category_i][guess_i] += 1

# 按行归一化混淆矩阵
for i in range(n_categories):
    confusion[i] = confusion[i] / confusion[i].sum()

# 设置绘图对象
fig = plt.figure()
ax = fig.add_subplot(111)
cax = ax.matshow(confusion.numpy())
fig.colorbar(cax)

# 设置坐标轴
ax.set_xticklabels([''] + all_categories, rotation=90)
ax.set_yticklabels([''] + all_categories)

# 强制每个刻度都显示标签
ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
ax.yaxis.set_major_locator(ticker.MultipleLocator(1))

# sphinx_gallery_thumbnail_number = 2
plt.show()

# 观察混淆矩阵中主对角线之外的亮点，可以发现哪些语言更容易被混淆。

# 支持手动输入姓名并让模型给出预测类别。

import math
import numpy as np

def predict(input_line, n_predictions=3):
    print('\n> %s' % input_line)
    with torch.no_grad():
        output = evaluate(lineToTensor(input_line))

        # 取概率最高的前 N 个类别
        topv, topi = output.topk(n_predictions, 1, True)
        predictions = []

        for i in range(n_predictions):
            value = topv[0][i].item()
            category_index = topi[0][i].item()
            print('(%.2f) %s' % (np.exp(value), all_categories[category_index]))
            predictions.append([value, all_categories[category_index]])

predict('Dovesky')
predict('Jackson')
predict('Hou')
