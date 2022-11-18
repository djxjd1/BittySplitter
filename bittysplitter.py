#!/usr/bin/python3


import configparser
import csv
import json
from decimal import Decimal
import getopt
import logging
import os
import re
import sys


def main(argv):
    if "-vv" in argv:
        print("Debugging")
        loglevel = logging.DEBUG
    elif "-v" in argv:
        print("Info")
        loglevel = logging.INFO
    else:
        loglevel = logging.WARNING

    logging.basicConfig(level=loglevel)

    config = configparser.ConfigParser(delimiters=('='))
    config.optionxform = str
    configPath = os.path.join(os.environ['HOME'], '.config', 'bittysplitter',
                              'conf.ini')
    config.read(configPath)

    inputdir = config.get('main', 'inputdir', fallback='')
    outputdir = config.get('main', 'outputdir', fallback='')

    try:
        opts, args = getopt.getopt(argv, 'hvi:o:', ['inputdir=', 'outputdir='])
    except getopt.GetoptError:
        help()

    regexFilters = loadRegexFilters(config)
    logging.debug(f"Regex Patterns {regexFilters}")

    for opt, arg in opts:
        if opt == '-h':
            help()
        if opt in ['-i', '--inputdir']:
            inputdir = arg
        elif opt in ['-o', '--outputdir']:
            outputdir = arg

    if inputdir and outputdir:
        inputFiles = getInputFiles(inputdir)
        logging.debug(f"Found files: {inputFiles}")
        for inputFile in inputFiles:
            logging.info(f"Opening file: {inputFile}")
            header, splitFiles = splitFile(inputdir, inputFile, regexFilters)
            logging.debug(f"Returned rows: {splitFiles}")
            for splitFile_ in splitFiles:
                os.makedirs(os.path.join(outputdir, splitFile_), exist_ok=True)
                newFile = os.path.join(outputdir, splitFile_, inputFile)
                logging.info(f"Writing to file: {newFile}")
                with open(newFile, 'w') as csvfile:
                    csvwriter = csv.writer(csvfile)
                    csvwriter.writerow(header)
                    csvwriter.writerows(splitFiles[splitFile_])
    else:
        help()


def loadRegexFilters(config):
    filters = {}
    for key in config['Splitters']:
        pattern = re.compile(key)
        filters[pattern] = config['Splitters'][key]
    return filters


def splitFile(inputdir, inputFile, regexFilters):
    csvData = {}
    with open(inputdir + os.sep + inputFile) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        rowNum = 0
        for row in csv_reader:
            if rowNum == 0:
                header = row
            else:
                try:
                    newRows = matchFilters(inputFile, row, regexFilters)
                except KeyError as e:
                    logging.error(f"Match not found for {inputFile}")
                    logging.error(f"on row {rowNum + 1}")
                    logging.error(f"Row: {row}")
                    raise KeyError(e)
                logging.debug(f"newRows: {newRows}")
                for key_ in newRows:
                    if key_ not in csvData or not csvData[key_]:
                        csvData[key_] = []
                    csvData[key_].append(newRows[key_])
            rowNum += 1
    return header, csvData


def matchFilters(inputFile, row, regexFilters):
    stringRow = ",".join(row)
    logging.debug(f"Row: {stringRow}")
    for regex in regexFilters:
        if not regex.match(stringRow):
            continue
        logging.info('Match found')
        splitterDict = json.loads(regexFilters[regex])
        rowsToSplit = splitterDict["rowsToSplit"]
        if "file" in splitterDict and splitterDict["file"] != inputFile:
            continue
        if "dateSplit" in splitterDict:
            for key in splitterDict["dateSplit"]:
                dateSplit = splitterDict["dateSplit"][key]
                rowDate = row[splitterDict["dateCol"]]
                if ((("DateEnd" not in dateSplit) or
                     rowDate <= dateSplit["DateEnd"]) and
                    (("DateStart" not in dateSplit) or
                     rowDate > dateSplit["DateStart"])):
                    return applyMap(row, dateSplit["split"], rowsToSplit)
            # throw error
            raise KeyError(f"Date split: {splitterDict['dateSplit']}")
        else:
            return applyMap(row, splitterDict["split"], rowsToSplit)
    raise KeyError("Match not found")


def applyMap(row, split, rowsToSplit):
    logging.info(f"Applying filter: {split}")
    logging.info(f"Row: {row}")
    return {x: [i if idx not in rowsToSplit else Decimal(i) * Decimal(split[x])
            for idx, i in enumerate(row)] for x in split}


def getInputFiles(inputdir):
    logging.info(f"Getting files from directory: {inputdir}")
    for (_, _, inputFiles) in os.walk(inputdir):
        return inputFiles


def help():
    print('bittysplitter.py -i <inputdir> -o <outputdir>')
    sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
