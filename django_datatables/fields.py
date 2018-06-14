import copy
import types
import datetime
import collections
import warnings
from itertools import tee
from django.utils.dateparse import parse_date, parse_datetime, parse_time
from django.utils import timezone
from django_datatables import *
from django.utils.functional import curry, total_ordering
from django.db.models.constants import LOOKUP_SEP
from django.db.models.fields import FieldDoesNotExist
from django.utils.translation import ugettext_lazy as _
from moneyed import Money
from moneyed.classes import CurrencyDoesNotExist
from decimal import InvalidOperation
from django.core.exceptions import ObjectDoesNotExist
from django.forms.utils import to_current_timezone, from_current_timezone
from datetime import timedelta
from django_datatables.widgets import PercentChangeWidget, TextInputWidget,\
    PhoneNumberWidget, ManyManyLabelWidget
                                    
get_title = lambda title: title.replace('_', ' ').title().strip()

BLANK_CHOICE_DASH = [("", "---------")]
CHOICE_NULL = '**NULL**'

@total_ordering
class Field(object):
    widget = TextWidget
    lookup_type = 'icontains'
    hidden = False
    
    # These track each time a Field instance is created. Used to retain order.
    # The auto_creation_counter is used for fields that Django implicitly
    # creates, creation_counter is used for all user-specified fields.
    creation_counter = 0
    
    def __init__(self, name=None, title=None, sorting=False, filter=False, 
                 choices=None, data_tip=None, title_tip=None, widget=None, 
                 localize=False, aggregate=False, 
                 sorting_with=False, filter_with=False,
                 error_messages=None, position=False, hidden=False,
                 form_field_name=False, 
                 pre_process_with=False, post_process_with=False,
                 add_null_choice=False):
        """
        @param name:           The name for the field
        @param title:          Title used for displaying the field
        @param sorting:        Turn off/on ability to sort data by this field
        @param filter:         Turn off/on ability to filter data by this field
        @param sorting_with:   Define a list of fields that should be used for 
                               sorting. Defaults to the field name. Implies sorting=True
        @param filter_with:    Define a list of fields that should be used for 
                               filtering. Defaults to the field name. Implies filter=True
        @param choices:        A list of choices that can be used to filter data
        @param data_tip:       A tool tip that is attached to each line of data - accepts
                               a string that is interpreted as a django template and has
                               {{ object }} as the current data item being processed.
        @param title_tip:      A tool tip that is attached to the field title (ie.. 
                               header in a html table).
        @param widget:         The widget to use for rendering.
        @param localize:       Whether this field should be localized or not.
        @param aggregate:      Whether aggregates for this field should be produced.
        @param error_messages: A list of default error messages.
        @param position:       The fields position. Fields are displayed in the 
                               order they are created however if you have a report
                               that extends another report you can control the 
                               position of each field using this value.
        @param hidden:         Whether this field should be hidden in datatables.
        """
        self.name = name
        self.title = title
        if sorting_with and not sorting:
            sorting = True
        self.sorting = sorting
        self.sorting_with = sorting_with
        if filter_with and not filter:
            filter = True
        self.filter = filter
        self.filter_with = filter_with
        if add_null_choice and choices:
            choices = [(CHOICE_NULL, '(Null)')] + list(choices)
        self._choices = choices
        self.data_tip = data_tip
        self.title_tip = title_tip
        self.aggregate = aggregate
        self.hidden = hidden
        self.form_field_name = form_field_name
        self.pre_process_with = pre_process_with
        self.post_process_with = post_process_with
        
        widget = widget or self.widget
        if isinstance(widget, type):
            attrs = {}
            if self.data_tip:
                attrs['data_tip'] = self.data_tip
            if self.title_tip:
                attrs['title_tip'] = self.title_tip
            widget = widget(self, attrs)

        # Trigger the localization machinery if needed.
        self.localize = localize
        if self.localize:
            widget.is_localized = True

        # Hook into self.widget_attrs() for any Field-specific HTML attributes.
        extra_attrs = self.widget_attrs(widget)
        if extra_attrs:
            widget.attrs.update(extra_attrs)

        self.widget = widget

        # Adjust the appropriate creation counter, and save our local copy.
        self.creation_counter = Field.creation_counter
        Field.creation_counter += 1
        self.position = position if position else self.creation_counter

        messages = {}
        for c in reversed(self.__class__.__mro__):
            messages.update(getattr(c, 'default_error_messages', {}))
        messages.update(error_messages or {})
        self.error_messages = messages

    def __eq__(self, other):
        # Needed for @total_ordering
        if isinstance(other, Field):
            return self.position == other.position
        return NotImplemented

    def __lt__(self, other):
        # This is needed because bisect does not take a comparison function.
        if isinstance(other, Field):
            return self.position < other.position
        return NotImplemented

    def __repr__(self):
        """
        Displays the module, class and name of the field.
        """
        path = '%s.%s' % (self.__class__.__module__, self.__class__.__name__)
        name = getattr(self, 'name', None)
        if name is not None:
            return '<%s: %s>' % (path, name)
        return '<%s>' % path

    def __deepcopy__(self, memodict):
        # We don't have to deepcopy very much here, since most things are not
        # intended to be altered after initial creation.
        obj = copy.copy(self)
        memodict[id(self)] = obj
        return obj
    
    def to_python(self, value):
        """
        Converts the input value into the expected Python data type, raising
        django.core.exceptions.ValidationError if the data can't be converted.
        Returns the converted value. Subclasses should override this.
        """
        if value == CHOICE_NULL:
            return None
        return value
    
    def set_attributes_from_name(self, name):
        if not self.name:
            self.name = name
        if not self.form_field_name:
            self.form_field_name = name
        if not self.title:
            self.title = get_title(name)
        if not self.filter_with:
            self.filter_with = (name, )
        if not self.sorting_with:
            self.sorting_with = name
        self.attname = self.get_attname()

    def contribute_to_class(self, cls, name):
        self.report = cls
        self.set_attributes_from_name(name)
        cls._meta.add_field(self)

    def get_attname(self):
        return self.name

    def get_flatchoices(self, include_blank=True,
                        blank_choice=BLANK_CHOICE_DASH):
        """
        Returns flattened choices with a default blank choice included.
        """
        first_choice = include_blank and blank_choice or []
        return first_choice + list(self.flatchoices)

    def _get_choices(self):
        if isinstance(self._choices, collections.Iterator):
            choices, self._choices = tee(self._choices)
            return choices
        else:
            return self._choices
    choices = property(_get_choices)

    def _get_flatchoices(self):
        """Flattened version of choices tuple."""
        flat = []
        for choice, value in self._choices:
            if isinstance(value, (list, tuple)):
                flat.extend(value)
            else:
                flat.append((choice,value))
        return flat
    flatchoices = property(_get_flatchoices)
    
    def widget_attrs(self, widget):
        """
        Given a Widget instance (*not* a Widget class), returns a dictionary of
        any HTML attributes that should be added to the Widget, based on this
        Field.
        """
        return {}
    
    def traverse_for_value(self, data, name=None):
        """
        Retrieve the value of a field by traversing data using the field's name.
        
        @param data: Either a dict or a model instance.
        
        Borrowed heavily from django.db.datas.sql.query.add_filter
        """
        if not name:
            name = self.name

        if isinstance(data, dict) and name in data:
            return data[name]

        parts = name.split(LOOKUP_SEP)
        if not parts:
            raise FieldError("Cannot parse field name %r" % self.name)

        num_parts = len(parts)
        
        # Traverse the lookup query to distinguish related fields from
        # lookup types.
        lookup_model = data
        for counter, field_name in enumerate(parts):
            try:
                lookup_field = getattr(lookup_model, field_name)
            except FieldDoesNotExist:
                # Not a field. Bail out.
                raise FieldError("Field '%s' does not exist for model '%s'." % (field_name, data.__class__.__name__))
            except ObjectDoesNotExist:
                return None
            except AttributeError:
                return None
            # Unless we're at the end of the list of lookups, let's attempt
            # to continue traversing relations.
            if (counter + 1) < num_parts:
                lookup_model = lookup_field

        return lookup_field
    
    def get_qs_for_term(self, term, exact=False):
        from django_datatables import ValidationError
        qs_params = None
        for filter_with in self.filter_with:
            try:
                lookup_type = 'exact' if exact and self.choices else self.lookup_type
                if ',' in term and self.choices:
                    lookup_type = 'in'
                    term = term.split(',')
                kwargs = {
                    # we only call to_python to ensure we can catch ValidationErrors and not put them in the params.
                    '%s__%s' % (filter_with, lookup_type): self.to_python(term)
                }
                q = Q(**kwargs)
                qs_params = qs_params | q if qs_params else q
                logger.debug("Filter '%s': %s" % (filter_with, kwargs))
            except ValidationError as e:
                # Don't include fields that do not validate...
                logger.debug("Suppressing ValidationError for report '%s' for field '%s' with term '%s': %s" % (self.__module__, filter_with, term, e))

        if qs_params:
            return qs_params
    
    def prepare_value(self, value):
        return value


