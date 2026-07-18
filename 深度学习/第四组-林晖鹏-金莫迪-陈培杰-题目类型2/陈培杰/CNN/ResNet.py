import torch
import torch.nn as nn

class BasicBlock(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1):
        super(BasicBlock, self).__init__()

        self.convs = nn.Sequential(
            nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=3, stride=stride, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels=out_channels,out_channels=out_channels, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(out_channels)
        )

        shortcut_layers = []
        if stride != 1:
            shortcut_layers.append(nn.AvgPool2d(kernel_size=2, stride=2))
        if in_channels != out_channels or stride != 1:
            shortcut_layers.append(nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=1, bias=False))
            shortcut_layers.append(nn.BatchNorm2d(out_channels))
        self.shortcut = nn.Sequential(*shortcut_layers)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        identity = x
        y = self.convs(x)
        y = y + self.shortcut(identity)
        y = self.relu(y)
        return y

class ResNet1(nn.Module):
    def __init__(self, ResBlock, num_classes=10):
        super(ResNet1, self).__init__()

        self.first_conv = nn.Sequential(
            nn.Conv2d(in_channels=3, out_channels=64, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True)
        )
        self.in_channels = 64

        self.layer1 = self._make_layer(out_channels=64, block=ResBlock, num_blocks=2, stride=1)     # 64 * 32 * 32
        self.layer2 = self._make_layer(out_channels=128, block=ResBlock, num_blocks=3, stride=2)    # 128 * 16 * 16
        self.layer3 = self._make_layer(out_channels=256, block=ResBlock, num_blocks=4, stride=2)    # 256 * 8 * 8
        self.layer4 = self._make_layer(out_channels=512, block=ResBlock, num_blocks=2, stride=2)    # 512 * 4 * 4

        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))

        self.classifier = nn.Linear(512, num_classes)

    def forward(self, x):
        out = self.first_conv(x)
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        out = self.avg_pool(out)
        out = out.view(out.shape[0], -1)
        out = self.classifier(out)
        return out

    def _make_layer(self, out_channels, block, num_blocks, stride):
        strides = [stride] + [1] * (num_blocks - 1)

        layers = []
        for s in strides:
            layers.append(block(in_channels=self.in_channels, out_channels=out_channels, stride=s))
            self.in_channels = out_channels
        return nn.Sequential(*layers)

def get_ResNet1():
    return ResNet1(BasicBlock)
