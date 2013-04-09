#!/usr/bin/env python
# -*- coding: utf8 -*-

import argparse
import json
import sys
import traceback


DEFAULT_OUTPUT_FILE = 'results.diff'


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
        description='''Compares two results files, and outputs the differences
            in product matches in a diff-like format. Differences are given one
            per line, grouped together by product. Each block begins with name
            of the product. Listings for that product present only in the first
            file are shown with "- " at the start of the line, and listings
            present only in the second file are preceded by "+ ".'''
    )
    parser.add_argument(
        'results_a',
        type=argparse.FileType('r'), metavar='FILE1',
        help='''first results file (containing JSON objects, one per line,
            naming a product with an array of matching listings)'''
    )
    parser.add_argument(
        'results_b',
        type=argparse.FileType('r'), metavar='FILE2',
        help='''second results file (same format as the first)'''
    )
    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'), metavar='OUTPUT_FILE',
        default=DEFAULT_OUTPUT_FILE,
        help='''write the differences between the results to this file
            (default is "results.diff")'''
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