class CharField(Field):
    pass


class EmailField(Field):
    pass


class IntegerField(Field):
    widget = IntegerWidget


class DurationField(CharField):
    widget = DurationWidget
    microseconds = False
    default_error_messages = {
        'invalid': _("'%s' value must be either an instance of timedelta or an integer."),
    }
    
    def __init__(self, microseconds=False, *args, **kwargs):
        """
        @param microseconds: If True then value is considered microseconds and should be converted to timedelta
        """
        CharField.__init__(self, *args, **kwargs)
        self.microseconds = microseconds

    def prepare_value(self, value):
        if isinstance(value, timedelta):
            return value
        if self.microseconds and value:
            return timedelta(microseconds=int(value))
        return value

    def to_python(self, value):
        if isinstance(value, timedelta):
            return value
        if self.microseconds and value:
            return timedelta(microseconds=value)

        from django_datatables import ValidationError
        msg = self.error_messages['invalid'] % value
        raise ValidationError(msg)

class BooleanField(CharField):
    
    def __init__(self, *args, **kwargs):
        if 'choices' not in kwargs:
            kwargs['choices'] = ((1, 'Yes'), (0, 'No'))
        CharField.__init__(self, *args, **kwargs)

class LabelField(Field):
    widget = LabelWidget

    def __init__(self, label_class=None, data_tip_icon='icon-question-sign', *args, **kwargs):
        """
        @param label_class: Either a string or a callable that is used as the label class.
        """
        self.label_class = label_class
        self.data_tip_icon = data_tip_icon
        Field.__init__(self, *args, **kwargs)
        
