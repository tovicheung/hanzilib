from __future__ import annotations
from typing import Literal

type Entity = str
type Decomposition = list[Entity]
type SyllableTree = tuple[str, list[SyllableTree] | None]

type Reading = Literal["Hangul", "Hiragana", "Katakana", "Kana", "Pinyin", "WadeGiles", "GR", "MandarinIPA", "MandarinBraille", "Jyutping", "CantoneseYale", "CantoneseIPA", "ShanghaineseIPA"]
