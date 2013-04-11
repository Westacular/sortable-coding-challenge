# -*- coding: utf8 -*-

import re
import json
import sys


# Note: '[^\W\d_]' is apparently the recommended character class
# for 'any unicode letter, but not digits' in python
_re_word_like = re.compile(r'^[^\W\d_]{3,}$', flags=re.U)

_re_short_number = re.compile(r'^\s*\d{1,3}\s*$', flags=re.U)

_break_words = []
for w in [u'for', u'pour', u'für']:
    _break_words.append(re.compile(r'\b' + w + r'\b', flags=re.U))


class ProductMatch(object):
    '''Simple class used to represent a match between a product and a
    listing.'''
    def __init__(self, product, listing, begin, length):
        self.product = product
        self.listing = listing
        self.begin = begin
        self.length = length

    def sanity_check(self):
        '''Runs a sanity check on a match, to make sure it's not matching
        something too insubstantial. Returns the match if it's deemed valid,
        and None if it isn't.'''

        out_match = self
        # If all we matched was a number, don't count it as a match ... unless
        # that's really all we have to go on.
        if _re_short_number.match(self.listing.searchable_title[self.begin:self.begin+self.length])\
                and not (_re_short_number.match(self.product.model) and not self.product.family):
            out_match = None
        # A single character should never be enough to constitute a match.
        elif self.length < 2:
            out_match = None

        return out_match


class Matcher(object):
    '''Stores a compiled regular expression and a flag to indicate whether the
    listing is required to match that re.'''
    def __init__(self, regex, required=True):
        self.re = re.compile(regex, re.U)
        self.required = required


class Listing(object):
    def __init__(self, jsonstring):
        self.orig_data = jsonstring
        jsondata = json.loads(jsonstring)
        self.title = jsondata['title'].lower()
        self.manufacturer = jsondata['manufacturer'].lower()
        self.price = jsondata['price']
        self.currency = jsondata['currency']
        self.make_searchable_title()

    def make_searchable_title(self):
        '''Create a copy of the title string, mangled such that it is suitable
        for searching against for model and manufacturer info. Stores the
        result in the .searchable_title attribute.'''

        self.searchable_title = self.title
        # Ignore things in parentheses: replace contents with spaces (to
        # preserve the distance for the 50-char truncation to follow)
        self.searchable_title = re.sub(
            r'\(.*?\)',
            lambda m: ' '*len(m.group()),
            self.searchable_title, flags=re.U)
        # Ignore anything following words like 'for'
        for w in _break_words:
            m = w.search(self.searchable_title)
            if m:
                self.searchable_title = self.searchable_title[:m.start()]

        # Only look at the first 50 characters; if the model number shows up
        # after that it's probably an accessory to the model, not the actual
        # product)
        self.searchable_title = self.searchable_title[:50]


