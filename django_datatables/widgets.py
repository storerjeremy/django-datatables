import os
from django.utils.html import format_html
from django.utils.encoding import force_text, smart_text
try:
    from django.forms.utils import flatatt
except ImportError: # Django < 1.9 compatibility
    from django.forms.util import flatatt
from django.utils import formats, six, datetime_safe
from django.utils.text import slugify
from django.forms.widgets import MediaDefiningClass, CheckboxInput
from string import Template
from decimal import Decimal
from django_toolkit.templatetags.buttons import imageonlybutton
from django.utils.safestring import mark_safe
from django.db import models
from django_toolkit.fields import ChoiceHumanReadable
from django_datatables.writers.html import HtmlWriter
from django.db.models.base import Model
from django.conf import settings
from django.template import Context, Template
from itertools import chain
from django.utils.timesince import timesince

class Widget(six.with_metaclass(MediaDefiningClass)):
    css = 'widget'
    is_localized = False
    
    def __init__(self, field, attrs=None):
        self.field = field
        if attrs is not None:
            self.attrs = attrs.copy()
        else:
            self.attrs = {}

    def render_title(self, writer, field, attrs=None):
        """
        Returns field's title rendered using Widget.
        """
        raise NotImplementedError

    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        """
        Returns this Widget rendered as HTML, as a Unicode string.
        """
        raise NotImplementedError

    def build_attrs(self, item={}, data={}, base_css='widget', extra_css=None, **kwargs):
        "Helper function for building an attribute dictionary."
        attrs = dict(self.attrs, **kwargs)
        attrs['class'] = base_css
        if 'data_tip' in attrs:
            attrs['data-tip'] = attrs['data_tip']
            del(attrs['data_tip'])
            if '{' in attrs['data-tip']:
                t = Template(attrs['data-tip'])
                c = Context({'object': item})
                attrs['data-tip'] = t.render(c)
        if data:
            for key, value in data.items():
                attrs['data-%s' % key.replace('_', '-')] = value
        if 'title_tip' in attrs:
            del(attrs['title_tip'])
        if extra_css:
            for css in extra_css:
                attrs['class'] += u' %s-%s' % (base_css, slugify(u'%s' % css))
        return attrs

    def build_title_attrs(self, base_css='widget', extra_css=None, **kwargs):
        "Helper function for building an attribute dictionary."
        attrs = dict(self.attrs, **kwargs)
        attrs['class'] = base_css
        if 'data_tip' in attrs:
            del(attrs['data_tip'])
        if 'title_tip' in attrs:
            attrs['data-tip'] = attrs['title_tip']
            del(attrs['title_tip'])
        if extra_css:
            for css in extra_css:
                attrs['class'] += u' %s-%s' % (base_css, slugify(u'%s' % css))
        return attrs

class TextWidget(Widget):
    css = 'widget-text'

    def _format_value(self, value, item):
        if self.field.choices:
            return force_text(dict(self.field.flatchoices).get(value, value), strings_only=True)
        if self.is_localized:
            return formats.localize_input(value)
        return value
    
    def render_title(self, writer, name, attrs=None):
        if self.field.title is None:
            value = u''
        else:
            value = self.field.title
        if not isinstance(writer, HtmlWriter):
            return value
        final_attrs = self.build_title_attrs(base_css=self.css, extra_css=(name.replace('_', '-'),))
        tip = ' <i class="icon-question-sign"></i>' if 'data-tip' in final_attrs else ''
        return format_html(u'<span{0} >{1}{2}</span>', flatatt(final_attrs), force_text(value), mark_safe(tip))
        
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if value is None:
            value = u''
        if callable(value):
            value = value()
        if not isinstance(writer, HtmlWriter):
            return value
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        return format_html(u'<span{0} data-raw="{1}">{2}</span>', 
                           flatatt(final_attrs), 
                           force_text(value), 
                           mark_safe(force_text(self._format_value(value, item))))


