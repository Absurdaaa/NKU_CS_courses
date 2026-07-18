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


class CharRNNGenerator(nn.Module):
    def __init__(self, input_size, hidden_size, output_size, category_size, dropout_p=0.1):
        super(CharRNNGenerator, self).__init__()
        self.hidden_size = hidden_size

        combined_size = category_size + input_size + hidden_size
        self.i2h = nn.Linear(combined_size, hidden_size)
        self.i2o = nn.Linear(combined_size, output_size)
        self.o2o = nn.Linear(hidden_size + output_size, output_size)
        self.dropout = nn.Dropout(dropout_p)
        self.softmax = nn.LogSoftmax(dim=1)

    def forward(self, category, input, hidden):
        combined = torch.cat((category, input, hidden), 1)
        hidden = self.i2h(combined)
        output = self.i2o(combined)
        output = self.o2o(torch.cat((hidden, output), 1))
        output = self.dropout(output)
        output = self.softmax(output)
        return output, hidden

    def initHidden(self, device=None):
        if device is None:
            device = next(self.parameters()).device
        return torch.zeros(1, self.hidden_size, device=device)




