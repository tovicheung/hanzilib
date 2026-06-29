# This file is part of hanzilib, a fork of cjklib.
#
# hanzilib is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# hanzilib is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with hanzilib.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

__all__ = [
    # abstract
    "ReadingConverter", "DialectSupportReadingConverter",
    "EntityWiseReadingConverter", "RomanisationConverter",
    # X To X
    "PinyinDialectConverter", "WadeGilesDialectConverter",
    "GRDialectConverter", "JyutpingDialectConverter", 
    "CantoneseYaleDialectConverter", "ShanghaineseIPADialectConverter",
    # X To Y
    "PinyinToWadeGilesConverter", "WadeGilesToConverter",
    "PinyinToGRConverter", "GRToPinyinConverter",
    "PinyinToIPAConverter",
    "PinyinToBrailleConverter", "BrailleToPinyinConverter",
    "JyutpingToYaleConverter", "YaleToJyutpingConverter",
    # bridge
    "BridgeConverter",
    ]

import abc
import re
import functools
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.sql import and_

from .. import dbconnector
from ..exception import ConversionError, AmbiguousConversionError,  InvalidEntityError, UnsupportedError
from ..util import titlecase, istitlecase

from . import operator as readingoperator, ReadingFactory, _registry, _bridge_lookup, getReadingConverterClasses
from .readings import Reading
from .types import Entity

if TYPE_CHECKING:
    from .operator import ReadingOperator
    from .converter import ReadingConverter


def register(cls: type[ReadingConverter]):
    _registry["readingConverterClasses"][(cls.SOURCE, cls.TARGET)] = cls
    return cls

class ReadingConverter(abc.ABC):
    """
    Defines an abstract converter between two or more *character readings*.
    This base class handles conversion between text and entities ([de]composition)
    
    Provides:
    * `.convert(string, fromReading, toReading)`

    Subclasses should implement:
    * `.convertEntities(readingEntities, fromReading, toReading)`
    """

    SOURCE: str
    TARGET: str

    def __init__(self,
            dbConnectInst: dbconnector.DatabaseConnector | None = None,
            sourceOperator: ReadingOperator | None = None,
            targetOperator: ReadingOperator | None = None,
        ):
        """
        :param dbConnectInst: instance of a
            :class:`~cjklib.dbconnector.DatabaseConnector`, if none is
            given, default settings will be assumed.
        :param sourceOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling source readings.
        :param targetOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling target readings.
        """

        self.db = dbConnectInst or dbconnector.getDBConnector()
        self._f = ReadingFactory(dbConnectInst=self.db)

        self._sourceOperator = sourceOperator or self._f._getReadingOperatorInstance(self.SOURCE)
        self._targetOperator = targetOperator or self._f._getReadingOperatorInstance(self.TARGET)

    def convert(self, string: str):
        """
        Converts a string in the source reading to the given target reading.

        :type string: str
        :param string: string written in the source reading
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
            * Impl: Make parameters fromReading, toReading optional if only
              one conversion direction is given. Same for
              :meth:`~_reading.converter.ReadingConverter.convertEntities`.
        """
        # decompose string
        fromReadingEntities = self._sourceOperator.decompose(string)
        # convert entities
        toReadingEntities = self.convertEntities(fromReadingEntities)
        # compose string
        return self._targetOperator.compose(toReadingEntities)

    @abc.abstractmethod
    def convertEntities(self, readingEntities: list[Entity]) -> list[Entity]:
        """
        Converts a list of entities in the source reading to the given target
        reading.

        The default implementation will raise a NotImplementedError.

        :type readingEntities: list of str
        :param readingEntities: list of entities written in source reading
        :rtype: list of str
        :return: list of entities written in target reading
        :raise ConversionError: on operations specific to the conversion between
            the two readings (e.g. error on converting entities).
        :raise UnsupportedError: if source or target reading is not supported
            for conversion.
        :raise InvalidEntityError: if an invalid entity is given.
        """
        pass

class DialectSupportReadingConverter(ReadingConverter):
    """
    Defines an abstract :class:`~_reading.converter.ReadingConverter`
    that support non-standard reading representations (dialect) as in- and
    output.

    Input will be converted to a standard representation of the input reading
    before the actual conversion step is done. If needed the converted reading
    will be converted to a defined dialect.

    Provides:
    * `.convertEntities(readingEntities, fromReading, toReading)`

    Subclasses should implement:
    * `.convertEntitySequence(entitySequence, fromReading, toReading)`
    """

    DEFAULT_READING_OPTIONS = {}
    """
    Defines the default reading options for the reading dialect used as a bridge
    in conversion between the user specified representation and the target
    reading.

    The most general reading dialect should be specified as to allow for a broad
    range of input.
    """

    def convertEntities(self, readingEntities):
        """
        Converts a list of entities in the source reading to the given target
        reading.

        :type readingEntities: list of str
        :param readingEntities: list of entities written in source reading
        :rtype: list of str
        :return: list of entities written in target reading
        :raise AmbiguousConversionError: if conversion for a specific entity of
            the source reading is ambiguous.
        :raise ConversionError: on other operations specific to the conversion
            between the two readings (e.g. error on converting entities).
        :raise UnsupportedError: if source or target reading is not supported
            for conversion.
        :raise InvalidEntityError: if an invalid entity is given.
        """
        # Split into reading and non-reading sequences; conversion will only done to reading entities later
        entitySequence: list[list[Entity] | Entity] = [] # contains (list of reading entitites) or non-reading entity
        for entity in readingEntities:
            readingEntitySequence: list[Entity] = []
            # get last reading entity sequence if any
            if entitySequence and isinstance(entitySequence[-1], list):
                readingEntitySequence = entitySequence.pop()

            if self._sourceOperator.isReadingEntity(entity) \
                or self._targetOperator.isFormattingEntity(entity):
                # add reading entity to preceding ones
                readingEntitySequence.append(entity)
                entitySequence.append(readingEntitySequence)
            else:
                if readingEntitySequence:
                    entitySequence.append(readingEntitySequence)
                # append non-reading entity
                entitySequence.append(entity)

        # Convert to standard form (if supported)
        if self._f.isReadingConversionSupported(self.SOURCE, self.SOURCE):
            # get default options if available used for converting the reading dialect
            if self.SOURCE in self.DEFAULT_READING_OPTIONS:
                fromDefaultOptions = self.DEFAULT_READING_OPTIONS[self.SOURCE]
            else:
                fromDefaultOptions = {}
            # use user specified source operator, set target to default form
            converter = self._f._getReadingConverterInstance(self.SOURCE,
                self.SOURCE,
                sourceOperator=self._sourceOperator,
                targetOptions=fromDefaultOptions)

            convertedEntitySequence: list[list[Entity] | Entity] = []
            for sequence in entitySequence:
                if isinstance(sequence, list):
                    # reading entity sequence
                    convertedEntities = converter.convertEntities(sequence)
                    convertedEntitySequence.append(convertedEntities)
                else:
                    convertedEntitySequence.append(sequence)
            entitySequence = convertedEntitySequence

        # Actual conversion
        toEntitySequence = self.convertEntitySequence(entitySequence)

        # Convert to requested form (if supported)
        if self._f.isReadingConversionSupported(self.TARGET, self.TARGET):
            # get default options if available used for converting the reading dialect
            if self.TARGET in self.DEFAULT_READING_OPTIONS:
                toDefaultOptions = self.DEFAULT_READING_OPTIONS[self.TARGET]
            else:
                toDefaultOptions = {}
            # use user specified target operator, set source to default form
            converter = self._f._getReadingConverterInstance(self.TARGET,
                self.TARGET, sourceOptions=toDefaultOptions,
                targetOperator=self._targetOperator)

            convertedEntitySequence = []
            for sequence in toEntitySequence:
                if type(sequence) == type([]):
                    convertedEntities = converter.convertEntities(sequence)
                    convertedEntitySequence.append(convertedEntities)
                else:
                    convertedEntitySequence.append(sequence)
            toEntitySequence = convertedEntitySequence

        # flatten into target entity list
        toReadingEntities = []
        for sequence in toEntitySequence:
            if isinstance(sequence, list):
                toReadingEntities.extend(sequence)
            else:
                toReadingEntities.append(sequence)

        return toReadingEntities

    @abc.abstractmethod
    def convertEntitySequence(self, entitySequence: list[list[Entity] | Entity]):
        """
        Convert a list of reading entities in standard representatinon given by
        :meth:`~_reading.converter.DialectSupportReadingConverter.DEFAULT_READING_OPTIONS`
        and non reading entities from the source reading to the target reading.

        The default implementation will raise a NotImplementedError.

        :type entitySequence: list structure
        :param entitySequence: list of reading entities given as list and
            non-reading entities as single str objects
        :rtype: list structure
        :return: list of converted reading entities given as list and
            non-reading entities as single str objects
        """
        pass


