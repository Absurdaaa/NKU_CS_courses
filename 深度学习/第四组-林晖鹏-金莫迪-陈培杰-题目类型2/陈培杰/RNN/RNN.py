import torch
import torch.nn as nn
import  torch.nn.utils.rnn as utils_rnn

from 深度学习手撕系列.RNN.NameDataset import n_letters, NameDataset


class CharRNN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size, num_layers=2):
        super(CharRNN, self).__init__()

        self.rnn = nn.RNN(input_size=input_size, hidden_size=hidden_size, 
                          num_layers=num_layers, batch_first=False)
        self.h2o = nn.Linear(in_features=hidden_size, out_features=output_size)
        
    def forward(self, x, lengths):
        packed = utils_rnn.pack_padded_sequence(x, lengths, batch_first=False, enforce_sorted=False)
        packed_outputs, h_n = self.rnn(packed)

        # h_n shape: (num_layers, batch_size, hidden_size)，取最后一层的隐状态

        outputs, _ = utils_rnn.pad_packed_sequence(packed_outputs, batch_first=False)

        output = self.h2o(h_n[-1])  # shape: (batch_size, output_size)
        if output.dim() == 1:
            output = output.unsqueeze(0)
        return output




