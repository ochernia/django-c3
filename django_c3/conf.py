from django.conf import settings


C3_LANGUAGES = getattr(
    settings,
    'DJANGO_C3_LANGUAGES',
    settings.LANGUAGES,
)


C3_PRIMARY_LANGUAGE = getattr(
    settings,
    'DJANGO_C3_PRIMARY_LANGUAGE',
    C3_LANGUAGES[0][0],
)
