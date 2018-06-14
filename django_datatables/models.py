from django.db import models
from django_toolkit.db.models import QuerySetManager
from django.db.models.query import QuerySet
from django.conf import settings

class DatatableState(models.Model):
    """Storage of Datatables state."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='datatable_states')
    report = models.CharField(max_length=191, db_index=True)
    uri = models.CharField(max_length=191)
    json = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = QuerySetManager()

    class Meta:
        index_together = [
            ["user", "uri"],
        ]

    def __unicode__(self):
        return '%s' % (self.uri)

    class QuerySet(QuerySet):
        def uri(self, uri):
            return self.filter(uri=uri)
        def user(self, user):
            return self.filter(user=user)
        def report(self, report):
            return self.filter(report=report)
