from django.urls import path, include
from .views import add_faqs,upload_faqs_to_voiceflow,FAQViewSet,save_chat,chatbot,get_transcript,available_sessions,custom_llm,AI_Assistant_knowledgebase
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'faqs', FAQViewSet, basename='faq')

urlpatterns = [
    path('save-chat/', save_chat, name='save-chat'),
    path('add-faqs/', add_faqs, name='add_faqs'),
    path('upload-faqs/', upload_faqs_to_voiceflow, name='upload_faqs_to_voiceflow'),
    path('', include(router.urls)),  # All endpoints under /AI-Assistant/
    path('transcript/', get_transcript, name='save-chat'),
    path('available-sessions/',available_sessions),
    path('chatbot/', chatbot, name='chatbot'),
    path('custom-llm/', custom_llm, name='custom_llm'),
    path("knowledgebase/",AI_Assistant_knowledgebase, name="knowledgebase"),
]