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

"""
Command line interface (*CLI*) to the library's build functionality.

.. todo::
    * bug: "Prefer" system does not work for additional builders
"""

import argparse
import sys
import os
from optparse import OptionParser, OptionGroup
import configparser
from typing import Any

# Absolute imports for cli
from hanzilib.build import DatabaseBuilder
from hanzilib import exception, dbconnector
from hanzilib.util import getConfigSettings, getDataPath#, ExtendedOption
from hanzilib import log

class CommandLineBuilder(object):
    """
    *Command line interface* (CLI) to the build functionality of hanzilib.
    """
    DESCRIPTION = """Builds the database for the hanzilib library.
The database is accessed according to the settings of hanzilib in hanzilib.conf.
Example: \"%prog build allAvail\". Builders can be given specific options with
format --BuilderName-option or --TableName-option, e.g.
\"--Unihan-wideBuild=yes\""""

    BUILD_GROUPS = {
        # source based
        'packaged': ['PinyinSyllables', 'WadeGilesSyllables',
            'WadeGilesPinyinMapping', 'PinyinIPAMapping', 'GRSyllables',
            'GRAbbreviation', 'GRRhotacisedFinals', 'PinyinGRMapping',
            'MandarinIPAInitialFinal', 'PinyinBrailleInitialMapping',
            'PinyinBrailleFinalMapping', 'PinyinInitialFinal',
            'WadeGilesInitialFinal', 'JyutpingSyllables',
            'JyutpingInitialFinal', 'CantoneseYaleSyllables',
            'CantoneseYaleInitialNucleusCoda', 'JyutpingYaleMapping',
            'JyutpingIPAMapping', 'CantoneseIPAInitialFinal',
            'CharacterShanghaineseIPA', 'ShanghaineseIPASyllables',
            'KangxiRadical',
            'KangxiRadicalIsolatedCharacter', 'RadicalEquivalentCharacter',
            'Strokes', 'StrokeOrder', 'CharacterDecomposition',
            'LocaleCharacterGlyph', 'StrokeCount', 'ComponentLookup',
            'CharacterRadicalResidualStrokeCount'],
        'UnihanCharacterSets': ['IICoreSet', 'GB2312Set', 'BIG5Set',
            # 'HKSCSSet',
            'BIG5HKSCSSet', 'JISX0208Set', 'JISX0208_0213Set'],
        'UnihanData': ['UnihanCharacterSets', 'CharacterKangxiRadical',
            'CharacterPinyin', 'CharacterJyutping', 'CharacterHangul',
            'CharacterVietnamese', 'CharacterJapaneseKun',
            'CharacterJapaneseOn', 'CharacterKanWaRadical',
            # 'CharacterJapaneseRadical', 'CharacterKoreanRadical',
            'CharacterVariant', 'Glyphs'],
        # library based
        'Readings': ['PinyinSyllables', 'WadeGilesSyllables',
            'WadeGilesPinyinMapping', 'PinyinIPAMapping', 'GRSyllables',
            'GRAbbreviation', 'GRRhotacisedFinals', 'PinyinGRMapping',
            'MandarinIPAInitialFinal', 'PinyinBrailleInitialMapping',
            'PinyinBrailleFinalMapping', 'PinyinInitialFinal',
            'WadeGilesInitialFinal', 'JyutpingSyllables',
            'JyutpingInitialFinal', 'CantoneseYaleSyllables',
            'CantoneseYaleInitialNucleusCoda', 'JyutpingYaleMapping',
            'JyutpingIPAMapping', 'CantoneseIPAInitialFinal',
            'CharacterShanghaineseIPA', 'ShanghaineseIPASyllables'],
        'SupportedCharacterReadings': ['CharacterPinyin', 'CharacterJyutping',
            'CharacterHangul', 'CharacterShanghaineseIPA'],
        'KangxiRadicalData': [
            # 'CharacterKangxiRadical',
            'CharacterChineseRadical',
            'KangxiRadical',
            'KangxiRadicalIsolatedCharacter', 'RadicalEquivalentCharacter',
            'CharacterRadicalResidualStrokeCount',
            'CharacterResidualStrokeCount'],
        'ShapeLookupData': ['Strokes', 'StrokeOrder', 'CharacterDecomposition',
            'LocaleCharacterGlyph', 'StrokeCount', 'ComponentLookup',
            'CharacterVariant', 'Glyphs'],
        'CharacterDomains': ['UnihanCharacterSets', 'GlyphInformationSet'],
        'hanzilibData': ['Readings', 'SupportedCharacterReadings',
            'KangxiRadicalData', 'ShapeLookupData', 'CharacterDomains'],
        # language based
        'fullMandarin': ['KangxiRadicalData', 'ShapeLookupData',
            'CharacterPinyin', 'PinyinSyllables', 'WadeGilesSyllables',
            'WadeGilesPinyinMapping', 'GRSyllables', 'GRRhotacisedFinals',
            'GRAbbreviation', 'PinyinGRMapping', 'PinyinIPAMapping',
            'MandarinIPAInitialFinal', 'PinyinBrailleInitialMapping',
            'PinyinBrailleFinalMapping', 'PinyinInitialFinal',
            'WadeGilesInitialFinal', 'GB2312Set', 'BIG5Set'],
        'fullCantonese': ['KangxiRadicalData', 'ShapeLookupData',
            'CharacterShanghaineseIPA', 'ShanghaineseIPASyllables',
            'GB2312Set', 'BIG5Set'],
        'fullShanghainese': ['KangxiRadicalData', 'ShapeLookupData',
            'CharacterJyutping', 'JyutpingSyllables', 'CantoneseYaleSyllables',
            'CantoneseYaleInitialNucleusCoda', 'JyutpingYaleMapping',
            'JyutpingIPAMapping', 'CantoneseIPAInitialFinal',
            'JyutpingInitialFinal', 'GB2312Set', 'BIG5HKSCSSet'],
        'fullJapanese': ['KangxiRadicalData', 'ShapeLookupData', 'JISX0208Set',
            'JISX0208_0213Set'],
        'fullKorean': ['KangxiRadicalData', 'ShapeLookupData',
            'CharacterHangul', 'IICoreSet'], # TODO IICoreSet as long as no better source exists
        'fullVietnamese': ['KangxiRadicalData', 'ShapeLookupData', 'IICoreSet'], # TODO IICoreSet as long as no better source exists
        'Dictionaries': [
            'CEDICT',
            # 'CEDICTGR',
            'HanDeDict',
            # 'CFDICT',
            'EDICT'
        ],
    }
    """
    Definition of build groups available to the user. Recursive definitions are
    not allowed and will lead to a lock up.
    """

    BUILD_GROUPS_CATEGORY = {
        "Source based": ["packaged", "UnihanCharacterSets", "UnihanData"],
        "Library based": ["Readings", "SupportedCharacterReadings", "KangxiRadicalData", "ShapeLookupData", "CharacterDomains", "hanzilibData"],
        "Language based": ["fullMandarin", "fullCantonese", "fullShanghainese", "fullJapanese", "fullKorean", "fullVietnamese", "Dictionaries"]
    }

    DB_PREFER_BUILDERS =  ['CombinedStrokeCountBuilder',
        'CombinedCharacterResidualStrokeCountBuilder']
    """Builders prefered for build process."""

    @classmethod
    def printFormattedLine(cls, outputString, lineLength=None,
        subsequentPrefix=''):
        """
        Formats the given input string to fit to a output with a limited line
        length and prints it to stdout with the systems encoding.

        :type outputString: str
        :param outputString: a string that is formated to fit to the screen
        :type lineLength: int
        :param lineLength: with of screen
        :type subsequentPrefix: str
        :param subsequentPrefix: prefix used after line break
        """
        if lineLength is None:
            try:
                lineLength = int(os.environ['COLUMNS'])
            except (KeyError, ValueError):
                lineLength = 80

        outputLines = []
        for line in outputString.split("\n"):
            outputEntityList = line.split()
            outputEntityList.reverse()
            column = 0
            output = ''
            while outputEntityList:
                entity = outputEntityList.pop()
                # if the next entity including one trailing space will
                # reach over, break the line
                if column > 0 and len(entity) + column >= lineLength:
                    output = output + "\n" + subsequentPrefix + entity
                    column = len(subsequentPrefix) + len(entity)
                else:
                    if column > 0:
                        output = output + ' '
                        column = column + 1
                    column = column + len(entity)
                    output = output + entity
                #if len(column) >= lineLength and outputEntityList:
                    #output = output + "\n" + subsequentPrefix
                    #column = len(subsequentPrefix)
            outputLines.append(output)

        print("\n".join(outputLines))

    @classmethod
    def getBuilderConfigSettings(cls):
        """
        Gets the builder settings from the section ``Builder`` from
        ```hanzilib.conf```.

        :rtype: dict
        :return: dictionary of builder options
        """
        return {} # temp
        configOptions = getConfigSettings('Builder')
        # don't convert to lowercase
        configparser.RawConfigParser.optionxform = lambda self, x: x
        config = configparser.RawConfigParser(configOptions)

        options = {}
        for builder in DatabaseBuilder.getTableBuilderClasses(
            resolveConflicts=False):
            if not builder.PROVIDES:
                continue

            for option in builder.getDefaultOptions():
                try:
                    metadata = builder.getOptionMetaData(option)
                    optionType = metadata.get('type', None)
                except KeyError:
                    optionType = None

                for opt in [option, '--%s-%s' % (builder.__name__, option),
                    '--%s-%s' % (builder.PROVIDES, option)]:
                    if config.has_option(None, opt):
                        if optionType == 'bool':
                            value = config.getboolean(configparser.DEFAULTSECT,
                                opt)
                        elif optionType == 'int':
                            value = config.getint(configparser.DEFAULTSECT,
                                opt)
                        elif optionType == 'float':
                            value = config.getfloat(configparser.DEFAULTSECT,
                                opt)
                        else:
                            value = config.get(configparser.DEFAULTSECT, opt)

                        options[opt] = value

        return options

    @classmethod
    def getConnectionConfigSettings(cls):
        """
        Gets the connections settings from hanzilib.conf.

        :rtype: dict
        :return: dictionary of connection options
        """
        options = {}
        config = dbconnector.getDefaultConfiguration()
        if 'sqlalchemy.url' in config:
            options['databaseUrl'] = config['sqlalchemy.url']
        if 'attach' in config:
            options['attach'] = config['attach']
        if 'registerUnicode' in config:
            options['registerUnicode'] = config['registerUnicode']
        return options

    @classmethod
    def getDefaultOptions(cls, includeConfig=True) -> dict[str, Any]:
        """
        Gets default options that always overwrite those specified in the build
        module. Boolean options of the :class:`~hanzilib.build.DatabaseBuilder`
        can not be changed here as they are hardcoded in the given command line
        options.
        """
        options = {}
        # dataPath
        options['dataPath'] = ['.', getDataPath()]
        # prefer
        options['prefer'] = cls.DB_PREFER_BUILDERS[:]

        if includeConfig:
            options.update(cls.getConnectionConfigSettings())
            options.update(cls.getBuilderConfigSettings())

        return options
    
    @classmethod
    def build_cli_parser(cls):
        description = cls.DESCRIPTION
        
        parser = argparse.ArgumentParser(
            prog="hanzi db",
            description=description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        subparsers = parser.add_subparsers(dest="db_command", help="Available commands")
        
        build_p = subparsers.add_parser("build", help="Build database")
        build_p.add_argument("groups", nargs="*", help="List of group names to build")
        
        groups_p = subparsers.add_parser("groups", help="List build groups")
        groups_p.add_argument("-a", "--all", action="store_true", dest="all", default=False, help="List all contents in groups")

        defaults = cls.getDefaultOptions()
        build_p.add_argument("-r", "--rebuild", action="store_true",
            dest="rebuildExisting", default=False,
            help="build tables even if they already exist")
        build_p.add_argument("-d", "--keep-depending", action="store_false",
            dest="rebuildDepending", default=True,
            help="don't rebuild build-depends tables that are not given")
        # cmd_parser.add_argument("-p", "--prefer", action=AppendResetDefaultAction,
        #     metavar="BUILDER", dest="prefer",
        #     help="builder preferred where several provide the same table [default: %(default)s]")
        build_p.add_argument("-q", "--quiet", action="store_true", dest="quiet",
            default=False, help="don't print anything on stdout")
        build_p.add_argument("--database", action="store", metavar="URL",
            dest="databaseUrl", default=defaults.get("databaseUrl", None),
            help="database url [default: %(default)s]")
        # cmd_parser.add_argument("--attach", action=AppendResetDefaultAction,
        #     metavar="URL", dest="attach",
        #     help="attachable databases [default: %(default)s]")
        # cmd_parser.add_argument("--registerUnicode", type=_optparse_bool_parser,
        #     metavar="BOOL", dest="registerUnicode",
        #     default=defaults.get("registerUnicode", False),
        #     help="register own Unicode functions if no ICU support available [default: %(default)s]")
        build_p.add_argument("--ignore-config", action="store_true",
            dest="ignoreConfig", default=False,
            help="ignore settings from hanzilib.conf")
        build_p.add_argument("-v", "--verbose", action="store_true",
            dest="verbose", default=False,
            help="verbose logging")

        optionSet = set(['rebuildExisting', 'rebuildDepending', 'quiet',
            'databaseUrl', "verbose"
            # 'attach', 'prefer'
        ])
        globalBuilderGroup = build_p.add_argument_group("Global builder options")
        localBuilderGroup = build_p.add_argument_group("Local builder options")

        for builder in DatabaseBuilder.getTableBuilderClasses(preferClassNameSet=cls.DB_PREFER_BUILDERS):
            if not builder.PROVIDES:
                continue

            for option, defaultValue in sorted(builder.getDefaultOptions().items()):
                try:
                    metadata = builder.getOptionMetaData(option)
                except KeyError:
                    continue
                
                # print("Processing", builder.__name__, option)

                metadata_key_to_option = {'action': 'action', 'type': 'type',
                    'metavar': 'metavar', 'choices': 'choices',
                        'description': 'help'}
                options_for_option = dict([(metadata_key_to_option[key], value) for key, value \
                    in list(metadata.items()) if key in metadata_key_to_option])

                if 'metavar' not in options_for_option:
                    if 'type' in options_for_option and options_for_option['type'] == 'bool':
                        options_for_option['metavar'] = 'BOOL'
                    else:
                        options_for_option['metavar'] = 'VALUE'

                if 'help' not in options_for_option:
                    options_for_option['help'] = ''

                default = defaults.get(option, defaultValue)
                if default == []:
                    options_for_option['help'] += ' [default: ""]'
                elif default is not None:
                    options_for_option['help'] += ' [default: %s]' % default

                # global option, only need to add it once, DatabaseBuilder makes
                #   sure option is consistent between builder
                options_for_option['dest'] = option
                if options_for_option.get("action", None) == "extendResetDefault":
                    options_for_option["action"] = "extend"
                if option not in optionSet:
                    # print(options_for_option)
                    globalBuilderGroup.add_argument('--' + option, **options_for_option)
                    optionSet.add(option)

                # local options
                #options['help'] = optparse.SUPPRESS_HELP
                localBuilderOption = '--%s-%s' % (builder.__name__, option)
                options_for_option['dest'] = localBuilderOption
                localBuilderGroup.add_argument(localBuilderOption, **options_for_option)

                localTableOption = '--%s-%s' % (builder.PROVIDES, option)
                options_for_option['dest'] = localTableOption
                localBuilderGroup.add_argument(localTableOption, **options_for_option)

        return parser


    # def buildParser(self):
    #     usage = "%(prog)s [options] [list | build TABLE [TABLE_2 ...]]"
    #     description = self.DESCRIPTION
    #     
    #     parser = OptionParser(usage=usage, description=description, option_class=ExtendedOption)
# 
    #     defaults = self.getDefaultOptions()
    #     parser.add_option("-r", "--rebuild", action="store_true",
    #         dest="rebuildExisting", default=False,
    #         help="build tables even if they already exist")
    #     parser.add_option("-d", "--keepDepending", action="store_false",
    #         dest="rebuildDepending", default=True,
    #         help="don't rebuild build-depends tables that are not given")
    #     parser.add_option("-p", "--prefer", action="appendResetDefault",
    #         metavar="BUILDER", dest="prefer",
    #         help="builder preferred where several provide the same table" \
    #             + " [default: %s]" % defaults.get("prefer", []))
    #     parser.add_option("-q", "--quiet", action="store_true", dest="quiet",
    #         default=False, help="don't print anything on stdout")
    #     parser.add_option("--database", action="store", metavar="URL",
    #         dest="databaseUrl", default=defaults.get("databaseUrl", None),
    #         help="database url [default: %default]")
    #     parser.add_option("--attach", action="appendResetDefault",
    #         metavar="URL", dest="attach",
    #         help="attachable databases [default: %s]"
    #             % defaults.get("attach", []))
    #     parser.add_option("--registerUnicode", action="store", type='bool',
    #         metavar="BOOL", dest="registerUnicode",
    #         help=("register own Unicode functions if no ICU support available"
    #             " [default: %s]" % defaults.get("registerUnicode", False)))
    #     parser.add_option("--ignoreConfig", action="store_true",
    #         dest="ignoreConfig", default=False,
    #         help="ignore settings from hanzilib.conf")
# 
    #     optionSet = set(['rebuildExisting', 'rebuildDepending', 'quiet',
    #         'databaseUrl', 'attach', 'prefer'])
    #     globalBuilderGroup = OptionGroup(parser, "Global builder commands")
    #     localBuilderGroup = OptionGroup(parser, "Local builder commands")
    #     for builder in DatabaseBuilder.getTableBuilderClasses(resolveConflicts=False):
    #         if not builder.PROVIDES:
    #             continue
# 
    #         for option, defaultValue in sorted(
    #             builder.getDefaultOptions().items()):
    #             try:
    #                 metadata = builder.getOptionMetaData(option)
    #             except KeyError:
    #                 continue
# 
    #             includeOptions = {'action': 'action', 'type': 'type',
    #                 'metavar': 'metavar', 'choices': 'choices',
    #                     'description': 'help'}
    #             options = dict([(includeOptions[key], value) for key, value \
    #                 in list(metadata.items()) if key in includeOptions])
# 
    #             if 'metavar' not in options:
    #                 if 'type' in options and options['type'] == 'bool':
    #                     options['metavar'] = 'BOOL'
    #                 else:
    #                     options['metavar'] = 'VALUE'
# 
    #             if 'help' not in options:
    #                 options['help'] = ''
# 
    #             default = defaults.get(option, defaultValue)
    #             if default == []:
    #                 options['help'] += ' [default: ""]'
    #             elif default is not None:
    #                 options['help'] += ' [default: %s]' % default
# 
    #             # global option, only need to add it once, DatabaseBuilder makes
    #             #   sure option is consistent between builder
    #             options['dest'] = option
    #             if option not in optionSet:
    #                 globalBuilderGroup.add_option('--' + option, **options)
    #                 optionSet.add(option)
# 
    #             # local options
    #             #options['help'] = optparse.SUPPRESS_HELP
    #             localBuilderOption = '--%s-%s' % (builder.__name__, option)
    #             options['dest'] = localBuilderOption
    #             localBuilderGroup.add_option(localBuilderOption, **options)
# 
    #             localTableOption = '--%s-%s' % (builder.PROVIDES, option)
    #             options['dest'] = localTableOption
    #             localBuilderGroup.add_option(localTableOption, **options)
# 
    #     parser.add_option_group(globalBuilderGroup)
    #     parser.add_option_group(localBuilderGroup)
# 
    #     return parser

    def listBuildGroups(self, all: bool = False):
        print("\033[1mGeneric groups:\033[m")
        print("       \033[33mall\033[m    for all tables understood by the build script (may fail if data is not available)")
        print("  \033[33mallAvail\033[m    for all data available to the build script")
        for key, names in self.BUILD_GROUPS_CATEGORY.items():
            print()
            print(f"\033[1m{key} groups:\033[m")
            for name in names:
                print(f"  \033[33m{name}\033[m")
                if all:
                    lst = ", ".join(self.BUILD_GROUPS[name])
                else:
                    lst = ", ".join(("*" if x in self.BUILD_GROUPS else "") + x for x in self.BUILD_GROUPS[name][:3])
                    if len(self.BUILD_GROUPS[name]) > 3:
                        lst += f", ... (+{len(self.BUILD_GROUPS[name])-3} more)"
                print(f"\033[3m    {lst}\033[m")

        print("\nBoth group names and table names can be given to the build process.")
        if not all:
            print("Run with --all to list all components in groups")

    def _combinePreferred(self, preferred, otherPreferred):
        """
        Combine two lists of preferred builders, by giving classes from the
        first list precedence.
        """
        builderClasses = DatabaseBuilder.getTableBuilderClasses(
            resolveConflicts=False)
        dbPreferClasses = [clss for clss in builderClasses
            if clss.__name__ in (preferred + otherPreferred)]

        # sort out the default preferred if they collide with user's choice
        dbPreferClasses = DatabaseBuilder.resolveBuilderConflicts(
            dbPreferClasses, preferred)

        return [clss.__name__ for clss in dbPreferClasses]

    def runBuild(self, groups: list[str], options: dict[str, Any]):
        if options.get("verbose", None):
            log.verbose = True
        if options.get("quiet", None):
            log.enabled = False
        # A group can be a table name
        if not groups:
            log.log("No group list provided, defaulting to allAvail")
            groups = ["allAvail"]
        
        groups_set = set(groups)
        # by default fail if a table couldn't be built
        options['noFail'] = False
        if 'all' in groups_set or 'allAvail' in groups_set:
            if 'allAvail' in groups_set:
                if len(groups_set) == 1:
                    # don't fail on non available
                    options['noFail'] = True
                else:
                    # allAvail not compatible with others, as allAvail means not
                    # failing if build fails, but others will need failing when
                    # explicitly named
                    raise ValueError("group 'allAvail' can't be specified " \
                        + "together with other groups.")
            # if generic group given get list
            groups_set = DatabaseBuilder.getSupportedTables()

        # unpack groups
        tables: list[str] = []
    
        while len(groups_set) != 0:
            group = groups_set.pop()
            if group in self.BUILD_GROUPS:
                groups_set.update(self.BUILD_GROUPS[group])
            else:
                tables.append(group)

        # re-add builders preferred by default, in case overwritten by user
        preferredBuilderNames = options.get("prefer", [])
        if preferredBuilderNames:
            options['prefer'] = self._combinePreferred(preferredBuilderNames,
                self.DB_PREFER_BUILDERS)

        # get database connection
        configuration = dbconnector.getDefaultConfiguration()
        configuration['sqlalchemy.url'] = options.pop('databaseUrl',
            configuration['sqlalchemy.url'])
        configuration['attach'] = [attach for attach in
            options.pop('attach', configuration.get('attach', [])) if attach]
        if 'registerUnicode' in options:
            configuration['registerUnicode'] = options.pop('registerUnicode')
        try:
            db = dbconnector.DatabaseConnector(configuration)
        except ValueError as e:
            print("Error: %s" % e, file=sys.stderr)
            return False

        # create builder instance
        dbBuilder = DatabaseBuilder(dbConnectInst=db, **options)

        try:
            dbBuilder.build(tables)
        except exception.UnsupportedError as e:
            print("Error building local tables, some names do not exist: %s" % e, file=sys.stderr)
            return False
        except KeyboardInterrupt:
            print("Keyboard interrupt.", file=sys.stderr)
            try:
                # remove temporary tables
                dbBuilder.clearTemporary()
            except KeyboardInterrupt:
                print("Interrupted while cleaning temporary tables", file=sys.stderr)
            return False

        return True

    def run(self, args=None):
        """
        Runs the builder
        """
        # parse command line parameters
        if args is None:
            parser = self.build_cli_parser()
            args = parser.parse_args()

        if args.db_command is None:
            print("hanzilib database manager (hanzi db)")
            return True
        
        command = args.db_command.lower()
        if command == "groups":
            self.listBuildGroups(all=args.all)
            return True
        elif command == "build":
            # temp, from buildParser
            optionSet = set(['rebuildExisting', 'rebuildDepending', 'quiet',
                'databaseUrl', "verbose"
                # 'attach', 'prefer'
            ])
            options = self.getDefaultOptions(includeConfig=not args.ignoreConfig)
            options.update(dict([(option, getattr(args, option)) for option \
                in optionSet if hasattr(args, option)]))

            return self.runBuild(args.groups, options)
        else:
            parser.error("unknown command '%s'" % command)

        return False


def main():
    if not CommandLineBuilder().run():
        sys.exit(1)

if __name__ == "__main__":
    main()