class EntityWiseReadingConverter(ReadingConverter):
    """
    Defines a converter that simply convert one syllable at a time

    Provides:
    * `.convertEntities(readingEntities, fromReading, toReading)`

    Subclasses should implement:
    * `.convertBasicEntity(entity, fromReading, toReading)`
    """
    def convertEntities(self, readingEntities):
        # do a entity wise conversion to the target reading
        toReadingEntities = []
        for entity in readingEntities:
            # convert reading entities, don't convert the rest
            if self._sourceOperator.isReadingEntity(entity):
                toReadingEntity = self.convertBasicEntity(entity)
                toReadingEntities.append(toReadingEntity)
            else:
                toReadingEntities.append(entity)

        return toReadingEntities

    @abc.abstractmethod
    def convertBasicEntity(self, entity: str) -> list[list[Entity] | Entity]:
        """
        Converts a basic entity (e.g. a syllable) in the source reading to the
        given target reading.

        This method is called by
        :meth:`~_reading.converter.EntityWiseReadingConverter.convertEntities`
        and a single entity is given for conversion.

        The default implementation will raise a NotImplementedError.

        :type entity: str
        :param entity: string written in the source reading
        :rtype: str
        :return: the entity converted to the ``toReading``
        :raise AmbiguousConversionError: if conversion for this entity of the
            source reading is ambiguous.
        :raise ConversionError: on other operations specific to the conversion
            of the entity.
        :raise InvalidEntityError: if the entity is invalid.
        """
        pass


class RomanisationConverter(DialectSupportReadingConverter):
    """
    Defines an abstract :class:`~_reading.converter.ReadingConverter`
    between two or more *romanisations*.

    Reading dialects can produce different entities which have to be handled by
    the conversion process. This is realised by converting the given reading
    dialect to a default form, then converting to the default target reading and
    finally converting to the specified target reading dialect. On conversion
    step thus involves three single conversion steps using a default form. This
    default form can be defined in
    :attr:`~_reading.converter.RomanisationConverter.DEFAULT_READING_OPTIONS`.

    Letter case will be transfered between syllables, no special formatting
    according to anyhow defined standards will be guaranteed.
    Letter case will be identified according to three classes: uppercase (all
    case-sensible characters are uppercase), titlecase (all case-sensible
    characters are lowercase except the first case-sensible character),
    lowercase (all case-sensible characters are lowercase). For entities of
    single latin characters uppercase has precedence over titlecase, e.g. *E5*
    will convert to *ÉH* in Cantonese Yale, not to *Éh*. In general letter
    case should be handled outside of cjklib if special formatting is required.

    The class itself can't be used directly, it has to be subclassed and
    :meth:`~_reading.converter.RomanisationConverter.convertBasicEntity`
    has to be implemented, as to make the translation of
    a syllable from one romanisation to another possible.
    """
    def convertEntitySequence(self, entitySequence):
        toEntitySequence: list[list[Entity] | Entity] = []
        for sequence in entitySequence:
            if isinstance(sequence, list):
                toSequence = []
                for entity in sequence:
                    if self._f.isReadingEntity(entity, self.SOURCE,
                        **self.DEFAULT_READING_OPTIONS[self.SOURCE]):
                        toReadingEntity = self.convertBasicEntity(entity.lower())

                        # transfer letter case, target reading dialect will take
                        #   care of final transformation (lower/both)
                        if entity.isupper():
                            toReadingEntity = toReadingEntity.upper()
                        elif istitlecase(entity):
                            toReadingEntity = titlecase(toReadingEntity)

                        toSequence.append(toReadingEntity)
                    else:
                        # formatting entity
                        toSequence.append(entity)
                toEntitySequence.append(toSequence)
            else:
                toEntitySequence.append(sequence)

        return toEntitySequence

    @abc.abstractmethod
    def convertBasicEntity(self, entity: Entity) -> Entity:
        """
        Converts a basic entity (e.g. a syllable) in the source reading to the
        given target reading.

        This method is called by
        :meth:`~_reading.converter.RomanisationConverter.convertEntities`
        and a lower case entity is given for conversion.
        The returned value should be in lower case characters too, as
        :meth:`~_reading.converter.RomanisationConverter.convertEntities`
        will take care of capitalisation.

        If a single entity needs to be converted it is recommended to use
        :meth:`~_reading.converter.RomanisationConverter.convertEntities`
        instead. In the general case it can not be ensured
        that a mapping from one reading to another can be done by the simple
        conversion of a basic entity. One-to-many mappings are possible and
        there is no guarantee that any entity of a reading recognised by
        :meth:`~_reading.operator.ReadingOperator.isReadingEntity`
        will be mapped here.

        The default implementation will raise a NotImplementedError.

        :type entity: str
        :param entity: string written in the source reading in lower case
            letters
        :rtype: str
        :return: the entity converted to the ``toReading`` in lower case
        :raise AmbiguousConversionError: if conversion for this entity of the
            source reading is ambiguous.
        :raise ConversionError: on other operations specific to the conversion
            of the entity.
        :raise InvalidEntityError: if the entity is invalid.
        """
        pass

@register
class PinyinDialectConverter(ReadingConverter):
    """
    Provides a converter for different representations of the Chinese
    romanisation *Hanyu Pinyin*.
    """
    
    SOURCE = TARGET = "Pinyin"

    def __init__(self,
            dbConnectInst: dbconnector.DatabaseConnector | None = None, 
            sourceOperator: ReadingOperator | None = None,
            targetOperator: ReadingOperator | None = None, 
            keepPinyinApostrophes: bool = False,
            breakUpErhua: str = "auto"
        ):
        """
        :param dbConnectInst: instance of a
            :class:`~cjklib.dbconnector.DatabaseConnector`, if none is
            given, default settings will be assumed.
        :param sourceOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling source readings.
        :paramd targetOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling target readings.
        :param keepPinyinApostrophes: if set to ``True`` apostrophes
            separating two syllables in Pinyin will be kept even if not
            necessary. Apostrophes missing according to the given rule will
            be added though.
        :param breakUpErhua: if set to ``'on'`` *Erhua* forms will be
            converted to single syllables with a full *er* syllable regardless
            of the Erhua form setting of the target reading, e.g. *zher* will
            be converted to *zhe*, *er*, if set to ``'auto'`` Erhua forms are
            converted if the given target reading operator doesn't support
            Erhua forms, if set to ``'off'`` Erhua forms will always be
            conserved.
        """
        super().__init__(dbConnectInst, sourceOperator, targetOperator)
        self._sourceOperator: readingoperator.PinyinOperator
        self._targetOperator: readingoperator.PinyinOperator

        self.keepPinyinApostrophes = keepPinyinApostrophes
        self.breakUpErhua = breakUpErhua

        if self.breakUpErhua not in ['on', 'auto', 'off']:
            raise ValueError("Invalid option %s for keyword 'breakUpErhua'"
                % repr(self.breakUpErhua))

        # get Erhua settings, 'twoSyllables' is default
        if self.breakUpErhua == 'on' \
            or (self.breakUpErhua == 'auto' \
                and self._targetOperator.erhua == 'ignore')\
            or (self._targetOperator.erhua == 'twoSyllables'\
            and self._sourceOperator.erhua == 'oneSyllable'):
            # need to convert from one-syllable-form to two-syllables-form
            self._convertErhuaFunc = self.convertToTwoSyllablesErhua
        elif self._targetOperator.erhua == 'oneSyllable'\
            and self._sourceOperator.erhua != 'oneSyllable':
            # need to convert from two-syllables-form to one-syllable-form
            self._convertErhuaFunc = self.convertToSingleSyllableErhua
        elif self._sourceOperator.erhua != 'ignore'\
            and self._targetOperator.erhua == 'ignore':
            # no real conversion but make sure to raise an error for Erhua forms
            self._convertErhuaFunc = self._checkForErhua
        else:
            # do nothing
            self._convertErhuaFunc = lambda x: x

    def convertEntities(self, readingEntities):
        """
        Converts a list of entities in the source reading to the given target
        reading.

        :type readingEntities: list of str
        :param readingEntities: list of entities written in source reading
        :rtype: list of str
        :return: list of entities written in target reading
        :raise AmbiguousConversionError: if conversion for a specific entity of
            the source reading is ambiguous.
        :raise ConversionError: on other operations specific to the conversion
            between the two readings (e.g. error on converting entities).
        :raise UnsupportedError: if source or target reading is not supported
            for conversion.
        :raise InvalidEntityError: if an invalid entity is given.
        """
        # remove apostrophes
        if not self.keepPinyinApostrophes:
            readingEntities = self._sourceOperator.removeApostrophes(readingEntities)

        targetOptions = {}
        for option in ['shortenedLetters', 'yVowel']:
            targetOptions[option] = getattr(self._targetOperator, option)

        # split syllables into plain syllable and tone part
        entityTuples = []
        for entity in readingEntities:
            # convert reading entities, don't convert the rest
            if self._sourceOperator.isReadingEntity(entity):
                # split syllable into plain part and tonal information
                plainSyllable, tone = self._sourceOperator.splitEntityTone(entity)

                entityTuples.append((plainSyllable, tone))
            else:
                entityTuples.append(entity)

        # fix Erhua forms if needed
        entityTuples = self._convertErhuaFunc(entityTuples)

        targetTones = self._targetOperator.getTones()

        # convert
        toReadingEntities = []
        for entry in entityTuples:
            if type(entry) == type(()):
                plainSyllable, tone = entry

                # check if target operator supports missing tones
                if tone not in targetTones:
                    # missing tone not supported, raise a conversion error
                    raise AmbiguousConversionError("Target reading does not " \
                        "support missing tone information")

                plainSyllable = self._sourceOperator.convertPlainEntity(plainSyllable, targetOptions)

                # fix Erhua form if needed
                if plainSyllable.lower() == 'r' \
                    and ((self.breakUpErhua == 'auto' \
                        and self._targetOperator.erhua == 'ignore') \
                        or self.breakUpErhua == 'on'):
                    # transfer letter case, title() cannot be tested, len() == 1
                    if plainSyllable.isupper():
                        plainSyllable = 'ER'
                    else:
                        plainSyllable = 'er'

                # letter case
                if self._targetOperator.case == 'lower':
                    plainSyllable = plainSyllable.lower()

                try:
                    toReadingEntities.append(
                        self._targetOperator.getTonalEntity(
                            plainSyllable, tone))
                except InvalidEntityError as e:
                    # handle this as a conversion error as the converted
                    #   syllable is not accepted by the operator
                    raise ConversionError(*e.args)
            elif entry == self._targetOperator.pinyinApostrophe:
                toReadingEntities.append(
                    self._targetOperator.pinyinApostrophe)
            else:
                toReadingEntities.append(entry)

        return toReadingEntities

    @staticmethod
    def convertToSingleSyllableErhua(entityTuples):
        """
        Converts the various *Erhua* forms in a list of reading entities to
        a representation with one syllable, e.g. ``['tou2', 'r5']`` to
        ``['tour2']``.

        :type entityTuples: list of tuple/str
        :param entityTuples: list of tuples with plain syllable and tone
        :rtype: list of tuple/str
        :return: list of tuples with plain syllable and tone
        """
        convertedTuples = []
        lastEntry = None
        for entry in entityTuples:
            if type(lastEntry) == type(()) and type(entry) == type(()):
                lastPlainSyllable, lastTone = lastEntry
                plainSyllable, _ = entry
                if plainSyllable.lower() == 'r' \
                    and lastPlainSyllable.lower() not in ['e', 'er', 'r', 'n',
                        'ng', 'hng', 'hm', 'm', 'ê']:
                    # merge two syllables and use tone of main syllable
                    convertedTuples.append((lastPlainSyllable + plainSyllable,
                        lastTone))
                    lastEntry = None
                else:
                    convertedTuples.append(lastEntry)
                    lastEntry = entry
            else:
                if lastEntry != None:
                    convertedTuples.append(lastEntry)
                lastEntry = entry
        if lastEntry != None:
            convertedTuples.append(lastEntry)

        return convertedTuples

    @staticmethod
    def convertToTwoSyllablesErhua(entityTuples):
        """
        Converts the various *Erhua* forms in a list of reading entities to
        a representation with two syllable, e.g. ``['tour2']`` to
        ``['tou2', 'r5']``.

        :type entityTuples: list of tuple/str
        :param entityTuples: list of tuples with plain syllable and tone
        :rtype: list of tuple/str
        :return: list of tuples with plain syllable and tone
        """
        convertedTuples = []
        for entry in entityTuples:
            if type(entry) != type(()):
                convertedTuples.append(entry)
            else:
                plainSyllable, tone = entry
                if plainSyllable[-1:].lower() == 'r' \
                    and plainSyllable.lower() not in ['er', 'r']:
                    # split syllable into plain syllable...
                    convertedTuples.append((plainSyllable[:-1], tone))
                    # ...and single 'r'
                    convertedTuples.append((plainSyllable[-1:], 5))
                else:
                    convertedTuples.append(entry)

        return convertedTuples

    @staticmethod
    def _checkForErhua(entityTuples):
        """
        Checks the given entities for Erhua forms and raises a ConversionError.

        :type entityTuples: list of tuple/str
        :param entityTuples: list of tuples with plain syllable and tone
        :rtype: list of tuple/str
        :return: list of tuples with plain syllable and tone
        :raise ConversionError: when an Erhua form is found
        """
        for entry in entityTuples:
            if type(entry) == type(()):
                plainSyllable, _ = entry

                if plainSyllable.endswith('r') and plainSyllable != 'er':
                    raise ConversionError(
                        "Cannot convert Erhua form in syllable '" \
                            + plainSyllable + "'")

        return entityTuples

