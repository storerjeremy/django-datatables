from django.utils import formats
from django.utils.functional import curry

class BaseWriter(object):
    is_localized = False
    
    def __init__(self, report, qs=None):
        self.report = report
        if qs is None:
            qs = report.queryset()
        self.qs = qs
    
    def _format_value(self, value):
        if self.is_localized:
            return formats.localize_input(value)
        return value