#!/usr/bin/python
# -*- coding: utf-8 -*-
# This file is part of cjklib.
#
# cjklib is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# cjklib is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with cjklib.  If not, see <http://www.gnu.org/licenses/>.

"""
*Command line interface* (*CLI*) to the library's functionality.

Check what this script offers on the command line with ``hanzi -h``.

The script's output depends on the following:

- dictionary setting in the cjklib's config file
- user locale settings are checked to guess appropriate values for the
    character locale and the default input and output readings
"""

__all__ = ["CharacterInfo"]

import sys
import getopt
import locale
import warnings

import typing

if typing.TYPE_CHECKING:
    from . import dbconnector, characterlookup, reading, dictionary, exception, __version__
else:
    import hanzilib
    from hanzilib import dbconnector
    from hanzilib import characterlookup
    from hanzilib import reading
    from hanzilib import dictionary
    from hanzilib import exception
    from hanzilib import __version__

from hanzilib.dictionary import search
from hanzilib.util import getConfigSettings


locale.setlocale(locale.LC_ALL, '')

class ExactMultiple(search.Exact):
    """Exact search strategy class matching any strings from a list."""
    @staticmethod
    def _getSubstrings(headwordStr):
        headwordSubstrings = []
        for left in range(0, len(headwordStr)):
            for right in range(len(headwordStr), left, -1):
                headwordSubstrings.append(headwordStr[left:right])
        return headwordSubstrings

    def getWhereClause(self, column, headwordStr):
        return column.in_(self._getSubstrings(headwordStr))

    def getMatchFunction(self, headwordStr):
        searchStrings = self._getSubstrings(headwordStr)
        return lambda cell: cell in searchStrings


