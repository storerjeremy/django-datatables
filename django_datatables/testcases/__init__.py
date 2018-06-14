from datetime import date
from decimal import Decimal
import django_datatables

class TestReport(django_datatables.Report):
    """
    A dummy report that can be used for testing.
    """
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    )
    
    name = django_datatables.CharField(title='Name', sorting=True, filter=True, title_tip='Here is the name')
    status = django_datatables.CharField(title='Status', sorting=True, filter=True, choices=STATUS_CHOICES, data_tip='$name is $status')
    dob = django_datatables.DateField(title='Birthdate')
    successful_calls = django_datatables.PercentField()
    calc = django_datatables.IntegerField(title_tip='An example that uses a callable on Item rather than an attr', filter=True, aggregate=True)
    
    class Meta:
        verbose_name = 'Test Report'
        description = 'This is a test report!'
        writers = (django_datatables.ConsoleWriter, django_datatables.HtmlWriter, django_datatables.UnicodeCsvWriter)

    def queryset(self):
        """
        Returns an iterator of the data.
        """
        return [
            self.Item('John Doe', TestReport.STATUS_ACTIVE, date(1980, 5, 6), (1, 2)),
            self.Item('Jane Doe', TestReport.STATUS_ACTIVE, date(1981, 2, 21), (Decimal('2'), 4)),
            self.Item('Billy Boe', TestReport.STATUS_ACTIVE, date(1965, 1, 1), (3, 10)),
            self.Item('Jesus Christ', TestReport.STATUS_INACTIVE, date(1946, 12, 25), (Decimal('11.2'), Decimal('22.4'))),
        ]

    class Item():
        """
        Definition of each row in the report. 
        """
        def __init__(self, name, status, dob, successful_calls):
            self.name = name
            self.status = status
            self.dob = dob
            self.successful_calls = successful_calls

        def calc(self):
            return self.successful_calls[0] + 5