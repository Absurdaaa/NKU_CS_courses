import warnings
import torch
from nltk.translate.bleu_score import corpus_bleu

from DataFactory import SOS_token, EOS_token, PAD_token

warnings.filterwarnings('ignore')

def train_model(encoder, decoder, train_loader, en_optimizer, de_optimizer, criterion, device, epochs=30):
    encoder.train()
    decoder.train()

    train_losses = []

    for epoch in range(epochs):
        train_loss = 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)

            mask = (x != PAD_token)
            lengths = mask.sum(dim=1).cpu()

            encoder_outputs, encoder_hidden = encoder(x, lengths)
            decoder_outputs, decoder_hidden, attentions = decoder(encoder_outputs, encoder_hidden, SOS_token, EOS_token, y, mask)

            loss = criterion(decoder_outputs.reshape(-1, decoder_outputs.shape[-1]), y.reshape(-1))

            en_optimizer.zero_grad()
            de_optimizer.zero_grad()
            loss.backward()
            en_optimizer.step()
            de_optimizer.step()

            train_loss += loss.item()

        train_loss /= len(train_loader)
        train_losses.append(train_loss)
        print(f"Epoch:[{epoch + 1}/{epochs}], Loss = {train_loss: .4f}")
    return train_losses


def train_and_validate_model(encoder, decoder, train_loader, validate_loader, en_optimizer, de_optimizer, criterion,
                             device, output_lang, epochs=50):
    train_losses = []
    validate_losses = []
    validate_bleus = []  # 新增：用于记录每个 epoch 的验证集 BLEU

    for epoch in range(epochs):
        # ==================== 训练阶段 ====================
        encoder.train()
        decoder.train()

        train_loss = 0

        for x, y in train_loader:
            x, y = x.to(device), y.to(device)

            mask = (x != PAD_token)
            lengths = mask.sum(dim=1).cpu()

            encoder_outputs, encoder_hidden = encoder(x, lengths)
            decoder_outputs, decoder_hidden, attentions = decoder(encoder_outputs, encoder_hidden, SOS_token, EOS_token,
                                                                  y, mask)

            loss = criterion(decoder_outputs.reshape(-1, decoder_outputs.shape[-1]), y.reshape(-1))

            en_optimizer.zero_grad()
            de_optimizer.zero_grad()

            loss.backward()

            en_optimizer.step()
            de_optimizer.step()

            train_loss += loss.item()

        train_loss /= len(train_loader)
        train_losses.append(train_loss)

        # ==================== 验证阶段 ====================
        encoder.eval()
        decoder.eval()

        validate_loss = 0
        references = []  # 收集当前 epoch 所有真实的参考译文
        hypotheses = []  # 收集当前 epoch 所有模型生成的译文

        with torch.no_grad():
            for x, y in validate_loader:
                x, y = x.to(device), y.to(device)

                mask = (x != PAD_token)
                lengths = mask.sum(dim=1).cpu()

                encoder_outputs, encoder_hidden = encoder(x, lengths)

                # 1. 计算验证 Loss (使用 Teacher Forcing)
                decoder_outputs_loss, _, _ = decoder(
                    encoder_outputs, encoder_hidden, SOS_token, EOS_token, target_tensor=y, mask=mask
                )

                loss = criterion(decoder_outputs_loss.reshape(-1, decoder_outputs_loss.shape[-1]), y.reshape(-1))
                validate_loss += loss.item()

                # 2. 生成文本以计算 BLEU (关闭 Teacher Forcing)
                decoder_outputs_gen, _, _ = decoder(
                    encoder_outputs, encoder_hidden, SOS_token, EOS_token, target_tensor=None, mask=mask
                )

                # 取出生成的最大概率词索引
                _, topi = decoder_outputs_gen.topk(1, dim=-1)
                decoded_ids = topi.squeeze(-1).cpu().numpy()
                target_ids = y.cpu().numpy()

                # 将索引转换为单词，方便 nltk 计算 BLEU
                for b in range(decoded_ids.shape[0]):
                    # 提取预测词
                    pred_words = []
                    for idx in decoded_ids[b]:
                        if idx == EOS_token or idx == PAD_token:
                            break
                        if idx != SOS_token:
                            pred_words.append(output_lang.index2word[idx])

                    # 提取目标词
                    target_words = []
                    for idx in target_ids[b]:
                        if idx == EOS_token or idx == PAD_token:
                            break
                        if idx != SOS_token:
                            target_words.append(output_lang.index2word[idx])

                    references.append([target_words])
                    hypotheses.append(pred_words)

            # 结算当前 Epoch 的验证指标
            validate_loss /= len(validate_loader)
            validate_losses.append(validate_loss)

            # 结算 BLEU 并转换为百分制
            epoch_bleu = corpus_bleu(references, hypotheses) * 100
            validate_bleus.append(epoch_bleu)

        print(
            f"Epoch:[{epoch + 1}/{epochs}], Train_Loss = {train_loss:.4f} | Validate_loss = {validate_loss:.4f} | Validate_BLEU = {epoch_bleu:.2f}")

    return train_losses, validate_losses, validate_bleus

def test_model(encoder, decoder, test_loader, output_lang, device):
    encoder.eval()
    decoder.eval()

    references = []
    hypotheses = []
    all_attentions = []

    with torch.no_grad():
        for x, y in test_loader:
            x, y = x.to(device), y.to(device)

            mask = (x != PAD_token)
            lengths = mask.sum(dim=1).cpu()

            encoder_outputs, encoder_hidden = encoder(x, lengths)
            decoder_output_tuple = decoder(encoder_outputs, encoder_hidden,
                SOS_token, EOS_token, target_tensor=None, mask=mask)
            
            # 处理 decoder 输出，可能包含注意力权重
            if len(decoder_output_tuple) == 3:
                decoder_outputs, decoder_hidden, attentions = decoder_output_tuple
                if attentions is not None:
                    all_attentions.append(attentions)
            else:
                decoder_outputs = decoder_output_tuple[0]

            # 取出概率最大的词的索引：(batch_size, seq_len)
            value, indices = decoder_outputs.topk(1, dim=-1)
            decoded_ids = indices.squeeze(-1).cpu().numpy()
            target_ids = y.cpu().numpy()

            # 将索引转换回单词进行 BLEU 计算
            for b in range(decoded_ids.shape[0]):
                pred_words = []
                for idx in decoded_ids[b]:
                    if idx == EOS_token or idx == PAD_token:
                        break
                    if idx != SOS_token:
                        pred_words.append(output_lang.index2word[idx])

                target_words = []
                for idx in target_ids[b]:
                    if idx == EOS_token or idx == PAD_token:
                        break
                    if idx != SOS_token:
                        target_words.append(output_lang.index2word[idx])

                # nltk bleu 要求 references 是一个列表的列表，因为一个句子可以有多个正确翻译
                references.append([target_words])
                hypotheses.append(pred_words)

    bleu_score = corpus_bleu(references, hypotheses)
    print(f"Test Set BLEU Score: {bleu_score * 100:.2f}")

    # 打印几个样例直观感受下
    print("\n--- Translation Examples ---")
    for i in range(min(3, len(references))):
        print(f"Target : {' '.join(references[i][0])}")
        print(f"Predict: {' '.join(hypotheses[i])}")
        print("-" * 30)

    # 如果有注意力权重，返回第一个 batch 的注意力
    attention_weights = all_attentions[0] if all_attentions else None
    return bleu_score, attention_weights