class CharacterInfo:
    """
    Provides lookup method services.
    """
    LANGUAGE_CHAR_LOCALE_MAPPING = {'zh': 'C', 'zh_CN': 'C', 'zh_SG': 'C',
        'zh_TW': 'T', 'zh_HK': 'T', 'zh_MO': 'T', 'ja': 'J', 'ko': 'K',
        'vi': 'V'}
    """Mapping table for locale to default character locale."""

    CHAR_LOCALE_NAME = {'T': 'traditional', 'C': 'Chinese simplified',
        'J': 'Japanese', 'K': 'Korean', 'V': 'Vietnamese'}
    """Character locale names."""

    CHAR_LOCALE_DEFAULT_READING = {'zh': "Pinyin", 'zh_CN': "Pinyin",
        'zh_SG': "Pinyin", 'zh_TW': "WadeGiles", 'zh_HK': "CantoneseYale",
        'zh_MO': "Jyutping", 'ko': 'Hangul', 'ja': 'Kana'}
    """Character locale's default character reading."""

    DICTIONARY_CHAR_LOCALE = {
        'HanDeDict': 'C',
        # 'CFDICT': 'C',
        'CEDICT': 'C',
        # 'CEDICTGR': 'T',
        'EDICT': 'J'}
    """Dictionary default locale."""

    READING_DEFAULT_DICTIONARY = {'Pinyin': 'CEDICT'}
    """Dictionary to use by default for a given reading."""

    VARIANT_TYPE_NAMES = {'C': 'Compatible variant',
        'M': 'Semantic variants', 'P': 'Specialised semantic variants',
        'Z': 'Z-Variants', 'S': 'Simplified variants',
        'T': 'Traditional variants'}
    """List of character variants and their names."""

    def __init__(self, charLocale=None, characterDomain='Unicode',
        readingN=None, dictionaryN=None, dictionaryDatabaseUrl=None):
        """
        Initialises the CharacterInfo object.

        :type charLocale: str
        :param charLocale: *character locale* (one out of TCJKV)
        :type characterDomain: str
        :param characterDomain: *character domain* (see
            L{characterlookup.CharacterLookup.getAvailableCharacterDomains()})
        :type readingN: str
        :param readingN: name of reading
        :type dictionaryN: str
        :param dictionaryN: name of dictionary
        :type dictionaryDatabaseUrl: str
        :param dictionaryDatabaseUrl: database connection setting in the format
            ``driver://user:pass@host/database``.
        """
        # print(f"CharacterInfo({charLocale=}, {characterDomain=}, {readingN=}, {dictionaryN=}, {dictionaryDatabaseUrl=})")
        if dictionaryN:
            dictObj = dictionary.getDictionaryClass(dictionaryN)

        if readingN:
            self.reading = readingN
        elif dictionaryN and hasattr(dictObj, 'READING') and dictObj.READING:
            self.reading = dictObj.READING
        else:
            self.reading = self.guessReading()

        if dictionaryDatabaseUrl:
            self.db = dbconnector.DatabaseConnector(
                {'sqlalchemy.url': dictionaryDatabaseUrl, 'attach': ['hanzilib']})
        else:
            self.db = dbconnector.getDBConnector()

        self.readingFactory = reading.ReadingFactory(dbConnectInst=self.db)

        if dictionaryN:
            if dictionaryN not in self.getAvailableDictionaries():
                raise ValueError("dictionary not available")
            self.dictionary = dictionaryN
        else:
            if self.reading in self.READING_DEFAULT_DICTIONARY \
                and self.reading in self.getAvailableDictionaries():
                self.dictionary = self.READING_DEFAULT_DICTIONARY[self.reading]
            else:
                # get a dictionary that is compatible with the selected reading
                for dictName in self.getAvailableDictionaries():
                    dictObj = dictionary.getDictionaryClass(dictName)
                    if (hasattr(dictObj, 'READING') and dictObj.READING
                        and (dictObj.READING == self.reading
                            or self.readingFactory.isReadingConversionSupported(
                                dictObj.READING, self.reading))):
                        self.dictionary = dictName
                        break
                else:
                    self.dictionary = None

        if charLocale:
            self.locale = charLocale
        elif self.dictionary and self.dictionary in self.DICTIONARY_CHAR_LOCALE:
            self.locale = self.DICTIONARY_CHAR_LOCALE[self.dictionary]
        else:
            self.locale = self.guessCharacterLocale()
        
        # print(f"CharacterInfo({self.locale=}, {self.reading=}, {self.dictionary=}, {self.db.databaseUrl=})")

        self.characterLookup = characterlookup.CharacterLookup(self.locale,
            characterDomain, dbConnectInst=self.db)
        self.characterLookupTraditional = characterlookup.CharacterLookup('T',
            characterDomain, dbConnectInst=self.db)

    # Settings

    def guessCharacterLocale(self):
        """
        Guesses the best suited character locale using the user's locale
        settings.

        :rtype: str
        :return: locale
        """
        # get local language and output encoding
        language, _ = locale.getlocale()

        # get character locale
        if language in self.LANGUAGE_CHAR_LOCALE_MAPPING:
            return self.LANGUAGE_CHAR_LOCALE_MAPPING[language]
        elif len(language) >= 2 \
            and language[0:2] in self.LANGUAGE_CHAR_LOCALE_MAPPING:
            # strip off geographic code
            return self.LANGUAGE_CHAR_LOCALE_MAPPING[language[0:2]]
        else:
            return 'T'

    def guessReading(self):
        """
        Guesses the best suited reading using the user's locale settings.

        :rtype: str
        :return: reading name
        """        
        language, _ = locale.getlocale()

        # get reading
        if language in self.CHAR_LOCALE_DEFAULT_READING:
            return self.CHAR_LOCALE_DEFAULT_READING[language]
        elif len(language) >= 2 \
            and language[0:2] in self.CHAR_LOCALE_DEFAULT_READING:
            # strip off geographic code
            return self.CHAR_LOCALE_DEFAULT_READING[language[0:2]]
        else:
            return 'Pinyin'

    def getAvailableDictionaries(self) -> list[str]:
        """
        Gets a list of available dictionaries supported.

        :rtype: list of str
        :return: names of available dictionaries
        """
        if not hasattr(self, '_availableDictionaries'):
            self._availableDictionaries = [dic.PROVIDES for dic in
                dictionary.getAvailableDictionaries(self.db)]
            self._availableDictionaries.sort()

        return self._availableDictionaries

    def hasDictionary(self):
        return self.dictionary != None

    def setCharacterDomain(self, characterDomain):
        if characterDomain \
            in self.characterLookup.getAvailableCharacterDomains():

            # self.characterLookup.setCharacterDomain(characterDomain)
            # self.characterLookupTraditional.setCharacterDomain(characterDomain)

            self.characterLookup.characterDomain = characterDomain
            self.characterLookupTraditional.characterDomain = characterDomain
            return True
        else:
            return False

    # Internal worker

    def getReadingOptions(self, string, readingN):
        """
        Guesses the reading options using the given string to support reading
        dialects.

        :type string: str
        :param string: reading string
        :type readingN: str
        :param readingN: reading name
        :rtype: dict
        :return: reading options
        """
        # guess reading parameters
        classObj = self.readingFactory.getReadingOperatorClass(readingN)
        if hasattr(classObj, 'guessReadingDialect'):
            return classObj.guessReadingDialect(string)
        else:
            return {}

    def getEquivalentCharTable(self, componentList,
        includeEquivalentRadicalForms=True):
        """
        Gets a list structure of equivalent chars for the given list of
        characters.

        If option ``includeEquivalentRadicalForms`` is set, all equivalent forms
        will be searched for when a Kangxi radical is given.

        :type componentList: list of str
        :param componentList: list of character components
        :type includeEquivalentRadicalForms: bool
        :param includeEquivalentRadicalForms: if ``True`` then characters in the
            given component list are interpreted as representatives for their
            radical and all radical forms are included in the search. E.g. 肉
            will include ⺼ as a possible component.
        :rtype: list of list of str
        :return: list structure of equivalent characters

        .. todo::
            * Impl: Once mapping of similar radical forms exist (e.g. 言 and 訁)
              include here.
        """
        # components for which we don't want to retrieve a equivalent character
        #   as it would resemble another radical form
        excludeEquivalentMapping = set(['⺄', '⺆', '⺇', '⺈', '⺊', '⺌',
            '⺍', '⺎', '⺑', '⺗', '⺜', '⺥', '⺧', '⺪', '⺫', '⺮',
            '⺳', '⺴', '⺶', '⺷', '⺻', '⺼', '⻏', '⻕'])

        equivCharTable = []
        for component in componentList:
            componentEquivalents = set([component])
            try:
                # check if component is a radical and get index
                radicalIdx = self.characterLookup.getKangxiRadicalIndex(
                    component)

                if includeEquivalentRadicalForms:
                    # if includeRadicalVariants is set get all forms
                    componentEquivalents.update(self.characterLookup\
                        .getKangxiRadicalRepresentativeCharacters(
                            radicalIdx))
                else:
                    if self.characterLookup.isRadicalChar(component):
                        if component not in excludeEquivalentMapping:
                            try:
                                componentEquivalents.add(self.characterLookup\
                                    .getRadicalFormEquivalentCharacter(
                                        component))
                            except exception.UnsupportedError:
                                # pass if no equivalent char existent
                                pass
                    else:
                        componentEquivalents.update(set(self.characterLookup\
                            .getCharacterEquivalentRadicalForms(component)) \
                            - excludeEquivalentMapping)
            except ValueError:
                pass

            equivCharTable.append(list(componentEquivalents))

        return equivCharTable

    def isSemanticVariant(self, char, variants):
        """
        Checks if the character is a semantic variant form of the given
        characters.

        :type char: str
        :param char: Chinese character
        :type variants: list of str
        :param variants: Chinese characters
        :rtype: bool
        :return: ``True`` if the character is a semantic variant form of the
            given characters, ``False`` otherwise.
        """
        vVariants = []
        for variant in variants:
            vVariants.extend(
                self.characterLookup.getCharacterVariants(variant, 'M'))
            vVariants.extend(
                self.characterLookup.getCharacterVariants(variant, 'P'))
        return char in vVariants

    # Features

    def convertReading(self, readingString, fromReading, toReading=None):
        """
        Converts a string in the source reading to the given target reading.

        :type readingString: str
        :param readingString: string written in the source reading
        :type fromReading: str
        :param fromReading: name of the source reading
        :type toReading: str
        :param toReading: name of the target reading
        :rtype: str
        :return: the input string converted to the ``toReading``
        :raise DecompositionError: if the string can not be decomposed into
            basic entities with regards to the source reading or the given
            information is insufficient.
        :raise CompositionError: if the target reading's entities can not be
            composed.
        :raise ConversionError: on operations specific to the conversion between
            the two readings (e.g. error on converting entities).
        :raise UnsupportedError: if source or target reading is not supported
            for conversion.

        .. todo::
            * Fix: Conversion without tones will mostly break as the target
              reading doesn't support missing tone information. Prefering
              'diacritic' version (Pinyin/CantoneseYale) over 'numbers' as
              tone marks in the absence of any marks would solve this issue
              (forcing fifth tone), but would mean we prefer possible false
              information over the less specific estimation of the given
              entities as missing tonal information.
        """
        if not toReading:
            toReading = self.reading
        options = self.getReadingOptions(readingString, fromReading)
        return self.readingFactory.convert(readingString, fromReading,
            toReading, sourceOptions=options)

    def getCharactersForKangxiRadicalIndex(self, radicalIndex):
        """
        Gets all characters for the given Kangxi radical index grouped by their
        residual stroke count.

        :type radicalIndex: int
        :param radicalIndex: Kangxi radical index
        :rtype: list of str
        :return: list of matching Chinese characters
        """
        strokeCountDict = {}
        for char, residualStrokeCount \
            in self.characterLookup.getResidualStrokeCountForKangxiRadicalIndex(
                radicalIndex):

            if residualStrokeCount not in strokeCountDict:
                strokeCountDict[residualStrokeCount] = set()
            strokeCountDict[residualStrokeCount].add(char)

        return strokeCountDict

    def getCharactersForReading(self, readingString, readingN=None):
        """
        Gets all know characters for the given reading.

        :type readingString: str
        :param readingString: reading entity for lookup
        :type readingN: str
        :param readingN: name of reading
        :rtype: list of str
        :return: list of characters for the given reading
        :raise UnsupportedError: if no mapping between characters and target
            reading exists.
        :raise ConversionError: if conversion from the internal source reading
            to the given target reading fails.
        """
        if not readingN:
            readingN = self.reading
        options = self.getReadingOptions(readingString, readingN)
        return self.characterLookup.getCharactersForReading(readingString,
            readingN, **options)

    def getReadingForCharacters(self, charList):
        """
        Gets a list of readings for a given character string.

        :type charList: list
        :param charList: list of Chinese characters
        :rtype: list of list of str
        :return: a list of readings per character
        :raise exception.UnsupportedError: raised when a translation from
            character to reading is not supported by the given target reading
        :raise exception.ConversionError: if conversion for the string is not
            supported
        """
        readings = []
        for char in charList:
            stringList = self.characterLookup.getReadingForCharacter(char,
                self.reading)
            if stringList:
                readings.append(stringList)
            else:
                readings.append([char])
        return readings

    def getSimplified(self, charList):
        """
        Gets the Chinese simplified character representation for the given
        character string.

        :type charList: list
        :param charList: list of Chinese characters
        :rtype: list of list of str
        :return: list of simplified Chinese characters
        """
        simplified = []
        for char in charList:
            simplifiedVariants \
                = set(self.characterLookup.getCharacterVariants(char, 'S'))
            if self.isSemanticVariant(char, simplifiedVariants):
                simplifiedVariants.add(char)
            if len(simplifiedVariants) == 0:
                simplified.append([char])
            else:
                simplified.append(list(simplifiedVariants))
        return simplified

    def getTraditional(self, charList):
        """
        Gets the traditional character representation for the given character
        string.

        :type charList: list
        :param charList: list of Chinese characters
        :rtype: list of list of str
        :return: list of simplified Chinese characters

        .. todo::
            * Lang: Implementation is too simple to cover all aspects.
        """
        traditional = []
        for char in charList:
            traditionalVariants \
                = set(self.characterLookup.getCharacterVariants(char, 'T'))
            if self.isSemanticVariant(char, traditionalVariants):
                traditionalVariants.add(char)
            if len(traditionalVariants) == 0:
                traditional.append([char])
            else:
                traditional.append(list(traditionalVariants))
        return traditional

    def _createDictionaryInstance(self, **options):
        dictObj = dictionary.getDictionaryClass(
            self.dictionary)

        # handle reading conversion
        if (hasattr(dictObj, 'READING') and dictObj.READING
            and self.readingFactory.isReadingConversionSupported(
                dictObj.READING, self.reading)):
            options['columnFormatStrategies'] = {
                'Reading': dictionary.format.ReadingConversion(
                    self.reading)}

        # handle multiple headwords
        if issubclass(dictObj, dictionary.CEDICT):
            if self.locale == 'C':
                options['entryFactory'] \
                    = dictionary.entry.UnifiedHeadword('s')
            else:
                options['entryFactory'] \
                    = dictionary.entry.UnifiedHeadword('t')

        # create dictionary
        return dictObj(dbConnectInst=self.db, **options)

    def searchDictionary(self, searchString, readingN=None, limit=None):
        """
        Searches the dictionary for matches of the given string.

        :type searchString: str
        :param searchString: search string
        :type readingN: str
        :param readingN: reading name
        :type limit: int
        :param limit: maximum number of entries
        """
        if not hasattr(self, '_dictInstance'):
            self._dictInstance = self._createDictionaryInstance()

        options = self.getReadingOptions(searchString, readingN)

        return self._dictInstance.getFor(searchString, orderBy=['Reading'],
            limit=limit, reading=readingN, **options)

    def searchHeadwords(self, searchString, limit=None):
        """
        Searches the dictionary for substring matches in headwords of the given
        string.

        :type searchString: str
        :param searchString: search string
        :type limit: int
        :param limit: maximum number of entries
        """
        if not hasattr(self, '_dictInstanceHeadwords'):
            self._dictInstanceHeadwords = self._createDictionaryInstance(
                headwordSearchStrategy=ExactMultiple())

        return self._dictInstanceHeadwords.getFor(searchString,
            orderBy=['Reading'], limit=limit)

    def getCharactersForComponents(self, componentList,
        includeEquivalentRadicalForms=True):
        """
        Gets all characters that contain the given components.

        If option ``includeEquivalentRadicalForms`` is set, all equivalent forms
        will be searched for when a Kangxi radical is given.

        :type componentList: list of str
        :param componentList: list of character components
        :type includeEquivalentRadicalForms: bool
        :param includeEquivalentRadicalForms: if ``True`` then characters in the
            given component list are interpreted as representatives for their
            radical and all radical forms are included in the search. E.g. 肉
            will include ⺼ as a possible component.
        :rtype: list of tuple
        :return: list of pairs of matching characters and their *glyphs*
        :raise ValueError: if an invalid *character locale* is specified

        .. todo::
            * Impl: Once mapping of similar radical forms exist (e.g. 言 and 訁)
              include here.
        """
        equivCharTable = self.getEquivalentCharTable(componentList,
            includeEquivalentRadicalForms)
        componentLookupResult \
            = self.characterLookup.getCharactersForEquivalentComponents(
                equivCharTable)
        return [char for char, _ in componentLookupResult]

    def getCharacterInformation(self, char):
        """
        Get the basic information for the given character.

        The following data is collected and returned in a dict:
            - char
            - locale
            - locale name
            - character domain
            - code point hex
            - code point dec
            - type
            - equivalent form (if type is ``'radical'``)
            - radical index
            - radical form (if available)
            - radical variants (if available)
            - stroke count (if available)
            - readings (if type is ``'character'``)
            - variants (if type is ``'character'``)
            - default glyph
            - glyphs

        :type char: str
        :param char: Chinese character
        :rtype: dict
        :return: character information as keyword value pairs
        """
        infoDict = {}

        # general information
        infoDict['char'] = char
        infoDict['locale'] = self.locale
        infoDict['locale name'] = self.CHAR_LOCALE_NAME[self.locale]
        infoDict['characterDomain'] = self.characterLookup.characterDomain
        infoDict['codepoint hex'] = 'U+%04X' % ord(char)
        infoDict['codepoint dec'] = str(ord(char))

        # radical
        if self.characterLookup.isRadicalChar(char):
            infoDict['type'] = 'radical'

            if self.characterLookup.isKangxiRadicalFormOrEquivalent(char):
                infoDict['radical index'] \
                    = self.characterLookup.getKangxiRadicalIndex(char)
            elif self.characterLookupTraditional\
                .isKangxiRadicalFormOrEquivalent(char):
                infoDict['radical index'] = self.characterLookupTraditional\
                    .getKangxiRadicalIndex(char)
            else:
                infoDict['radical index'] = None

            try:
                infoDict['equivalent form'] \
                    = self.characterLookup.getRadicalFormEquivalentCharacter(
                        char)
            except exception.UnsupportedError:
                pass

        else:
            infoDict['type'] = 'character'
            try:
                infoDict['radical index'] = self.characterLookup.getCharacterChineseRadicalIndex(char)
            except exception.NoInformationError:
                infoDict['radical index'] = None

        # regardless of type (radical/radical equivalent/other character) show
        #   radical forms
        if infoDict['radical index']:
            try:
                infoDict['radical form'] \
                    = self.characterLookupTraditional.getKangxiRadicalForm(
                        infoDict['radical index'])
                localeVariantForm \
                    = self.characterLookup.getKangxiRadicalForm(
                        infoDict['radical index'])
                variantList = []
                if localeVariantForm != infoDict['radical form']:
                    variantList.append(localeVariantForm)
                variantList.extend(
                    self.characterLookup.getKangxiRadicalVariantForms(
                        infoDict['radical index']))
                infoDict['radical variants'] = variantList
            except exception.NoInformationError:
                pass

        # stroke count
        try:
            infoDict['stroke count'] = self.characterLookup.getStrokeCount(char)
        except exception.NoInformationError:
            pass

        if not self.characterLookup.isRadicalChar(char):
            # reading information
            infoDict['readings'] = {}

            for readingN in self.readingFactory.getSupportedReadings():
                try:
                    readingList = self.characterLookup.getReadingForCharacter(
                        char, readingN)
                    if readingList:
                        infoDict['readings'][readingN] = readingList
                except exception.UnsupportedError:
                    pass
                except exception.ConversionError:
                    pass

            # character variants
            infoDict['variants'] = {}

            for variantType in self.VARIANT_TYPE_NAMES:
                variants = self.characterLookup.getCharacterVariants(char,
                    variantType)
                if variants:
                    infoDict['variants'][self.VARIANT_TYPE_NAMES[variantType]] \
                        = variants

        try:
            # character decomposition and stroke order
            infoDict['default glyph'] = self.characterLookup.getDefaultGlyph(
                char)
        except exception.NoInformationError:
            pass

        try:
            infoDict['glyphs'] = {}

            for glyph in self.characterLookup.getCharacterGlyphs(char):
                infoDict['glyphs'][glyph] = {}
                # character decomposition
                decomposition = self.characterLookup.getDecompositionTreeList(
                    char, glyph=glyph)

                if decomposition:
                    infoDict['glyphs'][glyph]['decomposition'] \
                        = decomposition

                # stroke order
                try:
                    infoDict['glyphs'][glyph]['stroke count'] \
                        = self.characterLookup.getStrokeCount(char,
                            glyph=glyph)

                    strokes = self.characterLookup.getStrokeOrder(char,
                        glyph=glyph, includePartial=True)
                    if set(strokes) != set([None]):
                        for i in range(len(strokes)):
                            if strokes[i] is None: strokes[i] = '？'
                        infoDict['glyphs'][glyph]['stroke order'] = strokes

                        infoDict['glyphs'][glyph]['stroke order abbrev'] \
                            = self.characterLookup.getStrokeOrderAbbrev(char,
                                glyph=glyph, includePartial=True)
                except exception.NoInformationError:
                    pass
        except exception.NoInformationError:
            pass

        # character domains
        domains = self.characterLookup.getAvailableCharacterDomains()
        infoDict['domains'] = ['Unicode']
        for characterDomain in domains:
            if characterDomain == 'Unicode':
                continue
            # TODO wasting instances here
            charLookup = characterlookup.CharacterLookup('T', characterDomain,
                dbConnectInst=self.db)
            if charLookup.isCharacterInDomain(char):
                infoDict['domains'].append(characterDomain)

        return infoDict


