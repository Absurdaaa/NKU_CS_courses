import torchvision.datasets as datasets
import torch
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T

def get_dataloader():
    transform = T.Compose(
        [
            T.ToTensor(),
            T.Normalize((0.5, ), (0.5, ))
        ]
    )
    train_dataset = datasets.FashionMNIST('data', train=True, transform=transform, download=True)
    test_dataset = datasets.FashionMNIST('data', train=False, transform=transform, download=True)

    train_loader = DataLoader(train_dataset, batch_size=512, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=512, shuffle=False)

    return train_loader, test_loader