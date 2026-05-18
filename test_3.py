
from hanzilib.characterlookup import CharacterLookup
cjk = CharacterLookup('C')
print(cjk.getDecompositionEntries("豐"))
print(cjk.getDecompositionEntries("榱"))
print(cjk.getStrokeOrderAbbrev('舧'))
