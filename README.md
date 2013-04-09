# Overview #

## Running the Code ##

This solution requires Python 2.7, and uses only the standard library. `./match.py` should work out of the box for matching the sample data. Run `./match.py -h` for usage information.

## Files ##

`classes.py` contains the classes used to store and process the products and listings data, and some simple related data structures for matching them.

`match.py` is a command-line tool to perform the matching, and contains the high-level logic for the algorithm. Matching the 20,000-listing sample data takes ~10s on my system.

`compare.py` is a little tool I put together to compare between results sets, as a way to track incremental improvements and regressions in the matches while refining the matching algorithm.


## Algorithm ##

The algorithm used in this solution is quite straight-forward.

* While reading in the products, build a list of manufacturers, and associate each product to the appropriate manufacturer.
* For each product, generate a set of regular expressions to be used against a listing title string to determine if the listing is a match.
* For each listing:
    * Determine the manufacturer(s).
        * If necessary, search within the title string for matches against manufacturer or product family names.
    * Compare the listing to each of that manufacturer's products, creating a list of ones that match.
    * Choose the best match, and associate the listing with that product

The techniques I've used to determine whether a listing matches a product mostly come down to a variety of simple (and somewhat arbitrary) rules that determine what parts of the product's `model` string are most important, and where and how they are allowed to occur in the listing's `title` string.

In other words: This is built on ugly heuristics and regular expressions, not an elegant probabilistic model. But it seems to work quite well.


## Text Processing and Matching ##

Here is where the complexities lie.

For the listing title:
* Ignore anything enclosed in parentheses.
* Ignore anything that comes after "for", "pour", or "für". This implies the listing is of the structure [accessory] for [product(s)].
* Ignore anything after the 50th character. The manufacturer, family, and model number are almost always mentioned at the start of the listing.

For the product's family string:
* Treat this as an optional thing to match (generally; see below)
* If the string has a hyphen, match it even if the hyphen is missing.

For the product's model string:
* Detect commonly occurring model prefixes and suffixes for a given manufacturer (such as "DSC-" for Sony cameras) and treat them as optional, if:
    * it's present in at least 10 products, and
    * at least 1/3 of the products for that manufacturer, and
    * it's at least 2 characters long
* Wherever there is punctuation or whitespace (i.e., \W) in the original model string, allow for extra/different/no punctuation or whitespace. Also allow it at the boundary between a letter and a number.
* Insist on a word-break at the start of the model string
* Insist on a word-break at the end of the model string, but allow for up to 3 non-numeric characters before that. Listings often attach letter suffixes to the model number to indicate colour, or other non-relevant details. I admit, this allowance is questionable; there are cases where a letter suffix is used to indicate a different product, and if a listing for that is present and a product entry is not, we will have a false positive match. However, this possibility does not seem to be an issue in the sample data.
* If the model string contains a space or a hyphen, allow the string to be split apart (i.e., tokenized) at those points and let the tokens be matched separately.
    * When doing so, treat as optional any segment containing only letters that is 3 letters or longer. Many product listings contain superfluous words that are absent in some of the corresponding listings.
    * However: if the model string *only* contains words, then mark all words as required.

For comparing the listings with products:
* Model string must match something in the listing title, subject to the above parameters.
* Because of uncertainties about the contents of the model string (particularly when matching individual tokens), perform a sanity check on each potential match:
    * If the *only* thing that is matched is a number with 3 or fewer digits, reject that match, unless the *original* model string is also a number of 3 or fewer digits, and the product entry contains no family string. This is to avoid false positives potentially created by treating various tokens (and the family string) as optional.
        * This implies: if the model string is just a number (with 3 or fewer digits), a listing must also match the family string in order to be considered a match. (The sample data actually contains no products where the model is just a number and there is no family specified.)
    * If the only thing matched was a single character, reject the match. (This does not actually occur at all with the sample data, but I wanted to guard against the possibility.)

Determining the best match:
* The best match is the one where the matched text starts earliest in the listing title. In the event of a tie, the match with the greatest amount of matching text wins.

