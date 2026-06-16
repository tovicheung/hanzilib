from hanzilib.characterlookup import CharacterLookup

cjk = CharacterLookup("C")

def get(x):
    return cjk.getReadingForCharacter(x, "Pinyin")[0]

def f(s):
    for c in s:
        yield get(c)

print(*f("人工智能" * 99))