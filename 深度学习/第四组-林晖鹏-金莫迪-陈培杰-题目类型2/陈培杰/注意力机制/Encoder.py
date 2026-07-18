import torch
import torch.nn as nn
import torch.nn.utils.rnn as rnn_utils

class EncoderRNN(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers=1, dropout_p=0.1):
        super(EncoderRNN, self).__init__()

        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(input_size, hidden_size)
        self.gru = nn.GRU(input_size=hidden_size, hidden_size=hidden_size, num_layers=num_layers, batch_first=True)
        self.dropout = nn.Dropout(dropout_p)

    def forward(self, x, lengths):
        embedded = self.dropout(self.embedding(x))

        packed = rnn_utils.pack_padded_sequence(embedded, lengths, batch_first=True, enforce_sorted=False)

        packed_outputs, h_n = self.gru(packed)

        outputs, _ = rnn_utils.pad_packed_sequence(packed_outputs, batch_first=True)
        return outputs, h_n
