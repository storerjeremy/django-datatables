import csv, logging
from django_datatables.writers.base import BaseWriter
from django_toolkit.table.console import ConsoleTable

class ConsoleWriter(BaseWriter):
    
    def write(self):
        """
        Write the csv to path
        
        @param path: The file path to write the csv to.
        @return UnicodeWriter: The UnicodeWriter instance used to write the csv.
        """
        rows = []
        for item in self.report.queryset():
            row = []
            for field in self.report.fields():
                row.append(field.widget.render(self, field.name, field.traverse_for_value(item), item))
            rows.append(row)

        if self.report.has_aggregates():
            rows.append(None)
            aggregates = self.report.get_aggregates()
            row = []
            for field in self.report.fields():
                row.append( (aggregates[field.name] if field.aggregate else '') )
            rows.append(row)

        return ConsoleTable(self.report.titles(), rows) 