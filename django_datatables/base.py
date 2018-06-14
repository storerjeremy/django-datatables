import sys, re, os
import logging
from django.utils import six
from bisect import bisect
from django.utils.encoding import force_text
from django.utils.functional import curry
from django.conf import settings
from django.utils.translation import string_concat
from django.utils.text import slugify
from django_datatables import writers
from django.core.cache import cache
from django.db.models import Q
import copy
get_verbose_name = lambda name: re.sub('(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))', ' \\1', name).lower().strip()

logger = logging.getLogger(__name__)

DEFAULT_NAMES = ('verbose_name', 'app_label', 'slug', 'description', 'writers', 'cache', 'form_prefix', 'sorting', 'listing')

class Options():
    def __init__(self, meta, app_label=None):
        self.app_label = app_label
        self.meta = meta
        self.fields = []
        self.slug = None
        self.verbose_name, self.verbose_name_plural = None, None
        self.description = None
        self.writers = []
        self.cache = False
        self.listing = False

    def add_field(self, field):
        self.fields.append(field) #insert(bisect(self.fields, field), field)

    def contribute_to_class(self, cls, name):
        cls._meta = self
        #self.report = cls
        self.app = re.sub('\.reports\.\w+$', '', cls.__module__)
        self.installed = self.app in settings.INSTALLED_APPS
        # First, construct the default values for these options.
        self.object_name = cls.__name__
        self.module_name = self.object_name.lower()
        self.form_prefix = False
        self.report_name = cls.__module__.split('.')[-1]
        self.verbose_name = u'%s - %s' % (get_verbose_name(self.app_label).title(), get_verbose_name(cls.__module__.split('.')[-1]).title())
        self.slug = slugify(self.verbose_name)
        self.writers = (writers.HtmlWriter, writers.ConsoleWriter, writers.UnicodeCsvWriter)

        # Next, apply any overridden values from 'class Meta'.
        if self.meta:
            meta_attrs = self.meta.__dict__.copy()
            for name in self.meta.__dict__:
                # Ignore any private attributes that Django doesn't care about.
                # NOTE: We can't modify a dictionary's contents while looping
                # over it, so we loop over the *original* dictionary instead.
                if name.startswith('_'):
                    del meta_attrs[name]
            for attr_name in DEFAULT_NAMES:
                if attr_name in meta_attrs:
                    setattr(self, attr_name, meta_attrs.pop(attr_name))
                elif hasattr(self.meta, attr_name):
                    setattr(self, attr_name, getattr(self.meta, attr_name))

            # Any leftover attributes must be invalid.
            if meta_attrs != {}:
                raise TypeError("'class Meta' got invalid attribute(s): %s" % ','.join(meta_attrs.keys()))
        else:
            self.verbose_name_plural = string_concat(self.verbose_name, 's')
        del self.meta

    def _prepare(self, report):
        pass

class ReportBase(type):
    """
    Metaclass for all reports - borrowed heavily from django ModelBase
    """
    def __new__(cls, name, bases, attrs):
        super_new = super(ReportBase, cls).__new__
        # six.with_metaclass() inserts an extra class called 'NewBase' in the
        # inheritance tree: Model -> NewBase -> object. Ignore this class.
        parents = [b for b in bases if isinstance(b, ReportBase) and
                not (b.__name__ == 'NewBase' and b.__mro__ == (b, object))]
        if not parents:
            # If this isn't a subclass of Model, don't do anything special.
            return super_new(cls, name, bases, attrs)

        # Create the class.
        module = attrs.pop('__module__')
        new_class = super_new(cls, name, bases, {'__module__': module})
        attr_meta = attrs.pop('Meta', None)
        if not attr_meta:
            meta = getattr(new_class, 'Meta', None)
        else:
            meta = attr_meta
        base_meta = getattr(new_class, '_meta', None)

        # Ensure we reset the creation counter for each report
        from django_datatables.fields import Field
        Field.creation_counter = 0

        kwargs = {'app_label': 'Report'}
        if getattr(meta, 'app_label', None) is None:
            # Figure out the app_label by looking one level up.
            # For 'django.contrib.sites.models', this would be 'sites'.
            report_module = sys.modules[new_class.__module__]
            try:
                kwargs = {"app_label": report_module.__name__.split('.')[-3]}
            except IndexError: pass

        new_class.add_to_class('_meta', Options(meta, **kwargs))

        field_names = set([f.name for f in new_class._meta.fields])

        # Add all attributes to the class.
        for obj_name, obj in attrs.items():
            new_class.add_to_class(obj_name, obj)
            #setattr(new_class, obj_name, obj)

        for base in parents:
            if not hasattr(base, '_meta'):
                # Things without _meta aren't functional reports, so they're
                # uninteresting parents.
                continue

            parent_fields = base._meta.fields
            # Check for clashes between locally declared fields and those
            # on the base classes (we cannot handle shadowed fields at the
            # moment).
            for field in parent_fields:
                if field.name in field_names:
                    raise Exception('Local field %r in class %r clashes '
                                     'with field of similar name from '
                                     'base class %r' %
                                        (field.name, name, base.__name__))

            for field in parent_fields:
                obj = copy.deepcopy(field)
                new_class.add_to_class(field.name, obj)
                setattr(new_class, field.name, obj)

            # Pass any non-abstract parent classes onto child.
            # new_class._meta.parents.update(base._meta.parents)

        # Ensure fields are in the correct order...
        new_class._meta.fields.sort()
        new_class._prepare()
        
        return new_class
    
    def add_to_class(cls, name, value):
        if hasattr(value, 'contribute_to_class'):
            value.contribute_to_class(cls, name)
        else:
            setattr(cls, name, value)
    
    def _prepare(cls):
        """
        Creates some methods/attrs once self._meta has been populated.
        """
        opts = cls._meta
        opts._prepare(cls)

        # Give the class a docstring -- its definition.
        if cls.__doc__ is None:
            cls.__doc__ = "%s(%s)" % (cls.__name__, ", ".join([f.attname for f in opts.fields]))

        if hasattr(cls, 'get_absolute_url'):
            cls.get_absolute_url = update_wrapper(curry(get_absolute_url, opts, cls.get_absolute_url),
                                                  cls.get_absolute_url)
        
        for writer in cls._meta.writers:
            setattr(cls._meta, 'supports_%s_writer' % writer.__name__, True)

