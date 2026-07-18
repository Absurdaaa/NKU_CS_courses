import torch
import matplotlib.pyplot as plt
import torchvision.utils as vutils


def show_model_structure(generator, discriminator):
    """要求1：打印生成器和判别器的模型结构"""
    print("========== Generator Structure ==========")
    print(generator)
    print("\n========== Discriminator Structure ==========")
    print(discriminator)


def plot_loss_curve(g_losses, d_losses):
    """要求1：绘制在 FashionMNIST 上的训练 loss 曲线"""
    plt.figure(figsize=(10, 5))
    plt.plot(g_losses, label="Generator Loss (G)")
    plt.plot(d_losses, label="Discriminator Loss (D)")
    plt.title("GAN Training Loss on FashionMNIST")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.grid(True)
    plt.savefig("loss_curve.png")
    plt.show()

def explore_latent_space(generator, device, is_dcgan=False, save_name="latent_space.png"):
    base_z = torch.randn(8, 100).to(device)
    selected_dims = [10, 30, 50, 70, 90]
    adjust_values = [-2.0, 0.0, 2.0]

    generator.eval()
    all_images = []

    with torch.no_grad():
        for dim in selected_dims:
            for val in adjust_values:
                z_modified = base_z.clone()
                z_modified[:, dim] = val
                if is_dcgan:
                    z_modified = z_modified.view(8, 100, 1, 1)
                imgs = generator(z_modified).cpu()
                imgs = (imgs + 1) / 2
                all_images.append(imgs)

    all_images_tensor = torch.cat(all_images, dim=0)
    grid = vutils.make_grid(all_images_tensor, nrow=8, padding=2)

    plt.figure(figsize=(10, 18))
    plt.imshow(grid.permute(1, 2, 0).numpy())
    plt.axis("off")
    plt.title("Latent Space Exploration (15 rows x 8 cols)")
    plt.savefig(save_name)
    plt.close()


def plot_combined_loss_curves(all_g_losses, all_d_losses):
    """
    all_g_losses 和 all_d_losses 是字典格式：
    {'SimpleGAN': [...], 'DCGAN': [...]}
    """
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    # 左子图：Generator Loss
    axes[0].plot(all_g_losses['SimpleGAN'], label='SimpleGAN G-Loss')
    axes[0].plot(all_g_losses['DCGAN'], label='DCGAN G-Loss')
    axes[0].set_title('Generator Loss Comparison')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Loss')
    axes[0].legend()
    axes[0].grid(True)

    # 右子图：Discriminator Loss
    axes[1].plot(all_d_losses['SimpleGAN'], label='SimpleGAN D-Loss')
    axes[1].plot(all_d_losses['DCGAN'], label='DCGAN D-Loss')
    axes[1].set_title('Discriminator Loss Comparison')
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('Loss')
    axes[1].legend()
    axes[1].grid(True)

    plt.tight_layout()
    plt.savefig("combined_loss_curves.png")
    plt.show()


def generate_8_images(generator, device, is_dcgan=False, save_name="8_random_images.png"):
    z = torch.randn(8, 100).to(device)
    if is_dcgan:
        z = z.view(8, 100, 1, 1)

    generator.eval()
    with torch.no_grad():
        fake_images = generator(z).cpu()

    fake_images = (fake_images + 1) / 2
    grid = vutils.make_grid(fake_images, nrow=8, padding=2, normalize=False)

    plt.figure(figsize=(12, 3))
    plt.imshow(grid.permute(1, 2, 0).numpy())
    plt.axis("off")
    plt.title(f"8 Generated Images ({save_name})")
    plt.savefig(save_name)
    plt.close()