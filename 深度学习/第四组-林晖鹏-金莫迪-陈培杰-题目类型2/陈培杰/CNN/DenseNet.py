import torch
import torch.nn as nn

class _DenseLayer(nn.Module):
    def __init__(self, in_channels, bn_size, growth_rate, drop_rate):
        super(_DenseLayer, self).__init__()

        self.drop_rate = drop_rate

        self.layers = nn.Sequential(
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels=in_channels, out_channels=bn_size * growth_rate, kernel_size=1, bias=False),
            nn.BatchNorm2d(bn_size * growth_rate),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels=bn_size * growth_rate, out_channels=growth_rate, kernel_size=3, stride=1, padding=1, bias=False)
        )

        self.dropout = nn.Dropout(drop_rate)
    def forward(self, x):
        identity = x
        y = self.layers(x)
        if self.drop_rate > 0:
            y = self.dropout(y)
        return torch.cat([identity, y], 1)

class _DenseBlock(nn.Module):
    def __init__(self, num_layers, num_input_features, bn_size, growth_rate, drop_rate):
        super(_DenseBlock, self).__init__()

        layers = []
        for i in range(num_layers):
            layers.append(_DenseLayer(in_channels=num_input_features + i * growth_rate, bn_size=bn_size, growth_rate=growth_rate, drop_rate=drop_rate))
        self.layers = nn.Sequential(*layers)

    def forward(self, x):
        return self.layers(x)

class _Transition(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(_Transition, self).__init__()

        self.layers = nn.Sequential(
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=1, bias=False),
            nn.AvgPool2d(kernel_size=2, stride=2)
        )

    def forward(self, x):
        return self.layers(x)

class DenseNet(nn.Module):
    def __init__(self, num_input_feature=64, growth_rate=8, bn_size=4, block_config=[6, 12, 32, 32], drop_rate=0, num_classes=10):
        super(DenseNet, self).__init__()

        self.first_conv = nn.Sequential(
            nn.Conv2d(in_channels=3, out_channels=64, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True)
        )

        input_features = num_input_feature
        layers = []
        for i, n in enumerate(block_config):
            layers.append(_DenseBlock(num_layers=n, num_input_features=input_features, bn_size=bn_size, growth_rate=growth_rate, drop_rate=drop_rate))
            input_features += n * growth_rate
            if i != len(block_config) - 1:
                layers.append(_Transition(in_channels=input_features, out_channels=input_features // 2))
                input_features //= 2
        self.layers = nn.Sequential(*layers)

        self.last_stage = nn.Sequential(
            nn.BatchNorm2d(input_features),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1))
        )

        self.classifier = nn.Linear(input_features, num_classes)

    def forward(self, x):
        y = self.first_conv(x)
        y = self.layers(y)
        y = self.last_stage(y)
        y = y.view(y.shape[0], -1)
        return self.classifier(y)

def get_DenseNet():
    return DenseNet()
