import torch
import torch.nn as nn

class SimpleNet(nn.Module):
    def __init__(self, num_classes=10):
        super(SimpleNet, self).__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 6, 5), # 4, 6, 28, 28
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(6, 16, 5),
            nn.ReLU(),
            nn.MaxPool2d(2, 2)
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(16 * 5 * 5, 120),
            nn.ReLU(),
            nn.Linear(120, 84),
            nn.ReLU(),
            nn.Linear(84, num_classes)
        )
    def forward(self, x):
        x = self.encoder(x)
        x = self.fc(x)
        return x

def ConvBNReLU(in_channels, out_channels, kernel_size, stride=1):
    padding = (kernel_size - 1) // 2

    return nn.Sequential(
        nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=kernel_size, stride=stride, padding=padding, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True)
    )

class CustomNet(nn.Module):
    def __init__(self, num_classes=10):
        super(CustomNet, self).__init__()

        self.first_conv = ConvBNReLU(in_channels=3, out_channels=32, kernel_size=3)
        # [32, 32, 32]
        self.layer1 = nn.Sequential(
            ConvBNReLU(in_channels=32, out_channels=64, kernel_size=5),
            ConvBNReLU(in_channels=64, out_channels=64, kernel_size=3),
            ConvBNReLU(in_channels=64, out_channels=64, kernel_size=3),
            ConvBNReLU(64, 64, 3),
            ConvBNReLU(64, 64, 3),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )
        # [64, 16, 16]
        self.layer2 = nn.Sequential(
            ConvBNReLU(64, 128, 3),
            ConvBNReLU(128, 128, 3),
            ConvBNReLU(128, 128, 3),
            ConvBNReLU(128, 128, 3),
            ConvBNReLU(128, 128, 3),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )
        # [128, 8, 8]
        self.layer3 = nn.Sequential(
            ConvBNReLU(128, 256, 3),
            ConvBNReLU(256, 256, 3),
            ConvBNReLU(256, 256, 3),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )
        # [256, 4, 4]
        self.layer4 = nn.Sequential(
            ConvBNReLU(256, 512, 5),
            ConvBNReLU(512, 512, 3)
        )
        # [512, 4, 4]

        self.last_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(512, num_classes)

    def forward(self, x):
        y = self.first_conv(x)
        y = self.layer1(y)
        y = self.layer2(y)
        y = self.layer3(y)
        y = self.layer4(y)
        y = self.last_pool(y)
        y = y.view(y.shape[0], -1)
        y = self.fc(y)
        return y


def get_SimpleNet():
    return SimpleNet()

def get_CustomNet():
    return CustomNet()



