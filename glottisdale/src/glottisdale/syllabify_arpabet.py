# Vendored from https://github.com/kylebgorman/syllabify (MIT License)
# ARPABET syllabifier using Maximum Onset Principle

#!/usr/bin/env python
# Copyright (c) 2012-2013 Kyle Gorman <gormanky@ohsu.edu>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# syllabify.py: prosodic parsing of ARPABET entries

from itertools import chain

## constants
SLAX   = {'IH1', 'IH2', 'EH1', 'EH2', 'AE1', 'AE2', 'AH1', 'AH2',
                                                    'UH1', 'UH2',}
VOWELS = {'IY1', 'IY2', 'IY0', 'EY1', 'EY2', 'EY0', 'AA1', 'AA2', 'AA0',
          'ER1', 'ER2', 'ER0', 'AW1', 'AW2', 'AW0', 'AO1', 'AO2', 'AO0',
          'AY1', 'AY2', 'AY0', 'OW1', 'OW2', 'OW0', 'OY1', 'OY2', 'OY0',
          'IH0', 'EH0', 'AE0', 'AH0', 'UH0', 'UW1', 'UW2', 'UW0', 'UW',
          'IY',  'EY',  'AA',  'ER',   'AW', 'AO',  'AY',  'OW',  'OY',
          'UH',  'IH',  'EH',  'AE',  'AH',  'UH',} | SLAX

## licit medial onsets

O2 = {('P', 'R'), ('T', 'R'), ('K', 'R'), ('B', 'R'), ('D', 'R'),
      ('G', 'R'), ('F', 'R'), ('TH', 'R'),
      ('P', 'L'), ('K', 'L'), ('B', 'L'), ('G', 'L'),
      ('F', 'L'), ('S', 'L'),
      ('K', 'W'), ('G', 'W'), ('S', 'W'),
      ('S', 'P'), ('S', 'T'), ('S', 'K'),
      ('HH', 'Y'), # "clerihew"
      ('R', 'W'),}
O3 = {('S', 'T', 'R'), ('S', 'K', 'L'), ('T', 'R', 'W')} # "octroi"

# This does not represent anything like a complete list of onsets, but
# merely those that need to be maximized in medial position.

def syllabify(pron, alaska_rule=True):
    """
    Syllabifies a CMU dictionary (ARPABET) word string
    """
    ## main pass
    mypron = list(pron)
    nuclei = []
    onsets = []
    i = -1
    for (j, seg) in enumerate(mypron):
        if seg in VOWELS:
            nuclei.append([seg])
            onsets.append(mypron[i + 1:j]) # actually interludes, r.n.
            i = j
    codas = [mypron[i + 1:]]
    ## resolve disputes and compute coda
    for i in range(1, len(onsets)):
        coda = []
        # boundary cases
        if len(onsets[i]) > 1 and onsets[i][0] == 'R':
            nuclei[i - 1].append(onsets[i].pop(0))
        if len(onsets[i]) > 2 and onsets[i][-1] == 'Y':
            nuclei[i].insert(0, onsets[i].pop())
        if len(onsets[i]) > 1 and alaska_rule and nuclei[i-1][-1] in SLAX \
                                              and onsets[i][0] == 'S':
            coda.append(onsets[i].pop(0))
        # onset maximization
        depth = 1
        if len(onsets[i]) > 1:
            if tuple(onsets[i][-2:]) in O2:
                depth = 3 if tuple(onsets[i][-3:]) in O3 else 2
        for j in range(len(onsets[i]) - depth):
            coda.append(onsets[i].pop(0))
        # store coda
        codas.insert(i - 1, coda)

    ## verify that all segments are included in the ouput
    output = list(zip(onsets, nuclei, codas))  # in Python3 zip is a generator
    flat_output = list(chain.from_iterable(chain.from_iterable(output)))
    if flat_output != mypron:
        raise ValueError(f"could not syllabify {mypron}, got {flat_output}")
    return output


def pprint(syllab):
    """
    Pretty-print a syllabification
    """
    return '.'.join('-'.join(' '.join(p) for p in syl) for syl in syllab)


def destress(syllab):
    """
    Generate a syllabification with nuclear stress information removed
    """
    syls = []
    for (onset, nucleus, coda) in syllab:
        nuke = [p[:-1] if p[-1] in {'0', '1', '2'} else p for p in nucleus]
        syls.append((onset, nuke, coda))
    return syls
