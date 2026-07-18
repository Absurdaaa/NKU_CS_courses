import os
from io import open

import matplotlib.pyplot as plt
import seaborn as sns
import torch
from nltk.translate.bleu_score import corpus_bleu

from DataFactory import EOS_token, PAD_token, SOS_token, prepareData, normalizeString
from Decoder import AttnDecoderRNN, DecoderRNN
from Encoder import EncoderRNN

device = torch.device('cuda' if torch.cuda.is_available() else "cpu")

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "models")
RESULTS_DIR = os.path.join(BASE_DIR, "test_results")

def read_lines():
    fra_dir = os.path.join(DATA_DIR, "fra.txt")
    eng_dir = os.path.join(DATA_DIR, "eng.txt")

    fra_raw_lines = open(fra_dir, encoding='utf-8').read().strip().split('\n')
    eng_raw_lines = open(eng_dir, encoding='utf-8').read().strip().split('\n')

    fra_lines = [normalizeString(s) for s in fra_raw_lines]
    eng_lines = [normalizeString(s) for s in eng_raw_lines]

    return fra_raw_lines, eng_raw_lines, fra_lines, eng_lines

def read_model(input_size, output_size, max_length):
    encoder_base_dir = os.path.join(MODEL_DIR, "encoder_base_final.pth")
    encoder_attn_dir = os.path.join(MODEL_DIR, "encoder_attn_final.pth")

    decoder_base_dir = os.path.join(MODEL_DIR, "decoder_base_final.pth")
    decoder_attn_dir = os.path.join(MODEL_DIR, "decoder_attn_final.pth")

    encoder_base = EncoderRNN(input_size=input_size, hidden_size=128)
    encoder_attn = EncoderRNN(input_size=input_size, hidden_size=128)

    decoder_base = DecoderRNN(hidden_size=128, output_size=output_size, num_layers=1, MAX_LENGTH=max_length)
    decoder_attn = AttnDecoderRNN(hidden_size=128, output_size=output_size, num_layers=1, MAXLENGTH=max_length)

    encoder_base.load_state_dict(torch.load(encoder_base_dir, map_location=device, weights_only=True))
    encoder_attn.load_state_dict(torch.load(encoder_attn_dir, map_location=device, weights_only=True))
    decoder_base.load_state_dict(torch.load(decoder_base_dir, map_location=device, weights_only=True))
    decoder_attn.load_state_dict(torch.load(decoder_attn_dir, map_location=device, weights_only=True))

    return encoder_base.to(device), encoder_attn.to(device), decoder_base.to(device), decoder_attn.to(device)


def sentence_to_tensor(lang, sentence):
    tokens = [word for word in sentence.split(' ') if word in lang.word2index]
    indexes = [lang.word2index[word] for word in tokens]
    indexes.append(EOS_token)
    return torch.tensor(indexes, dtype=torch.long), tokens


def translate_sentence(encoder, decoder, sentence, input_lang, output_lang):
    sentence = normalizeString(sentence)
    input_tensor, input_tokens = sentence_to_tensor(input_lang, sentence)
    input_tensor = input_tensor.unsqueeze(0).to(device)

    mask = (input_tensor != PAD_token)
    lengths = mask.sum(dim=1).cpu()

    with torch.no_grad():
        encoder_outputs, encoder_hidden = encoder(input_tensor, lengths)
        decoder_output_tuple = decoder(
            encoder_outputs, encoder_hidden, SOS_token, EOS_token, target_tensor=None, mask=mask
        )

    decoder_outputs = decoder_output_tuple[0]
    attentions = decoder_output_tuple[2] if len(decoder_output_tuple) > 2 else None

    _, topi = decoder_outputs.topk(1, dim=-1)
    decoded_ids = topi.squeeze(-1).squeeze(0).tolist()

    output_words = []
    for idx in decoded_ids:
        if idx == EOS_token or idx == PAD_token:
            break
        if idx != SOS_token:
            output_words.append(output_lang.index2word.get(idx, ""))
    output_words = [w for w in output_words if w]

    return input_tokens, output_words, attentions


