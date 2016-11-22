# -*- coding: utf-8 -*-
from collections import namedtuple

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import Http404, QueryDict
from django.shortcuts import redirect, render_to_response
from django.template import RequestContext
from django.utils.encoding import force_unicode
from django.utils.translation import get_language_info, ugettext

from .conf import C3_LANGUAGES
from .forms import MultilingualModelForm
from .utils import get_language_from_request


LanguageTab = namedtuple(
    'LanguageTab',
    field_names=['name', 'language', 'status', 'url', 'deactivate_url']
)


def get_language_name(language_code):
    return get_language_info(language_code)['name']


class MultilingualAdmin(admin.ModelAdmin):
    query_language_key = 'language'

    form = MultilingualModelForm
    change_form_template = 'admin/django_c3/change_form.html'
    deactivate_confirmation_template = 'admin/django_c3/deactivate_confirmation.html'

    def get_form(self, request, obj=None, **kwargs):
        FormClass = super(MultilingualAdmin, self).get_form(request, obj=obj, **kwargs)
        FormClass.language_code = get_language_from_request(request)
        return FormClass

    def get_urls(self):
        from django.conf.urls import url

        def pattern(regex, fn, name):
            args = [regex, self.admin_site.admin_view(fn)]
            return url(*args, name=self.get_admin_url(name))

        url_patterns = [
            pattern(
                r'^(.+)/deactivate-translation/(.+)/$',
                self.deactivate_translation_view,
                'deactivate_translation'
            ),
        ]

        return url_patterns + super(MultilingualAdmin, self).get_urls()

    def get_admin_url(self, name):
        model_name = self.model._meta.model_name
        url_name = "%s_%s_%s" % (self.model._meta.app_label, model_name, name)
        return url_name

    def get_bound_languages(self, obj):
        return obj.get_bound_languages()

    def get_configured_languages(self):
        return [language[0] for language in C3_LANGUAGES]

    def get_language_tabs(self, request, obj=None):
        tabs = [self.get_language_tab(request, language, obj=obj)
                for language in self.get_configured_languages()]
        return tabs

    def get_language_tab(self, request, language, obj=None):
        current_language = get_language_from_request(request)

        if obj:
            active_languages = self.get_bound_languages(obj)
        else:
            active_languages = []

        if request.method == 'GET':
            data = request.GET.copy()
        else:
            data = QueryDict('', mutable=True)

        data['language'] = language

        if language == current_language:
            status = 'current'
        elif language in active_languages:
            status = 'active'
        else:
            status = 'inactive'

        if obj and self.has_delete_permission(request, obj) and obj.translation_exists(language):
            deactivate_url_name = 'admin:{}'.format(self.get_admin_url('deactivate_translation'))
            deactivate_url = reverse(deactivate_url_name, args=[obj.pk, language])
        else:
            deactivate_url = None

        tab = LanguageTab(
            name=get_language_name(language),
            language=language,
            status=status,
            url='%s?%s' % (request.path, data.urlencode()),
            deactivate_url=deactivate_url,
        )
        return tab

    def deactivate_translation_view(self, request, object_id, language_code):
        "The 'delete translation' admin view for this model."
        opts = self.model._meta
        app_label = opts.app_label
        verbose_name = force_unicode(opts.verbose_name)

        obj = self.get_object(request, object_id)

        if not obj:
            raise Http404

        translation = obj.get_translation(
            language_code,
            include_inactive=False
        )

        if not translation:
            raise Http404

        if not self.has_delete_permission(request, obj):
            raise PermissionDenied

        language_name = get_language_name(language_code)

        if request.method == 'POST':
            # The user has already confirmed the deletion.
            obj_name = force_unicode(obj)
            message = 'deactivated %s translation of %s' % (language_name, obj_name)

            self.log_change(
                request,
                object=obj,
                message=message,
            )
            self.deactivate_translation(request, obj, language_code)

            user_message = ugettext(
                'The %(name)s "%(obj)s" %(language)s'
                ' translation was successfully deactivated.'
            ) % {
                'name': verbose_name,
                'obj': obj_name,
                'language': language_name
            }

            self.message_user(request, user_message)

            if not self.has_change_permission(request, None):
                return redirect('admin:index')

            change_url = 'admin:{}'.format(self.get_admin_url('change'))
            return redirect(change_url, obj.pk)

        class_name = '%s Translation' % verbose_name

        context = {
            "title": ugettext("Are you sure?"),
            "object_name": class_name,
            "object": obj,
            "opts": opts,
            "app_label": app_label,
        }

        response = render_to_response(
            self.deactivate_confirmation_template,
            context,
            RequestContext(request)
        )
        return response

    def deactivate_translation(self, request, obj, language_code):
        obj.deactivate_translation(language_code)

    def response_change(self, request, obj):
        response = super(MultilingualAdmin, self).response_change(request, obj)

        if 'Location' in response:
            add_url = reverse('admin:{}'.format(self.get_admin_url('add')))
            change_url = reverse('admin:{}'.format(self.get_admin_url('change')), args=[obj.pk])

            if response['Location'] in (add_url, change_url):
                if self.query_language_key in request.GET:
                    response['Location'] = '%s?%s=%s' % (response['Location'],
                        self.query_language_key, request.GET[self.query_language_key])
        return response

    def render_change_form(self, request, context, add=False, change=False,
                           form_url='', obj=None):
        lang_code = get_language_from_request(request)
        language_name = get_language_name(lang_code)
        context['title'] = u'%s (%s)' % (context['title'], language_name)
        context['language_tabs'] = self.get_language_tabs(request, obj=obj)
        return super(MultilingualAdmin, self).render_change_form(request, context, add, change, form_url, obj)


class MultilingualStackedInline(admin.StackedInline):
    form = MultilingualModelForm

    def get_formset(self, request, obj=None, **kwargs):
        class I18nForm(self.form):
            language_code = get_language_from_request(request)

        kwargs['form'] = I18nForm
        return super(MultilingualStackedInline, self).get_formset(request, obj=obj, **kwargs)


class MultilingualTabularInline(admin.TabularInline):
    form = MultilingualModelForm

    def get_formset(self, request, obj=None, **kwargs):
        class I18nForm(self.form):
            language_code = get_language_from_request(request)

        kwargs['form'] = I18nForm
        return super(MultilingualTabularInline, self).get_formset(request, obj=obj, **kwargs)
