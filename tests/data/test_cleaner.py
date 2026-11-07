"""Tests for ArabicTextCleaner. Uses only short, made-up example texts."""

from __future__ import annotations

import pytest

from arabic_dialect_identification_v2.data.cleaner import ArabicTextCleaner
from arabic_dialect_identification_v2.data.config import CleaningSettings

FATHA = "\N{ARABIC FATHA}"
DAMMA = "\N{ARABIC DAMMA}"
KASRA = "\N{ARABIC KASRA}"
SHADDA = "\N{ARABIC SHADDA}"
SUKUN = "\N{ARABIC SUKUN}"
TANWEEN = ("\N{ARABIC FATHATAN}", "\N{ARABIC DAMMATAN}", "\N{ARABIC KASRATAN}")
DAGGER_ALEF = "\N{ARABIC LETTER SUPERSCRIPT ALEF}"


def _settings(
    placeholders: tuple[str, ...] = ("حسابشخصي", "حسابشخصى", "رابطويب"),
    max_letter_repeats: int = 2,
    max_symbol_repeats: int = 1,
    protected_word_fragment: str = "لله",
) -> CleaningSettings:
    return CleaningSettings(
        placeholders=placeholders,
        max_letter_repeats=max_letter_repeats,
        max_symbol_repeats=max_symbol_repeats,
        protected_word_fragment=protected_word_fragment,
    )


@pytest.fixture
def cleaner() -> ArabicTextCleaner:
    return ArabicTextCleaner(_settings())


ALL_RULES = [
    "clean",
    "remove_placeholders",
    "remove_tatweel",
    "remove_diacritics",
    "normalize_alef",
    "reduce_repeated_letters",
    "reduce_repeated_symbols",
    "normalize_whitespace",
]


@pytest.mark.parametrize("rule", ALL_RULES)
@pytest.mark.parametrize("not_text", [None, 123, float("nan")])
def test_every_rule_rejects_non_text(cleaner: ArabicTextCleaner, rule: str, not_text: object) -> None:
    with pytest.raises(TypeError, match="Expected text as str"):
        getattr(cleaner, rule)(not_text)


@pytest.mark.parametrize("rule", ALL_RULES)
def test_every_rule_keeps_empty_text_empty(cleaner: ArabicTextCleaner, rule: str) -> None:
    assert getattr(cleaner, rule)("") == ""


# ---------- Rule 1: placeholders ----------


@pytest.mark.parametrize("placeholder", ["حسابشخصي", "حسابشخصى", "رابطويب"])
def test_each_placeholder_is_removed(cleaner: ArabicTextCleaner, placeholder: str) -> None:
    result = cleaner.remove_placeholders(f"{placeholder} انزين")
    assert placeholder not in result
    assert result.split() == ["انزين"]


def test_several_placeholders_in_one_text_are_all_removed(cleaner: ArabicTextCleaner) -> None:
    result = cleaner.remove_placeholders("حسابشخصي كيفك حسابشخصى شوف رابطويب")
    assert result.split() == ["كيفك", "شوف"]


def test_placeholder_stuck_to_words_does_not_glue_them(cleaner: ArabicTextCleaner) -> None:
    result = cleaner.remove_placeholders("مرحبارابطويبيا")
    assert result.split() == ["مرحبا", "يا"]


def test_repeated_placeholders_back_to_back_are_removed(cleaner: ArabicTextCleaner) -> None:
    assert cleaner.remove_placeholders("حسابشخصيحسابشخصي").strip() == ""


def test_text_without_placeholders_is_unchanged(cleaner: ArabicTextCleaner) -> None:
    text = "صباح الخير يا جماعة"
    assert cleaner.remove_placeholders(text) == text


def test_similar_but_different_words_are_kept(cleaner: ArabicTextCleaner) -> None:
    text = "حساب شخصي و رابط ويب"
    assert cleaner.remove_placeholders(text) == text


def test_placeholders_come_from_settings() -> None:
    cleaner = ArabicTextCleaner(_settings(placeholders=("@USER",)))
    assert cleaner.remove_placeholders("@USER hi").split() == ["hi"]


def test_no_placeholders_configured_leaves_text_unchanged() -> None:
    cleaner = ArabicTextCleaner(_settings(placeholders=()))
    assert cleaner.remove_placeholders("حسابشخصي انزين") == "حسابشخصي انزين"


def test_placeholder_with_special_regex_characters_is_matched_literally() -> None:
    cleaner = ArabicTextCleaner(_settings(placeholders=("[URL]",)))
    assert cleaner.remove_placeholders("see [URL] U R L").split() == ["see", "U", "R", "L"]


