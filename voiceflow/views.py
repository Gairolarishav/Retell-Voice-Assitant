from django.shortcuts import render
from django.conf import settings
from django.contrib import admin

# Create your views here.
# @admin.site.admin_view
def custom_llm(request):
    return render(request,'voiceflow/custom_llm.html')

# @admin.site.admin_view
def voiceflow_knowledgebase(request):
    return render(request,'voiceflow/knowledgebase.html')


