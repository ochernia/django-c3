import copy

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models.base import ModelBase
from django.utils.translation import override as force_language

from .conf import C3_LANGUAGES, C3_PRIMARY_LANGUAGE
from .exceptions import MultilingualFieldError
from .managers import MultilingualManager
from .utils import get_i18n_field_name, get_normalized_language, get_current_language


class MultilingualModelBase(ModelBase):

    def __new__(cls, name, bases, attrs):
        active_field_name = cls.get_active_field_name(name, bases, attrs)
        local_trans_fields, inherited_trans_fields = cls.get_trans_fields(name, bases, attrs)

        meta = attrs.get('Meta')

        if meta:
            # Cleanup custom Meta attributes
            if hasattr(meta, 'translate'):
                delattr(meta, 'translate')

            if hasattr(meta, 'active_field_name'):
                delattr(meta, 'active_field_name')

        translatable_fields = inherited_trans_fields + local_trans_fields

        if active_field_name not in translatable_fields:
            local_trans_fields.append(active_field_name)
            translatable_fields.append(active_field_name)

        # TODO: Handle unique_together with translatable fields?

        languages = [language[0] for language in C3_LANGUAGES
                     if language[0] != C3_PRIMARY_LANGUAGE]

        # Create a field for each configured language
        # for each translatable field.
        for field_name in local_trans_fields:
            field = attrs[field_name]

            for language in languages:
                i18n_field = cls.get_i18n_field(field, field_name, language)
                attrs[i18n_field.name] = i18n_field

        new_obj = super(MultilingualModelBase, cls).__new__(cls, name, bases, attrs)
        new_obj._meta.active_field_name = active_field_name
        new_obj._meta.translatable_fields = translatable_fields

        # Add a property that masks the translatable fields
        for field_name in local_trans_fields:
            # If there is already a property with the same name, we will leave it
            # This also happens if the Class is created multiple times
            # (Django's ModelBase has the ability to detect this and "bail out" but we don't)
            if type(new_obj.__dict__.get(field_name)) == property:
                continue

            if field_name in new_obj.__dict__:
                # Field has a descriptor so keep the descriptor under the primary language field
                primary_lang_field_name = get_i18n_field_name(field_name, C3_PRIMARY_LANGUAGE)
                setattr(new_obj, primary_lang_field_name, new_obj.__dict__[field_name])

            getter = cls.generate_field_getter(field_name)
            setter = cls.generate_field_setter(field_name)
            setattr(new_obj, field_name, property(getter, setter))
        return new_obj

    @classmethod
    def get_active_field_name(cls, name, bases, attrs):
        meta = attrs.get('Meta')

        if meta and hasattr(meta, 'active_field_name'):
            return meta.active_field_name

        # Check in parent classes
        for base in bases:
            if hasattr(base, '_meta') and hasattr(base._meta, 'active_field_name'):
                return base._meta.active_field_name

    @classmethod
    def get_trans_fields(cls, name, bases, attrs):
        local_trans_fields = []
        inherited_trans_fields = []
        meta = attrs.get('Meta')

        if meta and hasattr(meta, 'translate'):
            local_trans_fields = list(meta.translate)

        # Check for translatable fields in parent classes
        for base in bases:
            if hasattr(base, '_meta') and hasattr(base._meta, 'translatable_fields'):
                inherited_trans_fields.extend(list(base._meta.translatable_fields))

        # Validate the local_trans_fields
        for field in local_trans_fields:
            if field not in attrs:
                raise MultilingualFieldError(
                   '`%s` cannot be translated because it'
                     ' is not a field on the model %s' % (field, name)
                )

        return (local_trans_fields, inherited_trans_fields)

    @classmethod
    def get_i18n_field(cls, field, field_name, language):
        """
        Returns a copy of field renamed to match the given language
        """
        lang_field = copy.copy(field)
        # The new field cannot have the same creation_counter (else the ordering will be arbitrary)
        # We increment by a decimal point because we don't want to have
        # to adjust the creation_counter of ALL other subsequent fields
        # Limitation this trick: only supports up to 10,000 languages
        lang_field.creation_counter += 0.0001
        lang_field.name = get_i18n_field_name(field_name, language)
        lang_field.editable = False
        return lang_field

    @classmethod
    def generate_field_getter(cls, field):
        # Property that masks the getter of a translatable field
        def getter(self_reference):
            return self_reference.get_i18n_field_value(field)
        return getter

    @classmethod
    def generate_field_setter(cls, field):
        # Property that masks a setter of the translatable field
        def setter(self_reference, value):
            return self_reference.set_i18n_field_value(field, value)
        return setter


