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

"""
Character reading based functions (transliterations, romanizations, ...).
"""

__all__ = ['operator', 'converter', 'ReadingFactory']


from ..exception import UnsupportedError
from .. import dbconnector
from . import operator as readingoperator
# from . import converter as readingconverter

import typing
if typing.TYPE_CHECKING:
    from .converter import ReadingConverter
    from .operator import ReadingOperator

from typing import Any
from .readings import Reading, _get_reading_info

# Registry
# the registry also stores reading operators created from database

_registry = {'readingOperatorClasses': {}, 'readingConverterClasses': {}}

def _auto_discover():
    _registry["readingOperatorClasses"].update({
        clss.READING_NAME: clss for name in readingoperator.__all__
        if (clss := getattr(readingoperator, name))
        if issubclass(clss, readingoperator.ReadingOperator) and clss.READING_NAME
    })
    
    # converters = [
    #     clss for name in readingconverter.__all__
    #     if (clss := getattr(readingconverter, name))
    #     if issubclass(clss, readingconverter.ReadingConverter) and clss.CONVERSION_DIRECTIONS
    # ]

    # for c in converters:
    #     for fromReading, toReading in c.CONVERSION_DIRECTIONS:
    #         _registry['readingConverterClasses'][(fromReading, toReading)] = c


# from the original BridgeConverter
_bridges = [('WadeGiles', 'Pinyin', 'MandarinIPA'),
        ('MandarinBraille', 'Pinyin', 'MandarinIPA'),
        ('WadeGiles', 'Pinyin', 'MandarinBraille'),
        ('MandarinBraille', 'Pinyin', 'WadeGiles'),
        ('GR', 'Pinyin', 'WadeGiles'), ('MandarinBraille', 'Pinyin', 'GR'),
        ('WadeGiles', 'Pinyin', 'GR'), ('GR', 'Pinyin', 'MandarinBraille'),
        ('GR', 'Pinyin', 'MandarinIPA'), # TODO remove once there is a proper
                                         #   converter for GR to IPA
        ]

_bridge_lookup = {}
for from_reading, bridge_reading, to_reading in _bridges:
    _bridge_lookup[(from_reading, to_reading)] = bridge_reading



def getReadingOperatorClasses():
    """
    Gets all classes implementing
    :class:`~cjklib.reading.operator.ReadingOperator` from module
    :mod:`cjklib.reading.operator`.

    :rtype: list
    :return: list of all classes inheriting form
        :class:`~cjklib.reading.operator.ReadingOperator`
    """
    return _registry["readingOperatorClasses"]

def getReadingConverterClasses() -> dict[tuple[str, str], type[ReadingConverter]]:
    """
    Gets all classes implementing
    :class:`~cjklib.reading.converter.ReadingConverter` from module
    :mod:`cjklib.reading.converter`.

    :rtype: list
    :return: list of all classes inheriting form
        :class:`~cjklib.reading.converter.ReadingConverter`
    """
    return _registry["readingConverterClasses"]

