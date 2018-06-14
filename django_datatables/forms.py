from django.forms.models import ModelForm
from django_datatables.models import DatatableState

from django.forms.widgets import SelectMultiple
from itertools import chain
from django.forms.widgets import CheckboxInput
from django.utils.encoding import force_unicode
from django.utils.html import escape
from django.utils.safestring import mark_safe
from datetime import datetime
from django_datatables.writers.html import HtmlWriter
from django_datatables.helper import id_for_report, report_class_for_report
try:
    from django.forms.utils import flatatt
except ImportError: # Django < 1.9 compatibility
    from django.forms.util import flatatt

class DatatableStateSetForm(ModelForm):
    
    class Meta:
        model = DatatableState
        exclude = ('user',)
        
    def __init__(self, request, *args, **kwargs):
        super(ModelForm, self).__init__(*args, **kwargs)
        self.request = request

    def save(self, commit=True):
        try:
            # Attempt to update an existing state or simply refresh its 'updated' field.
            cleaned_data = self.cleaned_data
            self.instance = DatatableState.objects.get(uri=cleaned_data['uri'],
                                                       user=self.request.user)
            update_fields = ['updated']
            if self.instance.json != cleaned_data['json']:
                self.instance.json = cleaned_data['json']
                update_fields.append('json')
            self.instance.save(update_fields=update_fields)
        except DatatableState.DoesNotExist:
            # No existing state exists, create it
            self.instance = super(DatatableStateSetForm, self).save(commit=False)
            self.instance.user = self.request.user
            self.instance.save()
            
        return self.instance

class InlineDatatablesWidget(SelectMultiple):
    """
    A widget to render a Datatable as a field.
    
    Note that the datatable rendered as HTML and it contains the field definition,
    thus the name of the form_field_name supplied to the field definition must 
    match that of the form's field name.
    
    Inspired by http://skyl.org/log/post/skyl/2011/01/wherein-the-inner-workings-of-the-deathstarwidget-are-revealed/
    
    Example:
    <code>
        from django import forms
        import django_datatables 
        
        class MyDatable(django_datatables.Report):
            pk = datatables.CheckboxField(form_field_name='my_field_name', check_all=True)
            ...
            ...
            
        class MyForm(forms.Form):
            def __init__(self, request, *args, **kwargs):
                self.fields['my_field_name'] = forms.ModelMultipleChoiceField(queryset=MyModel.objects.all(),
                                                                              widget=InlineDatatablesWidget(MyDatable(request=request)))
    </code>
    """

    def __init__(self, datatable, *args, **kwargs):
        super(InlineDatatablesWidget, self).__init__(*args, **kwargs)
        self.datatable = datatable

    def render(self, name, value, attrs=None, choices=()):
        # Cast as a string - it's a little convoluted working out what type of data should be in the column...
        str_value = [] if value is None else [str(v) for v in value]

        final_attrs = self.build_attrs(attrs, **{'class': 'display datatable table table-striped table-bordered inline-datatables-widget',
                                                 'id': id_for_report(self.datatable)})
        writer = HtmlWriter(self.datatable)
        output = []
        if hasattr(self.choices, 'queryset'):
            queryset = self.choices.queryset
        else:
            queryset = self.choices
        
        output.append(u'''<table data-report="%s" 
                                 data-datatables-no-paging="1"
                                 data-datatables-no-buttons="1"
                                 data-datatables-no-search="1"
                                 data-default-sorting="%s" %s>
        <thead>
            <tr class="headers">
                %s
            </tr>''' % (
            report_class_for_report(self.datatable),
            escape(writer.default_sorting()),
            flatatt(final_attrs),
            writer.thead(),
        ))
        #if writer.has_filters:
        #    output.append(u'<tr class="filters">%s</tr>' % writer.filters())
        
        output.append(u'</thead>')
        output.append(u'<tbody>')
        output.append(writer.as_table(queryset, render_kwargs={'form_field_value': str_value}))
        output.append(u'</tbody>')
        
        if writer.has_aggregates():
            output.append(u'<tfoot><tr class="aggregates">%s</tr></tfoot>' % writer.aggregates())
        output.append(u'</table>')

        return mark_safe(u'\n'.join(output))
