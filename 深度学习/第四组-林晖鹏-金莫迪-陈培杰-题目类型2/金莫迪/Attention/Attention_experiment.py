from __future__ import annotations

import csv
import copy
import random
import re
import unicodedata
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, random_split

try:
    from tqdm.auto import tqdm
except Exception:
    tqdm = None

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data"
OUT = ROOT / "Attention" / "results"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED = 2026


def loop(x, **kwargs):
    return tqdm(x, **kwargs) if tqdm is not None else x


def ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def normalize_sentence(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFD", text.lower().strip()) if unicodedata.category(c) != "Mn")
    text = re.sub(r"([.!?])", r" \1", text)
    text = re.sub(r"[^a-z.!?]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_translation_pairs() -> list[tuple[str, str]]:
    path = DATA_ROOT / "eng-fra.txt"
    if not path.exists():
        raise RuntimeError(f"translation data not found: {path}")
    prefixes = ("i am ", "i m ", "he is ", "he s ", "she is ", "she s ", "you are ", "you re ", "we are ", "we re ", "it is ", "it s ")
    pairs = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        eng = normalize_sentence(parts[0])
        fra = normalize_sentence(parts[1])
        if len(eng.split()) < 8 and len(fra.split()) < 8 and eng.startswith(prefixes):
            pairs.append((fra, eng))
    if not pairs:
        raise RuntimeError("no translation pairs after filtering")
    return pairs


class Vocab:
    def __init__(self, sentences):
        words = sorted(set(w for s in sentences for w in s.split()))
        self.word2idx = {"SOS": 0, "EOS": 1, "PAD": 2}
        for w in words:
            self.word2idx[w] = len(self.word2idx)
        self.idx2word = {v: k for k, v in self.word2idx.items()}

    def encode(self, sentence, max_len):
        ids = [self.word2idx[w] for w in sentence.split()] + [1]
        ids = ids[:max_len]
        return ids + [2] * (max_len - len(ids))

    def decode(self, ids):
        words = []
        for idx in ids:
            word = self.idx2word.get(int(idx), "?")
            if word == "EOS":
                break
            if word not in {"SOS", "PAD"}:
                words.append(word)
        return " ".join(words)


class TranslationDataset(Dataset):
    def __init__(self, pairs, max_len=8):
        self.pairs = pairs
        self.max_len = max_len
        self.src_vocab = Vocab([p[0] for p in pairs])
        self.tgt_vocab = Vocab([p[1] for p in pairs])

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        src, tgt = self.pairs[idx]
        return (
            torch.tensor(self.src_vocab.encode(src, self.max_len), dtype=torch.long),
            torch.tensor(self.tgt_vocab.encode(tgt, self.max_len), dtype=torch.long),
            src,
            tgt,
        )


class Encoder(nn.Module):
    def __init__(self, vocab_size, hidden=128):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden, padding_idx=2)
        self.gru = nn.GRU(hidden, hidden, batch_first=True)

    def forward(self, src):
        return self.gru(self.embedding(src))


class PlainDecoder(nn.Module):
    def __init__(self, vocab_size, hidden=128):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden, padding_idx=2)
        self.gru = nn.GRU(hidden, hidden, batch_first=True)
        self.fc = nn.Linear(hidden, vocab_size)

    def forward(self, tgt_in, encoder_outputs, hidden):
        out, h = self.gru(self.embedding(tgt_in), hidden)
        return self.fc(out), h, None


class AttentionDecoder(nn.Module):
    def __init__(self, vocab_size, hidden=128):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden, padding_idx=2)
        self.attn = nn.Linear(hidden * 2, 1)
        self.gru = nn.GRU(hidden * 2, hidden, batch_first=True)
        self.fc = nn.Linear(hidden, vocab_size)

    def forward(self, tgt_in, encoder_outputs, hidden):
        emb = self.embedding(tgt_in)
        outputs, attentions = [], []
        h = hidden
        for t in range(tgt_in.size(1)):
            query = h[-1].unsqueeze(1).expand(-1, encoder_outputs.size(1), -1)
            weights = F.softmax(self.attn(torch.cat([query, encoder_outputs], dim=-1)).squeeze(-1), dim=-1)
            context = torch.bmm(weights.unsqueeze(1), encoder_outputs)
            out, h = self.gru(torch.cat([emb[:, t : t + 1], context], dim=-1), h)
            outputs.append(self.fc(out))
            attentions.append(weights.unsqueeze(1))
        return torch.cat(outputs, dim=1), h, torch.cat(attentions, dim=1)


