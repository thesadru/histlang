"""Sound change executor."""

import copy
import itertools
import typing
import unicodedata

from . import database, tokens
import dataclasses


@dataclasses.dataclass
class Match:
    """Matched word segment descriptor."""

    start: int
    """Starting index of in word."""
    end: int
    """Ending index of match in word."""
    group_matches: typing.Mapping[int, int]
    """Indexes of matched characters in listed groups (such as {p,t,k})."""
    modifier_group_matches: typing.Mapping[str | None, tokens.Phoneme]
    """Matched characters in groups only defined by modifiers (such as C). These must always be named."""


TONE_NAMES = ["top", "high", "high-mid", "mid", "low-mid", "low", "bottom"]


def tone_numbers_to_name(bars: typing.Sequence[int]) -> str:
    """Collapse up to 3 tone bars into a named tone."""
    bars = [i for i, next_i in itertools.zip_longest(bars, bars[1:]) if i != next_i]
    if len(bars) == 0:
        return "mid"
    elif len(bars) == 1:
        return TONE_NAMES[bars[0]]
    elif len(bars) == 2:
        if bars[0] < bars[1]:
            if bars[0] <= 3 and bars[1] >= 3:
                return "rising"
            elif bars[0] > 3:
                return "high rising"
            else:
                return "low rising"
        else:
            if bars[0] >= 3 and bars[1] <= 3:
                return "falling"
            elif bars[0] < 3:
                return "low falling"
            else:
                return "high falling"
    elif len(bars) == 3:
        if bars[0] < bars[1]:
            return "peaking"
        else:
            return "dipping"
    else:
        raise Exception("Tones variating by more than 3 levels cannot be named")


def get_exclusivity_of_metadata_value(value: str) -> str | None:
    """Get the category of exclusivity of a given metadata."""
    for exclusivity_key, exclusivity_values in database.metadata_exclusivity.items():
        if value in exclusivity_values:
            return exclusivity_key

    return None


def group_metadata_by_exclusivity(metadatas: typing.Collection[str]) -> tuple[dict[str, str], list[str]]:
    """Group metadata into inexclusive and exclusive categories."""
    exclusive: dict[str, str] = {}
    inexclusive: list[str] = []
    for metadata in metadatas:
        if exclusivity_key := get_exclusivity_of_metadata_value(metadata):
            exclusive[exclusivity_key] = metadata
        else:
            inexclusive.append(metadata)

    return exclusive, inexclusive


def combine_metadata_exclusively(*collections: typing.Collection[str]) -> list[str]:
    """Combine collections of metadata like with a phoneme and diacritic."""
    exclusive, inexclusive = group_metadata_by_exclusivity([j for i in collections for j in i])
    return [*exclusive.values(), *inexclusive]


def diacritics_to_metadata(diacritics: typing.Sequence[str]) -> list[str]:
    """Convert a collection of diacritics into metadata."""
    metadata: list[str] = []
    for diacritic in diacritics:
        for diacritic_metadata in database.diacritics:
            if diacritic_metadata.unichar == diacritic:
                metadata += diacritic_metadata.metadata
                break
        else:
            raise Exception(f"Unknown diacritic {'◌' + diacritic} ({unicodedata.name(diacritic)})")

    return metadata


def get_phoneme_metadata(phoneme: tokens.Phoneme) -> tuple[list[str], list[tokens.Modifier]]:
    """Get the metadata of a phoneme and include modifiers."""
    metadata: list[str] = []
    for phoneme_metadata in database.phonemes:
        if phoneme_metadata.unichar == phoneme.basephoneme:
            metadata += phoneme_metadata.metadata
            break
    else:
        raise Exception(f"Unknown base phoneme {phoneme.basephoneme}")

    return combine_metadata_exclusively(metadata, diacritics_to_metadata(phoneme.diacritics)), list(phoneme.modifiers)


def get_suprasegmentals_metadata(suprasegmentals: tokens.Suprasegmentals) -> list[str]:
    """Get suprasegmental data into metadata form."""
    all_suprasegmentals = suprasegmentals._word_pointer.suprasegmentals  # noqa # type: ignore
    syllable_count = len(all_suprasegmentals)
    syllable_index = all_suprasegmentals.index(suprasegmentals)
    stressed_syllable_index = next((i for i, x in enumerate(all_suprasegmentals) if x.stress), None)
    return (
        [tone_numbers_to_name(suprasegmentals.tone) + " tone"]
        + (["stress"] if suprasegmentals.stress else [])
        + (
            ["intertonic"]
            if ((syllable_index == 0 or syllable_index == syllable_count - 1) and stressed_syllable_index and abs(stressed_syllable_index - syllable_index) == 1)
            else []
        )
        + (["pretonic"] if stressed_syllable_index and syllable_index == stressed_syllable_index - 1 else [])
        + (["posttonic"] if stressed_syllable_index and syllable_index == stressed_syllable_index + 1 else [])
        + (["monosyllable"] if syllable_count == 1 else [])
    )


