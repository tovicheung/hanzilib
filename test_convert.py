
from hanzilib.reading import convert
from hanzilib.reading.readings import *

# Different methods of configuration
assert convert('lǎo shī', Pinyin, WadeGiles) == "lao³ shih¹"
assert convert('lǎo shī', Pinyin, WadeGiles(toneMarkType="numbers")) == "lao3 shih1"
assert convert('lao3 shi1', "Pinyin", "WadeGiles", sourceOptions={"toneMarkType": "numbers"}, targetOptions={"toneMarkType": "numbers"}) == "lao3 shih1"

assert convert("ju", Pinyin, WadeGiles) == "chü" # Umlaut
assert convert("qu", Pinyin, WadeGiles) == "ch’ü" # Aspiration + Umlaut
assert convert("qu", Pinyin, WadeGiles(wadeGilesApostrophe="'")) == "ch'ü" # Aspiration + Umlaut
assert convert("xu", Pinyin, WadeGiles) == "hsü"
assert convert("yuan", Pinyin, WadeGiles) == "yüan"
assert convert("yue", Pinyin, WadeGiles) == "yüeh"
assert convert("yan", Pinyin, WadeGiles) == "yen"
assert convert("xiong", Pinyin, WadeGiles) == "hsiung"

assert convert("lao3 shi1", Pinyin(toneMarkType="numbers"), GR) == "lao shy"
