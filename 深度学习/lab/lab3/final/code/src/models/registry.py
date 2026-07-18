"""Model registry helpers."""

from __future__ import annotations

from .seq2seq_attn import Seq2SeqAttention
from .seq2seq_luong import Seq2SeqLuong
from .seq2seq_rnn import Seq2SeqRNN

AVAILABLE_MODELS = (
    "seq2seq_rnn",
    "seq2seq_attn",
    "seq2seq_luong",
    "seq2seq_luong_dot",
    "seq2seq_luong_general",
    "seq2seq_luong_concat",
)


def build_model(
    model_name: str,
    src_vocab_size: int,
    tgt_vocab_size: int,
    hidden_size: int,
    num_layers: int,
    dropout: float,
    pad_idx: int,
    max_decode_length: int,
):
    # 统一从这里按名字建模，train.py 就不用自己写一堆 if/else 了。
    if model_name == "seq2seq_rnn":
        return Seq2SeqRNN(
            src_vocab_size=src_vocab_size,
            tgt_vocab_size=tgt_vocab_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout,
            pad_idx=pad_idx,
            max_decode_length=max_decode_length,
        )
    if model_name == "seq2seq_attn":
        return Seq2SeqAttention(
            src_vocab_size=src_vocab_size,
            tgt_vocab_size=tgt_vocab_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout,
            pad_idx=pad_idx,
            max_decode_length=max_decode_length,
        )
    if model_name in {"seq2seq_luong", "seq2seq_luong_dot", "seq2seq_luong_general", "seq2seq_luong_concat"}:
        score_method = {
            "seq2seq_luong": "general",
            "seq2seq_luong_dot": "dot",
            "seq2seq_luong_general": "general",
            "seq2seq_luong_concat": "concat",
        }[model_name]
        return Seq2SeqLuong(
            src_vocab_size=src_vocab_size,
            tgt_vocab_size=tgt_vocab_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout,
            pad_idx=pad_idx,
            max_decode_length=max_decode_length,
            score_method=score_method,
        )
    raise ValueError(f"Unknown model: {model_name}")