class Translation(object):
    fields = None
    master = None

    def __init__(self, language):
        self.language_code = language

    def __getattr__(self, field):
        if field in self.fields:
            return self.master.get_i18n_field_value(field, language=self.language_code)
        opts = self.master._meta
        raise FieldDoesNotExist('%s has no field named %r' % (opts.object_name, field))

    def __bool__(self):
        return self.is_active()

    __nonzero__ = __bool__

    def is_active(self):
        return self.master.translation_exists(self.language_code)

    def save(self, **data):
        self.master.save_translation(self.language_code, data)


class MultilingualModel(models.Model, metaclass=MultilingualModelBase):

    translation_is_active = models.BooleanField(
        default=False,
        editable=False
    )

    objects = MultilingualManager()

    class Meta:
        abstract = True
        active_field_name = 'translation_is_active'

    def __init__(self, *args, **kwargs):
        self._force_language = None

        # Rewrite any keyword arguments for translatable fields
        language = get_current_language()

        for field in self._meta.translatable_fields:
            if field in kwargs.keys():
                attrname = get_i18n_field_name(field, language)
                if attrname != field:
                    kwargs[attrname] = kwargs[field]
                    del kwargs[field]

        # We have to force the primary language before initializing or else
        # our "proxy" property will prevent the primary language values from being returned.
        self._force_language = get_normalized_language(settings.LANGUAGES[0][0])
        super(MultilingualModel, self).__init__(*args, **kwargs)
        self._force_language = None

    def save(self, *args, **kwargs):
        language = self.get_active_language()
        self.set_i18n_field_value(self._meta.active_field_name, True, language)
        # We have to force the primary language before saving or else
        # our "proxy" property will prevent the primary language values from being returned.
        old_forced_language = self._force_language
        self._force_language = get_normalized_language(settings.LANGUAGES[0][0])
        super(MultilingualModel, self).save(*args, **kwargs)
        # Now we can switch back
        self._force_language = old_forced_language

    def translate(self, language, **kwargs):
        # Temporarily force this objects language
        old_forced_language = self._force_language
        self._force_language = language
        # Set the values
        for key, val in kwargs.iteritems():
            setattr(self, key, val)  # Set values on the object
        # Now switch back
        self._force_language = old_forced_language

    def _get_translation(self, language):
        attrs = {'fields': self._meta.translatable_fields, 'master': self}
        class_name = '%sTranslation' % self.__class__.__name__
        return type(class_name, (Translation,), attrs)(language=language)

    def get_active_language(self):
        return self._force_language or get_current_language()

    def get_bound_languages(self):
        languages = [language[0] for language in C3_LANGUAGES
                     if self.translation_exists(language[0])]
        return languages

    def get_translation(self, language, include_inactive=True):
        is_active = self.translation_exists(language)

        if not is_active and not include_inactive:
            return None
        return self._get_translation(language)

    def get_translations(self, include_inactive=False):
        translations = []

        for language in C3_LANGUAGES:
            translation = self.get_translation(
                language[0],
                include_inactive=include_inactive
            )

            if translation or include_inactive:
                translations.append(translation)
        return translations

    def get_i18n_field_value(self, field_name, language=None):
        current_language = language or self.get_active_language()
        i18n_field_name = get_i18n_field_name(field_name, current_language)
        return getattr(self, i18n_field_name)

    def set_i18n_field_value(self, field_name, value, language=None):
        current_language = language or self.get_active_language()
        i18n_field_name = get_i18n_field_name(field_name, current_language)
        setattr(self, i18n_field_name, value)

    def get_i18n_field_value_with_fallbacks(self, field, language=None):
        current_language = language or self.get_active_language()
        value = self.get_i18n_field_value(field, current_language)

        if value:
            return value

        for language in C3_LANGUAGES:
            if language[0] != current_language:
                value = self.get_i18n_field_value(field, language[0])

                if value:
                    break
        return value

    def save_translation(self, language, data):
        # Set the is active field to True
        # we do it here to prevent it from being overridden
        data[self._meta.active_field_name] = True
        self.update_translation(language, data)

    def deactivate_translation(self, language):
        data = {self._meta.active_field_name: False}
        self.update_translation(language, data)

    def translation_exists(self, language):
        return self.get_i18n_field_value(self._meta.active_field_name, language)

    def update_translation(self, language, data):
        with force_language(language):
            # write to the db.
            # we bypass save() because saving a translation
            # should be very transparent.
            # So we avoid the save() method and signals.
            (self.__class__
             ._default_manager
             .filter(pk=self.pk)
             .update(**data))

        # update the current instance
        self.translate(language, **data)
