from __future__ import annotations

import csv
import copy
import random
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
OUT = ROOT / "RNN" / "results"
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


def confusion_matrix(y_true: list[int], y_pred: list[int], n_classes: int) -> list[list[int]]:
    mat = [[0] * n_classes for _ in range(n_classes)]
    for t, p in zip(y_true, y_pred):
        mat[t][p] += 1
    return mat


def save_confusion(path: Path, mat: list[list[int]], labels: list[str]) -> None:
    rows = []
    for i, row in enumerate(mat):
        item = {"label": labels[i]}
        item.update({labels[j]: v for j, v in enumerate(row)})
        rows.append(item)
    write_csv(path, rows)


class NameDataset(Dataset):
    def __init__(self, data_dir: Path | None = None):
        data_dir = data_dir or DATA_ROOT / "names"
        data: dict[str, list[str]] = {}
        for file in sorted(data_dir.glob("*.txt")):
            names = [line.strip() for line in file.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
            if names:
                data[file.stem] = names
        if not data:
            raise RuntimeError(f"name data not found: {data_dir}")
        self.labels = sorted(data)
        chars = sorted(set("".join(name.lower() for names in data.values() for name in names)))
        self.char2idx = {c: i + 1 for i, c in enumerate(chars)}
        self.items = []
        for lang, names in data.items():
            for name in names:
                self.items.append((name.lower(), self.labels.index(lang)))
        random.Random(SEED).shuffle(self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        return self.items[idx]


def collate_names(batch, char2idx):
    max_len = max(len(name) for name, _ in batch)
    x = torch.zeros(len(batch), max_len, dtype=torch.long)
    lengths = torch.tensor([len(name) for name, _ in batch], dtype=torch.long)
    y = torch.tensor([label for _, label in batch], dtype=torch.long)
    for i, (name, _) in enumerate(batch):
        for j, c in enumerate(name):
            x[i, j] = char2idx.get(c, 0)
    return x, lengths, y


class CharSequenceClassifier(nn.Module):
    def __init__(self, vocab_size: int, num_classes: int, cell: str, embed_dim=64, hidden_dim=128):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        rnn_cls = nn.LSTM if cell == "LSTM" else nn.RNN
        self.rnn = rnn_cls(embed_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, num_classes)

    def forward(self, x, lengths):
        emb = self.embedding(x)
        packed = nn.utils.rnn.pack_padded_sequence(emb, lengths.cpu(), batch_first=True, enforce_sorted=False)
        _, hidden = self.rnn(packed)
        h = hidden[0][-1] if isinstance(hidden, tuple) else hidden[-1]
        return self.fc(h)


@torch.no_grad()
def evaluate(model, loader):
    model.eval()
    loss_sum = total = correct = 0
    y_true, y_pred = [], []
    for x, lengths, y in loader:
        x, lengths, y = x.to(DEVICE), lengths.to(DEVICE), y.to(DEVICE)
        logits = model(x, lengths)
        loss_sum += F.cross_entropy(logits, y).item() * y.size(0)
        pred = logits.argmax(1)
        total += y.size(0)
        correct += (pred == y).sum().item()
        y_true.extend(y.cpu().tolist())
        y_pred.extend(pred.cpu().tolist())
    return loss_sum / total, correct / total, y_true, y_pred


def train_model(model, train_loader, val_loader, epochs=60, patience=8):
    model.to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    best_loss, bad_epochs = float("inf"), 0
    best_state = copy.deepcopy(model.state_dict())
    rows = []
    for epoch in loop(range(1, epochs + 1), desc=model.__class__.__name__, unit="epoch"):
        model.train()
        loss_sum = total = 0
        for x, lengths, y in loop(train_loader, desc=f"epoch {epoch}/{epochs}", leave=False):
            x, lengths, y = x.to(DEVICE), lengths.to(DEVICE), y.to(DEVICE)
            opt.zero_grad(set_to_none=True)
            loss = F.cross_entropy(model(x, lengths), y)
            loss.backward()
            opt.step()
            loss_sum += loss.item() * y.size(0)
            total += y.size(0)
        val_loss, val_acc, _, _ = evaluate(model, val_loader)
        if val_loss < best_loss - 1e-4:
            best_loss, bad_epochs, best_state = val_loss, 0, copy.deepcopy(model.state_dict())
        else:
            bad_epochs += 1
        early_stop = bad_epochs >= patience
        if epoch == 1 or epoch % 5 == 0 or early_stop:
            rows.append({"epoch": epoch, "train_loss": loss_sum / total, "val_loss": val_loss, "val_accuracy": val_acc, "best_val_loss": best_loss, "early_stop": early_stop})
        if early_stop:
            break
    model.load_state_dict(best_state)
    return rows


def main() -> None:
    random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    ensure(OUT)
    dataset = NameDataset()
    train_len = int(len(dataset) * 0.8)
    val_len = len(dataset) - train_len
    train_ds, val_ds = random_split(dataset, [train_len, val_len], generator=torch.Generator().manual_seed(SEED))
    collate = lambda b: collate_names(b, dataset.char2idx)
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True, collate_fn=collate)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False, collate_fn=collate)
    summary, structures = [], [f"device: {DEVICE}", f"total_samples: {len(dataset)}", f"labels: {dataset.labels}", "epochs: 60", "early_stopping: patience=8", ""]
    for cell in ["RNN", "LSTM"]:
        model = CharSequenceClassifier(len(dataset.char2idx) + 1, len(dataset.labels), cell)
        rows = train_model(model, train_loader, val_loader)
        val_loss, acc, y_true, y_pred = evaluate(model, val_loader)
        write_csv(OUT / f"{cell}_metrics.csv", [{"model": cell, **r} for r in rows])
        save_confusion(OUT / f"{cell}_confusion.csv", confusion_matrix(y_true, y_pred, len(dataset.labels)), dataset.labels)
        summary.append({"model": cell, "val_loss": val_loss, "val_accuracy": acc})
        structures.extend([f"===== {cell} =====", str(model), ""])
    write_csv(OUT / "rnn_summary.csv", summary)
    (OUT / "network_structures.txt").write_text("\n".join(structures), encoding="utf-8")


if __name__ == "__main__":
    main()
