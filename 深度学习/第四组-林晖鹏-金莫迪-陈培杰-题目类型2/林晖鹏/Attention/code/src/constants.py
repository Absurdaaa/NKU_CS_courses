"""Common constants for the translation experiments."""

from __future__ import annotations

PAD_TOKEN = 0
SOS_TOKEN = 1
EOS_TOKEN = 2
UNK_TOKEN = 3

SPECIAL_TOKENS = {
    "<PAD>": PAD_TOKEN,
    "<SOS>": SOS_TOKEN,
    "<EOS>": EOS_TOKEN,
    "<UNK>": UNK_TOKEN,
}

ENGLISH_PREFIXES = (
    "i am ",
    "i m ",
    "he is ",
    "he s ",
    "she is ",
    "she s ",
    "you are ",
    "you re ",
    "we are ",
    "we re ",
    "they are ",
    "they re ",
)
