"""Arabic text cleaning rules for QADI tweets.

Each rule is one small public method that takes a string and returns a
string, so every rule can be read, tested and reasoned about on its own.
``clean`` runs all seven rules in the agreed order.
"""

from __future__ import annotations

import re

from arabic_dialect_identification_v2.data.config import CleaningSettings


class ArabicTextCleaner:
    """Apply the agreed text-cleaning rules to a single tweet.

    The cleaner works on one string at a time and never sees a whole table,
    so it knows nothing about files, columns or rows.

    Rules, in the order ``clean`` applies them:
        1. remove_placeholders        حسابشخصي / حسابشخصى / رابطويب → space
        2. remove_tatweel             جـــميل → جميل
        3. remove_diacritics          مَجِيد → مجيد (words containing لله are kept)
        4. normalize_alef             أ إ آ ٱ → ا
        5. reduce_repeated_letters    هههههه → هه, sooo → soo
        6. reduce_repeated_symbols    !!! → !, 😂 😂 😂 → 😂 (digits untouched)
        7. normalize_whitespace       extra spaces removed, ends trimmed

    Example:
        cleaner = ArabicTextCleaner(config.cleaning)
        cleaner.clean("حسابشخصي جـــميل جداااا 😂😂😂")   # → "جميل جداا 😂"
    """

    TATWEEL: str = "\N{ARABIC TATWEEL}"  # ـ

    # Diacritics (tashkeel): every mark from fathatan to sukun
    # (ً ٌ ٍ َ ُ ِ ّ ْ), plus the superscript ("dagger") alef ٰ as in هٰذا.
    # Hamza letters (أ إ ؤ ئ) are letters, not diacritics, so they are not included.
    DIACRITICS_PATTERN: re.Pattern[str] = re.compile(
        "[\N{ARABIC FATHATAN}-\N{ARABIC SUKUN}\N{ARABIC LETTER SUPERSCRIPT ALEF}]"
    )

    # Alef forms that are unified to a plain alef ا (rule 4).
    ALEF_VARIANTS: str = (
        "\N{ARABIC LETTER ALEF WITH HAMZA ABOVE}"  # أ
        "\N{ARABIC LETTER ALEF WITH HAMZA BELOW}"  # إ
        "\N{ARABIC LETTER ALEF WITH MADDA ABOVE}"  # آ
        "\N{ARABIC LETTER ALEF WASLA}"  # ٱ
    )
    PLAIN_ALEF: str = "\N{ARABIC LETTER ALEF}"  # ا

    # A "word" is any run of characters without whitespace.
    WORD_PATTERN: re.Pattern[str] = re.compile(r"\S+")

    # A letter is a word character that is not a digit or underscore.
    # This covers Arabic and Latin letters alike.
    LETTER: str = r"[^\W\d_]"

    # A symbol is anything that is not a letter, digit, space or diacritic:
    # punctuation (! ؟ ، .), emoji and the underscore. An emoji may carry a
    # trailing variation selector or skin-tone modifier, which is kept with it.
    SYMBOL: str = (
        "(?:[^\\w\\s\N{ARABIC FATHATAN}-\N{ARABIC SUKUN}\N{ARABIC LETTER SUPERSCRIPT ALEF}]|_)"
        "[\N{VARIATION SELECTOR-16}\N{EMOJI MODIFIER FITZPATRICK TYPE-1-2}-\N{EMOJI MODIFIER FITZPATRICK TYPE-6}]*"
    )

    def __init__(self, cleaning: CleaningSettings) -> None:
        """Create a cleaner using the validated cleaning settings.

        All search patterns that depend on the settings are built once here,
        not once per tweet, because the cleaner is called hundreds of
        thousands of times.

        Args:
            cleaning: Rule values (placeholders, repeat limits, protected fragment).
        """
        self._cleaning = cleaning
        self._placeholder_pattern = self._build_placeholder_pattern(cleaning.placeholders)
        self._protected_fragment = self._strip_diacritics(cleaning.protected_word_fragment)
        self._alef_table = str.maketrans({variant: self.PLAIN_ALEF for variant in self.ALEF_VARIANTS})
        self._repeated_letter_pattern = re.compile(f"({self.LETTER})\\1{{{cleaning.max_letter_repeats},}}")
        self._repeated_symbol_pattern = re.compile(f"({self.SYMBOL})(?:\\s*\\1){{{cleaning.max_symbol_repeats},}}")

    def clean(self, text: str) -> str:
        """Apply all seven rules in the agreed order and return the cleaned tweet.

        The order matters: diacritics and tatweel are removed before
        repeats are counted, and whitespace is tidied last because the
        earlier rules can leave gaps behind.

        Args:
            text: One tweet.

        Returns:
            The fully cleaned tweet (may be empty if nothing meaningful is left).

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_string(text)
        text = self.remove_placeholders(text)
        text = self.remove_tatweel(text)
        text = self.remove_diacritics(text)
        text = self.normalize_alef(text)
        text = self.reduce_repeated_letters(text)
        text = self.reduce_repeated_symbols(text)
        return self.normalize_whitespace(text)

    def remove_placeholders(self, text: str) -> str:
        """Rule 1: replace every placeholder token with a space.

        A space is used instead of nothing so that a placeholder stuck to
        another word never glues two words together. Extra spaces are
        removed later by the whitespace rule.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_string(text)
        if self._placeholder_pattern is None:
            return text
        return self._placeholder_pattern.sub(" ", text)

    def remove_tatweel(self, text: str) -> str:
        """Rule 2: delete every tatweel (kashida) character ``ـ``.

        Tatweel only stretches a word visually, so it is removed with
        nothing in its place: ``جـــميل`` becomes ``جميل``.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_string(text)
        return text.replace(self.TATWEEL, "")

    def remove_diacritics(self, text: str) -> str:
        """Rule 3: remove diacritics from every word except protected words.

        Each word is checked on its own. A word is protected when, after
        ignoring its diacritics, it contains the protected fragment
        (``لله`` by default, which covers الله, والله, بالله, لله, اللهم).
        Protected words are kept exactly as written; all other words lose
        their diacritics. Spacing between words is left unchanged.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_string(text)
        return self.WORD_PATTERN.sub(self._clean_word_diacritics, text)

    def normalize_alef(self, text: str) -> str:
        """Rule 4: turn أ إ آ ٱ into a plain alef ا.

        Only these four alef forms change. ى ي ة ه and the hamza letters
        ؤ ئ are left exactly as they are.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_string(text)
        return text.translate(self._alef_table)

    def reduce_repeated_letters(self, text: str) -> str:
        """Rule 5: shorten any letter repeated too many times in a row.

        Applies to Arabic and Latin letters. With the default limit of 2,
        ``هههههه`` becomes ``هه`` and ``sooo`` becomes ``soo``. Digits are
        never shortened.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_string(text)
        limit = self._cleaning.max_letter_repeats
        return self._repeated_letter_pattern.sub(lambda match: match.group(1) * limit, text)

    def reduce_repeated_symbols(self, text: str) -> str:
        """Rule 6: shorten repeated punctuation and emoji.

        A symbol repeated more than the limit is shortened, even when the
        copies are separated by spaces: with the default limit of 1,
        ``!!!`` and ``😂 😂 😂`` both become a single symbol. Letters and
        digits are never affected (``2020`` stays ``2020``).

        Known limitation: emoji built from several joined parts (for
        example family or flag emoji) may not be shortened.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_string(text)
        limit = self._cleaning.max_symbol_repeats
        return self._repeated_symbol_pattern.sub(lambda match: match.group(1) * limit, text)

    def normalize_whitespace(self, text: str) -> str:
        """Rule 7: replace any run of spaces, tabs or new lines with one space, and trim the ends.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        self._require_string(text)
        return " ".join(text.split())

    def _clean_word_diacritics(self, word_match: re.Match[str]) -> str:
        """Return one word without diacritics, or unchanged if it is protected."""
        word = word_match.group()
        bare_word = self._strip_diacritics(word)
        if self._protected_fragment in bare_word:
            return word
        return bare_word

    @classmethod
    def _strip_diacritics(cls, text: str) -> str:
        """Remove every diacritic from ``text``, with no exceptions."""
        return cls.DIACRITICS_PATTERN.sub("", text)

    @staticmethod
    def _build_placeholder_pattern(placeholders: tuple[str, ...]) -> re.Pattern[str] | None:
        """Build one search pattern that matches any placeholder.

        Longer placeholders are tried first, so a placeholder that happens
        to start with a shorter one is always removed whole.
        Returns ``None`` when there are no placeholders to remove.
        """
        if not placeholders:
            return None
        longest_first = sorted(placeholders, key=len, reverse=True)
        return re.compile("|".join(re.escape(placeholder) for placeholder in longest_first))

    @staticmethod
    def _require_string(text: object) -> None:
        """Stop with a clear message if a rule receives something other than text."""
        if not isinstance(text, str):
            raise TypeError(f"Expected text as str, got {type(text).__name__}")
