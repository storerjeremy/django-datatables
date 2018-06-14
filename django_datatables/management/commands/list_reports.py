import sys, logging, importlib, os
from django.conf import settings
from django.core.management.base import BaseCommand
from datetime import datetime
from django_datatables import get_reports, load_report_class
from django_toolkit.table.console import ConsoleTable

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = 'my.datatables.module writer'
    help = "Write out a report. Currently supported writers are 'csv'."
    now = datetime.now()

    def handle(self, *args, **options):
        """
        Run/write out a particular report.
        """
        reports = get_reports()
        
        rows = [
            (
                load_report_class(app_name, name)._meta.verbose_name,
                load_report_class(app_name, name)._meta.description,
                "%s.reports.%s" % (app_name, name), 
                ", ".join([writer.__name__ for writer in load_report_class(app_name, name).writers()]),
            )
            for key, (name, app_name) in reports.iteritems()
        ]
        
        print ConsoleTable(('Name', 'Description', 'Module', 'Writers',), rows)
