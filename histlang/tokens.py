"""Sound change syntax tokenizer."""
# TODO: handle optionals e.g. (C)V
# TODO: handle number subscripts as part of basephone

from __future__ import annotations

import dataclasses
import itertools
import typing
import unicodedata


@dataclasses.dataclass
class ConditionChar:
    """A character valid only in conditions such as _ and #."""

    char: typing.Literal["_", "#"]
    """Unique condition character. _ = matched segment, # = word border"""
    modifiers: typing.Sequence[Modifier]
    """Specific required modifiers applied to _, expected to be suprasegmentals."""

    def __str__(self) -> str:
        return self.char + "".join(map(str, self.modifiers))


@dataclasses.dataclass
class Suprasegmentals:
    """Suprasegmental information attached to syllables."""

    stress: bool = False
    """Whether this phoneme is stressed."""
    tone: typing.Sequence[int] = ()
    """Which tone this phoneme carries."""
    
    _word_pointer: Word = object() # type: ignore


@dataclasses.dataclass
class Modifier:
    """A modifier in square brackets."""

    positive: bool
    """Whether it's preceded by + (as opposed to -) to mean this modifier is desired."""
    value: str

    def __str__(self) -> str:
        return "[" + "-+"[self.positive] + self.value + "]"


@dataclasses.dataclass
class Phoneme:
    """Defined phoneme class."""

    basephoneme: str
    """Clean character sequence describing this base phoneme. Most often a single unicode character."""
    diacritics: typing.Sequence[str]
    """List of phonetically-relevant diacritics."""
    modifiers: typing.Sequence[Modifier] = ()
    """List of modifiers. May be a sequence of modifier characters or a modifier word."""
    syllable: int = 0
    """Which syllable index this phoneme attaches to. Used for suprasegmentals."""

    def __str__(self) -> str:
        return self.basephoneme + "".join(self.diacritics) + "".join(map(str, self.modifiers))


@dataclasses.dataclass
class PhonemeGroup:
    """Collection of phonemes, either a dynamic or named group."""

    name: str | None = None
    """Name of the group if named."""
    collection: typing.Sequence[typing.Sequence[Phoneme]] = ()
    """Collection of underlying phonemes."""
    diacritics: typing.Sequence[str] = ()
    """Diacritics that were applied to a named group."""
    modifiers: typing.Sequence[Modifier] = ()
    """Tags that phonemes must satisfy. If members is empty then metadata includes all potential phonemes, otherwise it excludes."""

    def __str__(self) -> str:
        if self.name is not None:
            return self.name + "".join(self.diacritics) + "".join(map(str, self.modifiers))

        return "{" + ",".join("".join(map(str, i)) for i in self.collection) + "}"


@dataclasses.dataclass
class SoundChange:
    """The top sound change expression."""

    source: typing.Sequence[Phoneme | PhonemeGroup]
    output: typing.Sequence[Phoneme | PhonemeGroup]
    conditions: typing.Sequence[tuple[typing.Sequence[Phoneme | PhonemeGroup | ConditionChar], bool]] = ()

    def __str__(self) -> str:
        return (
            ("".join(map(str, self.source)) or "∅")
            + " → "
            + ("".join(map(str, self.output)) or "∅")
            + "".join(" " + "!/"[positive] + " " + "".join(map(str, phns)) for phns, positive in self.conditions)
        )


@dataclasses.dataclass
class Word:
    """Phonetic form of a word including its suprasegmental features."""

    phonemes: typing.Sequence[Phoneme]
    """IPA representation of a word."""
    suprasegmentals: typing.Sequence[Suprasegmentals]
    """Attributes of syllables of the given word."""

    def __str__(self) -> str:
        if len(self.suprasegmentals) <= 1:
            return "".join(map(str, self.phonemes))

        return "".join(
            ("ˈ" if s.stress else "" if i == 0 else ".")
            + "".join(str(p) for p in self.phonemes if p.syllable == i)
            + "".join(unicodedata.lookup(TONE_TO_TONE_BAR[i]) for i in s.tone)
            for i, s in enumerate(self.suprasegmentals)
        )


