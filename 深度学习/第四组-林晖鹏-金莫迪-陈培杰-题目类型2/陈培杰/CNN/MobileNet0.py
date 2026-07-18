import torch
import torch.nn as nn

def BottleNeck(in_channels, out_channels, stride):
    return nn.Sequential(
        nn.Conv2d(in_channels=in_channels, out_channels=in_channels, kernel_size=3, stride=stride, padding=1, bias=False, groups=in_channels),
        nn.BatchNorm2d(in_channels),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=1, stride=1, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True)
    )

class MobileNet(nn.Module):
    def __init__(self, num_classes=10):
        super(MobileNet, self).__init__()

        self.first_conv = nn.Sequential(
            nn.Conv2d(in_channels=3, out_channels=32, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True)
        )

        bn_config = [
            # in_channels, out_channels, stride
            [32, 64, 1],
            [64, 128, 2],
            [128, 128, 1],
            [128, 256, 2],
            [256, 256, 1],
            [256, 512, 2],
            [512, 512, 1],  # 连续 5 个不改变 size 的 512 通道 block
            [512, 512, 1],
            [512, 512, 1],
            [512, 512, 1],
            [512, 512, 1],
            [512, 1024, 2],
            [1024, 1024, 1]
        ]
        layers = []
        for in_channels, out_channels, stride in bn_config:
            layers.append(BottleNeck(in_channels, out_channels, stride))
        self.bottlenecks = nn.Sequential(*layers)

        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(1024, num_classes)
        self.drop_out = nn.Dropout(0.2)

        self.init_param()

    def init_param(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            if isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x):
        y = self.first_conv(x)
        y = self.bottlenecks(y)
        y = self.avg_pool(y)
        y = y.view(y.shape[0], -1)
        y = self.drop_out(y)
        y = self.fc(y)
        return y

def get_MobileNet():
    return MobileNet()
