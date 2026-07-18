import torch
import torch.nn as nn

class GRUCell(nn.Module):
    def __init__(self, input_size, hidden_size):
        super(GRUCell, self).__init__()

        self.input_size = input_size
        self.hidden_size = hidden_size

        self.w_z = nn.Parameter(torch.randn(hidden_size, hidden_size + input_size) * 0.01)
        self.w_r = nn.Parameter(torch.randn(hidden_size, hidden_size + input_size) * 0.01)
        self.w_candidate = nn.Parameter(torch.randn(hidden_size, hidden_size + input_size) * 0.01)

        self.b_z = nn.Parameter(torch.randn(hidden_size))
        self.b_r = nn.Parameter(torch.randn(hidden_size))
        self.b_candidate = nn.Parameter(torch.randn(hidden_size))

    def forward(self, x, h_t_1):
        if x.dim() == 1:
            x = x.unsqueeze(0)
        if h_t_1.dim() == 1:
            h_t_1 = h_t_1.unsqueeze(0)

        cat_input = torch.cat([h_t_1, x], dim=-1)

        z = torch.sigmoid(cat_input @ self.w_z.t() + self.b_z)
        r = torch.sigmoid(cat_input @ self.w_r.t() + self.b_r)

        r_m_h = r * h_t_1
        h_candidate = torch.tanh(torch.cat([r_m_h, x], dim=-1) @ self.w_candidate.t() + self.b_candidate)

        h_t = z * h_t_1 + (1 - z) * h_candidate
        return h_t

class GRU(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers=1):
        super(GRU, self).__init__()

        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.cells = nn.ModuleList()

        for i in range(num_layers):
            if i == 0:
                self.cells.append(GRUCell(input_size=input_size, hidden_size=hidden_size))
            else:
                self.cells.append(GRUCell(input_size=hidden_size, hidden_size=hidden_size))

    def forward(self, X, lengths=None):
        if X.dim() == 2:
            X = X.unsqueeze(1)

        seq_len, batch_size, input_size = X.shape

        h_states = [X.new_zeros(batch_size, self.hidden_size) for _ in range(self.num_layers)]

        if lengths is not None:
            mask = torch.arange(seq_len, device=X.device).unsqueeze(1) < lengths.to(X.device).unsqueeze(0)
        else:
            mask = None

        outputs = []

        for t, x in enumerate(X):
            layer_input = x
            for layer in range(self.num_layers):
                gru_cell = self.cells[layer]
                new_h = gru_cell(layer_input, h_states[layer])

                if mask is not None:
                    step_mask = mask[t].unsqueeze(1)
                    h_states[layer] = torch.where(step_mask, new_h, h_states[layer])
                else:
                    h_states[layer] = new_h
                layer_input = h_states[layer]
            outputs.append(layer_input)

        outputs = torch.stack(outputs, dim=0)

        return outputs, torch.stack(h_states)

class CharGRU(nn.Module):
    def __init__(self, input_size, hidden_size, output_size, num_layers):
        super(CharGRU, self).__init__()

        self.gru = GRU(input_size=input_size, hidden_size=hidden_size, num_layers=num_layers)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x, lengths=None):
        outputs, h_n = self.gru(x, lengths)
        out = self.fc(h_n[-1])
        return out