@register
class WadeGilesDialectConverter(EntityWiseReadingConverter):
    """
    Provides a converter for different representations of the Mandarin Chinese
    romanisation *Wade-Giles*.
    """
    SOURCE = TARGET = "WadeGiles"

    def convertBasicEntity(self, entity):
        # split syllable into plain part and tonal information
        plainSyllable, tone = self._sourceOperator.splitEntityTone(entity)

        targetOptions = {}
        for option in ['diacriticE', 'zeroFinal', 'umlautU',
            'wadeGilesApostrophe', 'useInitialSz']:
            targetOptions[option] = getattr(self._targetOperator,
                option)

        plainSyllable = self._sourceOperator.convertPlainEntity(plainSyllable, targetOptions)

        # fix letter case
        if self._targetOperator.case == 'lower':
            plainSyllable = plainSyllable.lower()

        # get syllable with tone mark
        try:
            return self._targetOperator.getTonalEntity(plainSyllable, tone)
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)
@register
class PinyinToWadeGilesConverter(RomanisationConverter):
    SOURCE = "Pinyin"
    TARGET = "WadeGiles"

    DEFAULT_READING_OPTIONS = {'Pinyin': {'erhua': 'ignore',
        'toneMarkType': 'numbers'}, 'WadeGiles': {}}

    def convertBasicEntity(self, entity):
        # split syllable into plain part and tonal information
        plainSyllable, tone = self._f.splitEntityTone(entity, self.SOURCE,
            **self.DEFAULT_READING_OPTIONS[self.SOURCE])

        # mapping from WG to Pinyin has old, dialect forms, use index
        table = self.db.tables['WadeGilesPinyinMapping']
        transSyllables = self.db.selectScalars(
            select(table.c.WadeGiles)
            .where(
                and_(
                    table.c.Pinyin == plainSyllable,
                    table.c.PinyinIdx == 0
                )
            )
        )
        if len(transSyllables) > 1:
            raise AmbiguousConversionError(
                "conversion for entity '%s' is ambiguous: %s" \
                    % (entity, ', '.join(transSyllables)))
        elif transSyllables:
            transSyllable = transSyllables[0]
        else:
            transSyllable = None

        if not transSyllable:
            raise ConversionError("conversion for entity '" + plainSyllable \
                + "' not supported")

        try:
            return self._f.getTonalEntity(transSyllable, tone, self.TARGET,
                **self.DEFAULT_READING_OPTIONS[self.TARGET])
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

@register
class WadeGilesToPinyinConverter(RomanisationConverter):
    SOURCE = "WadeGiles"
    TARGET = "Pinyin"
    # Use the tone mark type 'numbers' from Pinyin to support missing tonal
    #   information. Erhua furthermore is not supported.
    DEFAULT_READING_OPTIONS = {'Pinyin': {'erhua': 'ignore',
        'toneMarkType': 'numbers'}, 'WadeGiles': {}}

    def convertEntities(self, readingEntities):
        # For conversion from Wade-Giles remove the hyphens that will not be
        #   transfered to Pinyin.
        readingEntities = self._sourceOperator.removeHyphens(
                readingEntities)
        return super().convertEntities(readingEntities)

    def convertBasicEntity(self, entity):
        # split syllable into plain part and tonal information
        plainSyllable, tone = self._f.splitEntityTone(entity, self.SOURCE,
            **self.DEFAULT_READING_OPTIONS[self.SOURCE])

        table = self.db.tables['WadeGilesPinyinMapping']
        transSyllable = self.db.selectScalar(
            select(table.c.Pinyin)
            .where(table.c.WadeGiles == plainSyllable)
        )
        if not transSyllable:
            raise ConversionError("conversion for entity '" + plainSyllable \
                + "' not supported")

        try:
            return self._f.getTonalEntity(transSyllable, tone, self.TARGET,
                **self.DEFAULT_READING_OPTIONS[self.TARGET])
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

