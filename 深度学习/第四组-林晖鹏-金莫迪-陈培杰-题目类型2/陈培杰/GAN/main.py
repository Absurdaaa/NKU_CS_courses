import torch
import torch.nn as nn
import torch.optim as optim

from Datafactory import get_dataloader
from GAN import SimpleGenerator, SimpleDiscriminator, DCGenerator, DCDiscriminator
from TrainAndTest import train_model

# 注意：这里导入了新加的 plot_combined_loss_curves
from utils_vis import show_model_structure, plot_combined_loss_curves, generate_8_images, explore_latent_space

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def get_simpleGAN():
    return SimpleGenerator(), SimpleDiscriminator()


def get_DCGAN():
    return DCGenerator(), DCDiscriminator()


def main():
    train_loader, test_loader = get_dataloader()

    # 配置模型字典：Key为名称，Value为 (模型实例化函数, is_dcgan标志)
    models_config = {
        'SimpleGAN': (get_simpleGAN, False),
        'DCGAN': (get_DCGAN, True)
    }

    # 用于统一存储 Loss 数据的字典
    all_g_losses = {}
    all_d_losses = {}

    # 开始循环训练每一个模型
    for model_name, (get_model_fn, is_dcgan_flag) in models_config.items():
        print(f"\n{'=' * 20} 开始训练 {model_name} {'=' * 20}")

        generator, discriminator = get_model_fn()
        generator = generator.to(device)
        discriminator = discriminator.to(device)

        # 打印当前网络结构
        show_model_structure(generator, discriminator)

        # 为当前模型重新初始化优化器
        optimizer_g = optim.Adam(generator.parameters(), lr=0.0002, betas=(0.5, 0.999))
        optimizer_d = optim.Adam(discriminator.parameters(), lr=0.0002, betas=(0.5, 0.999))
        criterion = nn.BCEWithLogitsLoss()

        # 训练过程 (为了测试可以先把 epochs 调小，比如 5)
        g_losses, d_losses = train_model(generator, discriminator, train_loader, optimizer_g, optimizer_d, criterion,
                 epochs=60, is_dcgan=is_dcgan_flag, save_tag=model_name)

        # 将当前模型的 loss 保存到外层字典中
        all_g_losses[model_name] = g_losses
        all_d_losses[model_name] = d_losses

        # ================================
        # 保存模型权重到本地
        # ================================
        torch.save(generator.state_dict(), f"{model_name}_generator.pth")
        torch.save(discriminator.state_dict(), f"{model_name}_discriminator.pth")
        print(f" {model_name} 的模型权重已成功保存！")

        # 为当前模型生成图片（传入动态的文件名，避免后一个模型覆盖前一个）
        generate_8_images(generator, device, is_dcgan=is_dcgan_flag, save_name=f"{model_name}_8_images.png")
        explore_latent_space(generator, device, is_dcgan=is_dcgan_flag, save_name=f"{model_name}_latent_space.png")

    # 当循环结束，两个模型都训练完了，开始画对比图
    print("\n正在生成并保存并列 Loss 曲线图...")
    plot_combined_loss_curves(all_g_losses, all_d_losses)
    print(" 所有任务执行完毕！")


if __name__ == '__main__':
    main()