def getPrintableList(stringList, joinString = ""):
    """
    Gets a printable representation for the given list.

    :type stringList: list of list of str
    :param stringList: strings that need to be concatenated for output
    :type joinString: str
    :param joinString: string that concatenates the different values
    :rtype: str
    :return: printable representation for the given list
    """
    joinedStringList = []
    for elem in stringList:
        if len(elem) == 1:
            joinedStringList.append(elem[0])
        else:
            joinedStringList.append("[" + joinString.join(elem) + "]")
    return joinString.join(joinedStringList)

def getDecompositionForList(decompositionList):
    """
    Gets a fixed width string representation of the given decompositions.

    :type decompositionList: list
    :param decompositionList: a list of character decompositions
    :rtype: list of str
    :return: string representation of decomposition
    """
    # process a list of different decompositions
    stringList = []
    for decomposition in decompositionList:
        stringList.extend(getDecompositionForEntry(decomposition))
    return stringList

def getDecompositionForEntry(decomposition):
    """
    Gets a fixed width string representation of the given decomposition.

    :type decomposition: list
    :param decomposition: character decomposition tree
    :rtype: list of str
    :return: string representation of decomposition
    """
    # process one character of a decompositions
    stringList = [""]
    if type(decomposition[0]) != type(()):
        # IDS element
        stringList[0] = decomposition[0]
    else:
        char, _, decompList = decomposition[0]
        stringList[0] = char
        maxLineLen = 0
        for line in getDecompositionForList(decompList):
            # add decomposition of character in new line
            stringList.append(line)
            maxLineLen = max(maxLineLen, len(line))
        # add spaces to right side of first line to shift next character
        stringList[0] = stringList[0] \
            + "".join(["　" for i in range(1, maxLineLen)])
    # process next character and add new lines into list
    if len(decomposition) > 1:
        for i, line in enumerate(getDecompositionForEntry(
            decomposition[1:])):
            # generate new lines if necessary
            if i >= len(stringList):
                stringList.append("　")
            stringList[i] = stringList[i] + line
    return stringList

