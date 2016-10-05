# -*- coding: utf-8 -*-
import operator

from django.db.models import Q
from django.utils import translation

from .conf import C3_LANGUAGES
from .managers import rewrite_lookup_key


def get_i18n_search_query(model, query, value):
    queries = []

    for language in C3_LANGUAGES:
        code = language[0]
        with translation.override(code):
            # linguo does not follow Q objects
            # so we rewrite the lookup manually.
            i18n_query = rewrite_lookup_key(model, lookup_key=query)
            queries.append(Q(**{i18n_query: value}))

    if not queries:
        # don't fail with reduce if no languages
        return Q(**{query: value})
    return reduce(operator.or_, queries)
