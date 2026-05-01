# Hanzilib

Hanzilib is designed for working with Han characters (Hanzi, Kanji, Hanja, and chu Han) used in Chinese, Japanese, Korean, and Vietnamese (CJKV) languages. It provides a comprehensive set of tools to manage, analyze, and query information about characters based on their visual structure (radicals, glyphs, strokes), pronunciation (readings), and dictionary definitions.

Hanzilib is the successor of **cjklib**, which has remained dormant for more than a decade and was difficult to install for modern versions of Python. Hence, this fork was created as an attempt to port the entirety of (or most of) cjklib to modern Python.

Hanzilib also provides the cli tool `hanzi` for convenience.

**Important:** the interface (both Python and CLI) are not final

#### Useful sections
* [CLI examples](#cli-examples)
* [Python examples](#python-examples)
* [Details](#details-of-hanzilib)

## Installation

```sh
pip install hanzilib
```

After installing, run `hanzi build` to build the database

## Current state of the project
- Core ported to Python 3
- Core now uses SqlAlchemy 2.0
- **There is still a LOT to update/document**
- the legacy `EDICT` is used instead of `EDICT2`, this will be changed shortly

## CLI examples

Get character information: `-i` / `--information`
```console
$ hanzi -i 個
Information for character 個 (Chinese simplified locale, Unicode domain)
Unicode codepoint: U+500B (20491, character form)
In character domains: Unicode, BIG5, IICore, JISX0208_0213, GlyphInformation, JISX0208, BIG5HKSCS
Radical index: 9, radical form: ⼈, variants: ⺅
Stroke count: 10
Phonetic data (CantoneseYale): go
Phonetic data (GR): gee, geh
...
```

List characters with KangXi radical index: `-k` / `--by-radicalidx`
```console
$ hanzi -k 30 # 30 corresponds to 口
+2: 台叽叶叼召叭叾叵叨只史可叺叱叻叫号叧叹句叴另叮叩古
+3: 各吇吏吓吂吖叿吉同吋吐名吆吀叫吗吁吸吊吃吕吒吔合吅
+4: 呗君吩吶呚含呜呃呈呙呅听吲吠呐呖吼呒吙吝呀吣呌吹 ...
...
```

Get reading from string: `-r` / `--get-reading`
```console
$ hanzi -r 凍檸茶 # defaults to Pinyin
dòng níng chá

$ hanzi -r 凍檸茶 --target-reading Jyutping
dung3 ning4 caa4
```

Get character from reading: `-a` / `--by-reading`
```console
$ hanzi -a dòng # defaults to Pinyin
㓊㗢㢥㣚㣫㼯䆚䞒侗倲働冻凍动動勭垌姛娻峒崠恫戙挏栋桐棟洞湩烔狪甬硐筒筩絧胨胴腖衕詷迵酮霘駧騆𠄉𢳾𥫎𧡍𧼩𧽿𩐤𩐵𩭩𪔦

$ hanzi -a dung3 --source-reading Jyutping
冻凍崠胨腖𰎏
```

Conversion between simplified and traditional Chinese: `-f` / `-convert-form`
```console
$ hanzi -f 龍馬精神
Simplified: 龙马精神
Traditional: 龍馬精神

$ hanzi -f 飛機
Simplified: 飞[机機]     # two or more variants
Traditional: 飛機

$ hanzi -f 龙馬精神
Warning: input string has mixed simplified and traditional forms
Simplified: 龙马精神
Traditional: 龍馬精神
```

## Python examples

Character operations

```py
from hanzilib.characterlookup import CharacterLookup
cjk = CharacterLookup("C")

# Many methods; to be documented
```

Reading conversions

```py
from hanzilib.reading import ReadingFactory
f = ReadingFactory()
f.convert('lǎoshī', 'Pinyin', 'MandarinIPA') # lau˨˩.ʂʅ˥˥
```

## Details of hanzilib

### Readings

- **Reading operators** provide linguistic operations on a specific reading, such as decomposition (`'hok6jyut6ping3'` -> `['hok6', 'jyut6', 'ping3']`)

- **Reading converters** can convert from one reading to another

The supported readings of this library are tabulated below.

### Mandarin
Mandarin is a spoken language and the most widely used branch of the Chinese linguistic family. It relies on **hanzi** for its written expression.

| Reading | Description | Example |
|---|--------------|---|
| Pinyin | standard romanization of Mandarin; uses Latin symbols to spell out sounds | nǐ hǎo |
| Mandarin IPA | phonetic symbols to represent exact sounds in Mandarin | ni˨˩˦ xau˨˩˦ |
| Gwoyeu Romatzyh (GR) | romanization of Mandarin; uses letters to represent (e.g., ai (1st), air (2nd), ae (3rd), ay (4th)) tones | nii hau; Koong fu tzyy |
| Wade-Giles | predecessor of Pinyin; uses numbers, hyphens and apostrophes | ni hao / ni3 hao3; K’ung-fu-tzu / Kʻung3-fu1-tzŭ3 |
| Mandarin Braille | tactile writing system of Mandarin; maps Pinyin into braille cells | ⠝⠊⠂ ⠓⠖⠐

### Cantonese
Cantonese is primarily spoken in Hong Kong, Macau, and the Guangdong province of China. It relies on **hanzi** for its written expression.

| Reading | Description | Example |
|---|--------------|---|
| JyutPing (粵拼) | standard romanization of Cantonese; uses Latin letters and numbers to describe sounds | ning4 mung4 caa4 |
| Cantonese Yale | more intuitive romanization of Cantonese (mainly for English speakers); uses letters and diacritics | lihng mùng chà |
| Cantonese IPA | phonetic symbols to represent exact sounds in Mandarin | neŋ˨˩ mʊŋ˨˩ tsʰaː˨˩ |

### Supported reading conversions

Mandarin
- All inter-conversions are supported except from Mandarin IPA (ie all except `MandarinIPA -> X`)

Cantonese
- Inter-conversions within Jyutping and Cantonese Yale
- No conversion support for Cantonese IPA

## Changes since cjklib

- `kRSKangXi` (data from 康熙字典) was removed from Unihan in favour of `kRSUnicode`, which is now the standard for getting radicals of Chinese characters (See: [Unicode proposal L2/22-195](https://www.unicode.org/L2/L2022/22195-remove-krskangxi.pdf))

- `kRSKanwa` (data from 大漢和辭典), `kRSJapanese`, `kRSKorean` were removed from Unihan (See: [Unicode proposal L2/19-209](https://www.unicode.org/L2/L2019/19209-deprecate-fields.pdf))


Therefore, in this project, `CharacterKangxiRadical` and `CharacterKanwaRadical` are combined to `CharacterChineseRadical`