@register
class GRDialectConverter(ReadingConverter):
    """
    Provides a converter for different representations of the Chinese
    romanisation *Gwoyeu Romatzyh*.
    """
    SOURCE = TARGET = "GR"

    def __init__(self,
            dbConnectInst: dbconnector.DatabaseConnector | None = None, 
            sourceOperator: ReadingOperator | None = None,
            targetOperator: ReadingOperator | None = None,
            keepGRApostrophes: bool = False,
            breakUpAbbreviated: str = "auto",
        ):
        """
        :param dbConnectInst: instance of a
            :class:`~cjklib.dbconnector.DatabaseConnector`, if none is
            given, default settings will be assumed.
        :param sourceOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling source readings.
        :param targetOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling target readings.
        :param keepGRApostrophes: if set to ``True`` apostrophes separating
            two syllables in Gwoyeu Romatzyh will be kept even if not necessary.
            Apostrophes missing before 0-initials will be added though.
        :param breakUpAbbreviated: if set to ``'on'`` *abbreviated spellings*
            raise ConversionError("conversion for entity '" + plainSyllable \
            will be converted to full entities, e.g. *sherm.me* will be
            converted to *shern.me*, if set to ``'auto'`` abbreviated forms are
            converted if the given target reading operator doesn't support
            those forms, if set to ``'off'`` abbreviated forms will always be
            conserved.

        .. todo::
            * Impl: Strict mode for tone abbreviating spellings. Raise
              AmbiguousConversionError, e.g. raise on *a* which could be
              *.a* or *a*.
            * Impl: Add option to remove hyphens, "A Grammar of Spoken Chinese,
              p. xxii", Conversion to Pinyin can use that.
        """
        super().__init__(dbConnectInst, sourceOperator, targetOperator)

        self.keepGRApostrophes = keepGRApostrophes
        self.breakUpAbbreviated = breakUpAbbreviated

        # conversion of abbreviated forms
        if self.breakUpAbbreviated not in ['on', 'auto', 'off']:
            raise ValueError(
                "Invalid option %s for keyword 'breakUpAbbreviated'"
                    % repr(self.breakUpAbbreviated))

    def convertEntities(self, readingEntities):
        # abbreviated forms
        if self.breakUpAbbreviated == 'on' \
            or (self.breakUpAbbreviated == 'auto' \
                and not self._targetOperator.abbreviations):
            # remove x, v
            readingEntities = self.convertRepetitionMarker(readingEntities)
            # substitute abbreviations
            readingEntities = self.convertAbbreviatedEntities(readingEntities)

        if self.keepGRApostrophes:
            # convert separator apostrophe
            fromApostrophe = self._sourceOperator\
                .grSyllableSeparatorApostrophe
            toApostrophe = self._targetOperator\
                .grSyllableSeparatorApostrophe
            if fromApostrophe != toApostrophe:
                convertedEntities = []
                for entity in readingEntities:
                    if entity == fromApostrophe:
                        convertedEntities.append(toApostrophe)
                    else:
                        convertedEntities.append(entity)
        else:
            # remove syllable separator
            readingEntities = self._sourceOperator\
                .removeApostrophes(readingEntities)

        # capitalisation
        if self._targetOperator.case == 'lower':
            readingEntities = [entity.lower() for entity in readingEntities]

        # convert rhotacised final apostrophe
        fromApostrophe = self._sourceOperator\
            .grRhotacisedFinalApostrophe
        toApostrophe = self._targetOperator\
            .grRhotacisedFinalApostrophe
        if fromApostrophe != toApostrophe:
            readingEntities = [entity.replace(fromApostrophe, toApostrophe) \
                for entity in readingEntities]

        # convert optional neutral tone marker
        fromMarker = self._sourceOperator\
            .optionalNeutralToneMarker
        toMarker = self._targetOperator.optionalNeutralToneMarker
        if fromMarker != toMarker:
            convReadingEntities = []
            for entity in readingEntities:
                if entity.startswith(fromMarker) \
                    and self._sourceOperator.isReadingEntity(
                        entity):
                    entity = entity.replace(fromMarker, toMarker, 1)
                convReadingEntities.append(entity)
            readingEntities = convReadingEntities

        return readingEntities

    def convertRepetitionMarker(self, readingEntities):
        """
        Converts the *repetition markers* *x* and *v* to the full form they
        represent.

        :type readingEntities: list of str
        :param readingEntities: reading entities
        :rtype: list of str
        :return: reading entities with subsituted *repetition markers*
        :raise ConversionError: if repetition markers *x*, *v* don't follow a
            reading entity
        """
        def findReadingEntity(readingEntities, idx):
            while idx >= 0:
                if grOperator.isReadingEntity(readingEntities[idx]):
                    return idx
                idx -= 1

            return -1

        def getRepetitionEntity(repetitionEntity, realEntity):
            if realEntity in repeatLast or realEntity in repeatSecondLast:
                raise ConversionError(
                "Cluster of more than two repetition markers")
            try:
                plainRealEntity, realTone = grOperator.splitEntityTone(
                    realEntity)
                baseTone = grOperator.getBaseTone(realTone)
            except UnsupportedError as e:
                raise ConversionError(
                    "Unabled to get ethymological tone if  '%s': %s"
                    % (realEntity, e))

            toneMapping = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th'}

            if repetitionEntity.startswith('.'):
                tone = '5thToneEtymological%s' % toneMapping[baseTone]
            elif repetitionEntity.startswith(
                grOperator.optionalNeutralToneMarker):
                tone = '%sToneOptional5th' % toneMapping[baseTone]
            else:
                tone = realTone
            return grOperator.getTonalEntity(plainRealEntity, tone)

        repeatedEntities = []
        grOperator = self._sourceOperator

        # Convert repetition markers, go backwards as 'vx' needs the 'x' to
        #   be concious about the preceding 'v'.
        repeatLast = ['x', '.x', grOperator.optionalNeutralToneMarker + 'x']
        repeatSecondLast = ['v', '.v',
            grOperator.optionalNeutralToneMarker + 'v']
        for idx in range(len(readingEntities)-1, -1, -1):
            # test for 'x'
            if readingEntities[idx] in repeatLast:
                targetEntityIdx = findReadingEntity(readingEntities, idx-1)
                if targetEntityIdx < 0:
                    raise ConversionError(
                        "Target syllable not found for repetition marker"
                        "'x' at '%d'" % idx)

                # Check for special case preceding 'v'.
                vMarkerIdx = None
                if readingEntities[targetEntityIdx] in repeatSecondLast:
                    vMarkerIdx = targetEntityIdx
                    targetEntityIdx = findReadingEntity(readingEntities,
                        targetEntityIdx-1)
                    if targetEntityIdx < 0:
                        raise ConversionError(
                            "Target syllable not found for repetition markers"
                            "'vx' at '%d'" % idx)

                # fix tone and append
                repeatedEntities.insert(0, getRepetitionEntity(
                    readingEntities[idx], readingEntities[targetEntityIdx]))

                # For exact marker 'vx' (without whitespace or other
                #   non-reading characters in-between) include all
                #   non-reading entities between target syllables
                if vMarkerIdx != None and vMarkerIdx + 1 == idx:
                    vTargetEntityIdx = findReadingEntity(readingEntities,
                        targetEntityIdx-1)
                    for i in range(targetEntityIdx-1, vTargetEntityIdx, -1):
                        repeatedEntities.insert(0, readingEntities[i])

            # test for 'v'
            elif readingEntities[idx] in repeatSecondLast:
                # Look for second last entity
                targetEntityIdx = findReadingEntity(readingEntities, idx-1)
                targetEntityIdx = findReadingEntity(readingEntities,
                    targetEntityIdx-1)
                if targetEntityIdx < 0:
                    raise ConversionError(
                        "Target syllable not found for repetition marker"
                        "'v' at '%d'" % idx)

                # fix tone and append
                repeatedEntities.insert(0, getRepetitionEntity(
                    readingEntities[idx], readingEntities[targetEntityIdx]))
            else:
                repeatedEntities.insert(0, readingEntities[idx])

        return repeatedEntities

    def convertAbbreviatedEntities(self, readingEntities):
        """
        Converts the abbreviated GR spellings to the full form. Non-abbreviated
        forms will returned unchanged. Takes care of capitalisation.

        Multi-syllable forms may not be separated by whitespaces or other
        entities.

        To also convert *repetition markers* run
        :meth:`~_reading.converter.GRDialectConverter.convertRepetitionMarker`
        first.

        :type readingEntities: list of str
        :param readingEntities: reading entities
        :rtype: list of str
        :return: full entities
        :raise AmbiguousConversionError: if conversion is ambiguous.
        """
        convertedEntities = []
        grOperator = self._sourceOperator

        abbreviatedForms = grOperator.getAbbreviatedForms()
        maxLen = max([len(form) for form in abbreviatedForms])
        i = 0
        while i < len(readingEntities):
            maxLookahead = min(maxLen, len(readingEntities) - i)
            # from max len down to 1, check if this is a abbreviated form
            # testAbbreviationConsistency() from
            #   test.readingconverter.GRDialectConsistencyTest assures
            #   that no abbreviations overlap, so we there's max. one solution
            for entityCount in range(maxLookahead, 0, -1):
                originalEntities = readingEntities[i:i+entityCount]
                entities = [entity.lower() for entity in originalEntities]

                if tuple(entities) in abbreviatedForms:
                    abbrData = grOperator.getAbbreviatedFormData(entities)
                    # get all forms that are neither already full or ignorable
                    fullForms = set([tuple(full) for _, full, info in abbrData \
                        if len(info & set('FI')) == 0])

                    # check for ambiguous mapping
                    if len(fullForms) > 1:
                        full = [' '.join(form) for form in fullForms]
                        raise AmbiguousConversionError(
                            "conversion for entities '%s' is ambiguous: %s" \
                                % (' '.join(entities), ', '.join(full)))
                    elif len(fullForms) == 1:
                        converted = list(fullForms.pop())
                        # get proper letter case
                        if ''.join(originalEntities).isupper():
                            converted = [entity.upper() for entity in converted]
                        elif istitlecase(''.join(originalEntities)):
                            converted[0] = titlecase(converted[0])

                        convertedEntities.extend(converted)
                        i += entityCount

                        break
            else:
                # nothing found, continue to following entities
                convertedEntities.append(readingEntities[i])
                i += 1

        return convertedEntities

