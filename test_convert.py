
from hanzilib.reading import convert
from hanzilib.reading.readings import *

print(convert('lǎo shī', Pinyin, WadeGiles))
print(convert('lao3 shi1', Pinyin(toneMarkType="numbers"), WadeGiles(toneMarkType="numbers")))