# ---------- Rule 2: tatweel ----------


def test_tatweel_inside_a_word_is_removed(cleaner: ArabicTextCleaner) -> None:
    assert cleaner.remove_tatweel("جـــميل") == "جميل"


def test_tatweel_in_several_words_is_removed(cleaner: ArabicTextCleaner) -> None:
    assert cleaner.remove_tatweel("يـا هـلا") == "يا هلا"


def test_text_that_is_only_tatweel_becomes_empty(cleaner: ArabicTextCleaner) -> None:
    assert cleaner.remove_tatweel("ـــــ") == ""


@pytest.mark.parametrize("look_alike", ["-", "_", "—", "–"])
def test_look_alike_dashes_are_not_tatweel(cleaner: ArabicTextCleaner, look_alike: str) -> None:
    text = f"كلمة{look_alike}كلمة"
    assert cleaner.remove_tatweel(text) == text


# ---------- Rule 3: diacritics (with the protected-word exception) ----------


def test_diacritics_are_removed_from_normal_words(cleaner: ArabicTextCleaner) -> None:
    assert cleaner.remove_diacritics(f"م{FATHA}ج{KASRA}يد") == "مجيد"


@pytest.mark.parametrize("mark", [FATHA, DAMMA, KASRA, SHADDA, SUKUN, *TANWEEN, DAGGER_ALEF])
def test_every_listed_diacritic_is_removed(cleaner: ArabicTextCleaner, mark: str) -> None:
    assert cleaner.remove_diacritics(f"كت{mark}ب") == "كتب"


@pytest.mark.parametrize(
    "protected_word",
    [
        f"الل{SHADDA}{FATHA}ه",  # الله
        f"و{FATHA}الل{SHADDA}{FATHA}ه{KASRA}",  # والله
        f"ب{KASRA}الل{SHADDA}{FATHA}ه{KASRA}",  # بالله
        f"ل{KASRA}ل{SHADDA}{FATHA}ه{KASRA}",  # لله
        f"الل{SHADDA}{FATHA}ه{DAMMA}م{SHADDA}",  # اللهم
        f"الل{SHADDA}{DAGGER_ALEF}ه",  # الله with dagger alef
    ],
)
def test_words_containing_lillah_keep_their_diacritics(cleaner: ArabicTextCleaner, protected_word: str) -> None:
    assert cleaner.remove_diacritics(protected_word) == protected_word


def test_only_the_protected_word_keeps_diacritics_in_a_sentence(cleaner: ArabicTextCleaner) -> None:
    allah = f"الل{SHADDA}{FATHA}ه{KASRA}"
    text = f"ب{KASRA}س{SUKUN}م{KASRA} {allah} م{FATHA}ج{KASRA}يد"
    assert cleaner.remove_diacritics(text) == f"بسم {allah} مجيد"


def test_diacritics_rule_leaves_spacing_unchanged(cleaner: ArabicTextCleaner) -> None:
    assert cleaner.remove_diacritics(f"  م{FATHA}ن   ه{FATHA}ن{FATHA}ا ") == "  من   هنا "


def test_hamza_letters_are_not_treated_as_diacritics(cleaner: ArabicTextCleaner) -> None:
    text = "أحمد إن سؤال شئ"
    assert cleaner.remove_diacritics(text) == text


def test_protected_fragment_comes_from_settings() -> None:
    cleaner = ArabicTextCleaner(_settings(protected_word_fragment="محمد"))
    text = f"م{DAMMA}ح{FATHA}م{SHADDA}{FATHA}د ق{FATHA}ل{FATHA}م"
    assert cleaner.remove_diacritics(text) == f"م{DAMMA}ح{FATHA}م{SHADDA}{FATHA}د قلم"


def test_protected_fragment_written_with_diacritics_still_matches() -> None:
    cleaner = ArabicTextCleaner(_settings(protected_word_fragment=f"ل{SHADDA}{FATHA}ه"))
    allah = f"الل{SHADDA}{FATHA}ه"
    assert cleaner.remove_diacritics(allah) == allah


# ---------- Rule 4: alef ----------


@pytest.mark.parametrize(("before", "after"), [("أحمد", "احمد"), ("إن", "ان"), ("آخر", "اخر"), ("ٱلكتاب", "الكتاب")])
def test_alef_forms_become_plain_alef(cleaner: ArabicTextCleaner, before: str, after: str) -> None:
    assert cleaner.normalize_alef(before) == after


