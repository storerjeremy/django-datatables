from django.conf.urls import url, patterns
from django_datatables.views import GetDatatableStateView

urlpatterns = patterns('',
    # Datatables state
    url(r'^state/get/$', 
        view=GetDatatableStateView.as_view(),
        name="django_datatables_state_get", 
    ),
)