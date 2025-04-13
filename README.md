# histlang

Sound change applier.

## Usage
The program takes in a soundchange definition and a list of words and outputs a list of modified words.
```
python -m histlang changes.sc wordlist.txt outputwordlist.txt
```

Download python 3.11+ from [python.org](https://www.python.org/downloads/).

## Format documentation.

For information on what a sound change is you can check the [Sound change Wikipedia page](https://en.wikipedia.org/wiki/Sound_change).

Since the sound change format is not formally defined, this project makes its best effort to support the majority of requirements. This means that it interprets each word as a sequence of phonemes with each one having certain qualities.

A wordlist file is defined as a newline-separated file of phoneme sequences.
A sound change file is defined as a newline-separated file of sound change expressions or phoneme group definition expressions.

A sound change consists of 3 components: source, output and a list of conditions. Each component consists of phonemes or phoneme groups. These components are separated by any of "/>→". When processing a word, each soundchange will try to replace any source match with output if all condition match. 

A phoneme is expected to be in accordance with the International Phonetic Alphabet, written with its unicode syntax. It is a basephoneme (a sequence of unicode characters connected by a tie character) with diacritics (unicode modifier characters).

A phoneme group definition is defined as a single unicode character followed by an equals sign and then either a collection of phonemes in curly braces separated by commas (`T={p,t,k}`) or a sequence of modifiers enclosed in square brackets `N=[+nasal][-bilabial]`.

A phoneme group in a sound change may be a collection of phonemes in curly braces or a previously defined phoneme group with optional modifiers (`C[+velar]`). If it is the lone part of a component then it may be just a modifier (`[+velar]>[-voiced]`).

Modifiers are defined based on the IPA and match a phoneme and its diacritcs. Some suprasegmental modifiers such as `[+stressed]` or `[-falling tone]` are also supported. (`[+vowel]>[-voiced]/[-stress]`)

If a group is specified in the output component of a soundchange then its value is based on the matched group with the same name (including plain unnamed modifiers) in the input component. If the group in the output uses modifiers than a resulting phoneme will be dynamically generated.

Conditions may be preceded with `!` to instead require that they must not pass for a change to occur.


## Similarities

Basic [SCA²](https://www.zompist.com/scahelp.html)-based syntax is supported: 
```
c→g/V_V
gn/nh/_
u/o/_#
s//_#
```

Quality based syntax is supported:
```
[+consonant][-voiced] > [+palatalized]
[stop] > ∅ / _#
```

The most common syntax of [Index Diachronica](https://chridd.nfshost.com/diachronica/) is supported:
```
{ei,ɔi} → oi / C[-nasal]
qʷ qʷː ɢʷ → ħʷ qʷ ɣʷ
```
