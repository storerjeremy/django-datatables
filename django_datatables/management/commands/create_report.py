import sys, logging, importlib, os
from django.conf import settings
from django.core.management.base import BaseCommand
from datetime import datetime
from django_datatables.writers.csv_writers import UnicodeCsvWriter
from django_datatables.writers.console import ConsoleWriter

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    args = 'my.datatables.module writer'
    help = "Write out a report. Currently supported writers are 'csv'."
    now = datetime.now()

    def handle(self, *args, **options):
        """
        Run/write out a particular report.
        """
        if len(args) != 2:
            sys.exit("Incorrect usage - call with --help to see usage.") 
    
        module = args[0]
        writer = args[1]

        report = importlib.import_module(module).Report()
        
        supported_writers = (UnicodeCsvWriter, ConsoleWriter)
        
        if writer not in [supported_writer.__name__ for supported_writer in supported_writers]:
            sys.exit('Unknown writer: %s' % writer)
        
        writer_cls = globals()[writer]
        
        if not report.supports_writer(writer_cls):
            sys.exit('Writer %s not supported by report.' % writer) 
        
        if writer_cls == UnicodeCsvWriter:
            writer = UnicodeCsvWriter(report)
            path = os.path.join(settings.MEDIA_ROOT, settings.REPORT_ROOT, module, "%s-%s.csv" % (report._meta.slug, self.now.strftime('%Y%m%d%H%M%S')))
            if not os.path.isdir(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path), settings.FILE_UPLOAD_PERMISSIONS)
            writer.write(path)
            print "Created: %s" % path
        
        elif writer_cls == ConsoleWriter:
            print ConsoleWriter(report).write()
