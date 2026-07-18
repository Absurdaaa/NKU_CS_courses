import torch
import torch.nn as nn

class SimpleDiscriminator(nn.Module):
    def __init__(self, input_dim=28 * 28):
        super(SimpleDiscriminator, self).__init__()

        self.fc1 = nn.Linear(input_dim, 128)
        self.lrelu1 = nn.LeakyReLU(0.2)
        self.fc2 = nn.Linear(128, 1)

    def forward(self, x):
        x = x.view(x.shape[0], -1)
        out = self.fc1(x)
        out = self.lrelu1(out)
        out = self.fc2(out)
        return out

class SimpleGenerator(nn.Module):
    def __init__(self, z_dim=100):
        super(SimpleGenerator, self).__init__()

        self.fc1 = nn.Linear(z_dim, 128)
        self.lrelu1 = nn.LeakyReLU(0.2)
        self.fc2 = nn.Linear(128, 28 * 28)

    def forward(self, x):
        out = self.fc1(x)
        out = self.lrelu1(out)
        out = self.fc2(out)
        out = torch.tanh(out)
        out = out.view(out.shape[0], 1, 28, 28)
        return out


class DCDiscriminator(nn.Module):
    def __init__(self):
        super(DCDiscriminator, self).__init__()

        # 1 * 28 * 28
        self.first_conv = nn.Sequential(
            nn.Conv2d(in_channels=1, out_channels=32, kernel_size=4, stride=2, padding=1, bias=False),
            nn.LeakyReLU(0.2, inplace=True)
        )
        # 32 * 14 * 14
        self.blocks = nn.Sequential(
            self._block(in_channels=32, out_channels=64, kernel_size=4, stride=2, padding=1),    # 64 * 7 * 7
            self._block(in_channels=64, out_channels=128, kernel_size=3, stride=2, padding=1),   # 128 * 4 * 4
        )
        self.last_stage = nn.Sequential(
            nn.Conv2d(in_channels=128, out_channels=1, kernel_size=4, stride=1, padding=0, bias=False)
        )

    def _block(self, in_channels, out_channels, kernel_size, stride, padding):
        return nn.Sequential(
            nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=kernel_size, stride=stride, padding=padding, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.LeakyReLU(0.2)
        )

    def forward(self, x):
        out = self.first_conv(x)
        out = self.blocks(out)
        out = self.last_stage(out)
        return out

class DCGenerator(nn.Module):
    def __init__(self, z_dim=100):
        super(DCGenerator, self).__init__()

        # 100 * 1 * 1
        self.blocks = nn.Sequential(
            self._block(in_channels=z_dim, out_channels=256, kernel_size=4, stride=1, padding=0, out_padding=0),    # 256 * 4 * 4
            self._block(in_channels=256, out_channels=128, kernel_size=3, stride=2, padding=1, out_padding=0),  # 128 * 7 * 7
            self._block(in_channels=128, out_channels=64, kernel_size=4, stride=2, padding=1, out_padding=0),   # 64 * 14 * 14
        )

        self.last_stage = nn.Sequential(
            nn.ConvTranspose2d(in_channels=64, out_channels=1, kernel_size=4, stride=2, padding=1, output_padding=0, bias=False),   # 1 * 28 * 28
            nn.Tanh()
        )

    def _block(self, in_channels, out_channels, kernel_size, stride, padding, out_padding):
        return nn.Sequential(
            nn.ConvTranspose2d(in_channels=in_channels, out_channels=out_channels, kernel_size=kernel_size, stride=stride,
                               padding=padding, output_padding=out_padding, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        out = self.blocks(x)
        out = self.last_stage(out)
        return out