class BadgeField(Field):
    widget = BadgeWidget

    def __init__(self, badge_class=None, data_tip_icon='icon-question-sign', *args, **kwargs):
        """
        @param label_class: Either a string or a callable that is used as the label class.
        """
        self.badge_class = badge_class
        self.data_tip_icon = data_tip_icon
        Field.__init__(self, *args, **kwargs)

class FileField(CharField):
    widget = FileWidget
    
    def __init__(self, url=False, a_attrs={}, *args, **kwargs):
        """
        @param url: callback to retrieve the url.
        """
        self.url = url
        self.a_attrs = a_attrs
        Field.__init__(self, *args, **kwargs)

class DateField(Field):
    widget = DateWidget
    lookup_type = 'exact'
    default_error_messages = {
        'invalid': _("'%s' value has an invalid date format. It must be "
                     "in YYYY-MM-DD format."),
        'invalid_date': _("'%s' value has the correct format (YYYY-MM-DD) "
                          "but it is an invalid date."),
    }
    timesince=False
    timesince_reverse=False

    def __init__(self, timesince=False, timesince_reverse=False, *args, **kwargs):
        """
        @param timesince: If true, then the time since this date is displayed by the widget.
        """
        Field.__init__(self, *args, **kwargs)
        self.timesince = timesince
        self.timesince_reverse = timesince_reverse
    
    def to_python(self, value):
        from django_datatables import ValidationError
        if value is None:
            return value
        if isinstance(value, datetime.datetime):
            if settings.USE_TZ and timezone.is_aware(value):
                # Convert aware datetimes to the default time zone
                # before casting them to dates (#17742).
                default_timezone = timezone.get_default_timezone()
                value = timezone.make_naive(value, default_timezone)
            return value.date()
        if isinstance(value, datetime.date):
            return value

        try:
            parsed = parse_date(value)
            if parsed is not None:
                return parsed
        except ValueError:
            msg = self.error_messages['invalid_date'] % value
            raise ValidationError(msg)

        msg = self.error_messages['invalid'] % value
        raise ValidationError(msg)
    
    def get_qs_for_term(self, term, exact=False):
        from django_datatables import ValidationError

        if not term or len(term) == 0:
            return None
        
        if term == '~':
            # Ignore terms with no start or finish.
            return

        if '~' in term:
            start, finish = term.split('~')
            if len(start) == 0:
                start = False
            if len(finish) == 0:
                finish = False
        else:
            start = False
            finish = False
        
        qs_params = None

        for filter_with in self.filter_with:
            kwargs = {}
            try:
                if start:
                    kwargs['%s__gte' % filter_with] = self.to_python(start)
                if finish:
                    kwargs['%s__lte' % filter_with] = self.to_python(finish)
                if not start and not finish:
                    kwargs['%s__%s' % (filter_with, self.lookup_type)] = self.to_python(term)
                
                q = Q(**kwargs)
                qs_params = qs_params | q if qs_params else q
                logger.debug("Filter '%s': %s" % (filter_with, kwargs))
            except ValidationError as e:
                # Don't include fields that do not validate...
                logger.debug("Suppressing ValidationError for report '%s' for field '%s' with term '%s': %s" % (self.__module__, filter_with, term, e))

        if qs_params:
            return qs_params