def get_phoneme_metadata_with_suprasegmentals(phoneme: tokens.Phoneme, suprasegmental: tokens.Suprasegmentals) -> list[str]:
    """Combine phoneme metadata with suprasegmental metadata to include stress."""
    metadata, _ = get_phoneme_metadata(phoneme)
    return metadata + get_suprasegmentals_metadata(suprasegmental)


def is_metadata_matching(metadata: typing.Collection[str], requirements: typing.Collection[tokens.Modifier | str]) -> bool:
    """Checks whether metadata matches requirements."""
    return all((r.value in metadata) == r.positive if isinstance(r, tokens.Modifier) else r in metadata for r in requirements)


def is_phoneme_matching_modifiers(
    phoneme: tokens.Phoneme,
    metadata: typing.Collection[str],
    modifiers: typing.Collection[tokens.Modifier],
    suprasegmentals: tokens.Suprasegmentals,
) -> bool:
    """Checks whether a word phoneme matches a set of diacritics and modifiers."""
    return is_metadata_matching(
        get_phoneme_metadata_with_suprasegmentals(phoneme, suprasegmentals),
        [*combine_metadata_exclusively(metadata), *modifiers],
    )


def is_phoneme_matching(
    phoneme: tokens.Phoneme,
    condition: tokens.Phoneme,
    suprasegmentals: tokens.Suprasegmentals,
) -> bool:
    """Checks whether a word phoneme matches a condition."""
    return is_phoneme_matching_modifiers(phoneme, *get_phoneme_metadata(condition), suprasegmentals)


