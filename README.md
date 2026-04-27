# Hanzilib

Hanzi 漢字 (Han characters) are used mainly in the Chinese language. The original repo (`cjklib`) has been dormant for more than a decade and was difficult to install for modern versions of Python. Hence, this fork is created as an attempt to port the entirety of (or most of) cjklib to modern Python.

`hanzilib` can be installed from PyPI

After installing, run `hzbuild` to build the database


## Current state of the project
- Core functionality ported to Python 3
- Core functionality now uses SqlAlchemy 2.0
- **There is still a LOT to update/document**


### Notes
- the legacy version `EDICT` is used instead of `EDICT2`, this will be changed shortly


## Changes over the years
- `kRSKangXi` (data from 康熙字典) was removed from Unihan in favour of `kRSUnicode`, which is now the standard for getting radicals of Chinese characters (See: [Unicode proposal L2/22-195](https://www.unicode.org/L2/L2022/22195-remove-krskangxi.pdf))

- `kRSKanwa` (data from 大漢和辭典), `kRSJapanese`, `kRSKorean` were removed from Unihan (See: [Unicode proposal L2/19-209](https://www.unicode.org/L2/L2019/19209-deprecate-fields.pdf))


Relevant changes in this project:
- `CharacterKangxiRadical` and `CharacterKanwaRadical` is now `CharacterChineseRadical`