class DateTimeField(DateField):
    widget = DateTimeWidget
    lookup_type = 'exact'
    default_error_messages = {
        'invalid': _("'%s' value has an invalid format. It must be in "
                     "YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ] format."),
        'invalid_date': _("'%s' value has the correct format "
                          "(YYYY-MM-DD) but it is an invalid date."),
        'invalid_datetime': _("'%s' value has the correct format "
                              "(YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ]) "
                              "but it is an invalid date/time."),
    }
    
    def prepare_value(self, value):
        if isinstance(value, datetime.datetime):
            value = to_current_timezone(value)
        return value
    
    def to_python(self, value):
        from django_datatables import ValidationError
        if value is None:
            return value
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, datetime.date):
            value = datetime.datetime(value.year, value.month, value.day)
            if settings.USE_TZ:
                # For backwards compatibility, interpret naive datetimes in
                # local time. This won't work during DST change, but we can't
                # do much about it, so we let the exceptions percolate up the
                # call stack.
                warnings.warn("DateTimeField received a naive datetime (%s)"
                              " while time zone support is active." % value,
                              RuntimeWarning)
                default_timezone = timezone.get_default_timezone()
                value = timezone.make_aware(value, default_timezone)
            return value

        try:
            parsed = parse_datetime(value)
            if parsed is not None:
                return parsed
        except ValueError:
            msg = self.error_messages['invalid_datetime'] % value
            raise ValidationError(msg)

        try:
            parsed = parse_date(value)
            if parsed is not None:
                return datetime.datetime(parsed.year, parsed.month, parsed.day)
        except ValueError:
            msg = self.error_messages['invalid_date'] % value
            raise ValidationError(msg)

        msg = self.error_messages['invalid'] % value
        raise ValidationError(msg)
#
#    def to_python(self, value):
#        """
#        Validates that the input can be converted to a datetime. Returns a
#        Python datetime.datetime object.
#        """
#        if value in self.empty_values:
#            return None
#        if isinstance(value, datetime.datetime):
#            return from_current_timezone(value)
#        if isinstance(value, datetime.date):
#            result = datetime.datetime(value.year, value.month, value.day)
#            return from_current_timezone(result)
#        if isinstance(value, list):
#            # Input comes from a SplitDateTimeWidget, for example. So, it's two
#            # components: date and time.
#            if len(value) != 2:
#                raise ValidationError(self.error_messages['invalid'])
#            if value[0] in self.empty_values and value[1] in self.empty_values:
#                return None
#            value = '%s %s' % tuple(value)
#        result = super(DateTimeField, self).to_python(value)
#        return from_current_timezone(result)
#
#    def strptime(self, value, format):
#        return datetime.datetime.strptime(force_str(value), format)

