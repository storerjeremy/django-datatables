import tempfile, os, logging
from django.conf import settings
from datetime import date
from django.utils import unittest
from django_toolkit.csv.unicode import UnicodeReader
from django_datatables.writers.csv_writers import UnicodeCsvWriter
from django_datatables.testcases import TestReport

logger = logging.getLogger(__name__)

class CsvWriterTestCase(unittest.TestCase):

    def setUp(self):
        self.report = TestReport()
        self.writer = UnicodeCsvWriter(self.report)
        
    def test_file_exists(self):
        path = tempfile.mktemp('.csv')
        self.writer.write(path)
        self.assertTrue(os.path.exists(path))
        os.unlink(path)

    def test_csv_contents(self):
        path = tempfile.mktemp('.csv')
        self.writer.write(path)

        logger.warn(path)
        
        contents = open(path, 'rb').read()
        expected = "Name,Status,Birthdate,Successful Calls,Calc\r\n" \
                   "John Doe,active,1980-05-06,50% (1/2),6\r\n" \
                   "Jane Doe,active,1981-02-21,50% (2/4),7\r\n" \
                   "Billy Boe,active,1965-01-01,30% (3/10),8\r\n" \
                   "Jesus Christ,inactive,1946-12-25,50% (11.2/22.4),16.2\r\n"
        self.assertEquals(contents, expected)
        os.unlink(path)