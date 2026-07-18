import torch
import torch.nn
from torch.utils.data import Dataset, DataLoader, random_split
from torch.nn.utils.rnn import pad_sequence

import string
import unicodedata
import re
import random

import os
from io import open

SOS_token = 0
EOS_token = 1
PAD_token = 2

class Lang():
    def __init__(self, name):
        self.name = name
        self.word2index = {}
        self.word2count = {}
        self.index2word = {0: "SOS", 1: "EOS", 2: "PAD_token"}
        self.n_words = 3

    def addSentence(self, sentence):
        for word in sentence.split(' '):
            self.addWord(word)

    def addWord(self, word):
        if word not in self.word2index:
            self.word2index[word] = self.n_words
            self.word2count[word] = 1
            self.index2word[self.n_words] = word
            self.n_words += 1
        else:
            self.word2count[word] += 1


def unicodeToAscii(s):
    return ''.join([c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'])

def normalizeString(s):
    s = unicodeToAscii(s.lower().strip())
    s = re.sub(r"([.!?])", r" \1", s)
    s = re.sub(r"[^a-zA-Z!?]+", r" ", s)
    return s.strip()

def readLangs(lang1, lang2, reverse=False):
    print("Reading lines...")

    lines = open(f'data/{lang1}-{lang2}.txt', encoding='utf-8').read().strip().split('\n')

    pairs = [[normalizeString(s) for s in l.split('\t')] for l in lines]

    if reverse:
        pairs = [list(reversed(p)) for p in pairs]
        input_lang = Lang(lang2)
        output_lang = Lang(lang1)
    else:
        input_lang = Lang(lang2)
        output_lang = Lang(lang1)

    return input_lang, output_lang, pairs

def prepareData(lang1, lang2, reverse=False):
    input_lang, output_lang, pairs = readLangs(lang1, lang2, reverse)
    print("Read %s sentence pairs" % len(pairs))
    print("Counting words...")
    MAX_LENGTH = 0
    for pair in pairs:
        input_lang.addSentence(pair[0])
        output_lang.addSentence(pair[1])

        sentence1 = pair[0].split(' ')
        sentence2 = pair[1].split(' ')

        MAX_LENGTH = max(MAX_LENGTH, max(len(sentence1), len(sentence2)))
    print("Counted words:")
    print(input_lang.name, input_lang.n_words)
    print(output_lang.name, output_lang.n_words)

    return input_lang, output_lang, pairs, MAX_LENGTH

def indexesFromSentence(lang, sentence):
    return [lang.word2index[word] for word in sentence.split(' ')]

def tensorFromSentence(lang, sentence):
    indexes = indexesFromSentence(lang, sentence)
    indexes.append(EOS_token)
    return torch.tensor(indexes, dtype=torch.long)

def tensorsFromPair(lang1, lang2, pair):
    input_tensor = tensorFromSentence(lang1, pair[0])
    output_tensor = tensorFromSentence(lang2, pair[1])
    return input_tensor, output_tensor

class LangDataset(Dataset):
    def __init__(self, lang1: Lang, lang2: Lang, pairs):
        super(LangDataset, self).__init__()

        self.input_lang = lang1
        self.output_lang = lang2
        self.pairs = pairs

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        input_tensor, output_tensor = tensorsFromPair(self.input_lang, self.output_lang, self.pairs[idx])
        return input_tensor, output_tensor


def seq2seq_collate_fn(batch):
    # batch 是一个列表，里面包含了 __getitem__ 返回的 (input_tensor, output_tensor)
    input_tensors = [item[0] for item in batch]
    output_tensors = [item[1] for item in batch]

    # 将句子填充到该 batch 的最大长度 (batch_first=True 表示 batch_size 在第 0 维)
    input_padded = pad_sequence(input_tensors, batch_first=True, padding_value=PAD_token)
    output_padded = pad_sequence(output_tensors, batch_first=True, padding_value=PAD_token)

    return input_padded, output_padded

def get_alldata():
    input_lang, output_lang, pairs, MAXLENGTH = prepareData('eng', 'fra', True)
    all_data = LangDataset(input_lang, output_lang, pairs)
    return all_data, MAXLENGTH

def get_train_test_dataset(device, dataset):
    train_dataset, test_dataset = random_split(dataset, [0.9, 0.1], generator=torch.Generator().manual_seed(2026))
    return train_dataset, test_dataset

def get_dataloader(dataset, shuffle=False):
    return DataLoader(dataset, batch_size=256, shuffle=shuffle, collate_fn=seq2seq_collate_fn)


# if __name__ == '__main__':
#     input_lang, output_lang, pairs = prepareData('eng', 'fra', True)
#     print(random.choice(pairs))


