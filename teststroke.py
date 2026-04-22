# test build
if 0:
    from hanzilib.build.cli import main
    main()
from hanzilib.characterlookup import CharacterLookup
cjk = CharacterLookup('C')
print(cjk.getStrokeOrderAbbrev('吃'))
print(cjk.getStrokeOrder("吃"))