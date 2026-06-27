
from hanzilib.reading import convert
from hanzilib.reading.readings import *

print(convert('lǎo shī', Pinyin, WadeGiles))
print(convert('lǎo shī', Pinyin, WadeGiles(toneMarkType="numbers")))
print(convert('lao3 shi1', "Pinyin", "WadeGiles", sourceOptions={"toneMarkType": "numbers"}, targetOptions={"toneMarkType": "numbers"}))
