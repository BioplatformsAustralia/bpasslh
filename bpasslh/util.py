import string

import re
import csv


from collections import namedtuple

digit_words = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


def csv_to_named_tuple(
    typname, fname, mode="r", additional_context=None, cleanup=None, dialect="excel"
):
    if fname is None:
        return [], []

    def clean_name(s):
        s = s.lower().strip().replace("-", "_").replace(" ", "_")
        s = "".join(
            [
                t
                for t in s
                if t in string.ascii_letters or t in string.digits or t == "_"
            ]
        )
        if s[0] in string.digits:
            s = digit_words[s[0]] + s[1:]
        s = s.strip("_")
        s = re.sub(r"__+", "_", s).strip("_")
        # reserved words aren't permitted
        if s == "class":
            s = "class_"
        return s

    additional_keys = []
    if additional_context is not None:
        additional_keys += list(sorted(additional_context.keys()))
    with open(fname, mode) as fd:
        r = csv.reader(fd, dialect=dialect)
        header = [clean_name(t) for t in next(r)] + additional_keys
        typ = namedtuple(typname, header)
        rows = []
        for row in r:
            if cleanup is not None:
                row = [cleanup(t) for t in row]
            rows.append(typ(*(row + [additional_context[t] for t in additional_keys])))
        return header, rows
