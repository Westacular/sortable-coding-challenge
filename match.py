#!/usr/bin/env python
# -*- coding: utf8 -*-

# Solution to the Sortable Coding Challenge at
# http://sortable.com/blog/coding-challenge/

from classes import Product, Listing, Manufacturer
import argparse
import sys
import traceback

DEFAULT_PRODUCTS_FILE = 'data/products.txt'
DEFAULT_LISTINGS_FILE = 'data/listings.txt'
DEFAULT_RESULTS_FILE = 'data/results.txt'


def parse_my_arguments(arguments=None):
    '''Processes the arguments to the command using argparse and returns the
    resulting object.'''

    parser = argparse.ArgumentParser(
        description='''Matches items from product listings to known products.
                       Solution to the Sortable Coding Challenge.'''
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='increase output verbosity'
    )
    parser.add_argument(
        '-p', '--products',
        type=argparse.FileType('r'), metavar='PRODUCTS_FILE',
        default=DEFAULT_PRODUCTS_FILE,
        help='file containing JSON objects (one per line) describing the products'
    )
    parser.add_argument(
        '-l', '--listings',
        type=argparse.FileType('r'), metavar='LISTINGS_FILE',
        default=DEFAULT_LISTINGS_FILE,
        help='file containing JSON objects (one per line) containing the listings'
    )
    parser.add_argument(
        '-r', '--results',
        type=argparse.FileType('w'), metavar='RESULTS_FILE',
        default=DEFAULT_RESULTS_FILE,
        help='''write results to this file (one JSON object per line, naming a
                product and giving an array of matched listings objects)'''
    )
    parser.add_argument(
        '--suppress-empty',
        action='store_true',
        help='''in results file, do not include results objects for products
                that have no matched listings'''
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


def read_products_data(products_file):
    '''Reads product data from the passed file handle, creates corresponding
    `Product` objects, and (as need) `Manufacturer` objects storing lists of
    associated `Product`s. Returns a list containing all of the `Product`s, in
    the order they were read, and a dict containing all of the
    `Manufacturer`s, keyed by their names.'''
    manufacturers = {}
    products = []
    # Read and structure the data
    for pj in products_file:
        P = Product(pj)
        products.append(P)
        if P.manufacturer not in manufacturers:
            manufacturers[P.manufacturer] = Manufacturer(P.manufacturer, [P])
        else:
            manufacturers[P.manufacturer].add_product(P)
    return products, manufacturers


def read_listings_data(listings_file):
    '''Reads listing data from the passed file handle, creates and returns a
    list of corresponding `Listing` objects'''
    listings = []
    for lj in listings_file:
        L = Listing(lj)
        listings.append(L)
    return listings


def find_manufacturers_for_listing(listing, manufacturers):
    '''Returns a set (usually containing one item, but potentially more) of
    manufacturers that are believed to correspond to the listing. Each of the
    manufacturers should be searched for a product match.'''

    L = listing
    manufacturers_to_search = set()

    # First, a quick check if there's an exact match for the listing's
    # 'manufacturer' field
    if L.manufacturer in manufacturers:
        manufacturers_to_search = [manufacturers[L.manufacturer]]

    # Second, see if a known manufacturer name is at least present in the
    # listing's 'manufacturer' field.
    #
    # e.g., matching 'canon' to 'canon canada inc.'
    if not manufacturers_to_search:
        # Search a bit more thoroughly
        for (name, M) in manufacturers.iteritems():
            if name in L.manufacturer:
                manufacturers_to_search = set([M])
                break
            elif L.manufacturer and L.manufacturer in name:
                manufacturers_to_search.add(M)

    # Third, check for the presence of a manufacturer name or product family
    # name in the first three words of the listing title.
    if not manufacturers_to_search:
        title_start = ' '.join(L.searchable_title.split()[:3])
        for (name, M) in manufacturers.iteritems():
            if name in title_start:
                manufacturers_to_search = set([M])
                break
            for family in M.families:
                if family in title_start:
                    manufacturers_to_search.add(M)

    return manufacturers_to_search


def match_listings_to_products(listings, manufacturers, verbose=False):
    '''Finds, if possible, the best-matching product for each listing, and
    associates that listing with the matched product.'''

    # Tracking these for evaluation purposes
    unknown_manufacturer = []
    unknown_model = []

    if verbose:
        sys.stderr.write('Preparing manufacturer and product data for matching...\n')
    for M in manufacturers.itervalues():
        M.prepare_regexes(verbose=verbose)

    if verbose:
        sys.stderr.write('Starting the matching...\n')
    for n, L in enumerate(listings):
        if verbose and n % 1000 == 0:
            sys.stderr.write('Processed {n} of {total} listings...\n'.format(
                n=n, total=len(listings)
            ))

        manufacturers_to_search = find_manufacturers_for_listing(L, manufacturers)

        if not manufacturers_to_search:
            unknown_manufacturer.append(L)
            continue

        matches = []

        for M in manufacturers_to_search:
            matches += M.find_matching_products(L)

        if not matches:
            unknown_model.append(L)
            continue

        if len(matches) == 1:
            best_match = matches[0]
        else:
            # The best match is the one:
            # 1) whose match starts earliest in the listing
            # 2) with the longest matching amount of text
            matches.sort(key=lambda m: m.length, reverse=True)
            matches.sort(key=lambda m: m.begin)
            best_match = matches[0]

        best_match.product.associate_listing(L)

    if verbose:
        sys.stderr.write('\nMatching completed. Processed {total:5} listings:\n{0:6} matched,\n{1:6} listings with unknown manufacturers,\n{2:6} listings for unknown models from known manufacturers\n'.format(
            len(listings) - len(unknown_manufacturer) - len(unknown_model),
            len(unknown_manufacturer),
            len(unknown_model),
            total=len(listings)
        ))
    return unknown_manufacturer, unknown_model


def write_results(results_file, products, suppress_empty):
    # products.sort(key=lambda P: P.product_name)
    for P in products:
        if P.listings or not suppress_empty:
            results_file.write(P.result_json_compact)


def main(arguments=None):
    args = parse_my_arguments(arguments)

    if args.verbose:
        sys.stderr.write('Reading data...\n')

    products, manufacturers = read_products_data(args.products)
    args.products.close()

    listings = read_listings_data(args.listings)
    args.listings.close()

    unknown_manufacturer, unknown_model = match_listings_to_products(listings, manufacturers, verbose=args.verbose)

    write_results(args.results, products, args.suppress_empty)



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
