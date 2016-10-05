from django.conf import settings
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


def get_language_from_request(request):
    language_code = request.GET.get('language', None)

    # validate language
    for language in settings.LANGUAGES:
        if language[0] == language_code:
            break
    else:
        language_code = None

    if not language_code:
        language_code = translation.get_language_from_request(request, check_path=True)
    return language_code
