from django.utils import unittest
from django_datatables import ReportBase
from datetime import date
import django_datatables
from django_datatables.testcases import TestReport
from decimal import Decimal

class ReportTestCase(unittest.TestCase):

    def setUp(self):
        self.report = TestReport()
    
    def test_len_fields(self):
        self.assertEquals(len(self.report.fields()), 5)
    
    def test_field_names(self):
        self.assertEquals(
            [field.name for field in self.report.fields()], 
            ['name', 'status', 'dob', 'successful_calls', 'calc']
        )
    
    def test_field_types(self):
        self.assertEquals(
            [field.__class__ for field in self.report.fields()], 
            [django_datatables.CharField, django_datatables.CharField, django_datatables.DateField, django_datatables.PercentField, django_datatables.IntegerField]
        )

    def test_field_titles(self):
        self.assertEquals(
            [field.title for field in self.report.fields()], 
            ['Name', 'Status', 'Birthdate', 'Successful Calls', 'Calc']
        )
        
    def test_field_sorting(self):
        self.assertEquals(
            [field.sorting for field in self.report.fields()], 
            [True, True, False, False, False]
        )
        
    def test_field_filter(self):
        self.assertEquals(
            [field.filter for field in self.report.fields()], 
            [True, True, False, False, True]
        )
    
    def test_field_title_tips(self):
        self.assertEquals(
            [field.title_tip for field in self.report.fields()], 
            ['Here is the name', None, None, None, 'An example that uses a callable on Item rather than an attr']
        )
    
    def test_field_data_tips(self):
        self.assertEquals(
            [field.data_tip for field in self.report.fields()], 
            [None, '$name is $status', None, None, None]
        )
    
    def test_field_choices(self):
        self.assertEquals(
            [field.choices for field in self.report.fields()], 
            [None, (('active', 'Active'), ('inactive', 'Inactive')), None, None, None]
        )
        
    def test_queryset_len(self):
        self.assertEquals(len(self.report.queryset()), 4)
    
    def test_queryset_data_name(self):
        self.assertEquals(
            [item.name for item in self.report.queryset()], 
            ['John Doe', 'Jane Doe', 'Billy Boe', 'Jesus Christ']
        )

    def test_queryset_data_status(self):
        self.assertEquals(
            [item.status for item in self.report.queryset()], 
            ['active', 'active', 'active', 'inactive']
        )

    def test_queryset_data_dob(self):
        self.assertEquals(
            [item.dob for item in self.report.queryset()], 
            [date(1980, 5, 6), date(1981, 2, 21), date(1965, 1, 1), date(1946, 12, 25)]
        )

    def test_queryset_data_successful_calls(self):
        self.assertEquals(
            [item.successful_calls for item in self.report.queryset()], 
            [(1, 2), (Decimal('2'), 4), (3, 10), (Decimal('11.2'), Decimal('22.4'))]
        )

    def test_queryset_data_calc(self):
        self.assertEquals(
            [item.calc() for item in self.report.queryset()], 
            [6, Decimal('7'), 8, Decimal('16.2')]
        )
    
    def test_data_len(self):
        self.assertEquals(len(self.report.data()), 4)
    
    def test_data_name(self):
        self.assertEquals(
            [item['name'] for item in self.report.data()], 
            ['John Doe', 'Jane Doe', 'Billy Boe', 'Jesus Christ']
        )

    def test_data_status(self):
        self.assertEquals(
            [item['status'] for item in self.report.data()], 
            ['active', 'active', 'active', 'inactive']
        )

    def test_data_dob(self):
        self.assertEquals(
            [item['dob'] for item in self.report.data()], 
            [date(1980, 5, 6), date(1981, 2, 21), date(1965, 1, 1), date(1946, 12, 25)]
        )

    def test_data_successful_calls(self):
        self.assertEquals(
            [item['successful_calls'] for item in self.report.data()], 
            [(1, 2), (Decimal('2'), 4), (3, 10), (Decimal('11.2'), Decimal('22.4'))]
        )

    def test_data_calc(self):
        self.assertEquals(
            [item['calc'] for item in self.report.data()], 
            [6, Decimal('7'), 8, Decimal('16.2')]
        )

    def test_has_aggregates(self):
        self.assertEquals(self.report.has_aggregates(), True)
    
    def test_aggregates(self):
        self.assertEquals(
            self.report.get_aggregates(),
            {'calc': Decimal('37.2')}
        )