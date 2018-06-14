from django.utils.text import slugify
from django_datatables.writers.json import JsonWriter

def report_json_context_helper(report, source_url, create_url=None, submit_url=None, id_prepend='', tabletools=None):
    context = {
        'writer': JsonWriter(report),
        'report': report,
        'report_class': report_class_for_report(report), 
        'meta': report._meta,
        'id': id_for_report(report, id_prepend),
        'source_url': source_url
    }
    if create_url:
        context['create_url'] = create_url
    if submit_url:
        context['submit_url'] = submit_url
        context['form_prefix'] = report._meta.form_prefix
    if tabletools:
        context['tabletools'] = tabletools if isinstance(tabletools, basestring) else ",".join(tabletools)
    return context

def report_class_for_report(report):
    return '%s.%s' % (report.__module__, report.__class__.__name__)

def id_for_report(report, prepend=''):
    return slugify(u'%s-%s%s' % (report.__module__.replace('.', '-'), 
                                 report.__class__.__name__,
                                 prepend))