@dataclasses.dataclass
class PhonemeMetadata:
    """Metadata of a phoneme e.g. consonant, alveolar, palatalized."""

    unichar: str
    """String representation of the phoneme."""
    metadata: typing.Sequence[str]
    """Tags this phoneme satisfies."""

    def __str__(self) -> str:
        return self.unichar


@dataclasses.dataclass
class DiacriticMetadata:
    """Metadata of a diacritic."""

    names: typing.Sequence[str]
    """Unicode names for this diacritic."""
    metadata: typing.Sequence[str]
    """Tags this phoneme satisfies."""

    @property
    def unichar(self) -> str:
        return unicodedata.lookup(self.names[0])

    @property
    def representation(self) -> str:
        """Representation of this symbol with a dotted circle."""
        return "◌" + self.unichar

    def __str__(self) -> str:
        return self.representation


@dataclasses.dataclass
class SoundChangeContext:
    """Information about the source and target languages."""

    source: typing.Sequence[PhonemeMetadata]
    target: typing.Sequence[PhonemeMetadata]
    groups: typing.Sequence[PhonemeGroup]


def is_length_modifier(char: str) -> bool:
    return char in ("ː", "ˑ")


def is_suprasegmental(char: str) -> bool:
    return char in ("ˈ", ".")


def is_modifier(unichar: str) -> bool:
    """Checks whether a character is a modifier such as ʲ."""
    if is_length_modifier(unichar):
        return True
    if is_suprasegmental(unichar):
        return False
    if unicodedata.name(unichar) in [*DIACRITIC_TO_TONE, *TONE_BAR_TO_TONE]:
        return False

    category = unicodedata.category(unichar)
    return category in ("Lm", "Mn", "Sk")  # dʷ ẽ ɚ


def is_connector(unichar: str) -> bool:
    """Checks whether a unicode character is a connector."""
    category = unicodedata.category(unichar)
    name = unicodedata.name(unichar)
    return category == "Mn" and "DOUBLE BREVE" in name or category == "Pc" and "TIE" in name


def is_subscript(unichar: str) -> bool:
    """Checks whether a character is a subscript."""
    return "SUBSCRIPT" in unicodedata.name(unichar)