class IntegerWidget(TextWidget):
    css = 'widget-integer'


class DurationWidget(TextWidget):
    css = 'widget-duration'
    
    def _format_value(self, value, item):
        return '%s' % value


class BaseSpanWidget(TextWidget):
    span_base_class = ''

    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if value is None:
            value = u''
        if callable(value):
            value = value()
        if not isinstance(writer, HtmlWriter):
            return value
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        # Now work out the label class
        extra_css = self.get_extra_css()
        if extra_css:
            if '__' in extra_css:
                extra_css = self.field.traverse_for_value(item, extra_css)
                if callable(extra_css):
                    extra_css = extra_css()
            elif hasattr(value, extra_css):
                extra_css = getattr(value, extra_css)
                if callable(extra_css):
                    extra_css = extra_css()
            elif hasattr(item, extra_css):
                extra_css = getattr(item, extra_css)
                if callable(extra_css):
                    extra_css = extra_css()
            elif hasattr(report, extra_css):
                extra_css = getattr(report, extra_css)
                if callable(extra_css):
                    extra_css = extra_css(value)
        tip = ' <i class="%s"></i>' % self.field.data_tip_icon if self.field.data_tip_icon and final_attrs.get('data-tip') else ''
        return format_html(u'<span{0} data-raw="{1}"><span class="{2} {3}">{4}</span>{5}</span>', 
                           flatatt(final_attrs), 
                           force_text(value),
                           self.span_base_class, 
                           extra_css, 
                           mark_safe(force_text(self._format_value(value, item))),
                           mark_safe(tip))

class LabelWidget(BaseSpanWidget):
    css = 'widget-label'
    span_base_class = 'label'
    
    def get_extra_css(self):
        return self.field.label_class

class BadgeWidget(BaseSpanWidget):
    css = 'widget-badge'
    span_base_class = 'badge'
    
    def get_extra_css(self):
        return self.field.badge_class

class ManyManyLabelWidget(LabelWidget):
    """
    Renders the values inside an <a> tags separated by commas.
    """
    css = 'widget-many-many-label'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, is_self=False, **kwargs):
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        
        objects = value.all()
        
        if not isinstance(writer, HtmlWriter):
            return objects
        
        html = []
        
        for obj in objects:
            label = LabelWidget.render(self, report, writer, name, obj, item, row_number, attrs, is_self=is_self, **kwargs)
            if 'get_absolute_url' in dir(obj):
                html.append(format_html(
                    u'<span{0} ><a href="{1}">{2}</a>{3}</span>', 
                    flatatt(final_attrs), 
                    obj.get_absolute_url(),
                    label,
                    mark_safe(obj.get_append_markup()) if hasattr(obj, 'get_append_markup') else ''
                ))
            else:
                html.append(format_html(
                    u'<span{0} >{1}</span>', 
                    flatatt(final_attrs), 
                    label
                ))
        
        return " ".join(html)

class UrlWidget(TextWidget):
    """
    Renders the value inside an <a> tag.
    
    @todo: Write rendering function.
    """
    css = 'widget-url'
    target = '_blank'

    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if not isinstance(writer, HtmlWriter):
            return value
        if value is not None:
            value = '<a href="%s" target="%s">%s</a>' % (value, self.target, value)
        return super(UrlWidget, self).render(report, writer, name, value, item, row_number, attrs=None, **kwargs)

class XEditableWidget(TextWidget):
    """
    A widget for use with X-Editable
    
    :see: http://vitalets.github.io/x-editable/docs.html
    """
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if not isinstance(writer, HtmlWriter):
            return value
        
        if self.field.xeditable_attributes is None:
            method = '%s_attributes' % self.field.name
        else:
            method = self.field.xeditable_attributes
        
        a_attrs = {'href': '#', 'rel': 'editable'}
        a_attrs.update(**getattr(item, method)())
        
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        return format_html(u'<span{0} data-raw="{1}">{2}</span>', 
                           flatatt(final_attrs), 
                           force_text(value), 
                           mark_safe('<a %s>%s</a>' % (flatatt(a_attrs), value)))
 
