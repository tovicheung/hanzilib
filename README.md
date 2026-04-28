# Hanzilib


Hanzilib is an open-source Python library designed for working with Han characters (Hanzi, Kanji, Hanja, and chu Han) used in Chinese, Japanese, Korean, and Vietnamese (CJKV) languages. It provides a comprehensive set of tools to manage, analyze, and query information about characters based on their visual structure (radicals, glyphs, strokes), pronunciation (readings), and dictionary definitions.

Hanzilib is the successor of cjklib, which has remained dormant for more than a decade and was difficult to install for modern versions of Python. Hence, this fork is created as an attempt to port the entirety of (or most of) cjklib to modern Python.

## Installation

Installed from PyPI:
```sh
pip install hanzilib
```

After installing, run `hanzi build` to build the database

## Scope

### Readings

- **Reading operators** provide linguistic operations on a specific reading, such as decomposition (`'hok6jyut6ping3'` -> `['hok6', 'jyut6', 'ping3']`)

- **Reading converters** can convert from one reading to another

| Reading | Description | Example |
|---|--------------|---|
| Pinyin | standard romanization of Mandarin; uses Latin symbols to spell out sounds | nǐ hǎo |
| MandarinIPA | phonetic symbols to represent exact sounds in Mandarin | ni˨˩˦ xau˨˩˦ |
| JyutPing (粵拼) | standard romanization of Cantonese; uses Latin letters and numbers to describe sounds | ning4 mung4 caa4 |
| Cantonese Yale | more intuitive romanization of Cantonese (mainly for English speakers); uses letters and diacritics | lihng mùng chà |
| Cantonese IPA | phonetic symbols to represent exact sounds in Mandarin | neŋ˨˩ mʊŋ˨˩ tsʰaː˨˩ |

(unfinished list)

## Current state of the project
- Core ported to Python 3
- Core now uses SqlAlchemy 2.0
- **There is still a LOT to update/document**
- the legacy version `EDICT` is used instead of `EDICT2`, this will be changed shortly


## Changes over the years
- `kRSKangXi` (data from 康熙字典) was removed from Unihan in favour of `kRSUnicode`, which is now the standard for getting radicals of Chinese characters (See: [Unicode proposal L2/22-195](https://www.unicode.org/L2/L2022/22195-remove-krskangxi.pdf))

- `kRSKanwa` (data from 大漢和辭典), `kRSJapanese`, `kRSKorean` were removed from Unihan (See: [Unicode proposal L2/19-209](https://www.unicode.org/L2/L2019/19209-deprecate-fields.pdf))


Relevant changes in this project:
- `CharacterKangxiRadical` and `CharacterKanwaRadical` are combined to `CharacterChineseRadical`