@register
class GRToPinyinConverter(RomanisationConverter):
    SOURCE = "GR"
    TARGET = "Pinyin"
    
    DEFAULT_READING_OPTIONS = {'Pinyin': {'erhua': 'oneSyllable'},
        'GR': {'abbreviations': False}}

    def __init__(self,
            dbConnectInst: dbconnector.DatabaseConnector | None = None, 
            sourceOperator: ReadingOperator | None = None,
            targetOperator: ReadingOperator | None = None,
            grOptionalNeutralToneMapping: str = "original",
        ):
        super().__init__(dbConnectInst, sourceOperator, targetOperator)
        self.grOptionalNeutralToneMapping = grOptionalNeutralToneMapping

        if self.grOptionalNeutralToneMapping not in ['original', 'neutral']:
            raise ValueError(
                "Invalid option %s for keyword 'grOptionalNeutralToneMapping'"
                    % repr(self.grOptionalNeutralToneMapping))

        # mapping from GR tones to Pinyin
        self._grToneMapping = dict([(tone, int(tone[0])) \
            for tone in readingoperator.GROperator.TONES])
        # set optional neutral mapping
        if self.grOptionalNeutralToneMapping == 'neutral':
            for tone in ['1stToneOptional5th', '2ndToneOptional5th',
                '3rdToneOptional5th', '4thToneOptional5th']:
                self._grToneMapping[tone] = 5
    

    def convertBasicEntity(self, entity):
        erlhuahForm = False

        if self._grOperator.isRhotacisedReadingEntity(entity):
            # catch Erlhuah in GR
            baseEntities = self._grOperator.getBaseEntitiesForRhotacised(entity)
            if len(baseEntities) > 1:
                raise AmbiguousConversionError(
                    "conversion for entity '%s' is ambiguous (Erlhuah)" \
                        % entity)
            assert(len(baseEntities) == 1)
            plainSyllable, tone = baseEntities.pop()

            erlhuahForm = True
        else:
            # split syllable into plain part and tonal information
            plainSyllable, tone = self._f.splitEntityTone(entity, self.SOURCE,
                **self.DEFAULT_READING_OPTIONS[self.SOURCE])

        table = self.db.tables['PinyinGRMapping']
        transSyllable = self.db.selectScalar(
            select(table.c.Pinyin)
            .where(
                table.c.GR == plainSyllable
            )
        )
        transTone = self._grToneMapping[tone]

        if not transSyllable:
            raise ConversionError("conversion for entity '" + plainSyllable \
                + "' not supported")

        try:
            if erlhuahForm:
                transSyllable += 'r'

            return self._f.getTonalEntity(transSyllable, transTone,
                self.TARGET, **self.DEFAULT_READING_OPTIONS[self.TARGET])
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

    @functools.cached_property
    def _grOperator(self):
        """GROperator instance"""
        return readingoperator.GROperator(**self.DEFAULT_READING_OPTIONS['GR'])

@register
class PinyinToGRConverter(RomanisationConverter):
    SOURCE = "Pinyin"
    TARGET = "GR"
    # GR deals with Erlhuah in one syllable, force on Pinyin. Convert GR
    #   abbreviations to full forms
    DEFAULT_READING_OPTIONS = {'Pinyin': {'erhua': 'oneSyllable'},
        'GR': {'abbreviations': False}}

    _pyToneMapping = {1: '1stTone', 2: '2ndTone', 3: '3rdTone',
            4: '4thTone', 5: None}

    def convertBasicEntity(self, entity):
        erlhuahForm = False

        # split syllable into plain part and tonal information
        plainSyllable, tone = self._f.splitEntityTone(entity, self.SOURCE,
            **self.DEFAULT_READING_OPTIONS[self.SOURCE])

        # reduce Erlhuah form
        if plainSyllable != 'er' and plainSyllable.endswith('r'):
            erlhuahForm = True
            plainSyllable = plainSyllable[:-1]

        table = self.db.tables['PinyinGRMapping']
        transSyllable = self.db.selectScalar(
            select(table.c.GR)
            .where(
                table.c.Pinyin == plainSyllable
            )
        )
        if self._pyToneMapping[tone]:
            transTone = self._pyToneMapping[tone]
        else:
            raise AmbiguousConversionError("conversion for entity '" \
                + plainSyllable + "' with tone '" + str(tone) \
                + "' is ambiguous")

        if not transSyllable:
            raise ConversionError("conversion for entity '" + plainSyllable \
                + "' not supported")

        try:
            if erlhuahForm:
                try:
                    # lookup Erlhuah form for GR
                    return self._grOperator.getRhotacisedTonalEntity(
                        transSyllable, transTone)
                except UnsupportedError as e:
                    # handle this as a conversion error as the there is no
                    #   Erlhuah form given for the given tone
                    raise ConversionError(e)
            else:
                return self._f.getTonalEntity(transSyllable, transTone,
                    self.TARGET, **self.DEFAULT_READING_OPTIONS[self.TARGET])
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

    @functools.cached_property
    def _grOperator(self):
        """GROperator instance"""
        return readingoperator.GROperator(**self.DEFAULT_READING_OPTIONS['GR'])

