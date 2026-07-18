#!/usr/bin/env python3
"""将原始 Seq2Seq notebook 整理成单个 Python 脚本，便于阅读与运行。"""

from __future__ import unicode_literals, print_function, division

from io import open
import math
from pathlib import Path
import random
import re
import time
import unicodedata

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import optim
from torch.utils.data import DataLoader, RandomSampler, TensorDataset

plt.switch_backend("agg")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "eng-fra.txt"


# ============================================================================
# 一、数据准备
# ============================================================================

SOS_token = 0
EOS_token = 1
MAX_LENGTH = 10

eng_prefixes = (
    "i am ",
    "i m ",
    "he is",
    "he s ",
    "she is",
    "she s ",
    "you are",
    "you re ",
    "we are",
    "we re ",
    "they are",
    "they re ",
)


class Lang:
    """保存词表以及词和编号之间的映射关系。"""

    def __init__(self, name):
        self.name = name
        self.word2index = {}
        self.word2count = {}
        self.index2word = {0: "SOS", 1: "EOS"}
        self.n_words = 2  # 初始只包含 SOS 和 EOS

    def addSentence(self, sentence):
        for word in sentence.split(" "):
            self.addWord(word)

    def addWord(self, word):
        if word not in self.word2index:
            self.word2index[word] = self.n_words
            self.word2count[word] = 1
            self.index2word[self.n_words] = word
            self.n_words += 1
        else:
            self.word2count[word] += 1


def unicodeToAscii(text):
    """把 Unicode 字符串转成普通 ASCII，去掉重音等附加符号。"""
    return "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )


def normalizeString(text):
    """统一做小写化、去噪和简单标点切分。"""
    text = unicodeToAscii(text.lower().strip())
    text = re.sub(r"([.!?])", r" \1", text)
    text = re.sub(r"[^a-zA-Z!?]+", r" ", text)
    return text.strip()


def readLangs(lang1, lang2, reverse=False):
    print("开始读取语料...")

    # 读取平行语料文件，每行是一对翻译句子
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"未找到语料文件: {DATA_PATH}")
    lines = open(DATA_PATH, encoding="utf-8").read().strip().split("\n")

    # 先做标准化，再按制表符切成句对
    pairs = [[normalizeString(s) for s in line.split("\t")] for line in lines]

    # 如果 reverse=True，就把翻译方向从 eng->fra 改成 fra->eng
    if reverse:
        pairs = [list(reversed(pair)) for pair in pairs]
        input_lang = Lang(lang2)
        output_lang = Lang(lang1)
    else:
        input_lang = Lang(lang1)
        output_lang = Lang(lang2)

    return input_lang, output_lang, pairs


def filterPair(pair):
    """只保留较短且目标句满足指定前缀模式的样本。"""
    return (
        len(pair[0].split(" ")) < MAX_LENGTH
        and len(pair[1].split(" ")) < MAX_LENGTH
        and pair[1].startswith(eng_prefixes)
    )


def filterPairs(pairs):
    return [pair for pair in pairs if filterPair(pair)]


def prepareData(lang1, lang2, reverse=False):
    input_lang, output_lang, pairs = readLangs(lang1, lang2, reverse)
    print("原始句对数: %s" % len(pairs))
    pairs = filterPairs(pairs)
    print("过滤后句对数: %s" % len(pairs))
    print("开始统计词表...")

    for pair in pairs:
        input_lang.addSentence(pair[0])
        output_lang.addSentence(pair[1])

    print("词表统计完成:")
    print(input_lang.name, input_lang.n_words)
    print(output_lang.name, output_lang.n_words)
    return input_lang, output_lang, pairs


def indexesFromSentence(lang, sentence):
    return [lang.word2index[word] for word in sentence.split(" ")]


def tensorFromSentence(lang, sentence):
    indexes = indexesFromSentence(lang, sentence)
    indexes.append(EOS_token)
    return torch.tensor(indexes, dtype=torch.long, device=device).view(1, -1)


def tensorsFromPair(pair, input_lang, output_lang):
    input_tensor = tensorFromSentence(input_lang, pair[0])
    target_tensor = tensorFromSentence(output_lang, pair[1])
    return input_tensor, target_tensor


