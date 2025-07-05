from .models import Lead, CallHistory
from retell import Retell
from django.conf import settings
from django.utils.timezone import now, timedelta
import zoneinfo 
from .api import RetellCallConcurrency


# Main scheduled job (locked to avoid overlaps)
def scheduled_call_job():
    # Step 1: Check concurrency limit
    if RetellCallConcurrency() >= 20:
        print("🚦 Concurrency limit reached. Skipping this cycle.")
        return

    # Step 2: Get current time in local timezone
    utc_now = now()

    # Step 3: Get due leads for first-time and retry calls
    due_new_leads = Lead.objects.filter(
        scheduled_time__lte=utc_now,
        call_status='NEW',
        call_retry__lt=2
    )[:20]

    retry_leads = Lead.objects.filter(
        call_status='CONTACTED',
        call_outcome__in=['dial_busy', 'dial_no_answer', 'dial_failed'],
        call_retry__lt=2,
        updated_at__lte=utc_now - timedelta(hours=2)
    )[:10]

    all_due_leads = list(due_new_leads) + list(retry_leads)

    if not all_due_leads:
        print("✅ No leads to call right now.")
        return

    print(f"📞 Found {len(all_due_leads)} leads to call.")

    for lead in all_due_leads:
        # Optional: check again before each call if concurrency is too high
        if RetellCallConcurrency() >= 20:
            print("⏹️ Reached concurrency limit during processing. Stopping.")
            break

        try:
            client = Retell(api_key=settings.RETELL_API_KEY)

            call_response = client.call.create_phone_call(
                override_agent_id=str(lead.agent_id),
                from_number=settings.RETELL_PHONE,
                to_number=str(lead.phone),
                retell_llm_dynamic_variables={"name": str(lead.lead_name)}
            )

            # Save call history
            CallHistory.objects.create(
                lead=lead,
                from_number=call_response.from_number or "",
                to_number=call_response.to_number or "",
                direction=call_response.direction or "outbound",
                call_id=call_response.call_id or "",
                agent_id=call_response.agent_id or "",
                call_status=call_response.call_status or "registered"
            )

            # Update lead
            lead.call_status = 'CONTACTED'
            lead.call_retry += 1
            lead.save()

            print(f"📲 Call made to {lead.phone} | Retry #{lead.call_retry}")

        except Exception as e:
            print(f"❌ Failed to call {lead.phone}: {e}")
            if lead.call_retry < 2:
                lead.call_retry += 1
                lead.scheduled_time = now() + timedelta(hours=2)
                lead.save()
                print(f"🔁 Scheduled retry for {lead.phone} | Retry #{lead.call_retry}")