class TimeField(Field): pass
class MoneyField(Field):
    lookup_type = 'exact'
    default_error_messages = {
        'invalid': _("'%s' value has an invalid money format. It must be "
                     "in 0.00 format with an optional currency code located "
                     "before the currency - ie. AUD 0.00"),
    }
    
    def to_python(self, value):
        from django_datatables import ValidationError
        if value is None:
            return None
        if isinstance(value, Money):
            return value.amount
        if isinstance(value, Decimal):
            return Money(value, settings.DEFAULT_CURRENCY_CODE)
        if isinstance(value, basestring):
            try:
                (currency, value) = value.split()
                if currency and value:
                    return Money(value, currency).amount
                elif currency:
                    return Money(value).amount
            except CurrencyDoesNotExist: pass # Likely the user was searching for something with a space
            except InvalidOperation: pass # Its a valid currency but the value can't be converted to decimal
            except ValueError:
                try:
                    return Money(value).amount
                except InvalidOperation:
                    pass
        msg = self.error_messages['invalid'] % value
        raise ValidationError(msg)
    
    
class CountField(IntegerField):
    widget = CountWidget


class DecimalField(Field):
    widget = DecimalWidget
    
    def __init__(self, decimal_places=2, only_necessary_places=True, *args, **kwargs):
        """
        @param decimal_places: Set the decimal places values should be formatted to.
        @param only_necessary_places: Only show decimal places if necessary (ie.. 1 rather than 1.00)
        """
        self.decimal_places = decimal_places
        self.only_necessary_places = only_necessary_places
        Field.__init__(self, *args, **kwargs)

class PercentField(Field):
    """
    A field that displays a percentage accompanied with the raw values.
    """
    widget = PercentWidget
    
    def __init__(self, decimal_places=2, only_necessary_places=True, *args, **kwargs):
        """
        @param decimal_places: Set the decimal places values should be formatted to.
        @param only_necessary_places: Only show decimal places if necessary (ie.. 1 rather than 1.00)
        """
        self.decimal_places = decimal_places
        self.only_necessary_places = only_necessary_places
        Field.__init__(self, *args, **kwargs)

class PercentChangeField(Field):
    """
    A field that displays a percentage accompanied with the raw values.
    """
    widget = PercentChangeWidget
    
    def __init__(self, decimal_places=2, only_necessary_places=True, *args, **kwargs):
        """
        @param decimal_places: Set the decimal places values should be formatted to.
        @param only_necessary_places: Only show decimal places if necessary (ie.. 1 rather than 1.00)
        """
        self.decimal_places = decimal_places
        self.only_necessary_places = only_necessary_places
        Field.__init__(self, *args, **kwargs)
        
class UrlField(Field):
    widget = UrlWidget

class XEditableField(Field):
    """
    A field that renders X-Editable markup. 
    
    :see: http://vitalets.github.io/x-editable/docs.html
    """
    widget = XEditableWidget

    def __init__(self, xeditable_attributes=None, if_none='', *args, **kwargs):
        """
        :type xeditable_attributes: String of method name that is used for each 
                                    row to retrieve the x-editable attributes.
        """
        super(XEditableField, self).__init__(*args, **kwargs)
        self.xeditable_attributes = xeditable_attributes
        self.if_none = if_none
        
    def prepare_value(self, value):
        if value is None:
            return self.if_none
        return value
        
class GenericForeignKey(UrlField):
    widget = ForeignKeyWidget

class ForeignKey(UrlField):
    """
    Supports linking to the related object
    """
    widget = ForeignKeyWidget
    
    def __init__(self, model, choices=None, *args, **kwargs):
        """
        @param model: The model that forms the foreign key relationship
        @param choices: If True then a queryset is produced from model to create the choices. 
        """
        self.model = model
        if choices == True:
            kwargs['choices'] = [(obj.pk, '%s' % obj) for obj in model.objects.all()]
        elif choices:
            kwargs['choices'] = choices
        
        Field.__init__(self, *args, **kwargs)

