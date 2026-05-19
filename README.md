# Hanzilib

Hanzilib works with Han characters (Hanzi, Kanji, Hanja, and chu Han) used in Chinese, Japanese, Korean, and Vietnamese (CJKV) languages. It provides a comprehensive set of tools to manage, analyze, and query information about characters based on their visual structure (radicals, glyphs, strokes), pronunciation (readings), and dictionary definitions.

Hanzilib is a modern fork of **cjklib**, which has been unmaintained since 2012. Cjklib was difficult to install for modern versions of Python; some of its data sources are also no longer available. Hence, this fork was created as an attempt to port the entirety of (or most of) cjklib to modern Python.

Apart from a Python interface, hanzilib provides the `hanzi` cli tool for convenience (resembling the original `cjknife` command)

**Important ⚠️**
* hanzilib is a work in progress; the interface (both Python and CLI) are not final
* hanzilib is not backwards-compatible with cjklib. The API has been modernized for clarity and maintainability.

#### Jump to useful sections
* [CLI examples](#cli-examples)
* [Python examples](#python-examples)
* [Details](#details-of-hanzilib)

## Installation

```sh
pip install hanzilib
```

After installing, run `hanzi db build` to setup the internal database

## CLI examples

Get character information:
```console
$ hanzi lookup 個
Information for character 個 (Chinese simplified locale, Unicode domain)
Character type: character
Unicode codepoint: U+500B (20491)
In character domains: Unicode, JISX0208, GlyphInformation, JISX0208_0213, BIG5, BIG5HKSCS, IICore
Radical index: 9 , radical form: ⼈, variants: ⺅
Stroke count: 10

Reading (CantoneseYale): go
Reading (GR): gee, geh
Reading (Hangul): 개:0e
Reading (Jyutping): go3
Reading (MandarinBraille): ⠛⠢⠄, ⠛⠢⠆
Reading (MandarinIPA): kɤ˨˩˦, kɤ˥˩
Reading (Pinyin): gě, gè

Semantic variants: 个, 箇
Simplified variants: 个
Specialised semantic variants: 个, 箇

Glyph 0 (default)
Stroke count: 10
Stroke order: ㇒㇑㇑㇕㇐㇑㇑㇕㇐㇐ (P-S S-HZ H-S S-HZ-H H)
Decomposition:
⿰亻固　　　　　　　　　　
　　⿴囗　　　　古　　　　
　　　⿱冂　　一⿱十　　口
　　　　⿻丨？　⿻一丨
```

Get reading from string:
```console
$ hanzi to-reading 凍檸茶 # defaults to Pinyin
dòng níng chá

$ hanzi to-reading 凍檸茶 --target Jyutping
dung3 ning4 caa4
```

Find characters with KangXi radical index:
```console
$ hanzi find --radical 30 # 30 corresponds to 口
+2: 台叽叶叼召叭叾叵叨只史可叺叱叻叫号叧叹句叴另叮叩古
+3: 各吇吏吓吂吖叿吉同吋吐名吆吀叫吗吁吸吊吃吕吒吔合吅
+4: 呗君吩吶呚含呜呃呈呙呅听吲吠呐呖吼呒吙吝呀吣呌吹 ...
...
```

Find characters from reading:
```console
$ hanzi find --reading dòng # defaults to Pinyin
㓊㗢㢥㣚㣫㼯䆚䞒侗倲働冻凍动動勭垌姛娻峒崠恫戙挏栋桐棟洞湩烔狪甬硐筒筩絧胨胴腖衕詷迵酮霘駧騆𠄉𢳾𥫎𧡍𧼩𧽿𩐤𩐵𩭩𪔦

$ hanzi find --reading dung3 -s Jyutping
冻凍崠胨腖𰎏
```

Find characters with components:
```console
$ hanzi find --comp 日月
明﨟嬮腽靨朝胆腌輤醐酭擫檿曨猒晴盟輎瀭醑曌琞胉腖厭潮廟膫壓懨膻奣臈腪黶脂腊腺謿曡酳腹焽輸勗腤膜橗膾輣朚厴嚈擪萌腥懕冐焨胂臆皘擝腸 奛嘲
```

Filters can be combined!
```console
$ hanzi find --radical 30 --comp 月
嚈嗋啃哨喐唨唷咀嚨喻喩哊啨喟嘲嗍嘣嗗
```

Simplified and traditional Chinese: `zhscript`
```console
$ hanzi zhscript 龍馬精神
Simplified: 龙马精神
Traditional: 龍馬精神

$ hanzi zhscript 飛機
Simplified: 飞[机機]     # two or more variants
Traditional: 飛機

$ hanzi zhscript 龙馬精神
Warning: input string has mixed simplified and traditional forms
Simplified: 龙马精神
Traditional: 龍馬精神
```

## Python examples

Character operations:

```py
>>> from hanzilib.characterlookup import CharacterLookup
>>> cjk = CharacterLookup("C")

# Get stroke order
>>> cjk.getStrokeOrder('說')
['㇔', '㇐', '㇐', '㇐', '㇑', '㇕', '㇐', '㇒', '㇏', '㇑', '㇕', '㇐', '㇓', '㇟']

# Get characters from components
>>> cjk.getCharactersForComponents([u'门', u'⼉'])
[('阅', 0), ('阋', 0)]

# Many other methods; to be documented
```

Reading conversions:

```py
>>> from hanzilib.reading import ReadingFactory
>>> f = ReadingFactory()
>>> f.convert('lǎoshī', 'Pinyin', 'MandarinIPA')
lau˨˩.ʂʅ˥˥
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

#### Removed Unihan properties

For details regarding Unihan properties, see [Unicode Standard Annex #38](https://www.unicode.org/reports/tr38/)

- `kRSKangXi` (data from 康熙字典) was removed in version 15.1.0 in favour of `kRSUnicode`, which is now the standard for getting radicals of Chinese characters (See: [UTC Decision 173-C12](https://www.unicode.org/L2/L2022/22241.htm#173-C12))

- `kRSKanwa` (data from 大漢和辭典), `kRSJapanese`, `kRSKorean` were removed in version 13.0.0 (See: [Unicode proposal L2/19-209](https://www.unicode.org/L2/L2019/19209-deprecate-fields.pdf))

- `kHKSCS` was removed in version 15.1.0 (See: [UTC Decision 174-C10](https://www.unicode.org/L2/L2023/23005.htm#174-C10))

Therefore, in hanzilib:
- the tables `CharacterKangxiRadical` and `CharacterKanwaRadical` are combined to `CharacterChineseRadical`
- the following tables are removed (temporarily? maybe another data source can be found?)
    - `CharacterJapaneseRadical`
    - `CharacterKoreanRadical`
    - `HKSCSSet`

#### Missing dictionaries

Finding new data sources for:
- `CEDICTGR` ([Original data source (broken)](http://home.iprimus.com.au/richwarm/gr/cedictgr.zip))
- `CFDICT` ([Original data source(broken)](https://chine.in/chinois/open/CFDICT/cfdict.zip))

Also, the legacy `EDICT` is used instead of `EDICT2`, this will be changed shortly
