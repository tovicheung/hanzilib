from __future__ import annotations
from typing import Literal, TypeAlias

Entity: TypeAlias = str
Decomposition: TypeAlias = list[Entity]
SyllableTree: TypeAlias = tuple[str, list["SyllableTree"] | None]

Reading: TypeAlias = Literal["Hangul", "Hiragana", "Katakana", "Kana", "Pinyin", "WadeGiles", "GR", "MandarinIPA", "MandarinBraille", "Jyutping", "CantoneseYale", "CantoneseIPA", "ShanghaineseIPA"]