def usage():
    """
    Prints the usage for this script.
    """
    print("""Usage: hanzi COMMAND
hanzi provides a set of functions for dealing with Chinese characters and
their readings. This tool should provide quick access to the major functions of
the hanzilib library and at the same time demonstrate how the library can be used.

General commands:
  -i, --information=CHAR     print information about the given char
  -a, --by-reading=READING   prints a list of characters for the given reading
  -r, --get-reading=CHARSTR  prints the reading for a given character string
                               (for characters with multiple readings these are
                               grouped in square brackets; shows the character
                               itself if no reading information available)
  -f, --convert-form=CHARSTR converts the given characters from/to Chinese
                               simplified/traditional form (if ambiguous
                               multiple characters are grouped in brackets)
  -q CHARSTR                 performs commands -r and -f in one step
  -k, --by-radicalidx=RADICALIDX
                             get all characters for a radical given by its index
  -p, --by-components=CHARSTR
                             get all characters that include all the chars
                               contained in the given list as component
  -m, --convert-reading=READING
                             converts the given reading from the input reading
                             to the output reading (compatibility needed)
  -s, --source-reading=SOURCE
                             set given reading as input reading
  -t, --target-reading=TARGET
                             set given reading as output reading
  -l, --locale=LOCALE        set locale, i.e. one character out of TCJKV
  -d, --domain=DOMAIN        set character domain, e.g. 'GB2312'
  -L, --list-options         list available options for parameters
  -V, --version              print version number and exit
  -h, --help                 display this help and exit
  --database=DATABASEURL     database url
  -x SEARCHSTR               searches the dictionary (wildcards '_' and '%')
  -y SEARCHSTR               searches the dictionary for headword substrings
  -w, --set-dictionary=DICTIONARY
                             set dictionary""")
# TODO
  #-o, --by-strokes=STROKES   get all characters for a given stroke order
                               #(fuzzy search)

def version():
    """
    Prints the version of this script.
    """
    print("hanzi " + str(__version__) \
        + """\nCopyright (C) 2006-2010 cjklib developers

hanzi is part of hanzilib, which is the successor of cjklib.

cjklib is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version if not otherwise noted.
See the data files for their specific licenses.

cjklib is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with cjklib.  If not, see <http://www.gnu.org/licenses/>.""")

# Alternative reading names lookup
ALTERNATIVE_READING_NAMES = {'Hangul': ['hg'], 'Pinyin': ['py'],
    'WadeGiles': ['wade-giles', 'wg'], 'Jyutping': ['lshk', 'jp'],
    'CantoneseYale': ['cy']}

import argparse

