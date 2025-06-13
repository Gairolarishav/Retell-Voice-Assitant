from django.urls import path
from . import api

urlpatterns = [
    # path('jet/', include('jet.urls', 'jet')),  # Django JET URLS
    # path('grappelli/', include('grappelli.urls')), # grappelli URLS
    path('retell-call/', api.RetellCall, name='retell_call'),
    path('previous-lead/', api.previous_lead, name='previous_lead'),
    path('retell-webhook/', api.retell_webhook, name='retell_webhook'),
]
