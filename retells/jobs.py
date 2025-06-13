from .models import Lead, CallHistory
from retell import Retell
from django.conf import settings
from django.utils.timezone import now
from django.utils.timezone import now, timedelta
import zoneinfo 

def scheduled_call_job():
    # Get current UTC time
    utc_now = now()
    print(f"UTC now: {utc_now}")
    
    # Correct way to get local timezone from settings
    local_tz_name = getattr(settings, 'TIME_ZONE', 'UTC')
    local_timezone = zoneinfo.ZoneInfo(local_tz_name)

    # Convert UTC to local time
    current_time = utc_now.astimezone(local_timezone)

    # 1. New leads scheduled for the first call
    due_new_leads = Lead.objects.filter(
        scheduled_time__lte=current_time,
        call_status='NEW',
        call_retry__lt=2  # ensure only retry up to 2 times
    )[:20]

    # 2. Leads to retry (busy or no answer)
    retry_leads = Lead.objects.filter(
        call_status='CONTACTED',
        call_outcome__in=['dial_busy', 'dial_no_answer','dial_failed'],
        call_retry__lt=2,  # retry max 2 times
        updated_at__lte=current_time - timedelta(hours=2)
    )[:10]

    print('current_time - timedelta(hours=2) ===', current_time - timedelta(hours=2))

    # Combine both lead types
    all_due_leads = list(due_new_leads) + list(retry_leads)

    if not all_due_leads:
        print("✅ No leads due for call or retry.")
        return

    for lead in all_due_leads:
        try:
            client = Retell(api_key=settings.RETELL_API_KEY)

            call_response = client.call.create_phone_call(
                override_agent_id=str(lead.agent_id),
                from_number="+16362491522",
                to_number=str(lead.phone),
                retell_llm_dynamic_variables={"name": str(lead.lead_name)}
            )

            # Log the call
            CallHistory.objects.create(
                lead=lead,
                from_number=call_response.from_number or "",
                to_number=call_response.to_number or "",
                direction=call_response.direction or "outbound",
                call_id=call_response.call_id or "",
                agent_id=call_response.agent_id or "",
                call_status=call_response.call_status or "registered"
            )

            # Update lead status and retry count
            lead.call_status = 'CONTACTED'
            lead.call_retry += 1
            lead.save()

            print(f"📞 Call initiated to {lead.phone} | Retry: {lead.call_retry}")

        except Exception as e:
            print(f"❌ Error calling {lead.phone}: {e}")
            # On failure, mark for retry (if eligible)
            if lead.call_retry < 2:
                lead.call_status = 'RETRY'
                lead.call_retry += 1
                lead.scheduled_time = now() + timedelta(hours=2)
                lead.save()
                print(f"⏳ Retry scheduled for {lead.phone} in 2 hours. Retry count: {lead.call_retry}")