class ForeignKeyWidget(UrlWidget):
    """
    Renders the value inside an <a> tag.
    
    @todo: Write rendering function.
    """
    css = 'widget-foreign-key'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, is_self=False, **kwargs):
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        
        if is_self:
            obj = item
        else:
            obj = value
        
        if not isinstance(obj, models.Model) and obj != None:
            raise Exception("ForeignKeyWidget expects value to be an instance of Model not %s" % (obj))
        
        if not isinstance(writer, HtmlWriter):
            return value
        
        if 'get_absolute_url' in dir(obj):
            return format_html(
                u'<span{0} ><a href="{1}">{2}</a>{3}</span>', 
                flatatt(final_attrs), 
                obj.get_absolute_url(),
                value,
                mark_safe(obj.get_append_markup()) if hasattr(obj, 'get_append_markup') else ''
            )
        else:
            return format_html(
                u'<span{0} >{1}{2}</span>', 
                flatatt(final_attrs), 
                value,
                mark_safe(obj.get_append_markup()) if hasattr(obj, 'get_append_markup') else ''
            )

class ManyManyWidget(ForeignKeyWidget):
    """
    Renders the values inside an <a> tags separated by commas.
    """
    css = 'widget-many-many'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, is_self=False, **kwargs):
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        
        objects = value.all()
        
        if not isinstance(writer, HtmlWriter):
            return objects
        
        html = []
        
        for obj in objects:
            if 'get_absolute_url' in dir(obj):
                html.append(format_html(
                    u'<span{0} ><a href="{1}">{2}</a>{3}</span>', 
                    flatatt(final_attrs), 
                    obj.get_absolute_url(),
                    obj,
                    mark_safe(obj.get_append_markup()) if hasattr(obj, 'get_append_markup') else ''
                ))
            else:
                html.append(format_html(
                    u'<span{0} >{1}</span>', 
                    flatatt(final_attrs), 
                    obj
                ))
        
        return ", ".join(html)

class AnnotatedForeignKeyWidget(UrlWidget):
    """
    Renders the value inside an <a> tag.
    
    @todo: Write rendering function.
    """
    css = 'widget-annotated-foreign-key'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, is_self=False, **kwargs):
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        
        obj = self.field.model.objects.get(pk=item[self.field.name])
        
        if not isinstance(writer, HtmlWriter):
            return obj
        
        if 'get_absolute_url' in dir(obj):
            return format_html(
                u'<span{0} ><a href="{1}">{2}</a></span>', 
                flatatt(final_attrs), 
                obj.get_absolute_url(),
                obj
            )
        else:
            return format_html(
                u'<span{0} >{1}</span>', 
                flatatt(final_attrs), 
                obj
            )


class FileWidget(UrlWidget):
    css = 'widget-file'

    def _format_value(self, value, item):
        return os.path.basename(value.name)
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if value is None:
            value = u''
        if not isinstance(writer, HtmlWriter):
            return value
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        if self.field.url and hasattr(item, self.field.url):
            url = getattr(item, self.field.url)()
        else:
            url = value.url
        return format_html(
            u'<span{0} ><a href="{1}"{2}>{3}</a></span>', 
            flatatt(final_attrs), 
            url,
            flatatt(self.field.a_attrs),
            self._format_value(value, item)
        )


class SelfWidget(ForeignKeyWidget):
    css = 'widget-self'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if self.field.force_string:
            value = str(item)
        return super(SelfWidget, self).render(report, writer, name, value, item, row_number, attrs=None, is_self=True)

class CommaSeparatedWidget(TextWidget):
    css = 'widget-comma-separated'

    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        items = []

        if callable(value):
            value = value()
        
        for i in value:
            items.append(self.render_item(i, final_attrs, writer, name, value, item, row_number, attrs))
        return ", ".join(items)