@register
class PinyinToIPAConverter(DialectSupportReadingConverter):
    """
    Provides a converter between the Mandarin Chinese romanisation
    *Hanyu Pinyin* and the *International Phonetic Alphabet* (*IPA*) for
    Standard Mandarin. This converter provides only basic support for tones and
    the user needs to specify additional means when handling tone sandhi
    occurrences.

    .. todo::
        * Impl: Two different methods for tone sandhi and coarticulation
          effects?
        * Lang: Support for *Erhua* in mapping.
    """

    SOURCE = "Pinyin"
    TARGET = "MandarinIPA"

    DEFAULT_READING_OPTIONS = {'Pinyin': {'erhua': 'ignore',
        'toneMarkType': 'numbers', 'missingToneMark': 'noinfo',
        'case': 'lower'}}
    # TODO once we support Erhua, use oneSyllable form to lookup

    TONEMARK_MAPPING = {1: '1stTone', 2: '2ndTone', 3: '3rdToneRegular',
        4: '4thTone', 5: '5thTone'}

    NEUTRAL_TONE_MAPPING = {'1stTone': '5thToneHalfLow',
        '2ndTone': '5thToneMiddle', '3rdToneRegular': '5thToneHalfHigh',
        '3rdToneLow': '5thToneHalfHigh', '4thTone': '5thToneLow',
        '5thTone': '5thTone', '5thToneHalfHigh': '5thToneHalfHigh',
        '5thToneMiddle': '5thToneMiddle', '5thToneHalfLow':'5thToneHalfLow',
        '5thToneLow': '5thToneLow'}
    """Mapping of neutral tone following another tone."""

    def __init__(self,
            dbConnectInst: dbconnector.DatabaseConnector | None = None, 
            sourceOperator: ReadingOperator | None = None,
            targetOperator: ReadingOperator | None = None,
            sandhiFunction=None,
            coarticulationFunction=None,
        ):
        """
        :param dbConnectInst: instance of a
            :class:`~cjklib.dbconnector.DatabaseConnector`, if none is
            given, default settings will be assumed.
        :param sourceOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling source readings.
        :param targetOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling target readings.
        :param sandhiFunction: a function that handles tonal changes
            and converts a given list of entities to accommodate sandhi
            occurrences, see
            :meth:`~PinyinIPAConverter.lowThirdAndNeutralToneRule`
            for the default implementation.
        :param coarticulationFunction: a function that handles coarticulation
            effects, see
            :meth:`~PinyinIPAConverter.finalECoarticulation`
            for an example implementation.
        """
        super().__init__(dbConnectInst, sourceOperator, targetOperator)

        self.sandhiFunction = sandhiFunction or self.lowThirdAndNeutralToneRule
        self.coarticulationFunction = coarticulationFunction

        # set the sandhiFunction for handling tonal changes
        if self.sandhiFunction and not hasattr(self.sandhiFunction, '__call__'):
            raise ValueError("Non-callable object %s" \
                    % repr(self.sandhiFunction)
                + " for keyword 'sandhiFunction'")

        # set the sandhiFunction for handling general phonological changes
        if self.coarticulationFunction \
            and not hasattr(self.coarticulationFunction, '__call__'):
            raise ValueError("Non-callable object %s" \
                    % repr(self.coarticulationFunction)
                + " for keyword 'coarticulationFunction'")

    def convertEntitySequence(self, entitySequence):
        toEntitySequence = []
        for sequence in entitySequence:
            if type(sequence) == type([]):
                ipaTupelList = []
                for idx, entity in enumerate(sequence):
                    if self._f.isFormattingEntity(entity, self.SOURCE,
                        **self.DEFAULT_READING_OPTIONS[self.SOURCE]):
                        # ignore formatting entities
                        continue
                    # split syllable into plain part and tonal information
                    plainSyllable, tone = self._f.splitEntityTone(entity,
                        self.SOURCE,
                        **self.DEFAULT_READING_OPTIONS[self.SOURCE])

                    transEntry = None
                    if self.coarticulationFunction:
                        transEntry = self.coarticulationFunction(self,
                            sequence[:idx], plainSyllable, tone,
                                sequence[idx+1:])

                    if not transEntry:
                        # standard conversion
                        transEntry = self._convertSyllable(plainSyllable, tone)

                    ipaTupelList.append(transEntry)

                # handle sandhi
                if self._targetOperator.toneMarkType != 'None':
                    if self.sandhiFunction:
                        ipaTupelList = self.sandhiFunction(self, ipaTupelList)

                # get tonal forms
                toSequence = []
                for plainSyllable, tone in ipaTupelList:
                    entity = self._targetOperator.getTonalEntity(
                        plainSyllable, tone)
                    toSequence.append(entity)

                toEntitySequence.append(toSequence)
            else:
                toEntitySequence.append(sequence)

        return toEntitySequence

    def _convertSyllable(self, plainSyllable, tone):
        """
        Converts a single syllable from Pinyin to IPA.

        :type plainSyllable: str
        :param plainSyllable: plain syllable in the source reading
        :type tone: int
        :param tone: the syllable's tone
        :rtype: str
        :return: IPA representation
        """
        # lookup in database
        table = self.db.tables['PinyinIPAMapping']
        transSyllables = self.db.selectScalars(
            select(table.c.IPA)
            .where(
                and_(
                    table.c.Pinyin == plainSyllable,
                    table.c.Feature.in_(['', 'Default'])
                )
            )
        )

        if not transSyllables:
            raise ConversionError("conversion for entity '" + plainSyllable \
                + "' not supported")
        elif len(transSyllables) != 1:
            raise ConversionError("conversion for entity '" + plainSyllable \
                + "' ambiguous")
        if tone:
            transTone = self.TONEMARK_MAPPING[tone]
        else:
            transTone = None

        return transSyllables[0], transTone

    @staticmethod
    def lowThirdAndNeutralToneRule(converterInst, entityTuples):
        """
        Converts ``'3rdToneRegular'`` to ``'3rdToneLow'`` for syllables followed
        by others and ``'5thTone'`` to the respective forms when following
        another syllable.

        This function serves as the default rule and can be overwritten by
        giving a function as option ``sandhiFunction`` on instantiation.

        :type converterInst: instance
        :param converterInst: instance of the PinyinIPA converter
        :type entityTuples: list of tuple/str
        :param entityTuples: a list of tuples and strings. An IPA entity is
            given as a tuple with the plain syllable and its tone, other content
            is given as plain string.
        :rtype: list
        :return: converted entity list

        .. todo::
            * Lang: What to do on several following neutral tones?
        """
        # only convert 3rd tone to lower form when multiple syllables occur
        if len(entityTuples) <= 1:
            return entityTuples

        # convert
        convertedEntities = []
        precedingTone = None
        for idx, entry in enumerate(entityTuples):
            if type(entry) == type(()):
                plainSyllable, tone = entry

                if tone == '5thTone' and precedingTone:
                    tone = PinyinToIPAConverter.NEUTRAL_TONE_MAPPING[precedingTone]
                elif tone == '3rdToneRegular' and idx + 1 != len(entityTuples):
                    tone = '3rdToneLow'
                entry = (plainSyllable, tone)

                precedingTone = tone
            else:
                precedingTone = None

            convertedEntities.append(entry)

        return convertedEntities

    @staticmethod
    def finalECoarticulation(converterInst: PinyinToIPAConverter, leftContext, plainSyllable, tone,
        rightContext):
        """
        Example function for handling coarticulation of final *e* for the
        neutral tone.

        Only syllables with final *e* are considered for other syllables
        ``None`` is returned. This will trigger the regular conversion method.

        :type converterInst: instance
        :param converterInst: instance of the PinyinIPA converter
        :type leftContext: list of tuple/str
        :param leftContext: syllables preceding the syllable in question in the
            source reading
        :type plainSyllable: str
        :param plainSyllable: plain syllable in the source reading
        :type tone: int
        :param tone: the syllable's tone
        :type rightContext: list of tuple/str
        :param rightContext: syllables following the syllable in question in the
            source reading
        :rtype: str
        :return: IPA representation
        """
        if tone == 5:
            _, final = converterInst._sourceOperator.getOnsetRhyme(
                plainSyllable)
            if final == 'e':
                # lookup in database
                table = converterInst.db.tables['PinyinIPAMapping']
                transSyllables = converterInst.db.selectScalars(
                    select(table.c.IPA)
                    .where(
                        and_(
                            table.c.Pinyin == plainSyllable,
                            table.c.Feature == '5thTone'
                        )
                    )
                )
                if not transSyllables:
                    raise ConversionError("conversion for entity '" \
                        + plainSyllable + "' not supported")
                elif len(transSyllables) != 1:
                    raise ConversionError("conversion for entity '" \
                        + plainSyllable + "' and tone '" + str(tone) \
                        + "' ambiguous")

                return transSyllables[0], PinyinToIPAConverter.TONEMARK_MAPPING[tone]

@register
class PinyinToBrailleConverter(DialectSupportReadingConverter):
    SOURCE = "Pinyin"
    TARGET = "MandarinBraille"
    
    DEFAULT_READING_OPTIONS = {'Pinyin': {'erhua': 'ignore',
        'toneMarkType': 'numbers', 'missingToneMark': 'noinfo'}}

    PUNCTUATION_SIGNS_MAPPING = {'。': '⠐⠆', ',': '⠐', '?': '⠐⠄',
        '!': '⠰⠂', ':': '⠒', ';': '⠰', '-': '⠠⠤', '…': '⠐⠐⠐',
        '·': '⠠⠄', '(': '⠰⠄', ')': '⠠⠆', '[': '⠰⠆', ']': '⠰⠆'}
    
    def __init__(self,
            dbConnectInst: dbconnector.DatabaseConnector | None = None, 
            sourceOperator: ReadingOperator | None = None,
            targetOperator: ReadingOperator | None = None,
        ):
        super().__init__(dbConnectInst, sourceOperator, targetOperator)
        # get mappings
        self._createMappings()

        # punctuation mapping
        self._reversePunctuationMapping = {}
        for key in self.PUNCTUATION_SIGNS_MAPPING:
            if key in self._reversePunctuationMapping:
                # ambiguous mapping, so remove
                self._reversePunctuationMapping[key] = None
            else:
                value = self.PUNCTUATION_SIGNS_MAPPING[key]
                self._reversePunctuationMapping[value] = key

        # regex to split out punctuation
        self._pinyinPunctuationRegex = re.compile(r'(' \
            + '|'.join([re.escape(p) for p \
                in list(self.PUNCTUATION_SIGNS_MAPPING.keys())]) \
            + '|.+?)')

        braillePunctuation = list(set(self.PUNCTUATION_SIGNS_MAPPING.values()))
        # longer marks first in regex
        braillePunctuation.sort(key=functools.cmp_to_key(lambda x, y: len(y) - len(x)))
        self._braillePunctuationRegex = re.compile(r'(' \
            + '|'.join([re.escape(p) for p in braillePunctuation]) + '|.+?)')

    def _createMappings(self):
        """
        Creates the mappings of syllable initials and finals from the database.
        """
        # initials
        self._pinyinInitial2Braille = {}

        table = self.db.tables['PinyinBrailleInitialMapping']
        entries = self.db.selectRows(
            select(table.c.PinyinInitial, table.c.Braille)
        )

        for pinyinInitial, brailleChar in entries:
            # Pinyin 2 Braille
            if pinyinInitial in self._pinyinInitial2Braille:
                raise ValueError(
                    "Ambiguous mapping from Pinyin syllable initial to Braille")
            self._pinyinInitial2Braille[pinyinInitial] = brailleChar

        self._pinyinInitial2Braille[''] = ''

        # finals
        self._pinyinFinal2Braille = {}

        table = self.db.tables['PinyinBrailleFinalMapping']
        entries = self.db.selectRows(
            select(table.c.PinyinFinal, table.c.Braille)
        )

        for pinyinFinal, brailleChar in entries:
            # Pinyin 2 Braille
            if pinyinFinal in self._pinyinFinal2Braille:
                raise ValueError(
                    "Ambiguous mapping from Pinyin syllable final to Braille")
            self._pinyinFinal2Braille[pinyinFinal] = brailleChar

        # map ê to same Braille character as e
        self._pinyinFinal2Braille['ê'] = self._pinyinFinal2Braille['e']

    def convertEntitySequence(self, entitySequence):
        toReadingEntities = []
        for sequence in entitySequence:
            if type(sequence) == type([]):
                for entity in sequence:
                    if self._f.isReadingEntity(entity, self.SOURCE,
                        **self.DEFAULT_READING_OPTIONS[self.SOURCE]):
                        toReadingEntity = self.convertBasicEntity(entity)
                        toReadingEntities.append(toReadingEntity)
                    else:
                        toReadingEntities.append(entity)
            else:
                # find punctuation marks
                for subEntity in self._pinyinPunctuationRegex.findall(
                    sequence):
                    if subEntity in self.PUNCTUATION_SIGNS_MAPPING:
                        toReadingEntities.append(
                            self.PUNCTUATION_SIGNS_MAPPING[subEntity])
                    else:
                        toReadingEntities.append(subEntity)
    
        return toReadingEntities

    def convertBasicEntity(self, entity):
        """
        Converts a basic entity (a syllable) in the source reading to the given
        target reading.

        This method is called by
        :meth:`~_reading.converter.PinyinBrailleConverter.convertEntities`
        and a single entity is given for conversion.

        If a single entity needs to be converted it is recommended to use
        :meth:`~_reading.converter.PinyinBrailleConverter.convertEntities`
        instead. In the general case it can not be ensured
        that a mapping from one reading to another can be done by the simple
        conversion of a basic entity. One-to-many mappings are possible and
        there is no guarantee that any entity of a reading recognised by
        :meth:`~_reading.operator.ReadingOperator.isReadingEntity`
        will be mapped here.

        :type entity: str
        :param entity: string written in the source reading in lower case
            letters
        :rtype: str
        :return: the entity converted to the ``toReading`` in lower case
        :raise AmbiguousConversionError: if conversion for this entity of the
            source reading is ambiguous.
        :raise ConversionError: on other operations specific to the conversion
            of the entity.
        :raise InvalidEntityError: if the entity is invalid.
        """
        # split entity into plain part and tonal information
        # if fromReading in self.DEFAULT_READING_OPTIONS:
        #     fromOptions = self.DEFAULT_READING_OPTIONS[fromReading]
        # else:
        #     fromOptions = {}
        # fromOperator = self._f._getReadingOperatorInstance(fromReading,
        #     **fromOptions)

        fromOperator: readingoperator.PinyinOperator = self._sourceOperator

        plainEntity, tone = fromOperator.splitEntityTone(entity)

        # lookup in database
        initial, final = fromOperator.getOnsetRhyme(plainEntity)

        if plainEntity not in ['zi', 'ci', 'si', 'zhi', 'chi', 'shi', 'ri']:
            try:
                transSyllable = self._pinyinInitial2Braille[initial] \
                    + self._pinyinFinal2Braille[final]
            except KeyError:
                raise ConversionError("conversion for entity '" \
                    + plainEntity + "' not supported")
        else:
            try:
                transSyllable = self._pinyinInitial2Braille[initial]
            except KeyError:
                raise ConversionError("conversion for entity '" \
                    + plainEntity + "' not supported")
        
        try:
            return self._targetOperator.getTonalEntity(transSyllable, tone)
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