def find_differing_phoneme(phoneme: tokens.Phoneme, modifiers: typing.Sequence[tokens.Modifier]) -> tokens.Phoneme:
    """Find a new phoneme that matches in all aspects except with set modifiers changed."""
    assert not phoneme.modifiers

    # get old phoneme metadata
    old_metadata: list[str] = []
    for phoneme_metadata in database.phonemes:
        if phoneme_metadata.unichar == phoneme.basephoneme:
            old_metadata += phoneme_metadata.metadata
            break
    else:
        raise Exception(f"Unknown base phoneme {phoneme.basephoneme}")

    for diacritic in phoneme.diacritics:
        for diacritic_metadata in database.diacritics:
            if diacritic_metadata.unichar == diacritic:
                old_metadata += diacritic_metadata.metadata
                break
        else:
            raise Exception(f"Unknown diacritic {'◌' + diacritic}")

    required_metadata_exclusive, required_metadata_inclusive = group_metadata_by_exclusivity(old_metadata)
    forbidden_metadata_exclusive: dict[str, str] = {}

    for mod in modifiers:
        if mod.positive:
            if exclusivity_key := get_exclusivity_of_metadata_value(mod.value):
                required_metadata_exclusive[exclusivity_key] = mod.value
            else:
                required_metadata_inclusive.append(mod.value)
        else:
            if exclusivity_key := get_exclusivity_of_metadata_value(mod.value):
                if exclusivity_key in required_metadata_exclusive:
                    del required_metadata_exclusive[exclusivity_key]
                forbidden_metadata_exclusive[exclusivity_key] = mod.value
            else:
                if mod.value in required_metadata_inclusive:
                    required_metadata_inclusive.remove(mod.value)

    # it must have exactly: all required inclusive + all required exclusive + any not in forbidden exclusive
    # brute-force search all possible phonemes, then pick the best one
    possible_phonemes: list[tokens.Phoneme] = []
    for potential_basephoneme in database.phonemes:
        potential_basephoneme_metadata_exclusive, potential_basephoneme_metadata_inclusive = group_metadata_by_exclusivity(potential_basephoneme.metadata)

        if not all(
            exclusivity_key in required_metadata_exclusive or exclusivity_key in forbidden_metadata_exclusive
            for exclusivity_key, _ in potential_basephoneme_metadata_exclusive.items()
        ):
            continue
        if not all(metadata in required_metadata_inclusive for metadata in potential_basephoneme_metadata_inclusive):
            continue
        remaining_metadata_exclusive = {
            exclusivity_key: metadata
            for exclusivity_key, metadata in required_metadata_exclusive.items()
            if exclusivity_key not in potential_basephoneme_metadata_exclusive or potential_basephoneme_metadata_exclusive[exclusivity_key] != metadata
        }
        remaining_forbidden_metadata_exclusive = {
            exclusivity_key: metadata
            for exclusivity_key, metadata in forbidden_metadata_exclusive.items()
            if potential_basephoneme_metadata_exclusive.get(exclusivity_key) == metadata
        }
        remaining_metadata_inclusive = [i for i in required_metadata_inclusive if i not in potential_basephoneme_metadata_inclusive]

        required_diacritics: list[str] = []
        for potential_diacritic in database.diacritics:
            potential_diacritic_metadata_exclusive, potential_diacritic_metadata_inclusive = group_metadata_by_exclusivity(potential_diacritic.metadata)
            if not all(
                (exclusivity_key in remaining_metadata_exclusive and remaining_metadata_exclusive[exclusivity_key] == metadata)
                or (exclusivity_key in remaining_forbidden_metadata_exclusive and remaining_forbidden_metadata_exclusive[exclusivity_key] != metadata)
                for exclusivity_key, metadata in potential_diacritic_metadata_exclusive.items()
            ):
                continue
            if not all(metadata in remaining_metadata_inclusive for metadata in potential_diacritic_metadata_inclusive):
                continue

            remaining_metadata_exclusive = {k: v for k, v in remaining_metadata_exclusive.items() if k not in potential_diacritic_metadata_exclusive}
            remaining_forbidden_metadata_exclusive = {k: v for k, v in remaining_forbidden_metadata_exclusive.items() if k not in potential_diacritic_metadata_exclusive}
            remaining_metadata_inclusive = [i for i in remaining_metadata_inclusive if i not in potential_diacritic_metadata_inclusive]

            required_diacritics.append(potential_diacritic.unichar)

        if not remaining_metadata_inclusive and not remaining_metadata_exclusive:
            possible_phonemes.append(tokens.Phoneme(potential_basephoneme.unichar, required_diacritics, syllable=phoneme.syllable))

    if possible_phonemes:
        return min(possible_phonemes, key=lambda i: len(i.diacritics))

    required, forbidden = (*required_metadata_exclusive.values(), *required_metadata_inclusive), (*forbidden_metadata_exclusive.values(),)
    raise Exception(f"Cannot create {phoneme}{''.join(map(str, modifiers))} (i.e. phoneme with [{','.join(required)}] without [{''.join(forbidden)}])")


def find_source_match(
    word: tokens.Word,
    source_matcher: typing.Sequence[tokens.Phoneme | tokens.PhonemeGroup],
) -> list[Match]:
    """Find all possible matches inside of word."""
    matches: typing.Sequence[Match] = []
    possible_group_indexes = [(len(i.collection) or 1) if isinstance(i, tokens.PhonemeGroup) else 1 for i in source_matcher]
    for group_indexes in itertools.product(*[range(i) for i in possible_group_indexes]):
        for start in range(len(word.phonemes)):
            match_start = start
            cur_index = start
            group_matches: typing.Mapping[int, int] = {}
            modifier_group_matches: typing.Mapping[str | None, tokens.Phoneme] = {}
            group_matches_index = 0

            for match_token_idx, match_token in enumerate(source_matcher):
                if cur_index >= len(word.phonemes):
                    break

                if isinstance(match_token, tokens.Phoneme):
                    if not is_phoneme_matching(word.phonemes[cur_index], match_token, word.suprasegmentals[word.phonemes[cur_index].syllable]):
                        break
                    cur_index += 1
                elif len(match_token.collection) == 0:
                    if not is_phoneme_matching_modifiers(
                        word.phonemes[cur_index],
                        match_token.diacritics,
                        match_token.modifiers,
                        word.suprasegmentals[word.phonemes[cur_index].syllable],
                    ):
                        break
                    modifier_group_matches[match_token.name] = word.phonemes[cur_index]
                    cur_index += 1
                else:
                    for subtoken in match_token.collection[group_indexes[match_token_idx]]:
                        if cur_index >= len(word.phonemes):
                            break
                        met = [*get_phoneme_metadata(subtoken)[0], *match_token.diacritics]
                        if not is_phoneme_matching_modifiers(
                            word.phonemes[cur_index],
                            met,
                            match_token.modifiers,
                            word.suprasegmentals[word.phonemes[cur_index].syllable],
                        ):
                            break
                        cur_index += 1
                        group_matches_index += 1
                        group_matches[group_matches_index] = group_indexes[match_token_idx]
                    else:
                        continue
                    break
            else:
                matches.append(Match(match_start, cur_index - 1, group_matches, modifier_group_matches))

    return matches


