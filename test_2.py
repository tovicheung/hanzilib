from hanzilib.characterlookup import CharacterLookup

cjk = CharacterLookup("C")

assert cjk.getReadingForCharacter("熊", "Pinyin") == ["xióng"]
assert cjk.getStrokeOrderAbbrev("卩") == "HZG-S"