def get_dataloader(batch_size):
    input_lang, output_lang, pairs = prepareData("eng", "fra", True)

    n = len(pairs)
    input_ids = np.zeros((n, MAX_LENGTH), dtype=np.int32)
    target_ids = np.zeros((n, MAX_LENGTH), dtype=np.int32)

    for idx, (inp, tgt) in enumerate(pairs):
        inp_ids = indexesFromSentence(input_lang, inp)
        tgt_ids = indexesFromSentence(output_lang, tgt)
        inp_ids.append(EOS_token)
        tgt_ids.append(EOS_token)
        input_ids[idx, : len(inp_ids)] = inp_ids
        target_ids[idx, : len(tgt_ids)] = tgt_ids

    train_data = TensorDataset(
        torch.LongTensor(input_ids).to(device),
        torch.LongTensor(target_ids).to(device),
    )
    train_sampler = RandomSampler(train_data)
    train_dataloader = DataLoader(train_data, sampler=train_sampler, batch_size=batch_size)
    return input_lang, output_lang, pairs, train_dataloader


# ============================================================================
# 二、模型定义
# ============================================================================

class EncoderRNN(nn.Module):
    """编码器：把输入句子编码成隐藏状态序列和最终隐藏状态。"""

    def __init__(self, input_size, hidden_size, dropout_p=0.1):
        super(EncoderRNN, self).__init__()
        self.hidden_size = hidden_size
        self.embedding = nn.Embedding(input_size, hidden_size)
        self.gru = nn.GRU(hidden_size, hidden_size, batch_first=True)
        self.dropout = nn.Dropout(dropout_p)

    def forward(self, input_tensor):
        embedded = self.dropout(self.embedding(input_tensor))
        output, hidden = self.gru(embedded)
        return output, hidden


class DecoderRNN(nn.Module):
    """不带注意力的基础解码器。"""

    def __init__(self, hidden_size, output_size):
        super(DecoderRNN, self).__init__()
        self.embedding = nn.Embedding(output_size, hidden_size)
        self.gru = nn.GRU(hidden_size, hidden_size, batch_first=True)
        self.out = nn.Linear(hidden_size, output_size)

    def forward(self, encoder_outputs, encoder_hidden, target_tensor=None):
        batch_size = encoder_outputs.size(0)
        decoder_input = torch.empty(batch_size, 1, dtype=torch.long, device=device).fill_(SOS_token)
        decoder_hidden = encoder_hidden
        decoder_outputs = []

        for i in range(MAX_LENGTH):
            decoder_output, decoder_hidden = self.forward_step(decoder_input, decoder_hidden)
            decoder_outputs.append(decoder_output)

            if target_tensor is not None:
                # 训练时使用 teacher forcing：下一个时刻直接喂真实目标词
                decoder_input = target_tensor[:, i].unsqueeze(1)
            else:
                # 推理时使用上一步预测结果作为当前输入
                _, topi = decoder_output.topk(1)
                decoder_input = topi.squeeze(-1).detach()

        decoder_outputs = torch.cat(decoder_outputs, dim=1)
        decoder_outputs = F.log_softmax(decoder_outputs, dim=-1)
        return decoder_outputs, decoder_hidden, None

    def forward_step(self, input_tensor, hidden):
        embedded = self.embedding(input_tensor)
        output, hidden = self.gru(embedded, hidden)
        output = self.out(output)
        return output, hidden


class BahdanauAttention(nn.Module):
    """Bahdanau 加性注意力。"""

    def __init__(self, hidden_size):
        super(BahdanauAttention, self).__init__()
        self.Wa = nn.Linear(hidden_size, hidden_size)
        self.Ua = nn.Linear(hidden_size, hidden_size)
        self.Va = nn.Linear(hidden_size, 1)

    def forward(self, query, keys):
        # query 形状为 [batch, 1, hidden]，keys 形状为 [batch, seq_len, hidden]
        scores = self.Va(torch.tanh(self.Wa(query) + self.Ua(keys)))
        scores = scores.squeeze(2).unsqueeze(1)
        weights = F.softmax(scores, dim=-1)
        context = torch.bmm(weights, keys)
        return context, weights