class CommaSeparatedUrlWidget(CommaSeparatedWidget):
    css = 'widget-comma-separated-url'

    def render_item(self, i, final_attrs, writer, name, value, item, row_number, attrs=None):
        if not isinstance(writer, HtmlWriter):
            return "%s" % i
        else:
            return format_html(
                u'<span{0} ><a href="{1}">{1}</a></span>', 
                flatatt(final_attrs), 
                i
            )
            
class CommaSeparatedEmailWidget(CommaSeparatedWidget):
    css = 'widget-comma-separated-email'

    def render_item(self, i, final_attrs, writer, name, value, item, row_number, attrs=None):
        if not isinstance(writer, HtmlWriter):
            return "%s" % i
        else:
            return format_html(
                u'<span{0} ><a href="mailto:{1}">{1}</a></span>', 
                flatatt(final_attrs), 
                i
            )

class CommaSeparatedForeignKeyWidget(CommaSeparatedUrlWidget):
    css = 'widget-comma-separated-foreign-key'
    
    def render_item(self, i, final_attrs, writer, name, value, item, row_number, attrs=None):
        if not isinstance(i, models.Model) and i != None:
            raise Exception("CommaSeparatedForeignKeyWidget expects value to be an instance of Model not %s" % (item))
        
        if not isinstance(writer, HtmlWriter):
            return "%s" % i
        else:
            if 'get_absolute_url' in dir(i):
                return format_html(
                    u'<span{0} ><a href="{1}">{2}</a></span>', 
                    flatatt(final_attrs), 
                    i.get_absolute_url(),
                    i
                )
            else:
                return format_html(
                    u'<span{0} >{1}</span>', 
                    flatatt(final_attrs), 
                    i
                )

class DecimalWidget(TextWidget):
    css = 'widget-decimal'
    
    def _format_value(self, value, item):
        if self.field.only_necessary_places:
            if value is not None and value != '':
                return "%s" % round(value, self.field.decimal_places) if value % 1 else int(value)
        else:
            return "%s" % Decimal(value).quantize(Decimal('.%s' % '0'.zfill(self.field.decimal_places)))  

class PercentWidget(DecimalWidget):
    css = 'widget-percent'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if callable(value):
            value = value()
        if value is None:
            percent = Decimal('0')
            value = (Decimal('0'), Decimal('0'))
        else:
            if value[1] == 0:
                percent = Decimal('0')
            else:
                percent = (Decimal(value[0]) / Decimal(value[1])) * 100
        quantize = Decimal('.' + '0'.zfill(self.field.decimal_places))
        if not isinstance(writer, HtmlWriter):
            return ('%s%% (%s/%s)') % (
                self._format_value(percent, item), 
                self._format_value(value[0], item), 
                self._format_value(value[1], item)
            )
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        return format_html(
            u'<span{0} ><span class="{1}-percent">{2}%</span> <span class="{3}-values">({4}<span class="{3}-separator">/</span>{5})</span></span>', 
            flatatt(final_attrs), 
            self.css, 
            self._format_value(percent, item), 
            self.css, 
            self._format_value(value[0], item), 
            self._format_value(value[1], item)
        )