def save_attention_heatmap(attentions, input_tokens, output_tokens, file_path):
    if attentions is None:
        return

    attention = attentions[0].cpu().detach().numpy()
    enc_len = attention.shape[1]
    dec_len = attention.shape[0]

    enc_labels = input_tokens + ["EOS"]
    if len(enc_labels) != enc_len:
        enc_labels = [str(i) for i in range(enc_len)]

    if dec_len == len(output_tokens) + 1:
        dec_labels = output_tokens + ["EOS"]
    elif dec_len == len(output_tokens):
        dec_labels = output_tokens
    else:
        dec_labels = [str(i) for i in range(dec_len)]

    fig_width = max(8.0, enc_len * 0.6)
    fig_height = max(6.0, dec_len * 0.6)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    sns.heatmap(attention, cmap='viridis', cbar=True, ax=ax, xticklabels=enc_labels, yticklabels=dec_labels)
    ax.set_xlabel('Encoder Tokens')
    ax.set_ylabel('Decoder Tokens')
    ax.set_title('Attention Heatmap')

    fig.tight_layout()
    plt.savefig(file_path, dpi=300)
    plt.close(fig)


def evaluate_model(encoder, decoder, input_lang, output_lang, fra_lines, eng_lines, save_attn=False):
    encoder.eval()
    decoder.eval()

    references = []
    hypotheses = []
    translations = []

    for i, (fra_line, eng_line) in enumerate(zip(fra_lines, eng_lines)):
        input_tokens, output_words, attentions = translate_sentence(
            encoder, decoder, fra_line, input_lang, output_lang
        )

        ref_tokens = eng_line.split(' ')
        references.append([ref_tokens])
        hypotheses.append(output_words)

        translations.append((fra_line, eng_line, output_words))

        if save_attn and i < 10:
            file_path = os.path.join(RESULTS_DIR, f"attention_{i + 1:02d}.png")
            save_attention_heatmap(attentions, input_tokens, output_words, file_path)

    bleu_score = corpus_bleu(references, hypotheses) * 100
    return bleu_score, translations

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.chdir(BASE_DIR)

    input_lang, output_lang, _, max_length = prepareData('eng', 'fra', True)
    input_size = input_lang.n_words
    output_size = output_lang.n_words

    encoder_base, encoder_attn, decoder_base, decoder_attn = read_model(input_size, output_size, max_length)

    fra_raw_lines, eng_raw_lines, fra_lines, eng_lines = read_lines()

    bleu_base, base_translations = evaluate_model(
        encoder_base, decoder_base, input_lang, output_lang, fra_lines, eng_lines, save_attn=False
    )
    bleu_attn, attn_translations = evaluate_model(
        encoder_attn, decoder_attn, input_lang, output_lang, fra_lines, eng_lines, save_attn=True
    )

    bleu_path = os.path.join(RESULTS_DIR, "bleu_scores.txt")
    with open(bleu_path, 'w', encoding='utf-8') as f:
        f.write("Test BLEU Scores\n")
        f.write("================\n")
        f.write(f"Base RNN BLEU: {bleu_base:.2f}\n")
        f.write(f"Attention RNN BLEU: {bleu_attn:.2f}\n")

    translation_path = os.path.join(RESULTS_DIR, "translations.txt")
    with open(translation_path, 'w', encoding='utf-8') as f:
        for i, (fra_norm, eng_norm, base_pred) in enumerate(base_translations):
            attn_pred = attn_translations[i][2]
            f.write(f"Sentence {i + 1}\n")
            f.write("----------------\n")
            f.write(f"FR (raw): {fra_raw_lines[i]}\n")
            f.write(f"EN (raw): {eng_raw_lines[i]}\n")
            f.write(f"FR (norm): {fra_norm}\n")
            f.write(f"EN (norm): {eng_norm}\n")
            f.write(f"Base RNN: {' '.join(base_pred)}\n")
            f.write(f"Attention RNN: {' '.join(attn_pred)}\n\n")

    print(f"BLEU scores saved to {bleu_path}")
    print(f"Translations saved to {translation_path}")
    print(f"Attention heatmaps saved to {RESULTS_DIR}")


if __name__ == '__main__':
    main()




