from importlib import import_module

from bundesrag.locales import AVAILABLE_LANGUAGES

DEFAULT_LANGUAGE = "de"

_current_language = DEFAULT_LANGUAGE
_messages_by_language: dict[str, dict[str, str]] = {}


def set_language(language: str) -> None:
    """Sets the language used by subsequent t() calls.

    Module-level rather than threaded through every function, since output
    language is a single cross-cutting CLI setting, not per-call state."""
    global _current_language
    if language not in AVAILABLE_LANGUAGES:
        raise ValueError(f"Unsupported language: {language!r}")
    _current_language = language


def t(key: str, **kwargs: object) -> str:
    messages = _messages_by_language.get(_current_language)
    if messages is None:
        messages = import_module(f"bundesrag.locales.{_current_language}").MESSAGES
        _messages_by_language[_current_language] = messages
    message = messages[key]
    return message.format(**kwargs) if kwargs else message
