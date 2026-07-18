import torch
import torch.nn as nn
import torch.optim as optim

from DataFactory import get_alldata, get_dataloader, get_train_test_dataset, prepareData, PAD_token
from Encoder import EncoderRNN
from Decoder import DecoderRNN, AttnDecoderRNN

# 导入你之前写好的三个核心函数
from TrainAndTest import train_and_validate_model, train_model, test_model
import Plot


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using {device}")

    # ==========================================
    # 1. 准备数据
    # ==========================================
    print("Loading Data...")
    all_data, MAXLENGTH = get_alldata()
    input_lang, output_lang, _, _ = prepareData('eng', 'fra', True)
    input_size = input_lang.n_words
    output_size = output_lang.n_words

    # train_dataset 包含 80% 的数据，test_dataset 包含 20%
    train_dataset, test_dataset = get_train_test_dataset(device, all_data)

    # 将 train_dataset 再切分为 80% 的 train_small_dataset 和 20% 的 validate_dataset
    train_small_dataset, validate_dataset = get_train_test_dataset(device, train_dataset)

    # 获取对应的 Loader
    train_loader = get_dataloader(train_dataset, shuffle=True)  # 全量训练集 Loader
    train_small_loader = get_dataloader(train_small_dataset, shuffle=True)  # 切分后的训练集 Loader
    validate_loader = get_dataloader(validate_dataset)  # 验证集 Loader
    test_loader = get_dataloader(test_dataset)  # 最终测试集 Loader

    # 定义超参数
    epochs = 30
    learning_rate = 0.001
    criterion = nn.CrossEntropyLoss(ignore_index=PAD_token)

    # ==========================================
    # 阶段一：实验评估 (Train + Evaluate)
    # 目的：绘制 Loss 和 BLEU 的曲线，观察模型收敛趋势
    # ==========================================
    print("\n" + "=" * 50)
    print(" 阶段一：Train + Evaluate (用于绘制评估曲线)")
    print("=" * 50)

    # 1.1 初始化用于验证的模型
    encoder_base_val = EncoderRNN(input_size=input_size, hidden_size=128, num_layers=1, dropout_p=0.1).to(device)
    decoder_base_val = DecoderRNN(hidden_size=128, output_size=output_size, num_layers=1, MAX_LENGTH=MAXLENGTH).to(
        device)

    encoder_attn_val = EncoderRNN(input_size=input_size, hidden_size=128, num_layers=1, dropout_p=0.1).to(device)
    decoder_attn_val = AttnDecoderRNN(hidden_size=128, output_size=output_size, num_layers=1, MAXLENGTH=MAXLENGTH).to(
        device)

    # 1.2 验证 Base 模型
    print("\n[验证阶段] 训练 Base RNN...")
    en_opt_base_val = optim.Adam(encoder_base_val.parameters(), lr=learning_rate)
    de_opt_base_val = optim.Adam(decoder_base_val.parameters(), lr=learning_rate)
    train_loss_base, val_loss_base, val_bleu_base = train_and_validate_model(
        encoder_base_val, decoder_base_val, train_small_loader, validate_loader,
        en_opt_base_val, de_opt_base_val, criterion, device, output_lang=output_lang, epochs=epochs
    )

    # 1.3 验证 Attention 模型
    print("\n[验证阶段] 训练 Attention RNN...")
    en_opt_attn_val = optim.Adam(encoder_attn_val.parameters(), lr=learning_rate)
    de_opt_attn_val = optim.Adam(decoder_attn_val.parameters(), lr=learning_rate)
    train_loss_attn, val_loss_attn, val_bleu_attn = train_and_validate_model(
        encoder_attn_val, decoder_attn_val, train_small_loader, validate_loader,
        en_opt_attn_val, de_opt_attn_val, criterion, device, output_lang=output_lang,epochs=epochs
    )

    # ==========================================
    # 阶段二：全量重训 + 测试 (Train on Full + Test)
    # 目的：利用全部训练数据逼出模型极限性能，在 Test 集打分
    # ==========================================
    print("\n" + "=" * 50)
    print(" 阶段二：全量训练集重训 + 最终测试集评分")
    print("=" * 50)

    # 2.1 重新初始化一组全新的模型（极其重要，避免数据穿越）
    encoder_base_final = EncoderRNN(input_size=input_size, hidden_size=128, num_layers=1, dropout_p=0.1).to(device)
    decoder_base_final = DecoderRNN(hidden_size=128, output_size=output_size, num_layers=1, MAX_LENGTH=MAXLENGTH).to(
        device)

    encoder_attn_final = EncoderRNN(input_size=input_size, hidden_size=128, num_layers=1, dropout_p=0.1).to(device)
    decoder_attn_final = AttnDecoderRNN(hidden_size=128, output_size=output_size, num_layers=1, MAXLENGTH=MAXLENGTH).to(
        device)

    # 2.2 全量训练并测试 Base 模型
    print("\n[最终阶段] 在全量 Train Dataset 上训练 Base RNN...")
    en_opt_base_final = optim.Adam(encoder_base_final.parameters(), lr=learning_rate)
    de_opt_base_final = optim.Adam(decoder_base_final.parameters(), lr=learning_rate)
    # 调用只有 train 功能的函数，传入 train_loader (全量数据)
    train_model(encoder_base_final, decoder_base_final, train_loader, en_opt_base_final, de_opt_base_final, criterion,
                device, epochs=40)

    print("\n测试最终版 Base RNN...")
    test_bleu_base, attn_base = test_model(encoder_base_final, decoder_base_final, test_loader, output_lang, device)

    # 2.3 全量训练并测试 Attention 模型
    print("\n[最终阶段] 在全量 Train Dataset 上训练 Attention RNN...")
    en_opt_attn_final = optim.Adam(encoder_attn_final.parameters(), lr=learning_rate)
    de_opt_attn_final = optim.Adam(decoder_attn_final.parameters(), lr=learning_rate)
    train_model(encoder_attn_final, decoder_attn_final, train_loader, en_opt_attn_final, de_opt_attn_final, criterion,
                device, epochs=40)

    print("\n测试最终版 Attention RNN...")
    test_bleu_attn, attn_attn = test_model(encoder_attn_final, decoder_attn_final, test_loader, output_lang, device)

    # ==========================================
    # 阶段三：图表可视化与结果保存
    # ==========================================
    print("\n========== 开始生成并保存实验报告图表 ==========")

    # 画图用的是阶段一（验证阶段）产生的数据
    Plot.plot_models_comparison(
        train_loss_base, val_loss_base, val_bleu_base,
        train_loss_attn, val_loss_attn, val_bleu_attn,
        name1="Base RNN", name2="Attention RNN"
    )

    Plot.plot_single_model_metrics(train_loss_base, val_loss_base, val_bleu_base, "Base RNN")
    Plot.plot_single_model_metrics(train_loss_attn, val_loss_attn, val_bleu_attn, "Attention RNN")

    # 保存测试分数用的是阶段二（全量重训）产生的数据
    Plot.save_test_bleu("Base RNN", test_bleu_base, "Attention RNN", test_bleu_attn)

    # 绘制注意力权重热力图（仅对 Attention 模型）
    if attn_attn is not None:
        Plot.plot_attention_heatmap(attn_attn, "Attention RNN")

    # ==========================================
    # 阶段四：保存模型
    # ==========================================
    print("\n========== 保存训练好的模型 ==========")
    
    import os
    models_dir = 'models'
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
    
    # 保存 Base 模型
    torch.save(encoder_base_final.state_dict(), f'{models_dir}/encoder_base_final.pth')
    torch.save(decoder_base_final.state_dict(), f'{models_dir}/decoder_base_final.pth')
    print(f"Base RNN 模型已保存至 {models_dir}/encoder_base_final.pth 和 {models_dir}/decoder_base_final.pth")
    
    # 保存 Attention 模型
    torch.save(encoder_attn_final.state_dict(), f'{models_dir}/encoder_attn_final.pth')
    torch.save(decoder_attn_final.state_dict(), f'{models_dir}/decoder_attn_final.pth')
    print(f"Attention RNN 模型已保存至 {models_dir}/encoder_attn_final.pth 和 {models_dir}/decoder_attn_final.pth")



if __name__ == '__main__':
    main()