class Product(object):
    def __init__(self, jsonstring):
        self.orig_data = jsonstring
        jsondata = json.loads(jsonstring)
        self.product_name = jsondata['product_name']
        self.manufacturer = jsondata['manufacturer'].lower()
        self.model = jsondata['model'].lower()

        if 'family' in jsondata:
            self.family = jsondata['family'].lower()
        else:
            self.family = None

        self.listings = []

    def associate_listing(self, listing):
        '''Adds a listing to the list of associated (matching) listings'''
        self.listings.append(listing)


    @property
    def result_json(self):
        '''JSON string giving the product_name and an array of associated
        listings, formatted with one listing per line.'''

        output = '{"product_name": "' + self.product_name.encode('utf8') + '", "listings": [\n'
        if self.listings:
            for L in self.listings[:-1]:
                output += L.orig_data.strip() + ',\n'
            output += self.listings[-1].orig_data.strip()
        output += '\n]}\n'
        return output

    @property
    def result_json_compact(self):
        '''JSON string giving the product_name and an array of associated
        listings, formatted as a single line with no superfluous
        whitespace.'''

        output = '{"product_name":"' + self.product_name.encode('utf8') + '","listings":['
        if self.listings:
            for L in self.listings[:-1]:
                output += L.orig_data.strip() + ','
            output += self.listings[-1].orig_data.strip()
        output += ']}\n'
        return output


    @classmethod
    def _convert_model_to_regex_string(cls, model, ignorable=[], optional_prefix=None):
        '''Helper method that takes the given model string (along with other
        components) and mangles them into a regular expression suitable for
        matching. Primarily, this means being extremely permissive about
        whitespace and punctuation, and marking certain bits of the string as
        optional.'''

        # Espace the base string
        model = re.escape(model)
        for s in ignorable:
            # Mark all ignorable bits as optional components of the match
            model = re.sub(r'\b' + re.escape(s) + r'\b',
                           r'(?:' + re.escape(s) + r')?', model, flags=re.U)

        if optional_prefix:
            model = r'(?:' + re.escape(optional_prefix) + r'\W)?' + model

        # Find any non-word characters (all already escaped) and allow ANY
        # zero-or-more non-word characters at that location
        model = re.sub(r'\\\W', r'\W*', model, flags=re.U)

        # Note: '[^\W\d_]' is the recommended character class for
        # 'any unicode letter, but not digits' in python
        #
        # At any boundary between a letter and a number, allow there to be
        # punctuation or white-space.
        model = re.sub(r'([^\W\d_])(\d)', r'\1\W*\2', model, flags=re.U)
        model = re.sub(r'(\d)([^\W\d_])', r'\1\W*\2', model, flags=re.U)

        # This is a tricky decision: Should the tail be \D or \b?
        #
        # \D allows letter suffixes, which appear to commonly be insignificant
        # (e.g., indicating colour)... but there are known cases where it IS
        # significant for distinguishing models
        #
        # Also, only allow a few trailing letters before insisting on a word
        # break. We want to permit letter suffixes, but not allow the end of
        # the model number to accidentally match the start of a word (e.g.
        # "300D" matching "300 Digital" is undesired.)
        model = r'\b' + model + r'(?=\D{0,3}\b)'
        return model

    def prepare_matchers(self, ignorable=[]):
        '''Prepares the product for matching, marking the substrings listed
        `ignorable` as optional components for a match'''
        self._create_holistic_regex(ignorable)
        self._create_token_regexes(ignorable)

    def _create_holistic_regex(self, ignorable=[]):
        '''Initialises the matcher for this product, treating any substrings
        present in `ignorable` as optional.'''
        self._matcher = Matcher(Product._convert_model_to_regex_string(self.model, ignorable, self.family))

    def _create_token_regexes(self, ignorable=[], replace_dash=True):
        '''Initialises the split (tokenized) matchers for this product,
        treating any substrings present in `ignorable` as optional.'''

        self._token_matchers = []
        if replace_dash:
            tokens = re.split('[- _]+', self.model)
        else:
            tokens = self.model.split()

        # Add words from the family name to the token list
        if self.family:
            tokens += self.family.split()

        # Make sure there are no empty tokens
        tokens = [t for t in tokens if t]

        if len(tokens) == 1:
            # No point; this would be the same as the un-split matcher
            return

        # Start with the default assumption that word-like tokens (3+
        # characters containing only letters) are not necessary for a match
        words_skippable = True

        # If there are NO numbers in the model, that would be a poor
        # assumption.
        if re.match(r'^\D+$', self.model, flags=re.U):
            words_skippable = False

        # Scan through the tokens, checking for certain properties
        for tok in tokens:
            # Rationale for the following:
            #
            # Plain numbers and very short strings have a tendency to produce
            # false positives. If, by splitting on a dash, we produced tokens
            # of that nature, then try again without splitting on the dash, in
            # case that would leave the token attached to something else
            # relevant: If the model number contains 'A-200', matching an 'a'
            # and a '200' separately is meaningless.
            if replace_dash and (
                len(tok) < 3 or
                _re_short_number.match(tok)
            ):
                return self._create_token_regexes(ignorable, False)

        # Now actually make the matchers.
        for tok in tokens:
            if tok in ignorable or (self.family and tok in self.family):
                required = False
            # Make words/word-like things in model number optional: we want to
            # know if they match but don't mind if they don't.
            #
            elif words_skippable and _re_word_like.match(tok):
                required = False
            else:
                required = True
            self._token_matchers.append(Matcher(Product._convert_model_to_regex_string(tok), required))


    def match_listing(self, listing):
        '''Determines if `listing` matches this product. If it does, this
        returns a `ProductMatch` object representing the match. If it does
        not, returns None.'''

        match = None

        # First check if it matches the holistic matcher
        m = self._matcher.re.search(listing.searchable_title)

        if m:
            span = m.span()
            match = ProductMatch(self, listing, span[0], span[1] - span[0])
            # Do a sanity check here, so that if it fails, we fall through to
            # the token matchers.
            match = match.sanity_check()

        if not match and self._token_matchers:
            # Search for segments of model id separately
            amount_matched = 0
            still_matching = True
            mstart = len(listing.searchable_title)

            for matcher in self._token_matchers:
                m = matcher.re.search(listing.searchable_title)
                if m:
                    span = m.span()
                    mlength = span[1] - span[0]
                    if mlength:
                        amount_matched += mlength
                        mstart = min(mstart, span[0])
                elif matcher.required:
                    still_matching = False
                    break

            if still_matching:
                # Matched all required segments
                match = ProductMatch(self, listing, mstart, amount_matched)
                match = match.sanity_check()

        return match