def check_condition_match(
    word: tokens.Word,
    match: Match,
    condition: typing.Sequence[tokens.Phoneme | tokens.PhonemeGroup | tokens.ConditionChar],
) -> bool:
    """Check whether a match segment in a word works under the condition."""
    # condition matches PhonemeGroup independently of source and output
    possible_group_indexes = [(len(i.collection) or 1) if isinstance(i, tokens.PhonemeGroup) else 1 for i in condition]
    for group_indexes in itertools.product(*[range(i) for i in possible_group_indexes]):
        for start in range(len(word.phonemes)):
            cur_index = start
            if cur_index >= len(word.phonemes):
                break

            for match_token_idx, match_token in enumerate(condition):
                if cur_index < 0 or cur_index >= len(word.phonemes):
                    if not (isinstance(match_token, tokens.ConditionChar) and match_token.char == "#"):
                        break
                elif isinstance(match_token, tokens.ConditionChar):
                    if match_token.char == "#" and cur_index > 0 and cur_index < len(word.phonemes):
                        break
                    else:  # match_token.char == "_"
                        if cur_index != match.start or not is_phoneme_matching_modifiers(
                            word.phonemes[cur_index],
                            [],
                            match_token.modifiers,
                            word.suprasegmentals[word.phonemes[cur_index].syllable],
                        ):
                            break
                        cur_index = match.end + 1
                        continue
                elif isinstance(match_token, tokens.Phoneme):
                    if not is_phoneme_matching(word.phonemes[cur_index], match_token, word.suprasegmentals[word.phonemes[cur_index].syllable]):
                        break
                    cur_index += 1
                elif len(match_token.collection) == 0:
                    if not is_phoneme_matching_modifiers(
                        word.phonemes[cur_index],
                        match_token.diacritics,
                        match_token.modifiers,
                        word.suprasegmentals[word.phonemes[cur_index].syllable],
                    ):
                        break
                    cur_index += 1
                else:
                    for subtoken in match_token.collection[group_indexes[match_token_idx]]:
                        met = [*get_phoneme_metadata(subtoken)[0], *match_token.diacritics]
                        if not is_phoneme_matching_modifiers(
                            word.phonemes[cur_index],
                            met,
                            match_token.modifiers,
                            word.suprasegmentals[word.phonemes[cur_index].syllable],
                        ):
                            break
                        cur_index += 1
                    else:
                        continue
                    break
            else:
                return True

    return False


def find_soundchange_matches(word: tokens.Word, change: tokens.SoundChange) -> list[Match]:
    """Find all segments to be replaced, ensuring matches do not overlap."""
    matches: list[Match] = []
    last_end = -1
    for match in find_source_match(word, change.source):
        if all(check_condition_match(word, match, c) == b for c, b in change.conditions) and match.start > last_end:
            matches.append(match)
            last_end = match.end

    return matches


def determine_syllable_of_match(word: tokens.Word, match: Match) -> int:
    """Determine the syllable for a given match by finding the corresponding vowel."""
    for idx in range(match.start, match.end + 1):
        m, _ = get_phoneme_metadata(word.phonemes[idx])
        if "vowel" in m or "syllabic" in m:
            return word.phonemes[idx].syllable

    return word.phonemes[match.start].syllable


