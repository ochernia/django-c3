from django.utils import translation


def get_i18n_field_name(field_name, language):
    lang_code = get_normalized_language(language)
    return '%s_%s' % (field_name, lang_code)


def get_normalized_language(language_code):
    """
    Returns the actual language extracted from the given language code
    (ie. locale stripped off). For example, 'en-us' becomes 'en'.
    """
    return language_code.split('-')[0]


def get_current_language():
    """
    Wrapper around `translation.get_language` that returns the normalized
    language code.
    """
    return get_normalized_language(translation.get_language())
