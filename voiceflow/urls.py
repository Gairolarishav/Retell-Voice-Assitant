from django.urls import path
from . import views

urlpatterns = [
    path('custom-llm/', views.custom_llm, name='custom_llm'),
    path("voiceflow-knowledgebase/", views.voiceflow_knowledgebase, name="agent_list"),
]