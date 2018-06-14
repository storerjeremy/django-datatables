import csv, logging
from django_datatables.writers.base import BaseWriter
from django_toolkit.csv.unicode import UnicodeWriter

class UnicodeCsvWriter(BaseWriter):
    
    def write(self, f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL):
        """
        Write the csv to path
        
        @param f: Either a file like object or a file path
        @return UnicodeWriter: The UnicodeWriter instance used to write the csv.
        """
        if not hasattr(f, 'read'):
            handle = open(f, 'wb')
        else:
            handle = f
        
        writer = UnicodeWriter(handle, delimiter=delimiter, quotechar=quotechar, quoting=quoting)
        writer.writerow(self.report.titles())
        try:
            row_number = 0
            for item in self.qs:
                row = []
                for field in self.report.fields():
                    value = field.prepare_value(field.traverse_for_value(item))
                    if field.pre_process_with:
                        for callback in field.pre_process_with:
                            if hasattr(self.report, callback):
                                value = getattr(self.report, callback)(value, item)
                    rendered = field.widget.render(self.report, self, field.name, value, item, row_number)
                    if field.post_process_with:
                        for callback in field.post_process_with:
                            try:
                                callback = getattr(self.report, callback)
                            except TypeError: pass
                            rendered = callback(rendered, item)
                    row.append(u"%s" % rendered)
                writer.writerow(row)
                row_number += 1
        except UnicodeDecodeError as e:
            e.reason += ' - for row: %s' % ', '.join(row)
            raise e
        finally:
            if handle != f:
                # If we opened the file, close it.
                handle.close()