@pytest.mark.parametrize("unchanged", ["على", "علي", "مدرسة", "مدرسه", "سؤال", "شئ", "ا"])
def test_other_letters_are_not_changed_by_alef_rule(cleaner: ArabicTextCleaner, unchanged: str) -> None:
    assert cleaner.normalize_alef(unchanged) == unchanged


# ---------- Rule 5: repeated letters ----------


@pytest.mark.parametrize(
    ("before", "after"),
    [("هههههه", "هه"), ("جداااا", "جداا"), ("sooo", "soo"), ("NOOOO", "NOO"), ("ووو يا", "وو يا")],
)
def test_letters_repeated_more_than_twice_are_shortened(cleaner: ArabicTextCleaner, before: str, after: str) -> None:
    assert cleaner.reduce_repeated_letters(before) == after


@pytest.mark.parametrize("unchanged", ["الله", "هه", "good", "2000", "111111"])
def test_two_letters_and_any_digits_are_kept(cleaner: ArabicTextCleaner, unchanged: str) -> None:
    assert cleaner.reduce_repeated_letters(unchanged) == unchanged


def test_letter_limit_comes_from_settings() -> None:
    cleaner = ArabicTextCleaner(_settings(max_letter_repeats=3))
    assert cleaner.reduce_repeated_letters("هههههه") == "ههه"


# ---------- Rule 6: repeated symbols and emoji ----------


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("!!!", "!"),
        ("؟؟؟", "؟"),
        ("...", "."),
        ("😂😂😂", "😂"),
        ("😂 😂 😂", "😂"),
        ("! ! !", "!"),
        ("❤️❤️❤️", "❤️"),
        ("👍🏽👍🏽", "👍🏽"),
        ("a__b", "a_b"),
    ],
)
def test_repeated_symbols_are_shortened_to_one(cleaner: ArabicTextCleaner, before: str, after: str) -> None:
    assert cleaner.reduce_repeated_symbols(before) == after


@pytest.mark.parametrize("unchanged", ["2020", "!?", "😂🔥", "هههه", "a b c", "1,000"])
def test_digits_letters_and_different_symbols_are_kept(cleaner: ArabicTextCleaner, unchanged: str) -> None:
    assert cleaner.reduce_repeated_symbols(unchanged) == unchanged


def test_symbol_limit_comes_from_settings() -> None:
    cleaner = ArabicTextCleaner(_settings(max_symbol_repeats=2))
    assert cleaner.reduce_repeated_symbols("!!!!!") == "!!"


# ---------- Rule 7: whitespace ----------


@pytest.mark.parametrize(
    ("before", "after"),
    [("كلمة   كلمة", "كلمة كلمة"), ("  بداية", "بداية"), ("نهاية  ", "نهاية"), ("سطر\nسطر\tتاب", "سطر سطر تاب")],
)
def test_whitespace_is_collapsed_and_trimmed(cleaner: ArabicTextCleaner, before: str, after: str) -> None:
    assert cleaner.normalize_whitespace(before) == after


def test_only_spaces_becomes_empty(cleaner: ArabicTextCleaner) -> None:
    assert cleaner.normalize_whitespace("   \n\t ") == ""


# ---------- clean(): all rules together ----------


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("حسابشخصي جـــميل جداااا 😂😂😂", "جميل جداا 😂"),
        ("رابطويب", ""),
        (f"ب{KASRA}س{SUKUN}م{KASRA} الل{SHADDA}{FATHA}ه{KASRA}", f"بسم الل{SHADDA}{FATHA}ه{KASRA}"),
        ("أحمد قال إنه آسف!!!", "احمد قال انه اسف!"),
        ("! حسابشخصي !", "!"),
        (f"ه{FATHA}ه{FATHA}ه{FATHA}ه{FATHA}", "هه"),
        ("مبروك 2020 🎉 🎉", "مبروك 2020 🎉"),
    ],
)
def test_clean_applies_all_rules_in_order(cleaner: ArabicTextCleaner, before: str, after: str) -> None:
    assert cleaner.clean(before) == after


@pytest.mark.parametrize(
    "text",
    [
        "حسابشخصي جـــميل جداااا 😂😂😂",
        "!!! ؟؟؟ ،،",
        "أحمد إن آخر ٱلكتاب",
        f"و{FATHA}الل{SHADDA}{FATHA}ه{KASRA} ج{FATHA}م{KASRA}يل",
        "  x\n\ty  ",
        "sooo 😂 😂 good",
    ],
)
def test_cleaning_twice_gives_the_same_result_as_once(cleaner: ArabicTextCleaner, text: str) -> None:
    once = cleaner.clean(text)
    assert cleaner.clean(once) == once
