from django import forms


class MultilingualModelForm(forms.ModelForm):
    language_code = None

    def __init__(self, data=None, files=None, instance=None, **kwargs):
        # We force the language to the primary, temporarily disabling the
        # routing based on current active language.
        # This allows all field values to be extracted from the model in super's init()
        # as it populates self.initial)

        if instance:
            instance._force_language = self.language_code

        super(MultilingualModelForm, self).__init__(
            data=data, files=files, instance=instance, **kwargs
        )

    def save(self, *args, **kwargs):
        self.instance._force_language = self.language_code
        return super(MultilingualModelForm, self).save(*args, **kwargs)