@register
class BrailleToPinyinConverter(DialectSupportReadingConverter):
    """
    PinyinBrailleConverter defines a converter between the Mandarin Chinese
    romanisation *Hanyu Pinyin* and the *Braille* system for Mandarin Chinese.
    """

    SOURCE = "Braille"
    TARGET = "Pinyin"

    DEFAULT_READING_OPTIONS = {'Pinyin': {'erhua': 'ignore',
        'toneMarkType': 'numbers', 'missingToneMark': 'noinfo'}}

    PUNCTUATION_SIGNS_MAPPING = {'。': '⠐⠆', ',': '⠐', '?': '⠐⠄',
        '!': '⠰⠂', ':': '⠒', ';': '⠰', '-': '⠠⠤', '…': '⠐⠐⠐',
        '·': '⠠⠄', '(': '⠰⠄', ')': '⠠⠆', '[': '⠰⠆', ']': '⠰⠆'}

    def __init__(self,
            dbConnectInst: dbconnector.DatabaseConnector | None = None, 
            sourceOperator: ReadingOperator | None = None,
            targetOperator: ReadingOperator | None = None,
        ):
        """
        :param dbConnectInst: instance of a
            :class:`~cjklib.dbconnector.DatabaseConnector`, if none is
            given, default settings will be assumed.
        :param sourceOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling source readings.
        :param targetOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling target readings.
        """
        super().__init__(dbConnectInst, sourceOperator, targetOperator)
        # get mappings
        self._createMappings()

        # punctuation mapping
        self._reversePunctuationMapping = {}
        for key in self.PUNCTUATION_SIGNS_MAPPING:
            if key in self._reversePunctuationMapping:
                # ambiguous mapping, so remove
                self._reversePunctuationMapping[key] = None
            else:
                value = self.PUNCTUATION_SIGNS_MAPPING[key]
                self._reversePunctuationMapping[value] = key

        # regex to split out punctuation
        self._pinyinPunctuationRegex = re.compile(r'(' \
            + '|'.join([re.escape(p) for p \
                in list(self.PUNCTUATION_SIGNS_MAPPING.keys())]) \
            + '|.+?)')

        braillePunctuation = list(set(self.PUNCTUATION_SIGNS_MAPPING.values()))
        # longer marks first in regex
        braillePunctuation.sort(key=functools.cmp_to_key(lambda x, y: len(y) - len(x)))
        self._braillePunctuationRegex = re.compile(r'(' \
            + '|'.join([re.escape(p) for p in braillePunctuation]) + '|.+?)')

    def _createMappings(self):
        """
        Creates the mappings of syllable initials and finals from the database.
        """
        # initials
        self._braille2PinyinInitial = {}

        table = self.db.tables['PinyinBrailleInitialMapping']
        entries = self.db.selectRows(
            select(table.c.PinyinInitial, table.c.Braille)
        )

        for pinyinInitial, brailleChar in entries:
            # Braille 2 Pinyin
            if brailleChar not in self._braille2PinyinInitial:
                self._braille2PinyinInitial[brailleChar] = set()
            self._braille2PinyinInitial[brailleChar]
        self._braille2PinyinInitial[''] = set([''])

        # finals
        self._braille2PinyinFinal = {}

        table = self.db.tables['PinyinBrailleFinalMapping']
        entries = self.db.selectRows(
            select(table.c.PinyinFinal, table.c.Braille)
        )

        for pinyinFinal, brailleChar in entries:
            # Braille 2 Pinyin
            if brailleChar not in self._braille2PinyinFinal:
                self._braille2PinyinFinal[brailleChar] = set()
            self._braille2PinyinFinal[brailleChar].add(pinyinFinal)

    def convertEntitySequence(self, entitySequence):
        toReadingEntities = []
        for sequence in entitySequence:
            if type(sequence) == type([]):
                for entity in sequence:
                    toReadingEntity = self.convertBasicEntity(entity.lower())
                    toReadingEntities.append(toReadingEntity)
            else:
                # find punctuation marks
                for subEntity in self._braillePunctuationRegex.findall(
                    sequence):
                    if subEntity in self._reversePunctuationMapping:
                        if not self._reversePunctuationMapping[subEntity]:
                            raise AmbiguousConversionError(
                                "conversion for entity '" + subEntity \
                                    + "' is ambiguous")
                        toReadingEntities.append(
                            self._reversePunctuationMapping[subEntity])
                    else:
                        toReadingEntities.append(subEntity)

        return toReadingEntities

    def convertBasicEntity(self, entity):
        """
        Converts a basic entity (a syllable) in the source reading to the given
        target reading.

        This method is called by
        :meth:`~_reading.converter.PinyinBrailleConverter.convertEntities`
        and a single entity is given for conversion.

        If a single entity needs to be converted it is recommended to use
        :meth:`~_reading.converter.PinyinBrailleConverter.convertEntities`
        instead. In the general case it can not be ensured
        that a mapping from one reading to another can be done by the simple
        conversion of a basic entity. One-to-many mappings are possible and
        there is no guarantee that any entity of a reading recognised by
        :meth:`~_reading.operator.ReadingOperator.isReadingEntity`
        will be mapped here.

        :type entity: str
        :param entity: string written in the source reading in lower case
            letters
        :rtype: str
        :return: the entity converted to the ``toReading`` in lower case
        :raise AmbiguousConversionError: if conversion for this entity of the
            source reading is ambiguous.
        :raise ConversionError: on other operations specific to the conversion
            of the entity.
        :raise InvalidEntityError: if the entity is invalid.
        """
        # split entity into plain part and tonal information
        # if fromReading in self.DEFAULT_READING_OPTIONS:
        #     fromOptions = self.DEFAULT_READING_OPTIONS[fromReading]
        # else:
        #     fromOptions = {}
        # fromOperator = self._f._getReadingOperatorInstance(fromReading,
        #     **fromOptions)

        fromOperator: readingoperator.MandarinBrailleOperator = self._sourceOperator

        plainEntity, tone = fromOperator.splitEntityTone(entity)
        # mapping from Braille to Pinyin is ambiguous
        initial, final = fromOperator.getOnsetRhyme(plainEntity)

        # get all possible forms
        forms = []
        for i in self._braille2PinyinInitial[initial]:
            for f in self._braille2PinyinFinal[final]:
                # get Pinyin syllable
                table = self.db.tables['PinyinInitialFinal']
                entry = self.db.selectScalar(
                    select(table.c.Pinyin)
                    .where(
                        and_(
                            table.c.PinyinInitial == i,
                            table.c.PinyinFinal == f
                        )
                    )
                )
                if entry:
                    forms.append(entry)

        # narrow down to possible ones
        if len(forms) > 1:
            for form in forms[:]:
                if not self._targetOperator.isPlainReadingEntity(form):
                    forms.remove(form)
        if not forms:
            raise ConversionError("conversion for entity '" \
                + plainEntity + "' not supported")
        if len(forms) > 1:
            raise AmbiguousConversionError("conversion for entity '" \
                + plainEntity + "' is ambiguous")
        else:
            transSyllable = forms[0]

        try:
            return self._targetOperator.getTonalEntity(transSyllable,
                tone)
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

