from django.urls import path
from . import api

urlpatterns = [
    path('retell-call/', api.RetellCall, name='retell_call'),
    path('previous-lead/', api.previous_lead, name='previous_lead'),
    path('vapi-previous-lead/', api.vapi_previous_lead, name='vapi_previous_lead'),
    path('retell-webhook/', api.retell_webhook, name='retell_webhook'),
    path('voiceflow-webhook/', api.voiceflow_webhook, name='books_list'),
]