class AttnDecoderRNN(nn.Module):
    """带注意力机制的解码器。"""

    def __init__(self, hidden_size, output_size, dropout_p=0.1):
        super(AttnDecoderRNN, self).__init__()
        self.embedding = nn.Embedding(output_size, hidden_size)
        self.attention = BahdanauAttention(hidden_size)
        self.gru = nn.GRU(2 * hidden_size, hidden_size, batch_first=True)
        self.out = nn.Linear(hidden_size, output_size)
        self.dropout = nn.Dropout(dropout_p)

    def forward(self, encoder_outputs, encoder_hidden, target_tensor=None):
        batch_size = encoder_outputs.size(0)
        decoder_input = torch.empty(batch_size, 1, dtype=torch.long, device=device).fill_(SOS_token)
        decoder_hidden = encoder_hidden
        decoder_outputs = []
        attentions = []

        for i in range(MAX_LENGTH):
            decoder_output, decoder_hidden, attn_weights = self.forward_step(
                decoder_input,
                decoder_hidden,
                encoder_outputs,
            )
            decoder_outputs.append(decoder_output)
            attentions.append(attn_weights)

            if target_tensor is not None:
                # 训练阶段继续使用 teacher forcing
                decoder_input = target_tensor[:, i].unsqueeze(1)
            else:
                _, topi = decoder_output.topk(1)
                decoder_input = topi.squeeze(-1).detach()

        decoder_outputs = torch.cat(decoder_outputs, dim=1)
        decoder_outputs = F.log_softmax(decoder_outputs, dim=-1)
        attentions = torch.cat(attentions, dim=1)

        return decoder_outputs, decoder_hidden, attentions

    def forward_step(self, input_tensor, hidden, encoder_outputs):
        embedded = self.dropout(self.embedding(input_tensor))
        query = hidden.permute(1, 0, 2)
        context, attn_weights = self.attention(query, encoder_outputs)
        input_gru = torch.cat((embedded, context), dim=2)

        output, hidden = self.gru(input_gru, hidden)
        output = self.out(output)
        return output, hidden, attn_weights


# ============================================================================
# 三、训练流程
# ============================================================================

def train_epoch(dataloader, encoder, decoder, encoder_optimizer, decoder_optimizer, criterion):
    total_loss = 0

    for data in dataloader:
        input_tensor, target_tensor = data

        encoder_optimizer.zero_grad()
        decoder_optimizer.zero_grad()

        encoder_outputs, encoder_hidden = encoder(input_tensor)
        decoder_outputs, _, _ = decoder(encoder_outputs, encoder_hidden, target_tensor)

        loss = criterion(
            decoder_outputs.view(-1, decoder_outputs.size(-1)),
            target_tensor.view(-1),
        )
        loss.backward()

        encoder_optimizer.step()
        decoder_optimizer.step()
        total_loss += loss.item()

    return total_loss / len(dataloader)


def asMinutes(seconds):
    minutes = math.floor(seconds / 60)
    seconds -= minutes * 60
    return "%dm %ds" % (minutes, seconds)


def timeSince(since, percent):
    now = time.time()
    elapsed = now - since
    estimated_total = elapsed / percent
    remaining = estimated_total - elapsed
    return "%s (- %s)" % (asMinutes(elapsed), asMinutes(remaining))


def train(train_dataloader, encoder, decoder, n_epochs, learning_rate=0.001, print_every=100, plot_every=100):
    start = time.time()
    plot_losses = []
    print_loss_total = 0
    plot_loss_total = 0

    encoder_optimizer = optim.Adam(encoder.parameters(), lr=learning_rate)
    decoder_optimizer = optim.Adam(decoder.parameters(), lr=learning_rate)
    criterion = nn.NLLLoss()

    for epoch in range(1, n_epochs + 1):
        loss = train_epoch(
            train_dataloader,
            encoder,
            decoder,
            encoder_optimizer,
            decoder_optimizer,
            criterion,
        )
        print_loss_total += loss
        plot_loss_total += loss

        if epoch % print_every == 0:
            print_loss_avg = print_loss_total / print_every
            print_loss_total = 0
            print(
                "%s (%d %d%%) %.4f"
                % (timeSince(start, epoch / n_epochs), epoch, epoch / n_epochs * 100, print_loss_avg)
            )

        if epoch % plot_every == 0:
            plot_loss_avg = plot_loss_total / plot_every
            plot_losses.append(plot_loss_avg)
            plot_loss_total = 0

    showPlot(plot_losses)