class ReadingFactory(object):
    """
    Provides an abstract factory for creating
    :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>` and
    :class:`ReadingConverters <cjklib.reading.converter.ReadingConverter>`
    and a façade to directly access the methods offered by these classes.

    Instances of other classes are cached in the background and reused on later
    calls for methods accessed through the façade.
    :meth:`~cjklib.reading.ReadingFactory.createReadingOperator` and
    :meth:`~cjklib.reading.ReadingFactory.createReadingConverter` can be used to
    create new instances for use outside of the ReadingFactory.

    .. todo::
        * Impl: What about hiding of inner classes?
          :meth:`~cjklib.reading.ReadingFactory._checkSpecialOperators`
          method is called for internal converters and for external ones
          delivered by
          :meth:`~cjklib.reading.ReadingFactory.createReadingConverter`.
          Latter method doesn't return internal cached copies though, but
          creates new instances.
          :class:`~cjklib.reading.operator.ReadingOperator` also gets
          copies from ReadingFactory objects for internal instances.
          Sharing saves memory but changing one object
          will affect all other objects using this instance.
        * Impl: General reading options given for a converter with **options
          need to be used on creating a operator. How to raise errors to save
          user of specifying an operator twice, one per options, one per
          concrete instance (similar to sourceOptions and targetOptions)?
    """

    _sharedState = {'readingOperatorClasses': {}, 'readingConverterClasses': {}}
    """
    Dictionary holding global state information used by all instances of the
    ReadingFactory.
    """

    def __init__(self, databaseUrl=None, dbConnectInst=None):
        """
        Initialises the ReadingFactory.

        If no parameters are given default values are assumed for the connection
        to the database. The database connection parameters can be given in
        databaseUrl, or an instance of
        :class:`~cjklib.dbconnector.DatabaseConnector` can be passed in
        dbConnectInst, the latter one being preferred if both are specified.

        :type databaseUrl: str
        :param databaseUrl: database connection setting in the format
            ``driver://user:pass@host/database``.
        :type dbConnectInst: instance
        :param dbConnectInst: instance of a
            :class:`~cjklib.dbconnector.DatabaseConnector`
        """
        # get connector to database
        if dbConnectInst:
            self.db = dbConnectInst
        else:
            self.db = dbconnector.getDBConnector(databaseUrl)
        # create object instance cache if needed, shared with all factories
        #   using the same database connection
        if self.db not in _registry:
            # clear also generates the structure
            self.clearCache()
        
        _auto_discover()
    #{ Meta

    def clearCache(self):
        """Clears cached classes for the current database."""
        # self._sharedState[self.db] = {}
        # self._sharedState[self.db]['readingOperatorInstances'] = {}
        # self._sharedState[self.db]['readingConverterInstances'] = {}
        _registry[self.db] = {}
        _registry[self.db]['readingOperatorInstances'] = {}
        _registry[self.db]['readingConverterInstances'] = {}


    def getSupportedReadings(self) -> list[str]:
        """
        Gets a list of all supported readings.

        :rtype: list of str
        :return: a list of readings a
            :class:`~cjklib.reading.operator.ReadingOperator` is available for
        """
        return list(_registry['readingOperatorClasses'].keys())

    def getReadingOperatorClass(self, reading: str | Reading):
        """
        Gets the :class:`~cjklib.reading.operator.ReadingOperator`'s class
        for the given reading.

        :type readingN: str
        :param readingN: name of a supported reading
        :rtype: classobj
        :return: a :class:`~cjklib.reading.operator.ReadingOperator` class
        :raise UnsupportedError: if the given reading is not supported.
        """
        reading_name, _ = _get_reading_info(reading)
        if reading_name not in _registry['readingOperatorClasses']:
            raise UnsupportedError("reading '%s' not supported" % reading_name)
        return _registry['readingOperatorClasses'][reading_name]

    def createReadingOperator(self, reading: str | Reading, **options):
        """
        Creates an instance of a
        :class:`~cjklib.reading.operator.ReadingOperator` for the given reading.

        :type readingN: str
        :param readingN: name of a supported reading
        :param options: options for the created instance
        :rtype: instance
        :return: a :class:`~cjklib.reading.operator.ReadingOperator` instance
        :raise UnsupportedError: if the given reading is not supported.
        """

        reading_name, reading_opts = _get_reading_info(reading, options)
        operatorClass = self.getReadingOperatorClass(reading_name)

        if 'dbConnectInst' not in reading_opts:
            reading_opts['dbConnectInst'] = self.db
        return operatorClass(**reading_opts)

    def getReadingConverterClass(self, fromReading: str | Reading, toReading: str | Reading):
        """
        Gets the :class:`~cjklib.reading.converter.ReadingConverter`'s class
        for the given source and target reading.

        :type fromReading: str
        :param fromReading: name of the source reading
        :type toReading: str
        :param toReading: name of the target reading
        :rtype: classobj
        :return: a :class:`~cjklib.reading.converter.ReadingConverter` class
        :raise UnsupportedError: if conversion for the given readings is not
            supported.
        """
        from_reading_name, _ = _get_reading_info(fromReading)
        to_reading_name, _ = _get_reading_info(toReading)
        if not self.isReadingConversionSupported(from_reading_name, to_reading_name):
            raise UnsupportedError(
                "conversion from '%s' to '%s' not supported"
                % (from_reading_name, to_reading_name))
        return _registry['readingConverterClasses'][(from_reading_name, to_reading_name)]

    def createReadingConverter(self, fromReading: str | Reading, toReading: str | Reading, allowBridge: bool = True, **options):
        """
        Creates an instance of a
        :class:`~cjklib.reading.converter.ReadingConverter` for the given
        source and target reading and returns it wrapped as a
        :class:`~cjklib.reading.ReadingFactory.SimpleReadingConverterAdaptor`.

        As
        :class:`ReadingConverters <cjklib.reading.converter.ReadingConverter>`
        generally support more than one conversion
        direction the user needs to specify which source and target reading is
        needed on a regular instance. Wrapping the created instance in the
        adaptor gives a simple convert() and convertEntities() routine, such
        that on conversion the source and target readings don't have to be
        specified. Other methods signatures remain unchanged.

        :type fromReading: str
        :param fromReading: name of the source reading
        :type toReading: str
        :param toReading: name of the target reading
        :param options: options for the created instance
        :keyword hideComplexConverter: if true the
            :class:`~cjklib.reading.converter.ReadingConverter` is
            wrapped as a
            :class:`~cjklib.reading.ReadingFactory.SimpleReadingConverterAdaptor`
            (default).
        :keyword sourceOperators: list of
            :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>`
            used for handling source readings.
        :keyword targetOperators: list of :class:`ReadingOperators
            <cjklib.reading.operator.ReadingOperator>` used for handling
            target readings.
        :keyword sourceOptions: dictionary of options to configure the
            :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>`
            used for handling source readings. If an
            operator for the source reading is explicitly specified, no options
            can be given.
        :keyword targetOptions: dictionary of options to configure the
            :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>`
            used for handling target readings. If an
            operator for the target reading is explicitly specified, no options
            can be given.
        :rtype: instance
        :return: a
            :class:`~cjklib.reading.ReadingFactory.SimpleReadingConverterAdaptor`
            or :class:`~cjklib.reading.converter.ReadingConverter` instance
        :raise UnsupportedError: if conversion for the given readings is not
            supported.
        """
        from_reading, to_reading, converter_options = self._resolveConverterArgs(fromReading, toReading, options)
        
        opt = converter_options.copy()
        if 'dbConnectInst' not in opt:
            opt['dbConnectInst'] = self.db

        if not self.isReadingConversionSupported(from_reading.get_name(), to_reading.get_name()):
            if (not allowBridge) or (from_reading.get_name(), to_reading.get_name()) not in _bridge_lookup:
                raise UnsupportedError(
                    "conversion from '%s' to '%s' not supported"
                    % (from_reading.get_name(), to_reading.get_name()))
                        
            from .converter import BridgeConverter
            return BridgeConverter(from_reading.get_name(), to_reading.get_name(), **opt)

        converterClass = self.getReadingConverterClass(from_reading.get_name(), to_reading.get_name())

        return converterClass(**opt)

    def isReadingConversionSupported(self, fromReading, toReading):
        """
        Checks if the conversion from reading A to reading B is supported.

        :rtype: bool
        :return: true if conversion is supported, false otherwise
        """
        return (fromReading, toReading) \
            in _registry['readingConverterClasses']

    def isReadingOperationSupported(self, operation, readingN, **options):
        """
        Returns ``True`` if the given method is supported by the reading.

        :type operation: str
        :param operation: name of method
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: bool
        :return: ``True`` if method is supported, ``False`` otherwise.
        :raise ValueError: if the given method is not covered.
        """
        if not operation in ('decompose', 'compose', 'isReadingEntity',
            'isFormattingEntity',
            # romanisations
            'getDecompositions', 'segment', 'isStrictDecomposition',
            'getReadingEntities', 'getFormattingEntities',
            # Tonal fixed entities
            'getTones', 'getTonalEntity', 'splitEntityTone',
            'getPlainReadingEntities', 'isPlainReadingEntity'):
            raise ValueError("Operation '%s' is not a default reading operation"
                % operation)
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        return hasattr(readingOp, operation)

    # def getDefaultOptions(self, *args):
    #     """
    #     Returns the default options for the
    #     :class:`~cjklib.reading.operator.ReadingOperator` or
    #     :class:`~cjklib.reading.converter.ReadingConverter` applied for
    #     the given reading name or names respectively.

    #     The keyword 'dbConnectInst' is not regarded a configuration option and
    #     is thus not included in the dict returned.

    #     :raise ValueError: if more than one or two reading names are given.
    #     :raise UnsupportedError: if no ReadingOperator or ReadingConverter
    #         exists for the given reading or readings respectively.
    #     """
    #     if len(args) == 1:
    #         return self.getReadingOperatorClass(args[0]).getDefaultOptions()
    #     elif len(args) == 2:
    #         return self.getReadingConverterClass(args[0], args[1])\
    #             .getDefaultOptions()
    #     else:
    #         raise ValueError("Wrong number of arguments")

    def _getReadingOperatorInstance(self, reading: str | Reading, **options) -> ReadingOperator:
        """
        Returns an instance of a
        :class:`~cjklib.reading.operator.ReadingOperator` for the given
        reading from the internal cache and creates it if it doesn't exist yet.

        :type readingN: str
        :param readingN: name of a supported reading
        :param options: additional options for instance
        :rtype: instance
        :return: a :class:`~cjklib.reading.operator.ReadingOperator` instance
        :raise UnsupportedError: if the given reading is not supported.

        .. todo::
            * Impl: Get all options when calculating key for an instance and use
              the information on standard parameters thus minimising
              instances in cache. Same for
              :meth:`~cjklib.reading.ReadingFactory._getReadingConverterInstance`.
        """
        reading_name, reading_opts = _get_reading_info(reading, options)
        # construct key for lookup in cache
        cacheKey = (reading_name, self._getHashableCopy(reading_opts))
        # get cache
        instanceCache = _registry[self.db]['readingOperatorInstances']
        if cacheKey not in instanceCache:
            operatorInst = self.createReadingOperator(reading, **options)
            instanceCache[cacheKey] = operatorInst
        return instanceCache[cacheKey]

    def _getReadingConverterInstance(self, fromReading: str | Reading | type[Reading], toReading: str | Reading | type[Reading], allowBridge: bool = True, **options) -> ReadingConverter:
        """
        Returns an instance of a
        :class:`~cjklib.reading.converter.ReadingConverter` for the given
        source and target reading from the internal cache and creates it
        if it doesn't exist yet.

        :type fromReading: str
        :param fromReading: name of the source reading
        :type toReading: str
        :param toReading: name of the target reading
        :param options: additional options for instance
        :keyword sourceOperators: list of
            :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>`
            used for handling source readings.
        :keyword targetOperators: list of
            :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>`
            used for handling target readings.
        :keyword sourceOptions: dictionary of options to configure the
            :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>`
            used for handling source readings. If an operator for the
            source reading is explicitly specified, no options can be given.
        :keyword targetOptions: dictionary of options to configure the
            :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>`
            used for handling target readings. If an operator for the
            target reading is explicitly specified, no options can be given.
        :rtype: instance
        :return: an :class:`~cjklib.reading.converter.ReadingConverter` instance
        :raise UnsupportedError: if conversion for the given readings are not
            supported.

        .. todo::
            * Fix: Reusing of instances for other supported conversion
              directions isn't that efficient if a special ReadingOperator
              is specified for one direction, that doesn't affect others.
        """
        from_reading, to_reading, converter_options = self._resolveConverterArgs(fromReading, toReading, options)
        
        temp = self._getHashableCopy(converter_options)
        cacheKey = (from_reading, to_reading, temp)
        instanceCache = _registry[self.db]['readingConverterInstances']

        if cacheKey not in instanceCache:
            converterInst = self.createReadingConverter(from_reading, to_reading, allowBridge, **converter_options)
            # print()
            # print("CREATED CONVERTER", from_reading, to_reading, converter_options)
            # print()

            # use instance for all supported conversion directions
            # for convFromReading, convToReading in converterInst.CONVERSION_DIRECTIONS:
            #     oCacheKey = (Reading.from_name(convFromReading), Reading.from_name(convToReading), temp)
            #     if oCacheKey not in instanceCache:
            #         instanceCache[oCacheKey] = converterInst
            #         print(oCacheKey)
            #         print()

            instanceCache[cacheKey] = converterInst
        return instanceCache[cacheKey]
    
    def _resolveConverterArgs(self, fromReading: str | Reading | type[Reading], toReading: str | Reading | type[Reading], options: dict[str, Any]) -> tuple[Reading, Reading, dict[str, Any]]:
        """
        Resolve into the standard form of args:
        (fromReading: Reading, toReading: Reading, options)
        **options is passed into converter

        Precedence:
        * options.source_operator and .target_operator
        * options.sourceOptions and options.targetOptions
        * fields of fromReading and toReading
        * defaults of fromReading and toReading

        After processing, sourceOptions and targetOptions should not be present in options
        
        fromReading and toReading should be Reading objects that are consistent with
        options.source_operator and .target_operator (for cache key purposes)
        """

        # ensure correct reading types

        from .operator import ReadingOperator
        if "source_operator" in options:
            source_operator = options["source_operator"]
            if not isinstance(source_operator, ReadingOperator):
                raise TypeError # todo
            assert source_operator.READING_NAME == _get_reading_info(fromReading)[0]

            from_reading = Reading.from_operator(source_operator)
        else:
            source_options = _get_reading_info(fromReading)[1] | options.get("sourceOptions", {})
            options["source_operator"] = self._getReadingOperatorInstance(_get_reading_info(fromReading)[0], **source_options)

            from_reading = Reading.from_operator(options["source_operator"]) # temp
            
        if "target_operator" in options:
            target_operator = options["target_operator"]
            if not isinstance(target_operator, ReadingOperator):
                raise TypeError # todo
            assert target_operator.READING_NAME == _get_reading_info(toReading)[0]

            to_reading = Reading.from_operator(target_operator)
        else:
            target_options = _get_reading_info(toReading)[1] | options.get("targetOptions", {})
            options["target_operator"] = self._getReadingOperatorInstance(_get_reading_info(toReading)[0], **target_options)
            
            to_reading = Reading.from_operator(options["target_operator"])

        options.pop("sourceOptions", None)
        options.pop("targetOptions", None)

        return from_reading, to_reading, options

    @staticmethod
    def _getHashableCopy(data):
        """
        Constructs a unique hashable (partially deep-)copy for a given instance,
        replacing non-hashable datatypes ``set``, ``dict`` and ``list``
        recursively.

        :param data: non-hashable object
        :return: hashable object, ``set`` converted to a ``frozenset``, ``dict``
            converted to a ``frozenset`` of key-value-pairs (tuple), and ``list``
            converted to a ``tuple``.
        """
        if type(data) == type([]) or type(data) == type(()):
            newList = []
            for entry in data:
                newList.append(ReadingFactory._getHashableCopy(entry))
            return tuple(newList)
        elif type(data) == type(set([])):
            newSet = set([])
            for entry in data:
                newSet.add(ReadingFactory._getHashableCopy(entry))
            return frozenset(newSet)
        elif type(data) == type({}):
            newDict = {}
            for key in data:
                newDict[key] = ReadingFactory._getHashableCopy(data[key])
            return frozenset(list(newDict.items()))
        else:
            return data

    def convert(self, readingStr: str, fromReading: str | Reading | type[Reading], toReading: str | Reading | type[Reading], *, allowBridge: bool = True, sourceOptions: dict[str, Any] | None = None, targetOptions: dict[str, Any] | None = None, **options):
        options = options.copy()
        if sourceOptions:
            options["sourceOptions"] = sourceOptions
        if targetOptions:
            options["targetOptions"] = targetOptions

        readingConv = self._getReadingConverterInstance(fromReading, toReading, allowBridge=allowBridge, **options)
        return readingConv.convert(readingStr)

    def convertEntities(self, readingEntities, fromReading, toReading, **options):
        """
        Converts a list of entities in the source reading to the given target
        reading.

        :type readingEntities: list of str
        :param readingEntities: list of entities written in source reading
        :type fromReading: str
        :param fromReading: name of the source reading
        :type toReading: str
        :param toReading: name of the target reading
        :param options: additional options for handling the input
        :keyword sourceOperators: list of :class:`ReadingOperators
            <cjklib.reading.operator.ReadingOperator>` used for handling
            source readings.
        :keyword targetOperators: list of :class:`ReadingOperators
            <cjklib.reading.operator.ReadingOperator>` used for handling
            target readings.
        :keyword sourceOptions: dictionary of options to configure the
            :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>`
            used for handling source readings. If an
            operator for the source reading is explicitly specified, no options
            can be given.
        :keyword targetOptions: dictionary of options to configure the
            :class:`ReadingOperators <cjklib.reading.operator.ReadingOperator>`
            used for handling target readings. If an
            operator for the target reading is explicitly specified, no options
            can be given.
        :rtype: list of str
        :return: list of entities written in target reading
        :raise ConversionError: on operations specific to the conversion between
            the two readings (e.g. error on converting entities).
        :raise UnsupportedError: if source or target reading is not supported
            for conversion.
        :raise InvalidEntityError: if an invalid entity is given.
        """
        readingConv = self._getReadingConverterInstance(fromReading, toReading, **options)
        return readingConv.convertEntities(readingEntities)

    def decompose(self, string, readingN, **options):
        """
        Decomposes the given string into basic entities that can be mapped to
        one Chinese character each for the given reading.

        The given input string can contain other non reading characters, e.g.
        punctuation marks.

        The returned list contains a mix of basic reading entities and other
        characters e.g. spaces and punctuation marks.

        :type string: str
        :param string: reading string
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: list of str
        :return: a list of basic entities of the input string
        :raise DecompositionError: if the string can not be decomposed.
        :raise UnsupportedError: if the given reading is not supported.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        return readingOp.decompose(string)

    def compose(self, readingEntities, readingN, **options):
        """
        Composes the given list of basic entities to a string for the given
        reading.

        Composing entities can raise a :exc:`~cjklib.exception.CompositionError`
        if a non-reading entity is about to be joined with a reading entity
        and will result in a string that is impossible to decompose.

        :type readingEntities: list of str
        :param readingEntities: list of basic syllables or other content
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: str
        :return: composed entities
        :raise CompositionError: if the given entities can not be composed.
        :raise UnsupportedError: if the given reading is not supported.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        return readingOp.compose(readingEntities)

    def isReadingEntity(self, entity, readingN, **options):
        """
        Returns ``True`` if the given entity is a valid *reading entity*
        recognised by the reading operator, i.e. it will be returned by
        :meth:`~cjklib.reading.ReadingFactory.decompose`.

        :type entity: str
        :param entity: entity to check
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: bool
        :return: ``True`` if string is an entity of the reading, false otherwise.
        :raise UnsupportedError: if the given reading is not supported.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        return readingOp.isReadingEntity(entity)

    def isFormattingEntity(self, entity, readingN, **options):
        """
        Returns ``True`` if the given entity is a valid *formatting entity*
        recognised by the reading operator.

        :type entity: str
        :param entity: entity to check
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: bool
        :return: ``True`` if string is a formatting entity of the reading.
        :raise UnsupportedError: if the given reading is not supported.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        return readingOp.isFormattingEntity(entity)

    def getDecompositions(self, string, readingN, **options):
        """
        Decomposes the given string into basic entities that can be mapped to
        one Chinese character each for ambiguous decompositions. It all possible
        decompositions. This method is a more general version of
        :meth:`~cjklib.reading.ReadingFactory.decompose`.

        The returned list construction consists of two entity types: entities of
        the romanisation and other strings.

        :type string: str
        :param string: reading string
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: list of list of str
        :return: a list of all possible decompositions consisting of basic
            entities.
        :raise DecompositionError: if the given string has a wrong format.
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'getDecompositions'):
            raise UnsupportedError("method 'getDecompositions' not supported")
        return readingOp.getDecompositions(string)

    def segment(self, string: str, readingN: str, **options):
        """
        Takes a string written in the romanisation and returns the possible
        segmentations as a list of syllables.

        In contrast to :meth:`~cjklib.reading.ReadingFactory.decompose`
        this method merely segments continuous entities of the romanisation.
        Characters not part of the romanisation will not be dealt with,
        this is the task of the more general decompose method.

        :type string: str
        :param string: reading string
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: list of list of str
        :return: a list of possible segmentations (several if ambiguous) into
            single syllables
        :raise DecompositionError: if the given string has an invalid format.
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'segment'):
            raise UnsupportedError("method 'segment' not supported")
        return readingOp.segment(string)

    def isStrictDecomposition(self, decomposition, readingN, **options):
        """
        Checks if the given decomposition follows the romanisation format
        strictly to allow unambiguous decomposition.

        The romanisation should offer a way/protocol to make an unambiguous
        decomposition into it's basic syllables possible as to make the process
        of appending syllables to a string reversible. The testing on compliance
        with this protocol has to be implemented here. Thus this method can only
        return true for one and only one possible decomposition for all strings.

        :type decomposition: list of str
        :param decomposition: decomposed reading string
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: bool
        :return: False, as this methods needs to be implemented by the sub class
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'isStrictDecomposition'):
            raise UnsupportedError(
                "method 'isStrictDecomposition' not supported")
        return readingOp.isStrictDecomposition(decomposition)

    def getReadingEntities(self, readingN, **options):
        """
        Gets a set of all entities supported by the reading.

        The list is used in the segmentation process to find entity boundaries.

        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: set of str
        :return: set of supported *reading entities*
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'getReadingEntities'):
            raise UnsupportedError("method 'getReadingEntities' not supported")
        return readingOp.getReadingEntities()

    def getFormattingEntities(self, readingN, **options):
        """
        Gets a set of entities used by the reading to format
        *reading entities*.

        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: set of str
        :return: set of supported formatting entities
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'getFormattingEntities'):
            raise UnsupportedError(
                "method 'getFormattingEntities' not supported")
        return readingOp.getFormattingEntities()

    #}
    #{ TonalFixedEntityOperator methods

    def getTones(self, readingN, **options):
        """
        Returns a set of tones supported by the reading.

        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: list
        :return: list of supported tone marks.
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'getTones'):
            raise UnsupportedError("method 'getTones' not supported")
        return readingOp.getTones()

    def getTonalEntity(self, plainEntity, tone, readingN, **options):
        """
        Gets the entity with tone mark for the given plain entity and tone. The
        letter case of the given plain entity might not be fully conserved for
        mixed case strings.

        :type plainEntity: str
        :param plainEntity: entity without tonal information
        :param tone: tone
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: str
        :return: entity with appropriate tone
        :raise InvalidEntityError: if the entity is invalid.
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'getTonalEntity'):
            raise UnsupportedError("method 'getTonalEntity' not supported")
        return readingOp.getTonalEntity(plainEntity, tone)

    def splitEntityTone(self, entity, readingN, **options):
        """
        Splits the entity into an entity without tone mark (plain entity) and
        the entity's tone. The letter case of the given entity might not be
        fully conserved for mixed case strings.

        :type entity: str
        :param entity: entity with tonal information
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: tuple
        :return: plain entity without tone mark and entity's tone
        :raise InvalidEntityError: if the entity is invalid.
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'splitEntityTone'):
            raise UnsupportedError("method 'splitEntityTone' not supported")
        return readingOp.splitEntityTone(entity)

    def getPlainReadingEntities(self, readingN, **options):
        """
        Gets the list of plain entities supported by this reading. Different to
        :meth:`~cjklib.reading.ReadingFactory.getReadingEntities`
        the entities will carry no tone mark.

        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: set of str
        :return: set of supported syllables
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'getPlainReadingEntities'):
            raise UnsupportedError(
                "method 'getPlainReadingEntities' not supported")
        return readingOp.getPlainReadingEntities()

    def isPlainReadingEntity(self, entity, readingN, **options):
        """
        Returns true if the given plain entity (without any tone mark) is
        recognised by the romanisation operator, i.e. it is a valid entity of
        the reading returned by the segmentation method.

        Reading entities will be handled as being case insensitive.

        :type entity: str
        :param entity: entity to check
        :type readingN: str
        :param readingN: name of reading
        :param options: additional options for handling the input
        :rtype: bool
        :return: ``True`` if string is an entity of the reading, ``False``
            otherwise.
        :raise UnsupportedError: if the given reading is not supported or the
            reading doesn't support the specified method.
        """
        readingOp = self._getReadingOperatorInstance(readingN, **options)
        if not hasattr(readingOp, 'isPlainReadingEntity'):
            raise UnsupportedError(
                "method 'isPlainReadingEntity' not supported")
        return readingOp.isPlainReadingEntity(entity)


# Top-level interface (temp)

_factory = None

def _get_factory():
    global _factory
    if _factory is None:
        _factory = ReadingFactory()
    return _factory

def convert(
        readingStr: str,
        fromReading: str | Reading | type[Reading],
        toReading: str | Reading | type[Reading],
        *,
        allowBridge: bool = True,
        sourceOptions: dict[str, Any] | None = None,
        targetOptions: dict[str, Any] | None = None,
        **options,
    ) -> str:
    """
    Converts the given string in the source reading to the given target
    reading.

    :type readingStr: str
    :param readingStr: string that needs to be converted
    :type fromReading: str | Reading | type[Reading]
    :param fromReading: source reading
    :type toReading: str | Reading | type[Reading]
    :param toReading: target reading
    :param options: additional options for handling the input
    :keyword sourceOperators: list of :class:`ReadingOperators
        <hanzilib.reading.operator.ReadingOperator>` used for handling
        source readings.
    :keyword targetOperators: list of :class:`ReadingOperators
        <hanzilib.reading.operator.ReadingOperator>` used for handling
        target readings.
    :keyword sourceOptions: dictionary of options to configure the
        :class:`ReadingOperators <hanzilib.reading.operator.ReadingOperator>`
        used for handling source readings. If an
        operator for the source reading is explicitly specified, no options
        can be given.
    :keyword targetOptions: dictionary of options to configure the
        :class:`ReadingOperators <hanzilib.reading.operator.ReadingOperator>`
        used for handling target readings. If an
        operator for the target reading is explicitly specified, no options
        can be given.
    :rtype: str
    :return: the converted string
    :raise DecompositionError: if the string can not be decomposed into
        basic entities with regards to the source reading or the given
        information is insufficient.
    :raise CompositionError: if the target reading's entities can not be
        composed.
    :raise ConversionError: on operations specific to the conversion between
        the two readings (e.g. error on converting entities).
    :raise UnsupportedError: if source or target reading is not supported
        for conversion.
    """
    return _get_factory().convert(readingStr, fromReading, toReading, allowBridge=allowBridge, sourceOptions=sourceOptions, targetOptions=targetOptions, **options)


def decompose(string: str, readingN: str, **options):
    """
    Decomposes the given string into basic entities that can be mapped to
    one Chinese character each for the given reading.

    The given input string can contain other non reading characters, e.g.
    punctuation marks.

    The returned list contains a mix of basic reading entities and other
    characters e.g. spaces and punctuation marks.

    :type string: str
    :param string: reading string
    :type readingN: str
    :param readingN: name of reading
    :param options: additional options for handling the input
    :rtype: list of str
    :return: a list of basic entities of the input string
    :raise DecompositionError: if the string can not be decomposed.
    :raise UnsupportedError: if the given reading is not supported.
    """
    return _get_factory().decompose(string, readingN, **options)


def compose(readingEntities: list[str], readingN: str, **options):
    """
    Composes the given list of basic entities to a string for the given
    reading.

    Composing entities can raise a :exc:`~cjklib.exception.CompositionError`
    if a non-reading entity is about to be joined with a reading entity
    and will result in a string that is impossible to decompose.

    :type readingEntities: list of str
    :param readingEntities: list of basic syllables or other content
    :type readingN: str
    :param readingN: name of reading
    :param options: additional options for handling the input
    :rtype: str
    :return: composed entities
    :raise CompositionError: if the given entities can not be composed.
    :raise UnsupportedError: if the given reading is not supported.
    """
    return _get_factory().compose(readingEntities, readingN, **options)

def segment(string: str, readingN: str, **options):
    """
    Takes a string written in the romanisation and returns the possible
    segmentations as a list of syllables.

    In contrast to :meth:`~cjklib.reading.ReadingFactory.decompose`
    this method merely segments continuous entities of the romanisation.
    Characters not part of the romanisation will not be dealt with,
    this is the task of the more general decompose method.

    :type string: str
    :param string: reading string
    :type readingN: str
    :param readingN: name of reading
    :param options: additional options for handling the input
    :rtype: list of list of str
    :return: a list of possible segmentations (several if ambiguous) into
        single syllables
    :raise DecompositionError: if the given string has an invalid format.
    :raise UnsupportedError: if the given reading is not supported or the
        reading doesn't support the specified method.
    """
    return _get_factory().segment(string, readingN, **options)

# init
from . import converter
