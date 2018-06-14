import sys, logging, importlib, os
from django.conf import settings
from django.core.management.base import BaseCommand
from datetime import datetime
from django_datatables.writers.csv_writers import UnicodeCsvWriter
from django_datatables.writers.console import ConsoleWriter

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = 'module'
    help = "Delete a reports cache."
    now = datetime.now()

    def handle(self, *args, **options):
        """
        Run/write out a particular report.
        """
        if len(args) != 1:
            sys.exit("Incorrect usage - call with --help to see usage.") 
    
        report = importlib.import_module(args[0]).Report()
        report.delete_cache()