class PercentChangeWidget(DecimalWidget):
    css = 'widget-percent-change'
    separator = '<i class="icon-long-arrow-right"></i>'
    
    def _format_value(self, value, item):
        if value is None:
            return 'N/A'
        else:
            return super(PercentChangeWidget, self)._format_value(value, item)
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        
        if callable(value):
            value = value()
            
        if value[0] is None or value[1] is None:
            percent = None
        else:
            if value[1] == 0 or value[0] == 0:
                percent = None
            else:
                percent = ((Decimal(value[1]) - Decimal(value[0])) / Decimal(value[0])) * 100
        
        if not isinstance(writer, HtmlWriter):
            if percent is None and value[0] is None and value[1] is None:
                return 'N/A'
            return ('%s%% (%s->%s)') % (
                self._format_value(percent, item), 
                self._format_value(value[0], item), 
                self._format_value(value[1], item)
            )
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        
        if percent is None and value[0] is None and value[1] is None:
            return format_html(u'<span{0} >N/A</span>', flatatt(final_attrs),)
        else:
            return format_html(
                u'<span{0} >'
                    '<span class="{1}-percent">{2}%</span> '
                    '<span class="{3}-values">'
                        '('
                            '<span class="{3}-old" data-tip="Existing value">{4}</span>'
                            '<span class="{3}-separator">{6}</span>'
                            '<span class="{3}-new" data-tip="Current value">{5}</span>'
                        ')'
                    '</span>'
                '</span>', 
                flatatt(final_attrs), 
                self.css, 
                self._format_value(percent, item), 
                self.css,  
                self._format_value(value[0], item), 
                self._format_value(value[1], item),
                mark_safe(self.separator)
            )

class CountWidget(DecimalWidget):
    css = 'widget-count'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if value is None:
            count = 0
        elif hasattr(value, 'count') and callable(value.count):
            count = value.count()
        else:
            count = len(value)
        if not isinstance(writer, HtmlWriter):
            return count
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        return format_html(
            u'<span{0} >{1}</span>', 
            flatatt(final_attrs), 
            count
        )

class DateWidget(TextWidget):
    css = 'widget-date'

    def __init__(self, field, attrs=None, format=None, format_type='DATE_FORMAT'):
        super(DateWidget, self).__init__(field, attrs)
        if format:
            self.format = format
            self.manual_format = True
        else:
            self.format = formats.get_format(format_type)
            self.manual_format = False

#     def _format_value(self, value, item):
#         if self.is_localized and not self.manual_format:
#             return formats.localize_input(value)
#         elif hasattr(value, 'strftime'):
#             value = datetime_safe.new_date(value)
#             return value.strftime(self.format)
#         return value
    
    def _format_value(self, value, item):
        if self.is_localized and not self.manual_format:
            return self.timesince(formats.localize_input(value), item)
        return self.timesince(value, item)

    def timesince(self, value, item):
        from django_datatables.fields import F
        if self.field.timesince and value:
            try:
                now = None
                if isinstance(self.field.timesince, F):
                    now = self.field.traverse_for_value(item, self.field.timesince.name)
                return timesince(value, now=now, reversed=self.field.timesince_reverse)
            except AttributeError: pass # perhaps its not a date/datetime...
        elif hasattr(value, 'strftime') and self.manual_format:
            value = self.datetime_safe_callback(value)
            return value.strftime(self.format)
        elif value:
            value = self.field.to_python(value)
        return formats.localize(value)

    @property
    def datetime_safe_callback(self):
        return datetime_safe.new_date
    
class DateTimeWidget(DateWidget):
    css = 'widget-datetime'
    
    def __init__(self, *args, **kwargs):
        kwargs.update(format_type='DATETIME_FORMAT')
        super(DateTimeWidget, self).__init__(*args, **kwargs)
    
    @property
    def datetime_safe_callback(self):
        return datetime_safe.new_datetime
    
class ActionWidgetItem():
    pass

class ActionWidgetImageButton(ActionWidgetItem):
    
    def __init__(self, icon, title, viewname=None, **kwargs):
        self.icon = icon
        self.title = title
        self.viewname = viewname
        self.kwargs = kwargs
    
    def render(self):
        return imageonlybutton(self.icon, self.title, self.viewname, **self.kwargs)

class ActionsWidget(UrlWidget):
    css = 'widget-actions'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        """
        Render a list of ActionWidgetItem's
        """
        if not isinstance(writer, HtmlWriter):
            # This type of widget only supports html
            return None
        content = ''
        if value:
            items = value(request=report.request)
            if isinstance(items, dict):
                items = items.values()
            for item in items:
                content += item.render()
            final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
            return format_html(
                u'<span{0}>{1}</span>', 
                flatatt(final_attrs), 
                mark_safe(content)
            )