def showPlot(points):
    """绘制训练损失曲线。"""
    plt.figure()
    fig, ax = plt.subplots()
    loc = ticker.MultipleLocator(base=0.2)
    ax.yaxis.set_major_locator(loc)
    plt.plot(points)
    plt.xlabel("记录点")
    plt.ylabel("Loss")
    plt.title("训练损失曲线")
    fig.tight_layout()
    plt.show()


# ============================================================================
# 四、评估与注意力可视化
# ============================================================================

def evaluate(encoder, decoder, sentence, input_lang, output_lang):
    with torch.no_grad():
        input_tensor = tensorFromSentence(input_lang, sentence)
        encoder_outputs, encoder_hidden = encoder(input_tensor)
        decoder_outputs, decoder_hidden, decoder_attn = decoder(encoder_outputs, encoder_hidden)
        del decoder_hidden

        _, topi = decoder_outputs.topk(1)
        decoded_ids = topi.squeeze()

        decoded_words = []
        for idx in decoded_ids:
            if idx.item() == EOS_token:
                decoded_words.append("<EOS>")
                break
            decoded_words.append(output_lang.index2word[idx.item()])

    return decoded_words, decoder_attn


def evaluateRandomly(encoder, decoder, pairs, input_lang, output_lang, n=10):
    for _ in range(n):
        pair = random.choice(pairs)
        print(">", pair[0])
        print("=", pair[1])
        output_words, _ = evaluate(encoder, decoder, pair[0], input_lang, output_lang)
        output_sentence = " ".join(output_words)
        print("<", output_sentence)
        print("")


def showAttention(input_sentence, output_words, attentions):
    """可视化注意力权重矩阵。"""
    fig = plt.figure()
    ax = fig.add_subplot(111)
    cax = ax.matshow(attentions.cpu().numpy(), cmap="bone")
    fig.colorbar(cax)

    # 横轴是输入句子的各个词，纵轴是生成出的目标词
    ax.set_xticklabels([""] + input_sentence.split(" ") + ["<EOS>"], rotation=90)
    ax.set_yticklabels([""] + output_words)

    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    plt.show()


def evaluateAndShowAttention(input_sentence, encoder, decoder, input_lang, output_lang):
    output_words, attentions = evaluate(encoder, decoder, input_sentence, input_lang, output_lang)
    print("input =", input_sentence)
    print("output =", " ".join(output_words))
    showAttention(input_sentence, output_words, attentions[0, : len(output_words), :])


# ============================================================================
# 五、主程序
# ============================================================================

def main():
    hidden_size = 64
    batch_size = 32

    input_lang, output_lang, pairs, train_dataloader = get_dataloader(batch_size)

    encoder = EncoderRNN(input_lang.n_words, hidden_size).to(device)
    decoder = AttnDecoderRNN(hidden_size, output_lang.n_words).to(device)

    train(train_dataloader, encoder, decoder, 2, print_every=1, plot_every=1)

    encoder.eval()
    decoder.eval()
    evaluateRandomly(encoder, decoder, pairs, input_lang, output_lang)

    evaluateAndShowAttention("il n est pas aussi grand que son pere", encoder, decoder, input_lang, output_lang)
    evaluateAndShowAttention("je suis trop fatigue pour conduire", encoder, decoder, input_lang, output_lang)
    evaluateAndShowAttention("je suis desole si c est une question idiote", encoder, decoder, input_lang, output_lang)
    evaluateAndShowAttention("je suis reellement fiere de vous", encoder, decoder, input_lang, output_lang)


if __name__ == "__main__":
    main()