def cmd_lookup(parameter: str, charInfo: CharacterInfo):
    infoDict = charInfo.getCharacterInformation(parameter)

    print(("Information for character " + infoDict['char'] + " (" \
        + infoDict['locale name'] + " locale, " \
        + infoDict['characterDomain'] + ' domain)')\
    )
    print("Unicode codepoint: " + infoDict['codepoint hex'] + " (" \
        + infoDict['codepoint dec'] + ", "+ infoDict['type'] \
        + " form)")
    print("In character domains: " + ', '.join(infoDict['domains']))
    if 'equivalent form' in infoDict:
        print(("Equivalent character form: " \
            + infoDict['equivalent form'])\
        )

    if infoDict['radical index']:
        radicalForms = ""
        if infoDict['radical form']:
            radicalForms = ", radical form: " \
                + infoDict['radical form']
        if infoDict['radical variants']:
            radicalForms = radicalForms + ", variants: " \
                + ", ".join(infoDict['radical variants'])
        print(("Radical index: " + str(infoDict['radical index']) \
            + radicalForms)\
        )

    if 'stroke count' in infoDict:
        strokeCount = str(infoDict['stroke count'])
    else:
        strokeCount = 'N/A'
    print(("Stroke count: " + strokeCount))

    if infoDict['type'] == 'character':
        readingList = list(infoDict['readings'].keys())
        readingList.sort()
        for readingN in readingList:
            print(("Phonetic data (" + readingN + "): " \
                + ", ".join(infoDict['readings'][readingN]))\
            )

        variantList = list(infoDict['variants'].keys())
        variantList.sort()
        for variantType in variantList:
            print((variantType + ': ' \
                + ', '.join(infoDict['variants'][variantType]))\
            )

    glyphList = list(infoDict['glyphs'].keys())
    glyphList.sort()
    for glyph in glyphList:
        if 'stroke count' in infoDict['glyphs'][glyph]:
            strokeCount \
                = str(infoDict['glyphs'][glyph]['stroke count'])
        else:
            strokeCount = 'N/A'
        default = ""
        if glyph == infoDict['default glyph']:
            default = "(*)"
        print("Glyph " + str(glyph) + default + ', stroke count: ' \
            + strokeCount)

        if 'decomposition' in infoDict['glyphs'][glyph]:
            stringList = getDecompositionForList(
                infoDict['glyphs'][glyph]['decomposition'])
            print(("\n".join(stringList)))
        if 'stroke order' in infoDict['glyphs'][glyph]:
            print(("Stroke order: " + ''.join(
                infoDict['glyphs'][glyph]['stroke order']) + ' (' \
                + infoDict['glyphs'][glyph]['stroke order abbrev'] \
                + ')')
            )

HELP = """\
Usage: hanzi <COMMAND> [OPTIONS]

Database Management:
  build                     Initialize the database

Character Lookup:
  lookup <CHAR>             Get detailed information, components, and stroke count
  find --reading <STR>      Search for characters by phonetic reading
  find --radical <IDX>      Search for characters by radical index
  find --comp <CHARS>       Search for characters containing specific components

Text Processing:
  convert-form <TEXT>       Convert between Simplified and Traditional forms
  to-reading <TEXT>         Get the phonetic reading for a string of text
  convert-reading <TEXT>    Convert readings (e.g., Pinyin to Zhuyin)

Dictionary:
  dict install <NAME>       Download and install a specific dictionary
  dict list                 List installed and available dictionaries
  dict use <NAME>           Set the active dictionary
  dict search <QUERY>       Perform wildcard searches on definitions/headwords
  
Global Options:
  -l, --locale <TCJKV>      Set locale (default: C)
  -s, --src <TYPE>          Set source reading type (pinyin, jyutping, etc.)
  -t, --target <TYPE>       Set target reading type
  --json                    Output results in machine-readable JSON format
  -v, --version             Show version
  -h, --help                Show help
"""

from dataclasses import dataclass

# build lookup table for reading input names to reading 
readingLookup = {}
for readingN in reading.ReadingFactory().getSupportedReadings():
    readingLookup[readingN.lower()] = readingN
for readingN in ALTERNATIVE_READING_NAMES:
    # add alternative names
    for name in ALTERNATIVE_READING_NAMES[readingN]:
        readingLookup[name] = readingN

@dataclass
class HanziConfig:
    locale: str | None
    source_reading: str | None
    target_reading: str | None
    domain: str | None
    dictionary: str | None

    def __post_init__(self):
        if self.source_reading is not None:
            if self.source_reading.lower() in readingLookup:
                self.source_reading = readingLookup[self.source_reading.lower()]
            else:
                print(("Error: '%s' is not a valid reading" % self.source_reading
                    ), file=sys.stderr)
                sys.exit(1)
            
        if self.target_reading is not None:
            if self.target_reading.lower() in readingLookup:
                self.target_reading = readingLookup[self.target_reading.lower()]
            else:
                print(("Error: '%s' is not a valid reading" % self.target_reading
                    ), file=sys.stderr)
                sys.exit(1)
            
        if self.locale is not None:
            if self.locale.upper() in 'TCJKV':
                self.locale = self.locale.upper()
            else:
                print(("Error: '%s' is not a valid locale" % self.locale
                    ), file=sys.stderr)
                sys.exit(1)
        
        if self.dictionary is not None:
            dictionaries = dict([(dic.PROVIDES.lower(), dic.PROVIDES) for dic
                in dictionary.getDictionaryClasses()])
            if self.dictionary.lower() in dictionaries:
                self.dictionary = dictionaries[self.dictionary.lower()]
            else:
                print(("Error: '%s' is not a valid dictionary" %
                    self.dictionary), file=sys.stderr)
                sys.exit(1)

    def apply_args(self, args):
        d: dict = args.__dict__
        return type(self)(
            locale = d.get("locale") or self.locale,
            source_reading = d.get("src") or self.source_reading,
            target_reading = d.get("target") or self.target_reading,
            domain = d.get("domain") or self.domain,
            dictionary = d.get("dictionary") or self.dictionary
        )