class FormWidget(TextWidget):
    
    def get_form_element_attributes(self, item, form_prefix, form_field_name, row_number, value=None, **kwargs):
        """
        Get form element attributes.
        """
        kwargs['item'] = item
        kwargs['id'] = 'id_%s-%s-%s' % (form_prefix, row_number, form_field_name)
        kwargs['name'] = '%s-%s-%s' % (form_prefix, row_number, form_field_name)
        kwargs['base_css'] = self.css
        kwargs['extra_css'] = (form_field_name.replace('_', '-'),)

        kwargs['data'] = {
            'id-reference': 'id_%s-%s-id' % (form_prefix, row_number), 
            'formset-field-row': '%s' % row_number, 
            'formset-field-name': '%s' % form_field_name
        }
        if value != None:
            kwargs['value'] = force_text(self._format_value(value, item))
            kwargs['data']['raw'] = kwargs['value']

        return self.build_attrs(**kwargs)

class TextInputWidget(FormWidget):
    css = 'widget-textinput'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        """
        Render a select form field
        """
        if not isinstance(writer, HtmlWriter):
            return value
        if value is None:
            value = ''
        final_attrs = self.get_form_element_attributes(item, report._meta.form_prefix, self.field.form_field_name, row_number, value)
        final_attrs['type'] = 'text'
        output = format_html('<input{0}>', flatatt(final_attrs))
        return mark_safe(output)

class FormsetWidget(FormWidget):
    css = 'widget-formset'

    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        """
        Render hidden fields for a formset.
        """
        if not isinstance(writer, HtmlWriter):
            # This type of widget only supports html
            return None
        
        id_attrs = self.get_form_element_attributes(item, report._meta.form_prefix, 'id', row_number, item.pk, type='hidden')
        output = format_html('<input{0}>', flatatt(id_attrs))
        if self.field.delete:
            delete_attrs = self.get_form_element_attributes(item, report._meta.form_prefix, 'DELETE', row_number, type='hidden')
            output += format_html('<input{0}>', flatatt(delete_attrs))
        return mark_safe(output)

class SelectWidget(FormWidget):
    css = 'widget-select'
    allow_multiple_selected = False
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        """
        Render a select form field
        """
        if not isinstance(writer, HtmlWriter):
            return value
        content = ''
        if value is None: value = ''
        final_attrs = self.get_form_element_attributes(item, report._meta.form_prefix, self.field.form_field_name, row_number, value)
        output = [format_html('<select{0}>', flatatt(final_attrs))]
        choices = getattr(item, 'get_%s_choices' % name)() if getattr(item, 'get_%s_choices' % name, False) else self.field.choices
        options = self.render_options(choices, [value])
        if options:
            output.append(options)
        output.append('</select>')
        return mark_safe('\n'.join(output))

    def render_option(self, selected_choices, option_value, option_label):
        option_value = force_text(option_value)
        if option_value in selected_choices:
            selected_html = mark_safe(' selected="selected"')
            if not self.allow_multiple_selected:
                # Only allow for a single selection.
                selected_choices.remove(option_value)
        else:
            selected_html = ''
        return format_html('<option value="{0}"{1}>{2}</option>',
                           option_value,
                           selected_html,
                           force_text(option_label))

    def render_options(self, choices, selected_choices):
        # Normalize to strings.
        selected_choices = set(force_text(v) for v in selected_choices)
        output = []
        if choices:
            for option_value, option_label in choices:
                if isinstance(option_label, (list, tuple)):
                    output.append(format_html('<optgroup label="{0}">', force_text(option_value)))
                    for option in option_label:
                        output.append(self.render_option(selected_choices, *option))
                    output.append('</optgroup>')
                else:
                    output.append(self.render_option(selected_choices, option_value, option_label))
        return '\n'.join(output)

