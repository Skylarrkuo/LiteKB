from django.urls import path

from .run_views import AdminRuns

urlpatterns = [
    path("litekb/runs", AdminRuns.as_view()),
    path("litekb/runs/<uuid:run_id>", AdminRuns.as_view()),
]