def new_main():
    parent_parser = argparse.ArgumentParser(add_help=False)
    
    parser = argparse.ArgumentParser(
        prog="hanzi",
        description="""hanzi provides a set of functions for dealing with Chinese characters and
their readings. This tool should provide quick access to the major functions of
the hanzilib library and at the same time demonstrate how the library can be used."""
    )

    # global Options
    parser.add_argument("-v", "--version", action="version", version="%(prog)s 1.0.0")
    parent_parser.add_argument("-l", "--locale", choices=["T", "C", "J", "K", "V"], default="C",
                        help="Set locale (Traditional, Simplified, Japanese, etc.)")
    parent_parser.add_argument("-s", "--src", help="Set source reading type (e.g., pinyin)")
    parent_parser.add_argument("-t", "--target", help="Set target reading type (e.g., zhuyin)")
    parent_parser.add_argument("-d", "--domain", help="Set domain")
    parent_parser.add_argument("-w", "--dictionary", help="Set dictionary")
    # parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # hanzi build
    subparsers.add_parser("build", help="Initialize the database", parents=[parent_parser])

    # hanzi dict
    dict_parser = subparsers.add_parser("dict", help="Dictionary management", parents=[parent_parser])
    dict_sub = dict_parser.add_subparsers(dest="dict_action")

    # hanzi dict install
    install_p = dict_sub.add_parser("install", help="Install a dictionary")
    install_p.add_argument("name", help="Name of the dictionary to install")
    
    # hanzi dict list
    dict_sub.add_parser("list", help="List installed dictionaries")

    # hanzi dict search
    search_p = dict_sub.add_parser("search", help="Search dictionary definitions/headwords")
    search_p.add_argument("query", help="Search string (supports % and _ wildcards)")

    # hanzi lookup
    lookup_p = subparsers.add_parser("lookup", help="Detailed character information", parents=[parent_parser])
    lookup_p.add_argument("char", help="The character to look up")

    # hanzi find
    find_p = subparsers.add_parser("find", help="Search for characters using filters", add_help=False, parents=[parent_parser])
    find_p.add_argument("--reading", help="Filter by phonetic reading")
    find_p.add_argument("--radical", help="Filter by radical index")
    find_p.add_argument("--comp", help="Filter by components (e.g., '日月')")
    find_p.add_argument("--strokes", type=int, help="Filter by total stroke count")

    # hanzi convert-script
    conv_script_p = subparsers.add_parser("convert-script", help="Convert between Simplified/Traditional", parents=[parent_parser])
    conv_script_p.add_argument("text", help="The text string to convert")

    # hanzi to-reading
    to_reading_p = subparsers.add_parser("to-reading", help="Get phonetic reading for a string", parents=[parent_parser])
    to_reading_p.add_argument("text", help="The text string to read")

    # hanzi convert-reading
    phon_p = subparsers.add_parser("convert-reading", help="Convert between reading systems", parents=[parent_parser])
    phon_p.add_argument("text", help="The reading string to convert")

    # hanzi search-
    search_p = subparsers.add_parser("search", help="Wildcard dictionary search", parents=[parent_parser])
    search_p.add_argument("query", help="Search query (use _ or % for wildcards)")
    
    args = parser.parse_args()



    configSettings = getConfigSettings("hanzi")
    # url = configSettings.get("url")
    config = HanziConfig(
        locale = configSettings.get("locale"),
        source_reading = configSettings.get("reading"),
        target_reading = configSettings.get("reading"),
        domain = configSettings.get("domain", "Unicode"),
        dictionary = configSettings.get("dictionary"),
    )

    config = config.apply_args(args)

    try:
        char_info = CharacterInfo(
            charLocale = config.locale,
            readingN = config.target_reading,
            dictionaryN = config.dictionary,
            # dictionaryDatabaseUrl = 
        )
    except ValueError:
        print((("Error: dictionary '%(dict)s' not available."
            "\nInstall by running 'hanzi install-dict %(dict)s'")
                % {'dict': config.dictionary}), file=sys.stderr)
        sys.exit(1)
    
    # Resolved (TODO: remove excess processing)
    config.locale = char_info.locale
    config.dictionary = char_info.dictionary
    
    if not char_info.setCharacterDomain(config.domain):
        print("Warning: Unknown character domain '%s'" \
            % config.domain, file=sys.stderr)
    
    if config.source_reading is None:
        config.source_reading = char_info.reading
    if config.target_reading is None:
        config.target_reading = char_info.reading


    if args.command == "build":
        from hanzilib.build.cli import main
        main()
        return
        
    elif args.command == "dict":
        if args.dict_action == "install":
            from hanzilib.dictionary.install import main
            sys.argv.remove("dict")
            sys.argv.remove("install") # Temporary
            main()
        elif args.dict_action == "list":
            print("Not implemented yet")
    elif args.command == "lookup":
        cmd_lookup(args.char, char_info)
    elif args.command == "find":
        sets: list[set[str]] = []

        try:
            idx = int(args.radical)
        except ValueError:
            print("Radicals can only be specified by KangXi index for now")
            sys.exit(1)

        args.radical = idx

        # special handling if only --radical is specified
        if args.radical is not None and args.reading is None and args.comp is None and args.strokes is None:
            try:
                stroke_counts = char_info.getCharactersForKangxiRadicalIndex(args.radical)
            except ValueError:
                print("Error: bad parameter")
                sys.exit(1)
            for residaul_stroke_count in sorted(stroke_counts.keys()):
                print('+' + str(residaul_stroke_count) + ': ' \
                    + ''.join(stroke_counts[residaul_stroke_count]))
            sys.exit(0)

        if args.radical is not None:
            try:
                stroke_counts = char_info.getCharactersForKangxiRadicalIndex(args.radical)
                sets.append(set(ch for x in stroke_counts.values() for ch in x))
            except ValueError:
                print("Error: --radical: bad parameter")
                sys.exit(1)
        if args.reading is not None:
            try:
                character_list = char_info.getCharactersForReading(args.reading,
                    config.source_reading)
                sets.append(set(character_list))
            except exception.UnsupportedError:
                print("Error: --reading: no character mapping for this reading." \
                    + " Maybe the mapping in question has not been installed.")
                sys.exit(1)
            except exception.ConversionError:
                print("Error: --reading: unable to convert to internal reading")
                sys.exit(1)
        if args.comp is not None:
            componentList = list(args.comp)
            char_list = char_info.getCharactersForComponents(componentList)
            # print(''.join(char_list))
            sets.append(set(char_list))
        
        if len(sets) == 0:
            print(FIND_HELP)
            sys.exit(0)

        result = sets.pop(0)
        for x in sets:
            result.intersection_update(x)
        print(*result, sep="")
    
    elif args.command == "convert-script":
        char_list = list(args.text)
        simplified = getPrintableList(char_info.getSimplified(char_list))
        traditional = getPrintableList(char_info.getTraditional(char_list))
        if not args.text in (simplified, traditional):
            print("Warning: input string has mixed simplified and " \
                + "traditional forms")
        if simplified == traditional:
            print(f"Chinese simplified/Traditional: {simplified}")
        else:
            print(f"Simplified: {simplified}")
            print(f"Traditional: {traditional}")

    elif args.command == "to-reading":
        char_list = list(args.text)
        try:
            readingList = char_info.getReadingForCharacters(char_list)
            print(getPrintableList(readingList, " "))
        except exception.UnsupportedError:
            print("Error: no character mapping for this reading." \
                + " Maybe the mapping in question has not been " \
                + "installed.")
            sys.exit(1)
        except exception.ConversionError:
            print("Error: unable to convert to internal reading")
            sys.exit(1)


    elif args.command == "convert-reading":
        try:
            print(char_info.convertReading(args.text, config.source_reading, config.target_reading))
        except exception.DecompositionError as m:
            print("Error: invalid input string:", \
                str(m))
            sys.exit(1)
        except exception.CompositionError as m:
            print("Error: can't compose target entities:", \
                str(m))
            sys.exit(1)
        except exception.AmbiguousConversionError as m:
            print("Error: input reading is ambiguous, can't convert:", \
                str(m))
            sys.exit(1)
        except exception.ConversionError as m:
            print("Error: can't convert input string:", \
                str(m))
            sys.exit(1)
        except exception.UnsupportedError:
            print("Error: conversion for given readings not supported")
            sys.exit(1)
    

    elif args.command is None:
        parser.print_help()
    
FIND_HELP = """\
usage: hanzi find <FILTERS> [OPTIONS]

FILTERS can be used in combination:
  --reading READING         Filter by phonetic reading
  --radical RADICAL         Filter by radical index (e.g. 30), no support for radical (e.g. '口') for now
  --comp COMP               Filter by components (e.g. '日月')
  --strokes STROKES         Filter by total stroke count

OPTIONS:
  -l {T,C,J,K,V}, --locale {T,C,J,K,V}
                        Set locale (Traditional, Simplified, Japanese, etc.)
  -s SRC, --src SRC     Set source reading type (e.g., pinyin)
  -t TARGET, --target TARGET
                        Set target reading type (e.g., zhuyin)
"""

