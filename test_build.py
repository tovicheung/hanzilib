import warnings
warnings.filterwarnings("always", category=DeprecationWarning)

if 1:
    from hanzilib.build.cli import main
    main()
exit()
from hanzilib.characterlookup import CharacterLookup
cjk = CharacterLookup('C')
# Returns Pinyin readings for '我'
readings = cjk.getReadingForCharacter(u'我', 'GR')
print(readings)

from hanzilib.reading import ReadingFactory

print(ReadingFactory().getSupportedReadings())

if 1:
    from hanzilib.characterlookup import CharacterLookup
    cjk = CharacterLookup('C')
    print(cjk.getStrokeOrderAbbrev('吃'))
    print(cjk.getStrokeOrder("吃"))