@register
class JyutpingDialectConverter(EntityWiseReadingConverter):
    """
    Provides a converter for different representations of the Cantonese
    romanisation *Jyutping*.
    """
    SOURCE = TARGET = "Jyutping"

    def convertBasicEntity(self, entity):
        # split syllable into plain part and tonal information
        plainSyllable, tone \
            = self._sourceOperator.splitEntityTone(entity)

        # capitalisation
        if self._targetOperator.case == 'lower':
            plainSyllable = plainSyllable.lower()

        # get syllable with tone mark
        try:
            return self._targetOperator.getTonalEntity(plainSyllable,
                tone)
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

@register
class CantoneseYaleDialectConverter(EntityWiseReadingConverter):
    """
    Provides a converter for different representations of the *Cantonese Yale*
    romanisation system.
    """

    SOURCE = TARGET = "CantoneseYale"

    def convertBasicEntity(self, entity):
        # split syllable into plain part and tonal information
        plainSyllable, tone \
            = self._sourceOperator.splitEntityTone(entity)

        # capitalisation
        if self._targetOperator.case == 'lower':
            plainSyllable = plainSyllable.lower()

        # get syllable with tone mark
        try:
            transEntity = self._targetOperator.getTonalEntity(
                plainSyllable, tone)

            if istitlecase(entity) and not entity.isupper() \
                and transEntity.isupper():
                # don't change uppercase
                transEntity = titlecase(transEntity)
            return transEntity
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

@register
class JyutpingToYaleConverter(RomanisationConverter):
    SOURCE = "Jyutping"
    TARGET = "CantoneseYale"
    
    DEFAULT_READING_OPTIONS = {'Jyutping': {},
        'CantoneseYale': {'toneMarkType': 'internal'}}
        
    DEFAULT_TONE_MAPPING = {1: '1stToneLevel', 2: '2ndTone', 3: '3rdTone',
        4: '4thTone', 5: '5thTone', 6: '6thTone'}
    
    
    def __init__(self,
            dbConnectInst: dbconnector.DatabaseConnector | None = None, 
            sourceOperator: ReadingOperator | None = None,
            targetOperator: ReadingOperator | None = None,
            yaleFirstTone: str = "1stToneLevel",
        ):
        """
        :param dbConnectInst: instance of a
            :class:`~cjklib.dbconnector.DatabaseConnector`, if none is
            given, default settings will be assumed.
        :param sourceOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling source readings.
        :param targetOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling target readings.
        :param yaleFirstTone: tone in Yale which the first tone from Jyutping
            should be mapped to. Value can be ``'1stToneLevel'`` to map to the
            level tone with contour 55 or ``'1stToneFalling'`` to map to the
            falling tone with contour 53. This is only important if the target
            reading dialect uses diacritical tone marks.
        """
        super().__init__(dbConnectInst, sourceOperator, targetOperator)
        self.yaleFirstTone = yaleFirstTone

        # check yaleFirstTone for handling ambiguous conversion of first
        #   tone in Cantonese that has two different representations in Yale,
        #   but only one in Jyutping
        if self.yaleFirstTone not in ['1stToneLevel', '1stToneFalling']:
            raise ValueError("Invalid option %s for keyword 'yaleFirstTone'"
                % repr(self.yaleFirstTone))

        self.defaultToneMapping = self.DEFAULT_TONE_MAPPING.copy()
        self.defaultToneMapping[1] = self.yaleFirstTone

    def convertBasicEntity(self, entity):
        # split syllable into plain part and tonal information
        plainSyllable, tone = self._f.splitEntityTone(entity, self.SOURCE,
            **self.DEFAULT_READING_OPTIONS[self.SOURCE])

        # lookup in database
        
        table = self.db.tables['JyutpingYaleMapping']
        transSyllable = self.db.selectScalar(
            select(table.c.CantoneseYale)
            .where(
                table.c.Jyutping == plainSyllable
            )
        )
        # get tone
        if not tone:
            transTone = None
        else:
            transTone = self.defaultToneMapping[tone]

        if not transSyllable:
            raise ConversionError("conversion for entity '" + plainSyllable \
                + "' not supported")
        try:
            return self._f.getTonalEntity(transSyllable, transTone, self.TARGET,
                **self.DEFAULT_READING_OPTIONS[self.TARGET])
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

@register
class YaleToJyutpingConverter(RomanisationConverter):
    """
    Provides a converter between the Cantonese romanisation systems *Jyutping*
    and *Cantonese Yale*.
    """

    SOURCE = "CantoneseYale"
    TARGET = "Jyutping"
    # use special dialect for Yale to retain information for first tone and
    #   missing tones
    DEFAULT_READING_OPTIONS = {'Jyutping': {},
        'CantoneseYale': {'toneMarkType': 'internal'}}

    DEFAULT_TONE_MAPPING = {1: '1stToneLevel', 2: '2ndTone', 3: '3rdTone',
        4: '4thTone', 5: '5thTone', 6: '6thTone'}
    """
    Mapping of Jyutping tones to Yale tones. Tone 1 can be changed via option
    'yaleFirstTone'.
    """

    def convertBasicEntity(self, entity):
        # split syllable into plain part and tonal information
        plainSyllable, tone = self._f.splitEntityTone(entity, self.SOURCE,
            **self.DEFAULT_READING_OPTIONS[self.SOURCE])

        # lookup in database
        table = self.db.tables['JyutpingYaleMapping']
        transSyllable = self.db.selectScalar(
            select(table.c.Jyutping)
            .where(
                table.c.CantoneseYale == plainSyllable
            )
        )
        # get tone
        if tone:
            # get tone number from first character of string representation
            transTone = int(tone[0])
        else:
            transTone = None
        if not transSyllable:
            raise ConversionError("conversion for entity '" + plainSyllable \
                + "' not supported")
        try:
            return self._f.getTonalEntity(transSyllable, transTone, self.TARGET,
                **self.DEFAULT_READING_OPTIONS[self.TARGET])
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)

@register
class ShanghaineseIPADialectConverter(EntityWiseReadingConverter):
    """
    Provides a converter for different representations of Shanghainese IPA
    forms.
    """

    SOURCE = TARGET = "ShanghaineseIPA"
    _sourceOperator: readingoperator.ShanghaineseIPAOperator

    def convertBasicEntity(self, entity):
        # split syllable into plain part and tonal information
        plainSyllable, tone = self._sourceOperator.splitEntityTone(entity)

        # get syllable with tone mark
        try:
            return self._targetOperator.getTonalEntity(plainSyllable, tone)
        except InvalidEntityError as e:
            # handle this as a conversion error as the converted syllable is not
            #   accepted by the operator
            raise ConversionError(*e.args)


class BridgeConverter(ReadingConverter):
    """
    Provides a :class:`~_reading.converter.ReadingConverter`
    that converts between readings over a third reading called bridge reading.
    """

    def __init__(self,
            fromReading: str,
            toReading: str,
            dbConnectInst: dbconnector.DatabaseConnector | None = None,
            sourceOperator: ReadingOperator | None = None,
            targetOperator: ReadingOperator | None = None,
            **options,
        ):
        """
        :param fromReading: name of the source reading
        :param toReading: name of the target reading
        :param dbConnectInst: instance of a
            :class:`~cjklib.dbconnector.DatabaseConnector`, if none is
            given, default settings will be assumed.
        :param sourceOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling source readings.
        :param targetOperator: the
            :class:`ReadingOperators <_reading.operator.ReadingOperator>`
            used for handling target readings.
        :param options: extra options
        """
        
        # temp
        self.SOURCE = self.fromReading = fromReading # sourceOperator.READING_NAME
        self.TARGET = self.toReading = toReading # targetOperator.READING_NAME

        super().__init__(dbConnectInst, sourceOperator, targetOperator)
        
        # temp
        self.bridgeReading = _bridge_lookup[(self.fromReading, self.toReading)]

        # temp
        converterClassLookup: dict[tuple[str, str], type[ReadingConverter]] = {}
        for (source, target), clss in getReadingConverterClasses().items():
            converterClassLookup[(clss.SOURCE, clss.TARGET)] = clss
        
        def _isolate_options(func, options: dict[str, Any]):
            import inspect
            params = inspect.signature(func).parameters
            return {k: v for k, v in options.items() if k in params}
        
        self.conversionOptions1 = _isolate_options(converterClassLookup[(self.fromReading, self.bridgeReading)].__init__, options)
        self.conversionOptions2 = _isolate_options(converterClassLookup[(self.bridgeReading, self.toReading)].__init__, options)

        self.conversionOptions1["sourceOperator"] = sourceOperator
        self.conversionOptions2["targetOperator"] = targetOperator

    def convertEntities(self, readingEntities: list[str]) -> Reading:
        # to bridge reading
        bridgeReadingEntities = self._f.convertEntities(readingEntities,
            self.fromReading, self.bridgeReading, **self.conversionOptions1)

        # from bridge reading
        toReadingEntities = self._f.convertEntities(bridgeReadingEntities,
            self.bridgeReading, self.toReading, **self.conversionOptions2)

        return toReadingEntities