class ManyManyField(UrlField):
    """
    Supports linking to the related object
    """
    widget = ManyManyWidget
    
    def __init__(self, model, choices=None, *args, **kwargs):
        """
        @param model: The model that forms the foreign key relationship
        @param choices: If True then a queryset is produced from model to create the choices. 
        """
        self.model = model
        if choices == True:
            kwargs['choices'] = [(obj.pk, '%s' % obj) for obj in model.objects.all()]
        elif choices:
            kwargs['choices'] = choices
        
        Field.__init__(self, *args, **kwargs)

class ManyManyLabelField(ManyManyField):
    widget = ManyManyLabelWidget
    
    def __init__(self, model, choices=None, label_class=None, data_tip_icon='icon-question-sign', *args, **kwargs):
        super(ManyManyLabelField, self).__init__(model, choices, *args, **kwargs)
        self.label_class = label_class
        self.data_tip_icon = data_tip_icon

class SelfField(ForeignKey):
    widget = SelfWidget
    
    def __init__(self, model, force_string=True, *args, **kwargs):
        """
        @param model: The model that forms the foreign key relationship
        @param force_string: If true (default) then object is converted to a string and this is used as the value.
        """
        self.force_string = force_string
        ForeignKey.__init__(self, model, *args, **kwargs)

class AnnotatedForeignKey(ForeignKey):
    widget = AnnotatedForeignKeyWidget
    
class CommaSeparatedField(Field):
    """
    Comma separate a iterator
    """
    widget = CommaSeparatedWidget

class CommaSeparatedEmailField(CommaSeparatedField):
    """
    Comma separate a iterator and treat each value as a email
    """
    widget = CommaSeparatedEmailWidget

class CommaSeparatedUrlField(CommaSeparatedField):
    """
    Comma separate a iterator and treat each value as a url
    """
    widget = CommaSeparatedUrlWidget

class CommaSeparatedForeignKey(ForeignKey):
    """
    Comma separate a iterator and treat each value as a url
    """
    widget = CommaSeparatedForeignKeyWidget

class ActionsField(Field):
    widget = ActionsWidget

    def __init__(self, *args, **kwargs):
        """
        @param model: The model that forms the foreign key relationship
        """
        Field.__init__(self, *args, **kwargs)
        self.sorting = False

class BaseFormField(Field):
    form = True

class FormsetField(BaseFormField):
    widget = FormsetWidget
    
    def __init__(self, delete=False, *args, **kwargs):
        """
        @param model: The model that forms the foreign key relationship
        """
        Field.__init__(self, hidden=True, sorting=False, filter=False, *args, **kwargs)
        self.delete = delete
    
class SelectField(BaseFormField):
    widget = SelectWidget
        
class ModelSelectField(BaseFormField):
    widget = ModelSelectWidget
    
class CheckboxField(BaseFormField):
    widget = CheckboxWidget
    
    def __init__(self, check_all=False, *args, **kwargs):
        """
        @param check_all: If True, the title for the column will be replaced with a checkbox.
        """
        Field.__init__(self, *args, **kwargs)
        self.check_all = check_all
    
class DateInputField(BaseFormField, DateField):
    widget = DateInputWidget
    
class TextInputField(BaseFormField):
    widget = TextInputWidget

class DynamicField(CharField):
    """
    A field that doesn't exist on the model but on the datatable object itself.
    """
    widget = DynamicFieldWidget

    def traverse_for_value(self, data, name=None):
        return None

    def get_qs_for_term(self, term, exact=False):
        """
        No filtering available if it's not an actual field in a table.
        """
        pass

class PhoneNumberField(Field):
    """
    A field that can be used with django-phonenumbers
    
    :see: https://github.com/stefanfoulis/django-phonenumber-field
    """
    widget = PhoneNumberWidget

    def __init__(self, as_format='as_international', *args, **kwargs):
        """
        @param as_format: Specifies the formatting to use for the number - ie.. as_e164, as_international, as_national or as_rfc3966.
        """
        Field.__init__(self, *args, **kwargs)
        self.as_format = as_format
        
class F(object):
    """
    An expression representing the value of the given field.
    """
    def __init__(self, name):
        self.name = name
