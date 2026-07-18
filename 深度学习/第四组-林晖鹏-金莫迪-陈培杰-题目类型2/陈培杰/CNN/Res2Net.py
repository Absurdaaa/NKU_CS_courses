import torch
import torch.nn as nn

def ConvBNReLU(in_channels, out_channels, kernel_size, stride=1):
    padding = (kernel_size - 1) // 2
    return nn.Sequential(
            nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=kernel_size, stride=stride, padding=padding, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

def ConvBN(in_channels, out_channels, kernel_size, stride=1):
    padding = (kernel_size - 1) // 2
    return nn.Sequential(
            nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=kernel_size, stride=stride, padding=padding, bias=False),
            nn.BatchNorm2d(out_channels)
        )

class Res2NetBlock(nn.Module):
    expansion = 4
    def __init__(self, in_channels, out_channels, stride=1, basic_width=26, scale=4):
        super(Res2NetBlock, self).__init__()

        # 这里的 out_channels 如果代表最终输出，通常 in_channels -> 中间通道数 -> out_channels
        self.width = int(out_channels * basic_width / 64)
        self.nums = 1 if scale == 1 else scale - 1
        self.scale = scale  # 统一使用 scale 来控制分组数量
        self.stride = stride

        # 1. 1x1 降维
        self.conv1 = ConvBNReLU(in_channels=in_channels, out_channels=self.scale * self.width, kernel_size=1, stride=1)
        # 2. 3x3 卷积组，必须用 ModuleList，并传入真实的 stride
        self.conv2 = nn.ModuleList()
        for i in range(self.nums):
            self.conv2.append(ConvBN(in_channels=self.width, out_channels=self.width, kernel_size=3, stride=stride))
        # 3. 处理降采样时的 xs[0]
        if stride != 1:
            self.pool = nn.AvgPool2d(kernel_size=3, stride=stride, padding=1)
        else:
            self.pool = None
        self.relu1 = nn.ReLU(inplace=True)
        # 4. 1x1 升维
        self.conv3 = ConvBN(in_channels=self.scale * self.width, out_channels=out_channels, kernel_size=1, stride=1)

        shortcut_layers = []
        if stride != 1:
            shortcut_layers.append(nn.AvgPool2d(kernel_size=2, stride=2))
        if in_channels != out_channels or stride != 1:
            shortcut_layers.append(ConvBN(in_channels=in_channels, out_channels=out_channels, kernel_size=1))
        self.shortcut = nn.Sequential(*shortcut_layers)

        self.relu2 = nn.ReLU(inplace=True)
    def forward(self, x):
        identity = x

        out = self.conv1(x)

        xs = torch.split(out, self.width, 1)
        ys = []
        for i in range(self.scale):
            if i == 0:
                if self.pool is not None:
                    ys.append(self.pool(xs[i]))
                else:
                    ys.append(xs[i])
            elif i == 1:
                ys.append(self.conv2[i - 1](xs[i]))
            else:
                if self.stride == 1:
                    ys.append(self.conv2[i - 1](xs[i] + ys[-1]))
                else:
                    ys.append(self.conv2[i - 1](xs[i]))
        out = torch.cat(ys, 1)
        out = self.relu1(out)

        out = self.conv3(out)
        out = out + self.shortcut(identity)
        return self.relu2(out)

class Res2Net(nn.Module):
    def __init__(self, num_classes=10):
        super(Res2Net, self).__init__()

        self.first_conv = ConvBNReLU(in_channels=3, out_channels=64, kernel_size=3, stride=1)
        # [64, 32, 32]
        self.in_channels = 64
        self.layer1 = self._make_layer(out_channels=64, stride=1, num_layers=2)     # [64, 32, 32]
        self.layer2 = self._make_layer(out_channels=128, stride=2, num_layers=3)    # [128, 16, 16]
        self.layer3 = self._make_layer(out_channels=256, stride=2, num_layers=4)    # [256, 8, 8]
        self.layer4 = self._make_layer(out_channels=512, stride=2, num_layers=2)    # [512, 4, 4]

        self.pool = nn.AdaptiveAvgPool2d((1, 1))

        self.fc = nn.Linear(512, num_classes)

    def _make_layer(self, out_channels, stride, num_layers):
        strides = [stride] + [1] * (num_layers - 1)
        layers = []
        for s in strides:
            layers.append(Res2NetBlock(in_channels=self.in_channels, out_channels=out_channels, stride=s))
            self.in_channels = out_channels

        return nn.Sequential(*layers)

    def forward(self, x):
        out = self.first_conv(x)
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        out = self.pool(out)
        out = out.view(out.shape[0], -1)
        out = self.fc(out)
        return out

def get_Res2Net():
    return Res2Net()