DIACRITIC_TO_TONE: dict[str, tuple[int, ...]] = {
    "COMBINING DOUBLE ACUTE ACCENT": (0,),  # top
    "COMBINING ACUTE ACCENT": (1,),  # high
    "COMBINING MACRON": (3,),  # mid
    "COMBINING GRAVE ACCENT": (5,),  # low
    "COMBINING DOUBLE GRAVE ACCENT": (6,),  # bottom
    "COMBINING CIRCUMFLEX ACCENT": (1, 5),  # falling
    "COMBINING ACUTE-MACRON": (1, 3),  # high falling
    "COMBINING MACRON-GRAVE": (3, 5),  # low falling
    "COMBINING CARON": (5, 1),  # rising
    "COMBINING MACRON-ACUTE": (3, 1),  # high rising
    "COMBINING GRAVE-MACRON": (5, 3),  # low rising
    "COMBINING ACUTE-GRAVE-ACUTE": (1, 5, 1),  # dipping
    "COMBINING GRAVE-ACUTE-GRAVE": (5, 1, 5),  # peaking
}
TONE_NAME_TO_TONES: dict[str, tuple[int, ...]] = {
    "top": (0,),
    "high": (1,),
    "mid": (3,),
    "low": (5,),
    "bottom": (6,),
    "falling": (1, 5),
    "high falling": (1, 3),
    "low falling": (3, 5),
    "rising": (5, 1),
    "high rising": (3, 1),
    "low rising": (5, 3),
    "dipping": (1, 5, 1),
    "peaking": (5, 1, 5),
}
TONE_BAR_TO_TONE: dict[str, int] = {
    "MODIFIER LETTER EXTRA-HIGH TONE BAR": 1,
    "MODIFIER LETTER HIGH TONE BAR": 2,
    "MODIFIER LETTER MID TONE BAR": 3,
    "MODIFIER LETTER LOW TONE BAR": 4,
    "MODIFIER LETTER EXTRA-LOW TONE BAR": 5,
    "MODIFIER LETTER EXTRA-HIGH DOTTED TONE BAR": 1,
    "MODIFIER LETTER HIGH DOTTED TONE BAR": 2,
    "MODIFIER LETTER MID DOTTED TONE BAR": 3,
    "MODIFIER LETTER LOW DOTTED TONE BAR": 4,
    "MODIFIER LETTER EXTRA-LOW DOTTED TONE BAR": 5,
}
TONE_TO_TONE_BAR: dict[int, str] = {
    0: "MODIFIER LETTER EXTRA-HIGH TONE BAR",
    1: "MODIFIER LETTER EXTRA-HIGH TONE BAR",
    2: "MODIFIER LETTER HIGH TONE BAR",
    3: "MODIFIER LETTER MID TONE BAR",
    4: "MODIFIER LETTER LOW TONE BAR",
    5: "MODIFIER LETTER EXTRA-LOW TONE BAR",
    6: "MODIFIER LETTER EXTRA-LOW TONE BAR",
}


class Tokenizer:
    expr: str
    i: int = 0

    def __init__(self, expr: str) -> None:
        self.expr = unicodedata.normalize("NFD", expr)

    def read_char(self) -> str:
        """Reads the next char."""
        if self.i < len(self.expr):
            x = self.expr[self.i]
        else:
            x = ""

        self.i += 1
        return x

    def peek_char(self, dist: int = 0) -> str:
        """Reads the next char without moving forward."""
        if (self.i + dist) < len(self.expr):
            if self.expr[self.i + dist]:
                pass
            return self.expr[self.i + dist]

        return ""

    def lineend(self) -> bool:
        """Checks whether we are at the end of the line expression"""
        return self.i >= len(self.expr) or self.peek_char() == "\n"

    def skip_line(self) -> str:
        line = ""
        while not self.lineend():
            line += self.read_char()

        if self.peek_char() == "\n":
            line += self.read_char()

        return line

    def skip_spaces(self) -> None:
        while self.peek_char() == " ":
            self.read_char()


