from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from .models import Lead, CallHistory
from django.shortcuts import render
from retell import Retell
from django.conf import settings
from django.contrib import admin
from django.template.response import TemplateResponse

from django.views.decorators.csrf import csrf_exempt

Retell_Api_Key = settings.RETELL_API_KEY
@staff_member_required
def get_transcript(request, lead_id):
    history = CallHistory.objects.filter(lead__id=lead_id).order_by('-id').first()

    if history and history.transcript:
        return JsonResponse({'transcript': history.transcript})
    else:
        return JsonResponse({'transcript': 'Transcript not available'})


from collections import defaultdict


@admin.site.admin_view
@csrf_exempt
def agent_list_view(request):
    client = Retell(api_key=Retell_Api_Key)

    try:
        agent_responses = client.agent.list()
    except Exception as e:
        print("Error fetching agents:", e)
        agent_responses = []

    agents_by_id = defaultdict(list)
    for agent in agent_responses:
        agents_by_id[agent.agent_id].append(agent)

    latest_agents = []
    for agent_id, versions in agents_by_id.items():
        latest_version = max(versions, key=lambda a: a.version)
        latest_agents.append(latest_version)

    context = dict(
        admin.site.each_context(request),
        agents=latest_agents,
        title="Agent List (Latest Version)"
    )
    return TemplateResponse(request, "admin/agents_list.html", context)

def update_agent(request):
    if request.method == "POST":
        agent_id = request.POST.get("agent_id")
        new_language = request.POST.get("language")
        print("====new_language", new_language)
        print("====agent_id", agent_id)

        try:
            client = Retell(api_key=Retell_Api_Key)
            client.agent.update(agent_id=agent_id, language=new_language)


            return JsonResponse({"success": True, "message": "Language updated."})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return JsonResponse({"success": False, "message": "Invalid request"})


