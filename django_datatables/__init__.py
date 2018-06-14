import os
import sys
import imp
try:
    # Django versions >= 1.9
    from django.utils.module_loading import import_module
except ImportError:
    # Django versions < 1.9
    from django.utils.importlib import import_module
from django.conf import settings
from django_datatables.base import *
from django_datatables.widgets import *
from django_datatables.fields import *
from django_datatables.writers import *

# A cache of loaded reports, so that get_reports
# doesn't have to reload every time it's called.
_reports = None

def find_reports(report_dir):
    """
    Given a path to a management directory, returns a list of all the command
    names that are available.

    Returns an empty list if no commands are defined.
    """
    report_dir = os.path.join(report_dir, 'reports')
    try:
        return [f[:-3] for f in os.listdir(report_dir)
                if not f.startswith('_') and f.endswith('.py') and not f.startswith('test')]
    except OSError as e:
        return []

def find_report_module(app_name):
    """
    Determines the path to the reports module for the given app_name,
    without actually importing the application or the management module.

    Raises ImportError if the reports module cannot be found for any reason.
    """
    parts = app_name.split('.')
    parts.reverse()
    part = parts.pop()
    path = None

    # When using manage.py, the project module is added to the path,
    # loaded, then removed from the path. This means that
    # testproject.testapp.models can be loaded in future, even if
    # testproject isn't in the path. When looking for the management
    # module, we need look for the case where the project name is part
    # of the app_name but the project directory itself isn't on the path.
    try:
        f, path, descr = imp.find_module(part, path)
    except ImportError as e:
        if os.path.basename(os.getcwd()) != part:
            raise e
    else:
        if f:
            f.close()

    while parts:
        part = parts.pop()
        f, path, descr = imp.find_module(part, path and [path] or None)
        if f:
            f.close()
    return path

def load_report_class(app_name, name):
    """
    Given a name and an application name, returns the Report
    class instance. All errors raised by the import process
    (ImportError, AttributeError) are allowed to propagate.
    """
    return import_module('%s.reports.%s' % (app_name, name)).Report()

def get_reports():
    """
    Returns a dictionary mapping report names to their callbacks.

    This works by looking for a reports package in each installed application -- 
    if a reports package exists, all reports in that package are registered.

    The dictionary is in the format {report_name: app_name}. Key-value
    pairs from this dictionary can then be used in calls to
    load_report_class(app_name, report_name)

    The dictionary is cached on the first call and reused on subsequent
    calls.
    """
    global _reports
    if _reports is None:
        _reports = dict()
        
        # Find the installed apps
        from django.conf import settings
        apps = settings.INSTALLED_APPS

        # Find and load the reports for each installed app.
        for app_name in apps:
            try:
                path = find_report_module(app_name)
                for name in find_reports(path):
                    try:
                        report = load_report_class(app_name, name)
                        if isinstance(report, Report):
                            # Ensure that our report class extends ReportBase
                            _reports.update(dict([('%s.%s' % (report.__module__, report.__class__.__name__), (name, app_name))]))
                    except AttributeError as e:
                        pass
                    except ImportError as e:
                        pass
            except ImportError:
                pass

    return _reports

class FieldError(Exception):
    """Some kind of problem with a report field."""
    pass

class ValidationError(Exception):
    """A validation issue with a report field."""
    pass
