import os
import cStringIO
import logging
from django.shortcuts import Http404
from datetime import datetime
from django.views.generic.base import TemplateView
from django_datatables_view.base_datatable_view import BaseDatatableView
from django_datatables import load_report_class, HtmlWriter, JsonWriter
from django.utils.text import slugify
from django_toolkit.views import AjaxMixin, FileDownloadView
from django_datatables.helper import report_json_context_helper
from django.conf import settings
from django_datatables.forms import DatatableStateSetForm
from django_datatables.models import DatatableState
from django.utils.translation import ugettext as _
from django.views.generic.detail import DetailView
from django.http.response import HttpResponse

logger = logging.getLogger(__name__)

class DatatableView(BaseDatatableView, AjaxMixin, FileDownloadView):
    template_name = "django_datatables/detail.html"
    report = None
    report_app = None
    report_name = None
    xsend = False
    
    def initialize(self, **kwargs):
        if not self.report:
            if kwargs.has_key('app'):
                self.report_app = kwargs['app']
            if kwargs.has_key('report_name'):
                self.report_name = kwargs['report_name']
                
            self.report = load_report_class(self.report_app, self.report_name)
            
            if not self.report:
                raise Http404('Report %s.%s does not exist.' % (self.report_app, self.report_name))
    
            if not self.report.supports_writer(HtmlWriter):
                raise Http404('Report %s does not support HTML output.' % (self.report.__class__.__module__))

    def get(self, request, *args, **kwargs):
        self.initialize(**kwargs)
        self.report.set_request(request)
        if self.is_ajax() or self.accepts_json():
            self.save_state(request)
            return BaseDatatableView.get(self, request, *args, **kwargs)
        if self.request.GET.get('csv', False) != False:
            return self.csv(request, *args, **kwargs)
        return TemplateView.get(self, request, *args, **kwargs)

    def ordering(self, qs):
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.GET.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0
        
        if i_sorting_cols != 0:
            return BaseDatatableView.ordering(self, qs)
        elif hasattr(self.report._meta, 'sorting'):
            order = self.report._meta.sorting
            return qs.order_by(*order)
        else:
            return qs
        
    def save_state(self, request):
        """Save the state (ie.. ordering, searched fields etc..) of the datatable."""
        if 'state_uri' in request.GET:
            data = {'uri': request.GET['state_uri'],
                    'report': '%s.%s' % (self.report.__module__, self.report.__class__.__name__),
                    'json': request.GET['state_json']}
            form = DatatableStateSetForm(request, data=data)
            if form.is_valid():
                form.save()

    def csv(self, request, *args, **kwargs):
        """
        Send csv download to client.
        """
        from django_datatables.writers.csv_writers import UnicodeCsvWriter
        self.initialize(*args, **kwargs)
        qs = self.get_initial_queryset(*args, **kwargs)
        qs = self.filter_queryset(qs)
        self.csv_handle = cStringIO.StringIO()
        writer = UnicodeCsvWriter(self.report, qs)
        writer.write(self.csv_handle)
        self.csv_handle.reset()
        return FileDownloadView.render_to_response(self, {})
    
    def filename(self):
        return '%s-%s.csv' % (slugify(u'%s' % self.report.__module__.replace('.', '-')), datetime.now().strftime('%Y%m%d%H%M%S'))

    def openfile(self):
        return self.csv_handle
    
    def filesize(self):
        self.csv_handle.seek(0, os.SEEK_END)
        size = self.csv_handle.tell()
        self.csv_handle.reset()
        return size
    
    def content_type(self):
        return 'text/csv'

    def render_to_response(self, context):
        """ Returns a JSON response containing 'context' as payload
        """
        if self.is_ajax() or self.accepts_json():
            return BaseDatatableView.render_to_response(self, context)
        return TemplateView.render_to_response(self, context)

    def get_source_url(self):
        return self.request.path

    def has_aggregates(self):
        for field in self.report.fields():
            if field.aggregate:
                return True
        return False

    def get_aggregates(self, **kwargs):
        aggregate_kwargs = {}
        for field in self.report.fields():
            if field.aggregate:
                aggregate_kwargs[field.name] = field.aggregate
        
        if aggregate_kwargs:
            qs = self.filter_queryset(self.get_initial_queryset(**kwargs)).aggregate(**aggregate_kwargs)
            aggregates = []
            for field in self.report.fields():
                if field.aggregate:
                    aggregates.append(field.__class__().to_python(qs[field.name]))
                else:
                    aggregates.append(None)
            return aggregates

    def get_context_data(self, **kwargs):
        self.initialize(**kwargs)
        if self.is_ajax() or self.accepts_json():
            # Return the data via ajax, rather than the table itself.
            context = BaseDatatableView.get_context_data(self, **kwargs)
            if self.has_aggregates():
                context['aggregates'] = self.get_aggregates(**kwargs) 
            return context
        context = super(TemplateView, self).get_context_data(**kwargs)
        context.update(report_json_context_helper(self.report, 
                                                  self.get_source_url(), 
                                                  self.get_create_url(), 
                                                  self.get_submit_url(),
                                                  self.get_table_id_prepend(),
                                                  self.get_tabletools()))
        return context

    def get_create_url(self):
        return None
    
    def get_submit_url(self):
        return None
    
    def get_table_id_prepend(self):
        return ''
    
    def get_tabletools(self):
        return None

    @property
    def order_columns(self):
        return [field.sorting_with for field in self.report.fields()]

    def get_initial_queryset(self, *args, **kwargs):
        # return queryset used as base for futher sorting/filtering
        # these are simply objects displayed in datatable
        return self.report.queryset()

    def filter_queryset(self, qs):
        """
        Filter the queryset using parameters available in the request.
        """
        # First process the all fields search
        sSearch = self.request.GET.get('sSearch', None)
        
        qs_params = self.report.get_qs_for_term(sSearch)

        if qs_params:
            qs = qs.filter(qs_params)

        # Now process the column search for each column
        sColumns = self.request.GET.get('sColumns', None)
        if sColumns:
            sColumns = sColumns.split(',')
            for i, field_name in enumerate(sColumns):
                term = self.request.GET.get('sSearch_%s' % i, None)
                if term:
                    qs_params = self.report.field(field_name).get_qs_for_term(term, True)
                    if qs_params:
                        qs = qs.filter(qs_params)
        
        return qs

    def prepare_results(self, qs):
        # prepare list with output column data
        # queryset is already paginated here
        if settings.DEBUG:
            logger.debug(qs.query)
        return JsonWriter(self.report).as_json(qs)


class GetDatatableStateView(DetailView):
    model = DatatableState
    template_name = 'django_datatables/state-get.html'
    content_type = 'application/json'

    def get(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated():
            # If the user is not authenticaed, we can't save state for them, so just return.
            return HttpResponse()
        else:
            return super(GetDatatableStateView, self).get(request=request)

    def get_object(self, queryset=None):
        """
        Returns the object the view is displaying.

        By default this requires `self.queryset` and a `pk` or `slug` argument
        in the URLconf, but subclasses can override this to return any object.
        """
        
        # Use a custom queryset if provided; this is required for subclasses
        # like DateDetailView
        if queryset is None:
            queryset = self.get_queryset()
            
        queryset = queryset.filter(user=self.request.user, uri=self.request.GET.get('uri'))

        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except DatatableState.DoesNotExist:
            raise Http404(_("No %(verbose_name)s found matching the query") %
                          {'verbose_name': queryset.model._meta.verbose_name})
        return obj
    
    
