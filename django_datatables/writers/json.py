from django_datatables.writers.html import HtmlWriter
from django.core.context_processors import csrf

class JsonWriter(HtmlWriter):
    """
    Json report writer.
    """
    report = None