def apply_change_to_match(
    word: tokens.Word,
    change: typing.Sequence[tokens.Phoneme | tokens.PhonemeGroup],
    match: Match,
) -> list[tokens.Phoneme]:
    """Generate a new phoneme sequence from a match. Modifies suprasegmentals in place"""
    # TODO: Backreferences (potentially $₁)
    syllable = determine_syllable_of_match(word, match)
    result: list[tokens.Phoneme] = []
    group_matches_index = 0
    for change_token in change:
        differing_modifiers: list[tokens.Modifier] = []
        if change_token.modifiers:
            for i in change_token.modifiers:
                if i.value == "stress":
                    word.suprasegmentals[syllable].stress = i.positive
                elif " tone" in i.value:
                    word.suprasegmentals[syllable].tone = tokens.TONE_NAME_TO_TONES[i.value.removesuffix(" tone")]
                else:
                    differing_modifiers.append(i)

            if not (isinstance(change_token, tokens.PhonemeGroup) and len(change_token.collection) == 0):
                raise Exception("Modifiers on plain phonemes not supported, use a group or write the modified phoneme.")

        if isinstance(change_token, tokens.PhonemeGroup):
            if len(change_token.collection) == 0:
                old_p = match.modifier_group_matches[change_token.name]
                p = find_differing_phoneme(old_p, differing_modifiers)
                result.append(
                    tokens.Phoneme(
                        p.basephoneme,
                        list({*p.diacritics, *change_token.diacritics}),
                        [],  # these will always be empty no matter what
                        syllable,
                    )
                )
            else:
                result.extend(
                    [
                        tokens.Phoneme(
                            p.basephoneme,
                            list({*p.diacritics, *change_token.diacritics}),
                            [],  # these will always be empty no matter what
                            syllable,
                        )
                        for p in change_token.collection[
                            match.group_matches[group_matches_index]
                        ]  # this is incorrect, must separate into usable ones, also note the possibility of empty collection, maybe use named matches instead?
                    ]
                )
                group_matches_index += 1
        else:
            result.append(
                tokens.Phoneme(
                    change_token.basephoneme,
                    change_token.diacritics,
                    [],
                    syllable,
                )
            )

    return result


def apply_sound_change(
    word: tokens.Word,
    change: tokens.SoundChange,
) -> None:
    """Apply a sound change to a word in-place"""
    # TODO: clean up unused suprasegmentals from syllable erosion
    assert isinstance(word.phonemes, typing.MutableSequence)
    for match in find_soundchange_matches(word, change):
        word.phonemes[match.start : match.end + 1] = apply_change_to_match(word, change.output, match)


def apply_sound_changes(
    word: tokens.Word,
    changes: typing.Collection[tokens.SoundChange],
) -> tokens.Word:
    """Apply a series of sound changes to a word and return its new form."""
    word = copy.deepcopy(word)
    for change in changes:
        apply_sound_change(word, change)

    return word


def turn_phoneme_into_phoneme_or_phonemegroup(
    p: tokens.Phoneme | tokens.PhonemeGroup,
    groups: typing.Mapping[str, tokens.PhonemeGroup],
) -> tokens.Phoneme | tokens.PhonemeGroup:
    """Turn a Phoneme or PhonemeGroup into a proper PhonemeGroup based on context."""
    if isinstance(p, tokens.PhonemeGroup):
        for child in p.collection:
            for child_segment in child:
                if isinstance(child_segment, tokens.PhonemeGroup):
                    # arbitrary but necessary
                    raise Exception("Must not nest phoneme groups")
        return p

    if not (group := groups.get(p.basephoneme)):
        return p

    return tokens.PhonemeGroup(
        group.name,
        group.collection,
        p.diacritics,
        list({mod.value: mod for mod in [*p.modifiers, *group.modifiers]}.values()),
    )


def preprocess_soundchange_with_context(
    sc: tokens.SoundChange,
    groups: typing.Collection[tokens.PhonemeGroup],
) -> tokens.SoundChange:
    """Transform Phoneme into PhonemeGroup based on context."""
    group_by_name = {group.name: group for group in groups if group.name is not None}
    return tokens.SoundChange(
        [turn_phoneme_into_phoneme_or_phonemegroup(i, group_by_name) for i in sc.source],
        [turn_phoneme_into_phoneme_or_phonemegroup(i, group_by_name) for i in sc.output],
        [
            (
                [i if isinstance(i, tokens.ConditionChar) else turn_phoneme_into_phoneme_or_phonemegroup(i, group_by_name) for i in c],
                b,
            )
            for c, b in sc.conditions
        ],
    )


def tokenize_sound_changes(expr: str) -> list[tokens.SoundChange]:
    """Tokenize a sound change file and preprocess it."""
    toks = tokens.tokenize_sound_change_file(expr)
    sc, groups = [i for i in toks if isinstance(i, tokens.SoundChange)], [i for i in toks if isinstance(i, tokens.PhonemeGroup)]
    return [preprocess_soundchange_with_context(i, groups) for i in sc]
