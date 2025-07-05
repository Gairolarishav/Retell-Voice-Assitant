from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.timezone import now, timedelta
import zoneinfo

from retell import Retell
from retells.models import Lead, CallHistory
from retells.api import RetellCallConcurrency


class Command(BaseCommand):
    help = 'Call scheduled and retry leads using Retell API'

    def handle(self, *args, **kwargs):
        self.stdout.write(f"📞 Running scheduled call job at {now()}...")

        if RetellCallConcurrency() >= 20:
            self.stdout.write("🚦 Concurrency limit reached. Skipping.")
            return

        utc_now = now()

        due_new_leads = Lead.objects.filter(
            scheduled_time__lte=utc_now,
            call_status='NEW',
            call_retry__lt=2
        )[:20]

        retry_leads = Lead.objects.filter(
            call_status='CONTACTED',
            call_outcome__in=['dial_busy', 'dial_no_answer'],
            call_retry__lt=2,
            updated_at__lte=utc_now - timedelta(hours=2)
        )[:10]

        all_due_leads = list(due_new_leads) + list(retry_leads)

        if not all_due_leads:
            self.stdout.write("✅ No leads to call.")
            return

        self.stdout.write(f"📞 Found {len(all_due_leads)} leads to call.")

        for lead in all_due_leads:
            if RetellCallConcurrency() >= 20:
                self.stdout.write("⏹️ Concurrency maxed out. Stopping.")
                break

            try:
                client = Retell(api_key=settings.RETELL_API_KEY)

                call_response = client.call.create_phone_call(
                    override_agent_id=str(lead.agent_id),
                    from_number=settings.RETELL_PHONE,
                    to_number=str(lead.phone),
                    retell_llm_dynamic_variables={"name": str(lead.lead_name)}
                )

                CallHistory.objects.create(
                    lead=lead,
                    from_number=call_response.from_number or "",
                    to_number=call_response.to_number or "",
                    direction=call_response.direction or "outbound",
                    call_id=call_response.call_id or "",
                    agent_id=call_response.agent_id or "",
                    call_status=call_response.call_status or "registered"
                )

                lead.call_status = 'CONTACTED'
                # Only increment retry if this is a retry case (busy or no answer)
                if lead.call_outcome in ['dial_busy', 'dial_no_answer']:
                    lead.call_retry += 1
                lead.save()

                self.stdout.write(f"📲 Called {lead.phone} | Retry #{lead.call_retry}")

            except Exception as e:
                self.stdout.write(f"❌ Failed to call {lead.phone}: {e}")
                if lead.call_retry < 2:
                    lead.call_retry += 1
                    lead.scheduled_time = now() + timedelta(hours=2)
                    lead.save()
                    self.stdout.write(f"🔁 Retry scheduled for {lead.phone} | Retry #{lead.call_retry}")
