#!/usr/bin/env python
# -*- coding: utf8 -*-

import argparse
import json
import sys
import traceback


DEFAULT_OUTPUT_FILE = 'compare.diff'


class Result(object):
    # count = 0

    def __init__(self, jsonstring):
        self.orig_data = jsonstring
        # print Result.count
        # Result.count += 1
        jsondata = json.loads(jsonstring)
        self.product_name = jsondata['product_name']
        self.listings = []
        for lj in jsondata['listings']:
            L = ComparableListing(lj)
            self.listings.append(L)
        self.listings.sort(key=lambda L: L.price)


class ComparableListing(object):
    def __init__(self, jsonstring):
        if isinstance(jsonstring, str) or isinstance(jsonstring, unicode):
            self.orig_data = jsonstring
            jsondata = json.loads(jsonstring)
        else:
            jsondata = jsonstring
        self.title = jsondata['title'].lower()
        self.manufacturer = jsondata['manufacturer'].lower()
        self.price = jsondata['price']
        self.currency = jsondata['currency']
        self.matched = False

    def __eq__(self, list2):
        return (self.title == list2.title and
                self.manufacturer == list2.manufacturer and
                self.currency == list2.currency and
                self.price == list2.price
                )



def parse_my_arguments(arguments=None):
    '''Processes the arguments to the command using argparse and returns the
    resulting object.'''

    parser = argparse.ArgumentParser(
        description='''Compares two results files, and outputting the differences
            in product matches as a diff(-ish) file'''
    )

    parser.add_argument(
        'results_a',
        type=argparse.FileType('r'), metavar='FILENAME',
        help='first file containing JSON objects (one per line) describing the results'
    )

    parser.add_argument(
        'results_b',
        type=argparse.FileType('r'), metavar='FILENAME',
        help='second file containing JSON objects (one per line) describing the results'
    )

    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'), metavar='FILENAME',
        default=DEFAULT_OUTPUT_FILE,
        help='''write the differences between the results to this file'''
    )

    if arguments is not None:
        if isinstance(arguments, list):
            args = parser.parse_args(arguments)
        elif isinstance(arguments, str):
            args = parser.parse_args(arguments.split())
        else:
            raise TypeError("'arguments' must be either a string or a list of strings")
    else:
        args = parser.parse_args()

    return args


def read_results_data(results_file):
    results = {}
    # Read and structure the data
    for rj in results_file:
        R = Result(rj)
        results[R.product_name] = R

    results_file.close()
    return results


def main(arguments=None):
    args = parse_my_arguments(arguments)

    results_a = read_results_data(args.results_a)
    results_b = read_results_data(args.results_b)

    for name, R in results_a.iteritems():
        if name in results_b:
            Rb = results_b[name]

            for L in R.listings:
                for Lb in Rb.listings:
                    if Lb.matched:
                        continue
                    if L == Lb:
                        L.matched = True
                        Lb.matched = True
                        break

        first_diff = True
        for L in R.listings:
            if not L.matched:
                if first_diff:
                    args.output.write(name.encode('utf8') + ":\n")
                    first_diff = False
                args.output.write("- " + L.title.encode('utf8') + "\n")

        if name in results_b:
            for Lb in Rb.listings:
                if not Lb.matched:
                    if first_diff:
                        args.output.write(name.encode('utf8') + ":\n")
                        first_diff = False
                    args.output.write("+ " + Lb.title.encode('utf8') + "\n")

    args.output.close()




if __name__=='__main__':
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt as e:
        raise e
    except SystemExit as e:
        raise e
    except argparse.ArgumentError as e:
        print str(e)
    except Exception as e:
        print str(e)
        traceback.print_exc()
        sys.exit(1)
