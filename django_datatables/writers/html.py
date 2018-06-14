from __future__ import absolute_import

import csv, logging, json
from django_datatables.writers.base import BaseWriter
from django.utils.safestring import mark_safe
from django.utils import formats
from django.utils.text import slugify
from django.utils.encoding import force_text
try:
    from django.forms.utils import flatatt
except ImportError: # Django < 1.9 compatibility
    from django.forms.util import flatatt
from django.utils.html import format_html
from django_datatables_view.mixins import DTEncoder
from django.forms.widgets import Select
from collections import OrderedDict

class HtmlWriter(BaseWriter):
    """
    Html report writer.
    """
    def _get_filter_type_for_field(self, field):
        from django_datatables import fields
        if field.choices:
            return 'select'
        if isinstance(field, fields.CharField):
            return 'text'
        if isinstance(field, fields.IntegerField):
            return 'number'
        if isinstance(field, fields.DateTimeField) or isinstance(field, fields.DateField):
            return 'date-range'
        return 'text'
    
    def thead(self):
        from django_datatables.fields import FormsetField
        
        ths = []
        for field in self.report.fields():
            if isinstance(field, FormsetField):
                continue 
            slug = slugify(u'%s' % field.name.replace('_', '-'))
            css = [field.widget.css, '%s-%s' % (field.widget.css, slug)]
            data_filter = ''
            if field.sorting:
                css.append('sorting')
            if field.hidden:
                css.append('hide')
            if field.filter:
                css.append('filtering')
                data_filter += ' data-filter-selector="%s" data-filter-type="%s"' % (field.name, self._get_filter_type_for_field(field))
                if field.choices:
                    choices = []
                    for choice in field.choices:
                        if isinstance(choice[1], basestring):
                            choices.append({'value': choice[0], 'label': choice[1]})
                        else:
                            choices.append({'label': choice[0], 'value': [{'value': c[0], 'label': c[1]} for c in choice[1]]})
                    data_filter += " data-filter-choices='%s'" % (json.dumps(choices, cls=DTEncoder))
            ths.append('<th class="%s"%s>%s</th>' % (" ".join(css), data_filter, field.widget.render_title(self, field.name)))
        return mark_safe("\n".join(ths))

    def has_filters(self):
        return len([field for field in self.report.fields() if field.filter]) > 0
    
    def filters(self):
        from django_datatables.fields import FormsetField
        
        ths = []
        for field in self.report.fields():
            if isinstance(field, FormsetField):
                continue 
            input = ''
            css = [field.widget.css, '%s-%s' % (field.widget.css, slugify(u'%s' % field.name.replace('_', '-')))]
            if field.hidden:
                css.append('hidden')
            # This is driven by data tables now.
            #if field.filter:
            #    css.append('filter')
            #    if field.choices:
            #        choices = (('', ''), ) + field.choices
            #        input = Select(choices=choices).render(field.name, None, attrs={'class': 'chzn-select'})
            #    else:
            #        input = '<input type="text" name="%s" placeholder="Search %s..."/>' % (field.name, field.title)
            ths.append('<th class="%s">%s</th>' % (' '.join(css), input))
        return mark_safe("\n".join(ths))
    
    def has_aggregates(self):
        return len([field for field in self.report.fields() if field.aggregate]) > 0
    
    def aggregates(self):
        ths = []
        for field in self.report.fields():
            css = ['aggregate', field.widget.css, '%s-%s' % (field.widget.css, slugify(u'%s' % field.name.replace('_', '-')))]
            if field.hidden:
                css.append('hide')
            if field.aggregate:
                css.append('datatables-aggregate')
            ths.append('<th class="%s"></th>' % (' '.join(css)))
        return mark_safe("\n".join(ths))
    
    def as_json(self, items, render_kwargs={}):
        from django_datatables.fields import FormsetField
        
        jsons = []
        row_number = 0
        for item in items:
            if isinstance(item, dict):
                item['_report'] = self.report
            else:
                item._report = self.report
            json = OrderedDict()
            
            if 'get_row_id' in dir(item):
                json['DT_RowId'] = item.get_row_id()
            elif hasattr(item, 'pk'):
                json['DT_RowId'] = "row-%s" % item.pk

            if 'get_row_class' in dir(item):
                json['DT_RowClass'] = item.get_row_class()
            elif 'get_row_class' in dir(self.report):
                json['DT_RowClass'] = self.report.get_row_class(item)
            
            field_number = 0
            for field in self.report.fields():
                value = field.prepare_value(field.traverse_for_value(item))
                if field.pre_process_with:
                    for callback in field.pre_process_with:
                        try:
                            callback = getattr(self.report, callback)
                        except TypeError: pass
                        value = callback(value, item)
                rendered = field.widget.render(self.report, self, field.name, value, item, row_number, **render_kwargs)
                if field.post_process_with:
                    for callback in field.post_process_with:
                        try:
                            callback = getattr(self.report, callback)
                        except TypeError: pass
                        rendered = callback(rendered, item)
                if field_number not in json:
                    json[field_number] = ''
                if isinstance(field, FormsetField):
                    # FormsetField is a hidden field, just put it in the first field in the table.
                    json[0] += rendered
                else:
                    json[field_number] += rendered
                    field_number += 1
            jsons.append(json)
            row_number += 1
        return jsons
    
    def as_table(self, items, render_kwargs={}):
        rows = self.as_json(items, render_kwargs)
        
        output = []
        for row in rows:
            attrs = {}
            if 'DT_RowId' in row:
                attrs['id'] = row['DT_RowId']
                del row['DT_RowId']
            if 'DT_RowClass' in row:
                attrs['class'] = row['DT_RowClass']
                del row['DT_RowClass']
            tr = []
            for column in row.values():
                tr.append('<td>%s</td>' % column)

            output.append("<tr %s>%s</tr>\n" % (
                " ".join(['%s="%s"' % (key, value) for key,value in attrs.iteritems()]), 
                "\n".join(tr)
            ))
            
        return mark_safe('\n'.join(output))

    def default_sorting(self):
        """
        Return a json chunk suitable for datatables aaSorting parameter
        
        @see http://www.datatables.net/examples/basic_init/table_sorting.html
        """
        # Ensure we sort by something...
        sorting = [(0, 'asc')]

        if hasattr(self.report._meta, 'sorting'):
            sorting = [(self.report.field_index(sort.replace('-', '')), 'desc' if sort.startswith('-') else 'asc') for sort in self.report._meta.sorting if self.report.field_exists(sort.replace('-', ''))]
        elif hasattr(self.report, 'Item'):
            try:
                sorting = [(self.report.field_index(sort.replace('-', '')), 'desc' if sort.startswith('-') else 'asc') for sort in self.report.Item._meta.ordering]
            except ValueError: pass
        return json.dumps(sorting, cls=DTEncoder)
