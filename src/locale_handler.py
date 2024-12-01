import gettext

SUPPORTED_LANGUAGES = {"en", "pl"}

LANGUAGES = {
    "en": gettext.translation("messages", localedir="src/locales", languages=["en"], fallback=True),
    "pl": gettext.translation("messages", localedir="src/locales", languages=["pl"], fallback=True),
}


def _(text: str, language: str = "en") -> str:
    if language not in SUPPORTED_LANGUAGES:
        language = "en"
    return LANGUAGES[language].gettext(text)
