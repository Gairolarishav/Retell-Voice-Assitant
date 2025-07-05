from django.shortcuts import render
from retell import Retell
import json
from rest_framework.decorators import api_view
from django.http import JsonResponse
from .models import Lead,CallHistory #,BatchCall
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings


Retell_Api_Key = settings.RETELL_API_KEY

# Entries listing
@api_view(['GET','POST'])
def RetellCall(request):
    try:
        # Parse request data
        if request.content_type == 'application/json':
            data = request.data
            
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()

        # Validate required fields
        if not name or not phone:
            return JsonResponse({
                'success': False,
                'error': 'Name and phone number are required'
            }, status=400)
        
        # Initialize Retell client
        client = Retell(api_key=Retell_Api_Key)
        
        # Create phone call
        if RetellCallConcurrency()<20:
            phone_call_response = client.call.create_phone_call(
                from_number=settings.RETELL_PHONE,
                to_number=phone,
                retell_llm_dynamic_variables={"name": f"{name}"}
            )
          
            return JsonResponse({
                'success': True,
                'message': f'Call initiated for {name}',
                'call_id': phone_call_response.call_id if phone_call_response else None,
                'call_status': phone_call_response.call_status if phone_call_response else None,
                'note': 'Call details will be updated via webhook when call completes'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': "please wait to concurrency limit reached"
            })
        
    except Exception as e:
        try:
            error_message = e.response.json().get('message', str(e))
        except Exception:
            error_message = str(e)
        print(f"Error creating phone call: {error_message}")
        return JsonResponse({
            'success': False,
            'error': error_message
        })
    

# Alternative: Create a webhook handler to update call details after completion
from django.views.decorators.http import require_http_methods
@csrf_exempt
@require_http_methods(["POST"])
def retell_webhook(request):
    print('🔥 Webhook triggered!')
    try:     
        # Check if body is empty
        if not request.body:
            return JsonResponse({'error': 'Empty body'}, status=400)
        

        data = json.loads(request.body)
        print('data=====', data)
        call_data = data.get('call', {})
        call_id = call_data.get('call_id')
        event_type = data.get('event')

        if not call_id or not event_type:
            return JsonResponse({'error': 'Missing call_id or event'}, status=400)
        
        if event_type == 'call_started':
            return handle_call_started(call_data)
        elif event_type == 'call_ended':
            return handle_call_ended(call_data)
        elif event_type == 'call_analyzed':
            return handle_call_analyzed(call_data)
        else:
            print(f"Ignored call with unknown event: {event_type}")
            return JsonResponse({'status': f'ignored - unknown event ({event_type})'})
            

    except Exception as e:
        print(f'Webhook error: {str(e)}')
        return JsonResponse({'error': 'Internal server error'}, status=500)

# ✅ Create on call_started
def handle_call_started(call_data):
    call_id = call_data.get('call_id')
    
    if CallHistory.objects.filter(call_id=call_id).exists():
        callhis = CallHistory.objects.get(call_id=call_id)
        callhis.call_status = call_data.get('call_status', '')
        callhis.save()
        print(f"Call already started: {call_id}")

    print(f"Created call history for started call: {call_id}")
    return JsonResponse({'status': 'created'})

# ✅ Update on call_ended
def handle_call_ended(call_data):
    return update_call_history(call_data, include_analysis=False)

# ✅ Update & finalize on call_analyzed
def handle_call_analyzed(call_data):
    return update_call_history(call_data, include_analysis=True)


# 🔁 Common update logic
def update_call_history(call_data, include_analysis=False):
    call_id = call_data.get('call_id')
    to_number = call_data.get('to_number')
    call_analysis = call_data.get('call_analysis', {})
    custom_analysis_data = call_analysis.get('custom_analysis_data', {})
    
    lead = Lead.objects.get(phone=to_number)

    try:
        if CallHistory.objects.filter(call_id=call_id).exists():
            call = CallHistory.objects.get(call_id=call_id)

            call.call_status = call_data.get('call_status', call.call_status)
            call.disconnection_reason = call_data.get('disconnection_reason', call.disconnection_reason)
            call.recording_url = call_data.get('recording_url', call.recording_url)
            call.transcript = call_data.get('transcript', call.transcript)
            call.duration = call_data.get('duration_ms', call.duration)

            if include_analysis:
                call.call_successful = str(call_analysis.get('call_successful', call.call_successful))
                call.user_sentiment = str(call_analysis.get('user_sentiment', call.user_sentiment))

            if custom_analysis_data:
                # Separate rating from outcome tags
                outcome_json = {}
                rating = None
                for key, value in custom_analysis_data.items():
                    if key.lower() == "_rating":
                        try:
                            rating = int(value)
                        except ValueError:
                            rating = None
                    else:
                        outcome_json[key] = value

                call.call_rating = rating
                call.outcome_tag = outcome_json  # This will store a dictionary like {"name": "Yes", "Interested": "yES"}
                
                
                lead.outcome_tag = outcome_json
                lead.call_rating = rating

            call.save()
            print(f"Updated call history for event: call_id: {call_id}")
            lead.call_outcome = call_data.get('disconnection_reason')
            lead.save()

            return JsonResponse({'status': 'updated'})
        
        else:
            print("CallHistory not found")
            return JsonResponse({'error': 'CallHistory not found'}, status=404)

        
    

    except CallHistory.DoesNotExist:
        return JsonResponse({'error': 'CallHistory not found'}, status=404)
    except Exception as e:
        print(f"Update failed for {call_id}: {str(e)}")
        return JsonResponse({'error': 'Update failed'}, status=500)


@api_view(['GET','POST'])
def previous_lead(request):
    # Get second latest lead
    leads = Lead.objects.order_by('-created_at')[:2]
    
    if len(leads) < 2:
        return JsonResponse({"error": "Not enough leads found"}, status=404)

    lead = leads[1]  # second latest lead

    return JsonResponse({
        "previous_lead_name": lead.lead_name,
        "previous_lead_phone_no": str(lead.phone)
    })

@api_view(['POST'])
def vapi_previous_lead(request):
    try:
        tool_calls = request.data.get("message", {}).get("toolCalls", [])
        if not tool_calls:
            return JsonResponse({"error": "No toolCalls found"}, status=400)

        tool_call_id = tool_calls[0].get("id")

        # Get second latest lead
        leads = Lead.objects.order_by('-created_at')[:2]
        if len(leads) < 2:
            return JsonResponse({"error": "Not enough leads found"}, status=404)

        lead = leads[1]

        return JsonResponse({
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": {
                        "previous_lead_name": lead.lead_name,
                        "previous_lead_phone_no": str(lead.phone)
                    }
                }
            ]
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def RetellCallConcurrency():
    client = Retell(
        api_key=Retell_Api_Key,
    )
    try:
        concurrency = client.concurrency.retrieve()
        return concurrency.current_concurrency
    except Exception as e:
        print("Error fetching concurrency:", e)
        return 0
    

@api_view(['POST'])
def voiceflow_webhook(request):
    # Incoming JSON body
    data = request.data

    # Example: log it
    print("voiceflow======", data)

    # # Access fields
    # message = data.get('message')
    # user_id = data.get('userId')

    # Do something...
    return JsonResponse({'status': 'received'})
    
    