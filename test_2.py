from hanzilib import dictionary

print(dictionary.getAvailableDictionaries())


from hanzilib.reading import ReadingFactory
f = ReadingFactory()
# Convert Mandarin Pinyin to IPA
assert f.convert(u'lǎoshī', 'Pinyin', 'MandarinIPA') == "lau˨˩.ʂʅ˥˥"

print(f.convert('gwong2jau1waa2', 'Jyutping', 'CantoneseYale'))
print(f.getSupportedReadings())