class Seq2Seq(nn.Module):
    def __init__(self, src_vocab, tgt_vocab, attention=False, hidden=128):
        super().__init__()
        self.encoder = Encoder(src_vocab, hidden)
        self.decoder = AttentionDecoder(tgt_vocab, hidden) if attention else PlainDecoder(tgt_vocab, hidden)

    def forward(self, src, tgt):
        enc_out, h = self.encoder(src)
        decoder_in = torch.cat([torch.zeros(tgt.size(0), 1, dtype=torch.long, device=tgt.device), tgt[:, :-1]], dim=1)
        return self.decoder(decoder_in, enc_out, h)


@torch.no_grad()
def eval_loss(model, loader):
    model.eval()
    total_loss = total = 0
    for src, tgt, _, _ in loader:
        src, tgt = src.to(DEVICE), tgt.to(DEVICE)
        logits, _, _ = model(src, tgt)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), tgt.reshape(-1), ignore_index=2)
        total_loss += loss.item()
        total += 1
    return total_loss / max(total, 1)


def train_model(model, train_loader, val_loader, epochs=150, patience=10):
    model.to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    best_loss, bad_epochs = float("inf"), 0
    best_state = copy.deepcopy(model.state_dict())
    rows = []
    for epoch in loop(range(1, epochs + 1), desc=model.__class__.__name__, unit="epoch"):
        model.train()
        total_loss = total = 0
        for src, tgt, _, _ in loop(train_loader, desc=f"epoch {epoch}/{epochs}", leave=False):
            src, tgt = src.to(DEVICE), tgt.to(DEVICE)
            opt.zero_grad(set_to_none=True)
            logits, _, _ = model(src, tgt)
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), tgt.reshape(-1), ignore_index=2)
            loss.backward()
            opt.step()
            total_loss += loss.item()
            total += 1
        train_loss = total_loss / max(total, 1)
        val_loss = eval_loss(model, val_loader)
        if val_loss < best_loss - 1e-4:
            best_loss, bad_epochs, best_state = val_loss, 0, copy.deepcopy(model.state_dict())
        else:
            bad_epochs += 1
        early_stop = bad_epochs >= patience
        if epoch == 1 or epoch % 10 == 0 or early_stop:
            rows.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss, "best_val_loss": best_loss, "early_stop": early_stop})
        if early_stop:
            break
    model.load_state_dict(best_state)
    return rows


@torch.no_grad()
def translate(model, src_sentence: str, dataset: TranslationDataset):
    model.eval()
    src = torch.tensor([dataset.src_vocab.encode(src_sentence, dataset.max_len)], device=DEVICE)
    enc_out, h = model.encoder(src)
    inp = torch.tensor([[0]], device=DEVICE)
    preds, attn_rows = [], []
    for _ in range(dataset.max_len):
        logits, h, attn = model.decoder(inp, enc_out, h)
        token = logits[:, -1].argmax(-1)
        preds.append(token.item())
        if attn is not None:
            attn_rows.append(attn[:, -1].cpu())
        inp = token.view(1, 1)
        if token.item() == 1:
            break
    attention = torch.cat(attn_rows, dim=0).numpy().tolist() if attn_rows else []
    return dataset.tgt_vocab.decode(preds), attention


def main() -> None:
    random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    ensure(OUT)
    pairs = load_translation_pairs()
    dataset = TranslationDataset(pairs)
    val_len = max(1, int(len(dataset) * 0.1))
    train_len = len(dataset) - val_len
    train_ds, val_ds = random_split(dataset, [train_len, val_len], generator=torch.Generator().manual_seed(SEED))
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)
    rows_all, translations = [], []
    summary = [f"device: {DEVICE}", f"pairs: {len(pairs)}", f"train_pairs: {train_len}", f"val_pairs: {val_len}", "epochs: 150", "early_stopping: patience=10", ""]
    for name, use_attention in [("PlainSeq2Seq", False), ("AttentionSeq2Seq", True)]:
        model = Seq2Seq(len(dataset.src_vocab.word2idx), len(dataset.tgt_vocab.word2idx), attention=use_attention)
        rows = train_model(model, train_loader, val_loader)
        write_csv(OUT / f"{name}_metrics.csv", [{"model": name, **r} for r in rows])
        rows_all.extend({"model": name, **r} for r in rows)
        summary.extend([f"===== {name} =====", str(model), ""])
        for src, tgt in pairs[:8]:
            pred, attn = translate(model, src, dataset)
            translations.append({"model": name, "source": src, "target": tgt, "prediction": pred})
            if name == "AttentionSeq2Seq" and src == pairs[0][0]:
                write_csv(OUT / "attention_heatmap_matrix.csv", [{"target_step": i, **{f"src_{j}": v for j, v in enumerate(row)}} for i, row in enumerate(attn)])
                (OUT / "attention_heatmap_labels.txt").write_text(f"source: {src}\nprediction: {pred}\n", encoding="utf-8")
    write_csv(OUT / "seq2seq_metrics.csv", rows_all)
    write_csv(OUT / "translation_examples.csv", translations)
    (OUT / "network_structures.txt").write_text("\n".join(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