class Report(six.with_metaclass(ReportBase, object)):
    
    def __init__(self, request=None):
        if request is not None:
            self.set_request(request)
    
    def _raiseNotImplementedError(self, what, name):
        raise NotImplementedError("The %s '%s' was not defined by '%s.%s'" % (what, name, self.__module__, self.__class__.__name__))

    def queryset(self):
        """
        Return the queryset for this report.
        """
        self._raiseNotImplementedError('method', 'queryset')

    def fields(self, attr=None, value=None):
        """
        Return a list of fields optionally filtering the list using attr=value
        
        @param attr: The attribute to filter
        @param value: The value of the attribute
        @return: List of fields
        """
        fields = self._meta.fields
        if attr:
            return [field for field in fields if getattr(field, attr) == value]
        return fields 
    
    def field(self, name):
        """
        Retrieve a field by its name.
        """
        for field in self.fields():
            if field.name == name:
                return field

    def field_exists(self, name):
        return self.field(name) is not None

    def field_index(self, name):
        """
        Retrieve the field index by field name.
        """
        return self.fields().index(self.field(name))
    
    def titles(self):
        """
        Return a list of field titles.
        """
        return [field.title for field in self.fields()]
    
    def writers(self):
        """
        Return writers supported by this report.
        """
        return self._meta.writers

    def supports_writer(self, writer):
        """
        Return True if writer is supported by this report.
        """
        writers = self.writers()
        if isinstance(writer, basestring):
            writers = [_writer.__class__.__name__ for _writer in writers]
        return writer in writers

    def cache_key(self):
        """
        Return a cache key for this report.
        """
        return 'report-%s' % self.__class__.__name__

    def delete_cache(self):
        cache.delete(self.cache_key())

    def data(self):
        """
        Retrieve the data for a report and possibly cache it.
        """
        if hasattr(self, '_data'):
            return self._data
        if self._meta.cache:
            # Check if the data exists in cache
            self._data = cache.get(self.cache_key())
            if not self._data:
                self._data = self._gather_data()
                cache.set(self.cache_key(), self._data, self._meta.cache.seconds)
        else:
            self._data = self._gather_data()
        return self._data

    def set_request(self, request):
        """
        Set the request object that is being used to display this report.
        """
        self.request = request

    def _gather_data(self):
        """
        Gather the data into a list of dicts
        @return list: A list of dicts with field names forming the dict keys.
        """
        rows = []
        for item in self.queryset():
            row = {}
            for field in self.fields():
                at = getattr(item, field.name)
                row[field.name] = at() if callable(at) else at
            rows.append(row)
        return rows

    def has_aggregates(self):
        return len([field for field in self.fields() if field.aggregate]) > 0
    
    def get_aggregates(self):
        if not self.has_aggregates():
            return None
        if hasattr(self, '_aggregates'):
            return self._aggregates
        self._aggregates = {}
        aggregate_fields = [field for field in self.fields() if field.aggregate]
        for item in self.data():
            for field in aggregate_fields:
                if not field.name in self._aggregates:
                    self._aggregates[field.name] = item[field.name]
                else:
                    self._aggregates[field.name] += item[field.name]
        return self._aggregates
    
    def get_qs_for_term(self, term):
        """
        Get a queryset object that uses term to filter the entire report.
        """
        if not term or len(term) == 0:
            return None
        
        qs_params = None
        for field in self.fields('filter', True):
            q = field.get_qs_for_term(term)
            if q:
                qs_params = qs_params | q if qs_params else q
        return qs_params