class Manufacturer(object):
    def __init__(self, name, products):
        self.name = name
        self.products = []
        self.known_families = set()
        for P in products:
            self.add_product(P)

    def add_product(self, product):
        self.products.append(product)
        # Progressively build a set of known family names
        if product.family:
            self.known_families.add(product.family)
            if '-' in product.family:
                self.known_families.add(product.family.replace('-', ''))

    def find_matching_products(self, listing):
        '''Returns a list containing a `ProductMatch` object for each of the
        products from this manufacturer that match `listing`.'''
        matches = []
        for P in self.products:
            match = P.match_listing(listing)
            if match:
                matches.append(match)

        return matches

    def prepare_regexes(self, verbose=False):
        '''Does some analysis of the model strings for the products of this
        manufacturer, then prepares the `Product` objects for matching
        against.'''
        # If the same repeating prefix or suffix is present in many of the model
        # numbers, we can probably ignore it as redundant (as it will likely be
        # missing from some product listings)
        # e.g.: all Panasonic model numbers begin with "DMC-"
        histogram = {}
        for P in self.products:
            segments = P.model.replace('-', ' ').split()
            for seg in [segments[0], segments[-1]]:
                if seg in histogram:
                    histogram[seg] += 1
                else:
                    histogram[seg] = 1

        ignorable_segments = set()
        for seg, count in histogram.iteritems():
            # Reasoning for the criteria:
            #
            # 1) It must be at least 2 characters long; if it's only one
            #    character, it's unlikely a merchant would drop it from the
            #    listing
            #
            # 2) It must be present in at least a third of the products; i.e.,
            #    common enough that it's unnecessary to mention it with the
            #    model number because in-context it can be assumed
            #
            # 3) At least 10 occurences: this is mainly to guard against cases
            #    where there are only a few listings for the manufacturer and
            #    criteria 2) is not enough to make a conclusion
            #
            if len(seg) >= 2 and count > len(self.products) / 3 and count >= 10:
                ignorable_segments.add(seg)
                if verbose:
                    sys.stderr.write('\tMarking "{seg}" from model strings for {man} as optional (present in {count} of {num} models)\n'.format(
                        seg=seg,
                        man=self.name.capitalize(),
                        count=count,
                        num=len(self.products)
                    ))

        for P in self.products:
            P.prepare_matchers(ignorable_segments)
