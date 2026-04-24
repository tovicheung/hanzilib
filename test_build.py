import warnings
warnings.filterwarnings("always", category=DeprecationWarning)

if 1:
    from hanzilib.build.cli import main
    main()

from hanzilib.characterlookup import CharacterLookup
cjk = CharacterLookup('C')
# Returns Pinyin readings for '我'
readings = cjk.getReadingForCharacter(u'我', 'Pinyin')
print(readings)

if 1:
    from hanzilib.characterlookup import CharacterLookup
    cjk = CharacterLookup('C')
    print(cjk.getStrokeOrderAbbrev('吃'))
    print(cjk.getStrokeOrder("吃"))
