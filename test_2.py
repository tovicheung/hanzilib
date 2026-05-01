from hanzilib import dictionary
from pprint import pprint
print(dictionary.getAvailableDictionaries())

from hanzilib.reading import ReadingFactory
f = ReadingFactory()
pprint(f._sharedState["readingConverterClasses"])

# Convert Mandarin Pinyin to IPA
assert f.convert(u'lǎoshī', 'Pinyin', 'MandarinIPA') == "lau˨˩.ʂʅ˥˥"
print(f.getSupportedReadings())

from hanzilib.characterlookup import CharacterLookup

cjk = CharacterLookup("C")

bear = "熊"
bear_pinyin = cjk.getReadingForCharacter(bear, "Pinyin")
print(bear_pinyin)
print(cjk.getStrokeOrderAbbrev("卩"))