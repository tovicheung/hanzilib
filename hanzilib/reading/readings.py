from __future__ import annotations

# This module is created for better type support among the messy options
# that are passed back and forth between ReadingFactory, ReadingConverter and ReadingOperator

# Temp; these may be absorbed into operator later

from dataclasses import dataclass, asdict, fields
from typing import Any, Callable, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from .operator import ReadingOperator

class Reading:
    def to_dict(self):
        return asdict(self)
    
    def get_name(self):
        return type(self).__name__
    
    @staticmethod
    def from_name(name: str, options: dict[str, Any] | None = None) -> Reading:
        if name not in _registry:
            raise ValueError("Not supported: " + str(name))
        return _registry[name](**(options or {}))
    
    @staticmethod
    def from_operator(operator: ReadingOperator):
        typ = _registry[operator.READING_NAME]
        kwargs = {}
        for field in fields(typ):
            kwargs[field.name] = getattr(operator, field.name)
        return typ(**kwargs)

@dataclass(frozen=True)
class _RomanisationBase(Reading):
    strictSegmentation: bool = False
    case: Literal["lower", "both"] = "both"

@dataclass(frozen=True)
class _TonalIPABase(Reading):
    toneMarkType: Literal["numbers", "superscriptNumbers", "chaoDigits", "superscriptChaoDigits", "ipaToneBar", "diacritics", "none"] = "ipaToneBar"
    missingToneMark: Literal["noinfo", "ignore"] = "noinfo"

# from PinyinOperator.aeoApostropheRule (temp)
def aeoApostropheRule(operatorInst, precedingEntity, followingEntity):
    if precedingEntity and operatorInst.isReadingEntity(precedingEntity) \
        and operatorInst.isReadingEntity(followingEntity):

        plainSyllable, _ = operatorInst.splitEntityTone(followingEntity)

        # take care of corner case Erhua form e'r, that needs to be
        #   distinguished from er
        if plainSyllable.lower() == 'r':
            precedingPlainSyllable, _ = operatorInst.splitEntityTone(
                precedingEntity)
            return precedingPlainSyllable.lower() == 'e'

        return plainSyllable[0].lower() in ['a', 'e', 'o'] \
            or plainSyllable.lower() in ['n', 'ng', 'nr', 'ngr', 'ê', 'ŋ',
                'ŋr']
    return False


@dataclass(frozen=True)
class Pinyin(_RomanisationBase):
    toneMarkType: Literal["numbers", "diacritics", "none"] = "diacritics"
    missingToneMark: Literal["fifth", "noinfo", "ignore"] = "noinfo"
    strictDiacriticPlacement: bool = False
    pinyinDiacritics: tuple[str, str, str, str] = ('\u0304', '\u0301', '\u030c', '\u0300')
    yVowel: str = "ü"
    shortenedLetters: bool = False
    pinyinApostrophe: str = "'"
    erhua: Literal["ignore", "twoSyllables", "oneSyllable"] = "twoSyllables"
    pinyinApostropheFunction: Callable[[ReadingOperator, str, str]] = aeoApostropheRule

@dataclass(frozen=True)
class WadeGiles(_RomanisationBase):
    diacriticE: str = "ê"
    zeroFinal: str = "ŭ"
    umlautU: str = "ü"
    useInitialSz: bool = False
    wadeGilesApostrophe: str = "’"
    neutralToneMark: Literal["none", "zero", "five"] = "none"
    toneMarkType: Literal["numbers", "superscriptNumbers", "none"] = "superscriptNumbers"
    missingToneMark: Literal["noinfo", "ignore"] = "noinfo"

@dataclass(frozen=True)
class GR(_RomanisationBase):
    abbreviations: bool = True
    grRhotacisedFinalApostrophe: str = "’"
    grSyllableSeparatorApostrophe: str = "’"
    optionalNeutralToneMarker: str = "˳"

@dataclass(frozen=True)
class MandarinIPA(_TonalIPABase):
    pass

@dataclass(frozen=True)
class MandarinBraille(Reading):
    toneMarkType: Literal["braille", "none"] = "braille"
    missingToneMark: Literal["fifth", "extended"] = "extended"

@dataclass(frozen=True)
class Jyutping(_RomanisationBase):
    toneMarkType: Literal["numbers", "none"] = "numbers"
    missingToneMark: Literal["noinfo", "ignore"] = "noinfo"

@dataclass(frozen=True)
class CantoneseYale(_RomanisationBase):
    toneMarkType: Literal["diacritics", "numbers", "none"] = "diacritics"
    missingToneMark: Literal["noinfo", "ignore"] = "noinfo"
    strictDiacriticPlacement: bool = False
    yaleFirstTone: Literal["1stToneLevel", "1stToneFalling"] = "1stToneLevel"

@dataclass(frozen=True)
class CantoneseIPA(_TonalIPABase):
    stopTones: Literal["none", "general", "explicit"] = "none"
    firstToneName: Literal['HighLevel', 'MidLevel', 'MidLowLevel', 'HighRising',
        'MidLowRising', 'MidLowFalling', 'HighFalling'] = "HighLevel"

@dataclass(frozen=True)
class ShanghaineseIPA(_TonalIPABase):
    constrainEntering: bool = False
    constrainToneCategories: bool = False

def _get_reading_info(obj: str | Reading | type[Reading], extra_options = None) -> tuple[str, dict[str, Any]]:
    if extra_options is None:
        extra_options = {}
    if isinstance(obj, Reading):
        return obj.get_name(), obj.to_dict() | extra_options
    elif isinstance(obj, type) and issubclass(obj, Reading):
        return obj.__name__, obj().to_dict() | extra_options
    if obj in _registry:
        return obj, _registry[obj]().to_dict() | extra_options # temp
    return obj, extra_options

_registry: dict[str, type[Reading]] = {}

for k, v in globals().copy().items():
    if type(v) is type and issubclass(v, Reading):
        _registry[k] = v
