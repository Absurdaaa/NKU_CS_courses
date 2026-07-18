import torch
import torch.nn as nn
from NameDataset import n_letters, NameDataset

class LSTMCell(nn.Module):
    def __init__(self, input_size, hidden_size):
        super().__init__()

        self.input_size = input_size
        self.hidden_size = hidden_size
        weight_scale = 0.01

        self.w_f = nn.Parameter(torch.randn(hidden_size, input_size + hidden_size) * weight_scale)
        self.w_i = nn.Parameter(torch.randn(hidden_size, input_size + hidden_size) * weight_scale)
        self.w_c = nn.Parameter(torch.randn(hidden_size, input_size + hidden_size) * weight_scale)
        self.w_o = nn.Parameter(torch.randn(hidden_size, input_size + hidden_size) * weight_scale)

        self.b_f = nn.Parameter(torch.zeros(hidden_size))
        self.b_i = nn.Parameter(torch.zeros(hidden_size))
        self.b_c = nn.Parameter(torch.zeros(hidden_size))
        self.b_o = nn.Parameter(torch.zeros(hidden_size))

    def forward(self, input, h_t_1, c_t_1):
        if input.dim() == 1:
            input = input.unsqueeze(0)
        if h_t_1.dim() == 1:
            h_t_1 = h_t_1.unsqueeze(0)
        if c_t_1.dim() == 1:
            c_t_1 = c_t_1.unsqueeze(0)

        cat_input = torch.cat([h_t_1, input], dim=-1)
        f_t = torch.sigmoid(cat_input @ self.w_f.t() + self.b_f)
        i_t = torch.sigmoid(cat_input @ self.w_i.t() + self.b_i)
        candidate_c = torch.tanh(cat_input @ self.w_c.t() + self.b_c)
        o_t = torch.sigmoid(cat_input @ self.w_o.t() + self.b_o)

        c_t = f_t * c_t_1 + i_t * candidate_c
        h_t = o_t * torch.tanh(c_t)
        return h_t, c_t

class LSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers):
        super().__init__()

        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.cells = nn.ModuleList()
        for i in range(num_layers):
            if i == 0:
                self.cells.append(LSTMCell(input_size=input_size, hidden_size=hidden_size))
            else:
                self.cells.append(LSTMCell(input_size=hidden_size, hidden_size=hidden_size))


    def forward(self, X, lengths=None):
        if X.dim() == 2:
            X = X.unsqueeze(1)

        seq_len, batch_size, input_size = X.shape
        h_states = [X.new_zeros(batch_size, self.hidden_size) for _ in range(self.num_layers)]
        c_states = [X.new_zeros(batch_size, self.hidden_size) for _ in range(self.num_layers)]

        outputs = [] # 用于收集所有时间步的顶层隐藏状态

        if lengths is not None:
            mask = torch.arange(seq_len, device=X.device).unsqueeze(1) < lengths.to(X.device).unsqueeze(0)
        else:
            mask = None

        for t, x, in enumerate(X):
            layer_input = x
            for layer in range(self.num_layers):
                lstm_cell = self.cells[layer]
                new_h, new_c = lstm_cell(layer_input, h_states[layer], c_states[layer])

                if mask is not None:
                    step_mask = mask[t].unsqueeze(1)
                    h_states[layer] = torch.where(step_mask, new_h, h_states[layer])
                    c_states[layer] = torch.where(step_mask, new_c, c_states[layer])
                else:
                    h_states[layer] = new_h
                    c_states[layer] = new_c
                layer_input = h_states[layer]
            outputs.append(layer_input)

        outputs = torch.stack(outputs, dim=0)
        return outputs, (torch.stack(h_states), torch.stack(c_states))


class CharLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, output_size, num_layers):
        super().__init__()
        self.lstm = LSTM(input_size=input_size, hidden_size=hidden_size, num_layers=num_layers)
        self.fc = nn.Linear(hidden_size, output_size)  

    def forward(self, x, lengths=None):
        outputs, (h_n, c_n) = self.lstm(x, lengths)
        # h_n[-1] 就是最后一层在最后时间步的输出
        out = self.fc(h_n[-1])

        if out.dim() == 1:
            out.unsqueeze(0)

        return out



