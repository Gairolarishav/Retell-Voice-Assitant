from django.urls import path
from .views import SaveChatView,chatbot,get_transcript,available_sessions,custom_llm,AI_Assistant_knowledgebase

urlpatterns = [
    path('save-chat/', SaveChatView.as_view(), name='save-chat'),
    path('transcript/', get_transcript, name='save-chat'),
    path('available-sessions/',available_sessions),
    path('chatbot/', chatbot, name='chatbot'),
    path('custom-llm/', custom_llm, name='custom_llm'),
    path("knowledgebase/",AI_Assistant_knowledgebase, name="knowledgebase"),
]