class PhoneticTokenizer(Tokenizer):
    def read_phoneme_and_suprasegmentals(self) -> tuple[Phoneme, str]:
        """Read a phoneme maybe followed by attributes or containing suprasegmental information.."""
        base = self.read_char()
        while not self.lineend() and is_subscript(self.peek_char()):
            base += self.read_char()
        while not self.lineend() and is_connector(self.peek_char()):
            _tie = self.read_char()
            base += self.read_char()
            while not self.lineend() and is_subscript(self.peek_char()):
                base += self.read_char()

        # TODO: subscripts as part of base

        suprasegmental_modifiers = ""
        diacritics: list[str] = []
        while not self.lineend():
            if is_length_modifier(self.peek_char()):
                diacritics.append("")
                while is_length_modifier(self.peek_char()):
                    diacritics[-1] += self.read_char()
                continue
            elif unicodedata.name(self.peek_char()) in DIACRITIC_TO_TONE:
                suprasegmental_modifiers += self.read_char()
            elif is_modifier(self.peek_char()):
                diacritics.append(self.read_char())
                continue
            else:
                break

        modifiers: list[Modifier] = []
        while self.peek_char() == "[":
            modifiers.append(self.read_bracketed_modifier())

        return Phoneme(base, diacritics, modifiers), suprasegmental_modifiers

    def read_phoneme(self) -> Phoneme:
        """Read just a phoneme, asserting there is no suprasegmental information."""
        p, s = self.read_phoneme_and_suprasegmentals()
        assert not s, "Suprasegmental information must not be present in sound change, consider using modifiers e.g. [+stress] or [+high tone]"
        return p

    def read_bracketed_modifier(self) -> Modifier:
        """Read an attribute in brackets."""
        assert self.read_char() == "["

        if self.peek_char() in ("+", "-"):
            positive = self.read_char() == "+"
        else:
            positive = True

        x: str = ""
        while True:
            if self.lineend():
                raise TypeError("Unclosed square bracket")
            if self.peek_char() == "[":
                raise TypeError("Cannot nest attributes, must be chained")
            if self.peek_char() == "]":
                assert self.read_char() == "]"
                break

            x += self.read_char()

        return Modifier(positive, x)

    def read_phoneme_collection(self) -> PhonemeGroup:
        """Read a collection of possible phonemes"""
        assert self.read_char() == "{"

        collection: list[list[Phoneme]] = [[]]
        while self.peek_char() != "}":
            if self.peek_char() in (",", " "):
                self.read_char()
                collection.append([])
                continue

            collection[-1].append(self.read_phoneme())

        assert self.read_char() == "}"
        return PhonemeGroup(None, collection)

    def read_phoneme_or_collection(self) -> Phoneme | PhonemeGroup:
        if self.peek_char() == "{":
            return self.read_phoneme_collection()

        return self.read_phoneme()


class SoundChangeTokenizer(PhoneticTokenizer):
    def tokenize(self) -> list[SoundChange | PhonemeGroup]:
        """Convert the whole file into a list of sound changes and group definitions."""
        x: list[SoundChange | PhonemeGroup] = []
        while self.i < len(self.expr):
            if self.peek_char() in ("\n", "\t", " "):
                _whitespace = self.read_char()
                continue
            if self.peek_char() == "#":
                self.skip_line()
                continue
            if self.peek_char(+1) == "=":
                x.append(self.tokenize_phoneme_group_line())
                continue
            x.extend(self.tokenize_line())

        return x

    def tokenize_line(self) -> list[SoundChange]:
        """Convert the expression line into a sound change token."""
        sources: list[list[Phoneme | PhonemeGroup]] = [[]]
        outputs: list[list[Phoneme | PhonemeGroup]] = [[]]

        for part in (sources, outputs):
            self.skip_spaces()
            while not self.lineend():
                char = self.peek_char()
                if char == " ":
                    self.skip_spaces()
                    if part[-1]:
                        part.append([])
                    continue
                if char == "∅":
                    _null = self.read_char()
                    continue
                if char in "/>→":
                    _sep = self.read_char()
                    break
                if char == "[":
                    modifiers: list[Modifier] = []
                    while self.peek_char() == "[":
                        modifiers.append(self.read_bracketed_modifier())
                    part[-1].append(PhonemeGroup("", modifiers=modifiers))
                    continue

                part[-1].append(self.read_phoneme_or_collection())

            if self.lineend() and part == sources:
                raise Exception("Line is missing output and conditions")

        if len(sources) > 1:
            sources = [x for x in sources if x]
        if len(outputs) > 1:
            outputs = [x for x in outputs if x]
        if len(sources) != len(outputs) and len(outputs) > 1:
            raise Exception("Mismatched source/output sizes")

        # TODO: allow condition to be just +stress
        conditions: list[tuple[list[Phoneme | PhonemeGroup | ConditionChar], bool]] = [([], True)]
        self.skip_spaces()
        while not self.lineend():
            char = self.peek_char()
            if char == " ":
                self.skip_spaces()
                if conditions[-1][0]:
                    conditions.append(([], True))
                continue
            if char == "∅":
                _null = self.read_char()
                continue
            if char in "/!":
                sep = self.read_char()
                conditions.append(([], sep != "!"))
                continue
            if char == "[":
                modifiers: list[Modifier] = []
                while self.peek_char() == "[":
                    modifiers.append(self.read_bracketed_modifier())
                conditions[-1][0].append(PhonemeGroup("", modifiers=modifiers))
                continue
            if char in ("_", "#"):
                c = typing.cast("typing.Literal['_', '#']", self.read_char())
                modifiers: list[Modifier] = []
                while self.peek_char() == "[":
                    modifiers.append(self.read_bracketed_modifier())
                conditions[-1][0].append(ConditionChar(c, modifiers))
                continue

            conditions[-1][0].append(self.read_phoneme_or_collection())

        scs: list[SoundChange] = []
        conditions = [cond for cond in conditions if cond[0]]
        for source, output in itertools.zip_longest(sources, outputs, fillvalue=None):
            scs.append(SoundChange(source or sources[0], output or outputs[0], conditions))

        return scs

    def tokenize_phoneme_group_line(self) -> PhonemeGroup:
        """Tokenize a phoneme group definition."""
        name = self.read_char()
        assert self.read_char() == "="
        if self.peek_char() == "[":
            modifiers: list[Modifier] = []
            while self.peek_char() == "[":
                modifiers.append(self.read_bracketed_modifier())
            return PhonemeGroup(name, modifiers=modifiers)

        if self.peek_char() == "{":
            return PhonemeGroup(name, self.read_phoneme_collection().collection)

        raise Exception("Phoneme group definition must be A=[+modifier] or A={a,b}")


