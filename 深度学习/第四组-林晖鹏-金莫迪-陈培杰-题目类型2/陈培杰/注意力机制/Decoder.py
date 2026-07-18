import torch
import torch.nn as nn
import torch.nn.functional as F

class DecoderRNN(nn.Module):
    def __init__(self, hidden_size, output_size, num_layers, MAX_LENGTH):
        super(DecoderRNN, self).__init__()

        self.embedding = nn.Embedding(output_size, hidden_size)
        self.gru = nn.GRU(input_size=hidden_size, hidden_size=hidden_size, num_layers=num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)
        self.MAX_LENGTH = MAX_LENGTH

    def forward(self, encoder_outputs, encoder_hidden, SOS_token, EOS_token, target_tensor=None, mask=None):
        batch_size = encoder_outputs.shape[0]
        device = encoder_hidden.device

        decoder_input = torch.empty(batch_size, 1, dtype=torch.long, device=device).fill_(SOS_token)
        decoder_hidden = encoder_hidden

        decoder_outputs = []

        if target_tensor is not None:
            decode_steps = target_tensor.shape[1]
        else:
            decode_steps = self.MAX_LENGTH

        for i in range(decode_steps):
            decoder_output, decoder_hidden = self.forward_step(decoder_input, decoder_hidden)
            decoder_outputs.append(decoder_output)

            if target_tensor is not None:
                decoder_input = target_tensor[:, i].unsqueeze(1)
            else:
                value, indices = decoder_output.topk(1)
                decoder_input = indices.squeeze(-1).detach()

                if batch_size == 1 and decoder_input.item() == EOS_token:
                    break

        decoder_outputs = torch.cat(decoder_outputs, dim=1)
        return decoder_outputs, decoder_hidden, None

    def forward_step(self, input, hidden):
        embedded = self.embedding(input)
        embedded = F.relu(embedded)
        output, h_n = self.gru(embedded, hidden)
        output = self.fc(output)
        return output, h_n

class BahdanauAttention(nn.Module):
    def __init__(self, hidden_size):
        super(BahdanauAttention, self).__init__()

        self.Wa = nn.Linear(hidden_size, hidden_size)
        self.Ua = nn.Linear(hidden_size, hidden_size)
        self.Va = nn.Linear(hidden_size, 1)

    def forward(self, query, keys, mask=None):
        scores = self.Va(torch.tanh(self.Wa(query) + self.Ua(keys)))

        scores = scores.squeeze(-1)

        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)

        weights = F.softmax(scores, dim=1)
        weights_t = weights.unsqueeze(1)
        context = torch.bmm(weights_t, keys)
        return context, weights_t

class AttnDecoderRNN(nn.Module):
    def __init__(self, hidden_size, output_size, MAXLENGTH, num_layers, dropout=0.1):
        super(AttnDecoderRNN, self).__init__()

        self.embedding = nn.Embedding(output_size, hidden_size)
        self.attention = BahdanauAttention(hidden_size)
        self.gru = nn.GRU(2 * hidden_size, hidden_size, batch_first=True, num_layers=num_layers)
        self.fc = nn.Linear(hidden_size, output_size)
        self.dropout = nn.Dropout(dropout)
        self.MAXLENGTH = MAXLENGTH

    def forward_step(self, input, hidden, encoder_outputs, mask=None):
        embedded = self.embedding(input)
        embedded = self.dropout(embedded)

        query = hidden[-1].unsqueeze(1)

        context, attn_weights = self.attention(query, encoder_outputs, mask)
        input_gru = torch.cat([embedded, context], dim=2)

        output, h_n = self.gru(input_gru, hidden)
        output = self.fc(output)
        return output, h_n, attn_weights

    def forward(self, encoder_outputs, encoder_hidden, SOS_token, EOS_token, target_tensor=None, mask=None):
        batch_size = encoder_outputs.shape[0]
        device = encoder_outputs.device

        decoder_input = torch.empty(batch_size, 1, dtype=torch.long, device=device).fill_(SOS_token)
        decoder_hidden = encoder_hidden

        decoder_outputs = []
        attentions = []

        if target_tensor is not None:
            decoder_steps = target_tensor.shape[1]
        else:
            decoder_steps = self.MAXLENGTH

        for i in range(decoder_steps):
            decoder_output, decoder_hidden, attn_weights = self.forward_step(decoder_input, decoder_hidden, encoder_outputs, mask)
            decoder_outputs.append(decoder_output)
            attentions.append(attn_weights)

            if target_tensor is not None:
                decoder_input = target_tensor[:, i].unsqueeze(1)
            else:
                value, indices = decoder_output.topk(1)
                decoder_input = indices.squeeze(-1).detach()

                if batch_size == 1 and decoder_input.item() == EOS_token:
                    break

        decoder_outputs = torch.cat(decoder_outputs, dim=1)
        attentions = torch.cat(attentions, dim=1)
        return decoder_outputs, decoder_hidden, attentions




