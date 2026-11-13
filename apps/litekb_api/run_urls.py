from django.urls import path

from .run_views import AgentRuns, Agents, CancelRun, ResumeRun, RunDetail, RunEvents

urlpatterns = [
    path("agents", Agents.as_view()),
    path("agents/<uuid:agent_id>/runs", AgentRuns.as_view()),
    path("runs/<uuid:run_id>", RunDetail.as_view()),
    path("runs/<uuid:run_id>/events", RunEvents.as_view()),
    path("runs/<uuid:run_id>/cancel", CancelRun.as_view()),
    path("runs/<uuid:run_id>/resume", ResumeRun.as_view()),
]