from functools import wraps

def _handle_interrupt(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except KeyboardInterrupt:
            print("\nKeyboard interrupt.", file=sys.stderr)
            sys.exit(1)
    return wrapper

@_handle_interrupt
def main():
    if "--old" not in sys.argv:
        return new_main()
    sys.argv.remove("--old")

    output_encoding = sys.stdout.encoding or locale.getpreferredencoding() or 'ascii'
    
    if len(sys.argv) == 1:
        sys.argv.append("--help")

    # Temporary measure
    if sys.argv[1] == "install-dict":
        from hanzilib.dictionary.install import main
        sys.argv.remove("install-dict")
        main()
        return
    
    if sys.argv[1] == "build":
        from hanzilib.build.cli import main
        main()
        return
    
    # parse command line parameters
    try:
        opts, _ = getopt.getopt(sys.argv[1:],
            "i:a:r:f:q:k:p:o:m:s:t:l:d:c:b:e:x:y:w:LVh", ["help", "version",
            "locale=", "domain=", "source-reading=", "target-reading=",
            "information=", "by-reading=", "get-reading=", "convert-form=",
            "by-radicalidx=", "by-components=", "by-strokes=",
            "convert-reading=", "set-dictionary=", "list-options", "database="])
    except getopt.GetoptError:
        # print help information and exit
        usage()
        sys.exit(2)

    # build lookup table for reading input names to reading 
    readingLookup = {}
    for readingN in reading.ReadingFactory().getSupportedReadings():
        readingLookup[readingN.lower()] = readingN
    for readingN in ALTERNATIVE_READING_NAMES:
        # add alternative names
        for name in ALTERNATIVE_READING_NAMES[readingN]:
            readingLookup[name] = readingN

    configSettings = getConfigSettings('hanzi')
    url = configSettings.get("url")
    dictionaryN = configSettings.get("dictionary")
    sourceReading = configSettings.get("reading")
    targetReading = configSettings.get("reading")
    charLocale = configSettings.get("locale")
    charDomain = configSettings.get("domain", "Unicode")

    # command that will be executed once all parameters are parsed
    command = None
    parameter = None

    # start to check parameters
    if len(opts) == 0:
        print("Use parameter -h for a short summary on supported functions")

    for o, a in opts:
        # help screen
        if o in ("-h", "--help"):
            usage()
            sys.exit()

        # version message
        elif o in ("-V", "--version"):
            version()
            sys.exit()

        # setting of source reading
        elif o in ("-s", "--source-reading"):
            if a.lower() in readingLookup:
                sourceReading = readingLookup[a.lower()]
            else:
                print(("Error: '%s' is not a valid reading" % a
                    ), file=sys.stderr)
                sys.exit(1)

        # setting of target reading
        elif o in ("-t", "--target-reading"):
            if a.lower() in readingLookup:
                targetReading = readingLookup[a.lower()]
            else:
                print(("Error: '%s' is not a valid reading" % a
                    ), file=sys.stderr)
                sys.exit(1)

        # setting of locale
        elif o in ("-l", "--locale"):
            if a.upper() in 'TCJKV':
                charLocale = a.upper()
            else:
                print(("Error: '%s' is not a valid locale" % a
                    ), file=sys.stderr)
                sys.exit(1)

        # setting of locale
        elif o in ("-d", "--domain"):
            charDomain = a

        # setting of dictionary
        elif o in ("-w", "--set-dictionary"):
            dictionaries = dict([(dic.PROVIDES.lower(), dic.PROVIDES) for dic
                in dictionary.getDictionaryClasses()])
            if a.lower() in dictionaries:
                dictionaryN = dictionaries[a.lower()]
            else:
                print(("Error: '%s' is not a valid dictionary" %
                    a), file=sys.stderr)
                sys.exit(1)

        # setting of database
        elif o in ("--database"):
            url = a

        else:
            # set this as a command executed later
            command = o
            parameter = a

    try:
        charInfo = CharacterInfo(charLocale=charLocale,
            readingN=targetReading, dictionaryN=dictionaryN,
            dictionaryDatabaseUrl=url)
    except ValueError:
        print((("Error: dictionary '%(dict)s' not available."
            "\nInstall by running 'hanzi install-dict %(dict)s'")
                % {'dict': dictionaryN}), file=sys.stderr)
        sys.exit(1)
    
    # resolved parameters
    charLocale = charInfo.locale
    dictionaryN = charInfo.dictionary

    if not charInfo.setCharacterDomain(charDomain):
        print("Warning: Unknown character domain '%s'" \
            % charDomain, file=sys.stderr)

    if not sourceReading:
        sourceReading = charInfo.reading
    if not targetReading:
        targetReading = charInfo.reading

    # execute command

    # character information table
    if command in ("-i", "--information"):
        if len(parameter) == 1:
            infoDict = charInfo.getCharacterInformation(parameter)

            print(("Information for character " + infoDict['char'] + " (" \
                + infoDict['locale name'] + " locale, " \
                + infoDict['characterDomain'] + ' domain)')\
            )
            print("Unicode codepoint: " + infoDict['codepoint hex'] + " (" \
                + infoDict['codepoint dec'] + ", "+ infoDict['type'] \
                + " form)")
            print("In character domains: " + ', '.join(infoDict['domains']))
            if 'equivalent form' in infoDict:
                print(("Equivalent character form: " \
                    + infoDict['equivalent form'])\
                )

            if infoDict['radical index']:
                radicalForms = ""
                if infoDict['radical form']:
                    radicalForms = ", radical form: " \
                        + infoDict['radical form']
                if infoDict['radical variants']:
                    radicalForms = radicalForms + ", variants: " \
                        + ", ".join(infoDict['radical variants'])
                print(("Radical index: " + str(infoDict['radical index']) \
                    + radicalForms)\
                )

            if 'stroke count' in infoDict:
                strokeCount = str(infoDict['stroke count'])
            else:
                strokeCount = 'N/A'
            print(("Stroke count: " + strokeCount))

            if infoDict['type'] == 'character':
                readingList = list(infoDict['readings'].keys())
                readingList.sort()
                for readingN in readingList:
                    print(("Phonetic data (" + readingN + "): " \
                        + ", ".join(infoDict['readings'][readingN]))\
                    )

                variantList = list(infoDict['variants'].keys())
                variantList.sort()
                for variantType in variantList:
                    print((variantType + ': ' \
                        + ', '.join(infoDict['variants'][variantType]))\
                    )

            glyphList = list(infoDict['glyphs'].keys())
            glyphList.sort()
            for glyph in glyphList:
                if 'stroke count' in infoDict['glyphs'][glyph]:
                    strokeCount \
                        = str(infoDict['glyphs'][glyph]['stroke count'])
                else:
                    strokeCount = 'N/A'
                default = ""
                if glyph == infoDict['default glyph']:
                    default = "(*)"
                print("Glyph " + str(glyph) + default + ', stroke count: ' \
                    + strokeCount)

                if 'decomposition' in infoDict['glyphs'][glyph]:
                    stringList = getDecompositionForList(
                        infoDict['glyphs'][glyph]['decomposition'])
                    print(("\n".join(stringList)))
                if 'stroke order' in infoDict['glyphs'][glyph]:
                    print(("Stroke order: " + ''.join(
                        infoDict['glyphs'][glyph]['stroke order']) + ' (' \
                        + infoDict['glyphs'][glyph]['stroke order abbrev'] \
                        + ')')
                    )
        else:
            # encoding errors can lead to a string > 1 char
            print(repr(parameter))
            print("Error: bad parameter or encoding error")
            sys.exit(1)

    elif command in ("-q", "-r", "-f", "--get-reading", "--convert-form"):
        charList = list(parameter)
        # character to reading conversion
        if command in ("-q", "-r", "--get-reading"):
            try:
                readingList = charInfo.getReadingForCharacters(charList)
                print(getPrintableList(readingList, " "))
            except exception.UnsupportedError:
                print("Error: no character mapping for this reading." \
                    + " Maybe the mapping in question has not been " \
                    + "installed.")
                sys.exit(1)
            except exception.ConversionError:
                print("Error: unable to convert to internal reading")
                sys.exit(1)

        # conversion between simplified/traditional forms
        if command in ("-q", "-f", "--convert-form"):
            simplified = getPrintableList(charInfo.getSimplified(charList))
            traditional = getPrintableList(charInfo.getTraditional(
                charList))
            if not parameter in (simplified, traditional):
                print("Warning: input string has mixed simplified and " \
                    + "traditional forms")
            if simplified == traditional:
                print(f"Chinese simplified/Traditional: {simplified}")
            else:
                print(f"Simplified: {simplified}")
                print(f"Traditional: {traditional}")

    # character lookup by reading
    elif command in ("-a", "--by-reading"):
        try:
            characterList = charInfo.getCharactersForReading(parameter,
                sourceReading)
            print("".join(characterList))
        except exception.UnsupportedError:
            print("Error: no character mapping for this reading." \
                + " Maybe the mapping in question has not been installed.")
            sys.exit(1)
        except exception.ConversionError:
            print("Error: unable to convert to internal reading")
            sys.exit(1)

    # character lookup by Kangxi radical index
    elif command in ("-k", "--by-radicalidx"):
        try:
            strokeCountDict = charInfo.getCharactersForKangxiRadicalIndex(
                int(parameter))
            for residualStrokeCount in sorted(strokeCountDict.keys()):
                print('+' + str(residualStrokeCount) + ': ' \
                    + ''.join(strokeCountDict[residualStrokeCount]))
        except ValueError:
            print("Error: bad parameter")
            sys.exit(1)

    # character lookup by components
    elif command in ("-p", "--by-components"):
        componentList = list(parameter)
        charList = charInfo.getCharactersForComponents(componentList)
        print(''.join(charList))

    # TODO
    ## character lookup by stroke order
    #elif command in ("-o", "--by-strokes"):
        #strokeLookupResult = charInfo.getCharactersForStrokeOrderFuzzy(
            #parameter, charLocale, 0.46)
        #strokeLookupResult.sort(reverse=True, key=operator.itemgetter(2))
        #charList = [char for char, _, _ in strokeLookupResult]
        #print ''.join(charList).encode(output_encoding, "replace")

    # reading conversion
    elif command in ("-m", "--convert-reading"):
        try:
            print(charInfo.convertReading(parameter, sourceReading,
                targetReading).encode(output_encoding, "replace"))
        except exception.DecompositionError as m:
            print("Error: invalid input string:", \
                str(m))
            sys.exit(1)
        except exception.CompositionError as m:
            print("Error: can't compose target entities:", \
                str(m))
            sys.exit(1)
        except exception.AmbiguousConversionError as m:
            print("Error: input reading is ambiguous, can't convert:", \
                str(m))
            sys.exit(1)
        except exception.ConversionError as m:
            print("Error: can't convert input string:", \
                str(m))
            sys.exit(1)
        except exception.UnsupportedError:
            print("Error: conversion for given readings not supported")
            sys.exit(1)

    # dictionary search
    elif command == "-x":
        if not charInfo.hasDictionary():
            print(("Error: no dictionary available"
                "\nInstall one by running 'installcjkdict DICTIONARY_NAME'"), file=sys.stderr)
            sys.exit(1)

        results = charInfo.searchDictionary(parameter, sourceReading)
        for entry in results:
            if entry.Reading:
                string = ("%(Headword)s %(Reading)s %(Translation)s"
                    % entry._asdict())
            else:
                string = "%(Headword)s %(Translation)s" % entry._asdict()
            print(string)

    # dictionary search
    elif command == "-y":
        if not charInfo.hasDictionary():
            print(("Error: no dictionary available"
                "\nInstall one by running 'installcjkdict DICTIONARY_NAME'"), file=sys.stderr)
            sys.exit(1)

        results = charInfo.searchHeadwords(parameter)
        for entry in results:
            if entry.Reading:
                string = ("%(Headword)s %(Reading)s %(Translation)s"
                    % entry._asdict())
            else:
                string = "%(Headword)s %(Translation)s" % entry._asdict()
            print(string)

    # TODO deprecated
    elif command in ("-c", "-b", "-e"):
        alternative = parameter
        if command != "-b":
            alternative = '%%%s' % alternative
        if command != "-e":
            alternative = '%s%%' % alternative

        warnings.warn(("Option '%s' is deprecated"
            " and will disappear from future versions."
            " Use '-x \"%s\"' instead")  % (command, alternative),
            category=DeprecationWarning)

        if not charInfo.hasDictionary():
            print("Error: no dictionary available")
            sys.exit(1)

        results = charInfo.searchDictionary(alternative, sourceReading)
        for entry in results:
            if entry.Reading:
                string = ("%(Headword)s %(Reading)s %(Translation)s"
                    % entry._asdict())
            else:
                string = "%(Headword)s %(Translation)s" % entry._asdict()
            print(string)

    # listing of available options for parameter setting
    elif command in ("-L", "--list-options"):
        # locales
        print("Current locale: " + charLocale + " (" \
            + CharacterInfo.CHAR_LOCALE_NAME[charLocale] + ")")
        print("Supported locales: " + ", ".join(
            ["%s: %s" % entry for entry \
                in sorted(CharacterInfo.CHAR_LOCALE_NAME.items())]))
        # character domain
        print("Current character domain: " + charDomain)
        print("Available domains: " + ", ".join(
            charInfo.characterLookup.getAvailableCharacterDomains()))
        # readings
        print("Current source reading: %s" % sourceReading)
        print("Current target reading: %s" % targetReading)
        readingsList = []
        for readingName in reading.ReadingFactory().getSupportedReadings():
            if readingName in ALTERNATIVE_READING_NAMES:
                readingsList.append(readingName + " (" \
                    + ", ".join(ALTERNATIVE_READING_NAMES[readingName]) \
                    + ")")
            else:
                readingsList.append(readingName)
        print("Supported readings: " + ", ".join(readingsList))
        # dictionary
        if dictionaryN:
            print("Current dictionary: %s" % dictionaryN)
        else:
            print("Currently no dictionary set")

        availableDictionaries = charInfo.getAvailableDictionaries()
        if availableDictionaries:
            dictionaryList = []
            for dictionaryName in availableDictionaries:
                dictObj = dictionary.getDictionaryClass(dictionaryName)

                if dictObj.READING:
                    dictionaryList.append("%s (%s)"
                        % (dictionaryName, dictObj.READING))
                else:
                    dictionaryList.append(dictionaryName)
            print("Available dictionaries: " + ", ".join(dictionaryList))
        else:
            print("No dictionaries available")

    else:
        print("Error: command unknown")
        usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