class ModelSelectWidget(SelectWidget):
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        """
        Render a select form field
        """
        if value and isinstance(value, Model):
            value = value.pk
        return super(ModelSelectWidget, self).render(report, writer, name, value, item, row_number)

class CheckboxWidget(FormWidget):
    css = 'widget-checkbox'

    def render_title(self, writer, name, attrs=None):
        if self.field.check_all and isinstance(writer, HtmlWriter):
            final_attrs = self.build_title_attrs(base_css=self.css, extra_css=(name.replace('_', '-'),))
            tip = ' <i class="icon-question-sign"></i>' if 'data-tip' in final_attrs else ''
            cb = CheckboxInput({'class': 'datatables-checkall', 'data-checkall': self.field.form_field_name})
            title = cb.render('_%s_check_all' % self.field.form_field_name, False)
            return format_html(u'<span{0} >{1}{2}</span>', flatatt(final_attrs), title, mark_safe(tip))
        else:
            return super(CheckboxWidget, self).render_title(writer, name, attrs)
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        """
        Render a select form field
        """
        if not isinstance(writer, HtmlWriter):
            return value
        if value is None:
            value = ''
        final_attrs = self.get_form_element_attributes(item, report._meta.form_prefix, self.field.form_field_name, row_number, value)
        cb = CheckboxInput(final_attrs) #, check_test=lambda value: value in str_values)
        try:
            checked = str(value) in kwargs['form_field_value']
        except KeyError:
            checked = False
        return cb.render(self.field.form_field_name, checked)

class DateInputWidget(DateWidget, FormWidget):
    css = 'widget-date-input'
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        """
        Render a select form field
        """
        if not isinstance(writer, HtmlWriter):
            return value
        if value is None:
            value = ''
        final_attrs = self.get_form_element_attributes(item, report._meta.form_prefix, self.field.form_field_name, row_number, value)
        final_attrs['type'] = 'text'
        output = format_html('<input{0}>', flatatt(final_attrs))
        return mark_safe(output)


class DynamicFieldWidget(TextWidget):
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if value is None:
            value = u''
        if hasattr(report, 'get_%s' % name):
            value = getattr(report, 'get_%s' % name)(item)
        elif callable(value):
            value = value(item)
        if not isinstance(writer, HtmlWriter):
            return value
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        return format_html(u'<span{0} data-raw="{1}">{2}</span>', 
                           flatatt(final_attrs), 
                           force_text(value), 
                           mark_safe(force_text(self._format_value(value, item))))


class PhoneNumberWidget(TextWidget):
    """
    A widget that can be used with django-phonenumbers
    
    :see: https://github.com/stefanfoulis/django-phonenumber-field
    """
    css = 'widget-phone-number'
    
    def _format_value(self, value, item):
        if self.field.as_format is None:
            return value
        else:
            if len(value) > 0:
                return getattr(value, self.field.as_format)
    
    def render(self, report, writer, name, value, item, row_number, attrs=None, **kwargs):
        if value is None:
            return super(PhoneNumberWidget, self).render(report, writer, name, value, item, row_number, attrs, **kwargs)
        if callable(value):
            value = value()
        if not isinstance(writer, HtmlWriter):
            return self._format_value(value, item)
        final_attrs = self.build_attrs(item=item, base_css=self.css, extra_css=(name.replace('_', '-'),))
        if value is None:
            return format_html(u'<span{0} data-raw="{1}">{2}</span>',
                               flatatt(final_attrs),
                               force_text(value),
                               mark_safe(force_text(self._format_value(value, item)))
                               )
        else:
            return format_html(u'<span{0} data-raw="{1}"><a href="tel:{2}">{3}</a></span>',
                               flatatt(final_attrs),
                               force_text(value),
                               value,
                               mark_safe(force_text(self._format_value(value, item)))
                               )