class WordTokenizer(PhoneticTokenizer):
    def tokenize(self) -> list[Word]:
        """Tokenize a list of IPA words."""
        words: list[Word] = []

        while self.i < len(self.expr):
            if self.peek_char() in ("\n", "\t", " "):
                _whitespace = self.read_char()
                continue
            if self.peek_char() == "#":
                self.skip_line()
                continue
            words.append(self.tokenize_word())

        return words

    def tokenize_word(self) -> Word:
        """Tokenize a word written in the IPA."""
        phonemes: list[Phoneme] = []
        suprasegmentals: list[Suprasegmentals] = [Suprasegmentals()]

        if self.peek_char() == "ˈ":
            self.read_char()
            suprasegmentals[0].stress = True

        while not self.lineend():
            if self.peek_char() in (" ", "\t"):
                _whitespace = self.read_char()
                continue
            if self.peek_char() == ".":
                self.read_char()
                suprasegmentals.append(Suprasegmentals(stress=False))
                continue
            if self.peek_char() == "ˈ":
                self.read_char()
                suprasegmentals.append(Suprasegmentals(stress=True))
                continue
            if unicodedata.name(self.peek_char()) in TONE_BAR_TO_TONE:
                tones: list[int] = []
                while unicodedata.name(self.peek_char()) in TONE_BAR_TO_TONE:
                    tones.append(TONE_BAR_TO_TONE[unicodedata.name(self.read_char())])
                suprasegmentals[-1].tone = tones
                if self.peek_char() not in (".", "ˈ"):
                    suprasegmentals.append(Suprasegmentals(stress=False))

            p, sm = self.read_phoneme_and_suprasegmentals()
            p.syllable = len(suprasegmentals) - 1
            phonemes.append(p)
            if sm:
                suprasegmentals[-1].tone = DIACRITIC_TO_TONE[unicodedata.name(sm)]

        word = Word(phonemes, suprasegmentals)
        for s in suprasegmentals:
            s._word_pointer = word # noqa # type: ignore
        return word


def tokenize_sound_change_file(expr: str) -> list[SoundChange | PhonemeGroup]:
    """Tokenize a sound change file."""
    return SoundChangeTokenizer(expr).tokenize()


def tokenize_words(expr: str) -> list[Word]:
    """Tokenize a list of IPA words."""
    return WordTokenizer(expr).tokenize()
