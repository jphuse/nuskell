#
#  nuskell/parser/crn_parser.py
#  NuskellCompilerProject
#
# Copyright (c) 2010-2020 Caltech. All rights reserved.
# Written by Seung Woo Shin (seungwoo.theory@gmail.com).
#            Stefan Badelt (stefan.badelt@gmail.com)
#
from pyparsing import (Word, Literal, Group, Suppress, Optional, ZeroOrMore, 
                       Combine, nums, alphas, alphanums, delimitedList, 
                       StringStart, StringEnd, LineEnd, srange, OneOrMore,
                       pythonStyleComment, ParseElementEnhance)


def crn_document_setup(modular=False):
    """Parse a formal chemical reaction network.

    Args:
      modular <optional:bool>: Adds an additional nesting for modules within a
        CRN. Use one line per module (';' separates reactions).

    Format:
      # A list of reactions, optionally with reaction rates:
      # <- this is a comment!
      B + B -> C    # [k = 1]
      C + A <=> D   # [kf = 1, kr = 1]
      <=> A  [kf = 15, kr = 6]

      # Note that you can write multiple reactions in one line:
      A + 2C -> E [k = 13.78]; E + F <=> 2A  [kf = 13, kr = 14]

    Returns:

    """
    # NOTE: If you want to add support for multiple modules per line, you can use
    # the '|' character.

    W = Word
    G = Group
    S = Suppress
    O = Optional
    C = Combine
    L = Literal

    def T(x, tag):
        """ Return a *Tag* to distinguish (ir)reversible reactions """
        def TPA(tag):
            return lambda s, l, t: t.asList() + [tag]
        return x.setParseAction(TPA(tag))

    crn_DWC = "".join(
        [x for x in ParseElementEnhance.DEFAULT_WHITE_CHARS if x != "\n"])
    ParseElementEnhance.setDefaultWhitespaceChars(crn_DWC)

    identifier = W(alphas, alphanums + "_")

    multiplier = W(nums)
    species = G(O(multiplier) + identifier)

    rate = C(W(nums) + O((L('.') + W(nums)) | (L('e') + O('-') + W(nums))))

    k = G(S('[') + S('k') + S('=') + rate + S(']'))
    rev_k = G(S('[') + S('kf') + S('=') + rate + S(',') +
              S('kr') + S('=') + rate + S(']'))

    reaction = T(G(O(delimitedList(species, "+"))) +
                 S("->") +
                 G(O(delimitedList(species, "+"))) + O(k), 'irreversible')

    rev_reaction = T(G(O(delimitedList(species, "+"))) +
                     S("<=>") +
                     G(O(delimitedList(species, "+"))) + O(rev_k), 'reversible')

    expr = G(reaction | rev_reaction)

    if modular:
        module = G(expr + ZeroOrMore(S(";") + expr))
    else:
        module = expr + ZeroOrMore(S(";") + expr)

    formal = G(O(S(";")) + L("formals") + S(L("=") +
                                            L("{")) + O(delimitedList(identifier)) + S("}"))

    signal = G(O(S(";")) + L("signals") + S(L("=") +
                                            L("{")) + O(delimitedList(identifier)) + S("}"))

    fuel = G(O(S(";")) + L("fuels") + S(L("=") +
                                        L("{")) + O(delimitedList(identifier)) + S("}"))

    addon = formal | signal | fuel

    crn = OneOrMore(module + ZeroOrMore(S(LineEnd()))) + \
        ZeroOrMore(addon + ZeroOrMore(S(LineEnd())))

    document = StringStart() + ZeroOrMore(S(LineEnd())) + crn + StringEnd()
    document.ignore(pythonStyleComment)
    return document


def _post_process(crn):
    """
      Take a CRN and return it together with a list of formal species.
      If additional information on signal and fuel species was provided, this
      gets processed here as well.
    """
    def remove_multipliers(species):
        flat = []
        for s in species:
            if len(s) == 1:
                flat.append(s[0])
            elif len(s) == 2:
                ss = [s[1]] * int(s[0])
                flat.extend(ss)
        return flat

    new = []
    fsp = set()
    ssp = set()
    csp = set()  # fuel species (formerly called constant species
    for line in crn:
        if line[0] == "formals":
            fsp = fsp.union(line[1:])
        elif line[0] == "signals":
            ssp = ssp.union(line[1:])
        elif line[0] == "fuels":
            csp = csp.union(line[1:])
        elif len(line) == 3:
            # No rate specified
            r, p, t = line
            r = remove_multipliers(r)
            p = remove_multipliers(p)
            if t == 'reversible':
                new.append([r, p, [None, None]])
            elif t == 'irreversible':
                new.append([r, p, [None]])
            else:
                raise ValueError('Wrong CRN format!', line)
        elif len(line) == 4:
            r, p, k, t = line
            r = remove_multipliers(r)
            p = remove_multipliers(p)
            if t == 'reversible':
                assert len(k) == 2
                new.append([r, p, k])
            elif t == 'irreversible':
                assert len(k) == 1
                new.append([r, p, k])
            else:
                raise ValueError('Wrong CRN format!', line)
        else:
            raise ValueError('Wrong CRN format!', line)
        fsp = fsp.union(r).union(p)
    crn = new

    if not ssp:
        ssp = fsp

    if ssp & csp:
        raise ValueError(
            "{} declared as signal & fuel species".format(
                ssp & csp))

    return crn, sorted(list(fsp)), sorted(list(ssp)), sorted(list(csp))

def parse_crn_file(filename):
    """Parses a CRN from a file.

    Args:
      filename (<str>): Path to the input file.

    """
    crn_document = crn_document_setup()
    crn = crn_document.parseFile(filename, parseAll=True).asList()
    return _post_process(crn)


def parse_crn_string(data):
    """Parses a CRN in string format.

    Args:
      data (<str>): A CRN string.
    """
    crn_document = crn_document_setup()
    return _post_process(crn_document.parseString(data).asList())
