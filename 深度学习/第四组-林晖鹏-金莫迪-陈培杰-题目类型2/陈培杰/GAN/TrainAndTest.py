import os

import torch
import torch.nn
from torchvision.utils import make_grid, save_image

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def get_latent_noise(batch_size, is_dcgan=False):
    if is_dcgan:
        return torch.randn(batch_size, 100, 1, 1)
    return torch.randn(batch_size, 100)

def train_model(generator, discriminator, train_loader, optimizer_g, optimizer_d, criterion,
                epochs=100, is_dcgan=False, save_dir="evolution_progress", save_tag=None):
    g_losses = []
    d_losses = []

    generator.train()
    discriminator.train()

    # 固定噪声：用于单张图像的演变过程追踪
    fixed_noise = get_latent_noise(1, is_dcgan=is_dcgan).to(device)
    evolution_imgs = []
    save_root = save_dir
    if save_tag:
        save_root = os.path.join(save_root, str(save_tag))
    os.makedirs(save_root, exist_ok=True)

    for epoch in range(epochs):
        epoch_g_loss = 0
        epoch_d_loss = 0
        for x, y in train_loader:
            batch_size = x.shape[0]
            x, y = x.to(device), y.to(device)

            # 先train D
            D_x = discriminator(x)
            lab_real = torch.zeros_like(D_x)
            lossD_real = criterion(D_x, lab_real)

            z = get_latent_noise(batch_size, is_dcgan=is_dcgan).to(device)
            x_gen = generator(z).detach()
            D_G_z = discriminator(x_gen)
            lab_fake = torch.ones_like(D_G_z)
            lossD_fake = criterion(D_G_z, lab_fake)

            lossD = lossD_real + lossD_fake
            optimizer_d.zero_grad()
            lossD.backward()
            optimizer_d.step()

            # 再 train G

            z = get_latent_noise(batch_size, is_dcgan=is_dcgan).to(device)
            x_gen = generator(z)
            D_G_z = discriminator(x_gen)
            lab_real_for_g = torch.zeros_like(D_G_z)
            lossG = criterion(D_G_z, lab_real_for_g)

            optimizer_g.zero_grad()
            lossG.backward()
            optimizer_g.step()

            epoch_d_loss += lossD.item()
            epoch_g_loss += lossG.item()

        epoch_g_loss /= len(train_loader)
        epoch_d_loss /= len(train_loader)
        g_losses.append(epoch_g_loss)
        d_losses.append(epoch_d_loss)

        # 固定噪声评估：每个 Epoch 结束缓存一张图像
        generator.eval()
        with torch.no_grad():
            fixed_imgs = generator(fixed_noise)
        # 反归一化到 [0, 1]
        fixed_imgs = (fixed_imgs + 1) / 2.0
        fixed_imgs = fixed_imgs.clamp(0, 1)
        evolution_imgs.append(fixed_imgs[0].detach().cpu())
        save_path = os.path.join(save_root, f"epoch_{epoch + 1:03d}.png")
        save_image(fixed_imgs, save_path)
        generator.train()

        print(f"Epoch [{epoch+1}/{epochs}]  Loss D: {epoch_d_loss:.4f}, Loss G: {epoch_g_loss:.4f}")

    # 将所有 epoch 的图像横向拼接保存
    if evolution_imgs:
        grid = make_grid(torch.stack(evolution_imgs, dim=0), nrow=len(evolution_imgs), padding=2)
        save_path = os.path.join(save_root, "evolution_progress.png")
        save_image(grid, save_path)

    return g_losses, d_losses

