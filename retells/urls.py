from django.urls import path
from . import views

urlpatterns = [
    path('get-transcript/<int:lead_id>/', views.get_transcript, name='get_transcript'),
    path("agents/", views.agent_list_view, name="agent_list"),
    path("Update-agent/", views.update_agent, name="update_agent"),
]