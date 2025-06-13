from django.contrib import admin
from .models import Lead,CallHistory
from django.utils.html import format_html
from django import forms
from django.conf import settings
from retell import Retell
from django.utils import timezone

class LeadForm(forms.ModelForm):
    call_now = forms.BooleanField(required=False, label="Call Now")
    agent_id = forms.ChoiceField(label="Select Agent", choices=[], required=True)
    scheduled_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label="Scheduled Time"
    )

    class Meta:
        model = Lead
        exclude = ['agent_name','call_outcome','call_status','outcome_tag','call_rating']
        widgets = {
            'phone': forms.TextInput(attrs={'placeholder': '+919876543210'}),
        }
        

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            client = Retell(api_key=settings.RETELL_API_KEY)
            agents = client.agent.list()

            agent_map = {}
            for agent in agents:
                if (agent.agent_id not in agent_map) or (agent.version > agent_map[agent.agent_id].version):
                    agent_map[agent.agent_id] = agent

            agent_choices = [('', '-- Select an Agent --')]
            agent_choices.extend([
                (a.agent_id, f"{a.agent_name} (v{a.version}) [{a.language}]") 
                for a in agent_map.values()
            ])
            self.fields['agent_id'].choices = agent_choices
        except Exception as e:
            self.fields['agent_id'].choices = [('', '-- Select an Agent --')]
            self.fields['agent_id'].help_text = f"❌ Failed to load agents: {e}"

    def clean(self):
        cleaned_data = super().clean()
        call_now = cleaned_data.get("call_now")
        scheduled_time = cleaned_data.get("scheduled_time")

        from .api import RetellCallConcurrency  # or wherever you defined it

        if call_now and RetellCallConcurrency() >= 20:
            raise forms.ValidationError("⚠️ Concurrency limit reached. Please wait until ongoing calls complete.")

        if call_now and scheduled_time:
            raise forms.ValidationError("You cannot select both 'Call Now' and a 'Scheduled Time'. Please choose one.")

        if not call_now and not scheduled_time:
            raise forms.ValidationError("Please select either 'Call Now' or set a 'Scheduled Time'.")

        if scheduled_time and scheduled_time < timezone.now():
            raise forms.ValidationError("Scheduled time cannot be in the past.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        selected_agent_id = self.cleaned_data.get("agent_id")

        if isinstance(selected_agent_id, list):
            selected_agent_id = selected_agent_id[0]

        instance.agent_id = selected_agent_id

        # Set agent_name for display
        try:
            client = Retell(api_key=settings.RETELL_API_KEY)
            agent = next((a for a in client.agent.list() if a.agent_id == selected_agent_id), None)
            instance.agent_name = agent.agent_name if agent else "Unknown"
        except Exception:
            instance.agent_name = "Unknown"

        if commit:
            instance.save()

        return instance

    
    
@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    form = LeadForm
    change_form_template = "admin/retells/lead/change_form.html"
    # change_list_template = "admin/retells/lead/change_list.html"

    list_display = [
        'lead_name_display', 'phone_display', 'call_status_display', 'call_outcome_display',
        'duration_display', 'view_transcript_display', 'agent_name_display',
        'scheduled_time_display', 'outcome_tag_display', 'call_rating_display'
    ]
    list_filter = ['call_outcome', 'created_at','agent_name']
    search_fields = ['lead_name', 'phone']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        call_now = form.cleaned_data.get("call_now")
        if call_now:
            try:
                client = Retell(api_key=settings.RETELL_API_KEY)
                # Create phone call
                call_response = client.call.create_phone_call(
                    override_agent_id = str(obj.agent_id),
                    from_number="+16362491522",
                    to_number=str(obj.phone),
                    retell_llm_dynamic_variables={"name": f"{str(obj.lead_name)}"}
                )
                obj.call_status = 'CONTACTED'
                
                call_history = CallHistory.objects.create(
                    lead=obj,
                    from_number=call_response.from_number or "",
                    to_number=call_response.to_number or "",
                    direction=call_response.direction or "outbound",
                    call_id=call_response.call_id or "",
                    agent_id=call_response.agent_id or "",
                    call_status=call_response.call_status or "registered",
                    call_successful="",  # Will be updated via webhook
                    disconnection_reason="",  # Will be updated via webhook
                    user_sentiment="",  # Will be updated via webhook
                    transcript="",  # Will be updated via webhook
                    recording_url=""
                )
                
                print(f"Call initiated: {call_history.call_id}")
            except Exception as e:
                print(f"❌ Error creating call: {e}")
                obj.call_status = 'UNREACHABLE'
                raise forms.ValidationError(f"Failed to create call: {str(e)}")
            obj.save()

    def lead_name_display(self, obj):
        return obj.lead_name or "-"
    lead_name_display.short_description = 'Lead Name'

    def phone_display(self, obj): return obj.phone or "-"
    phone_display.short_description = 'Phone'

    def call_status_display(self, obj):
        return obj.get_call_status_display()
    call_status_display.short_description = 'Call Status'

    def call_outcome_display(self, obj): return obj.call_outcome or "-"
    call_outcome_display.short_description = 'Call Outcome'

    def agent_name_display(self, obj): return obj.agent_name or "-"
    agent_name_display.short_description = 'Agent Name'

    def scheduled_time_display(self, obj):
        if obj.call_now:
            return "Instant"
        return obj.scheduled_time.strftime('%Y-%m-%d %H:%M') if obj.scheduled_time else "-"
    scheduled_time_display.short_description = 'Scheduled'

    def outcome_tag_display(self, obj): return obj.outcome_tag or "-"
    outcome_tag_display.short_description = 'Outcome Tag'

    def call_rating_display(self, obj): return obj.call_rating or "-"
    call_rating_display.short_description = 'Call Rating'


    def duration_display(self, obj):
        latest_call = CallHistory.objects.filter(lead=obj).order_by('-created_at').first()
        if latest_call and latest_call.duration:
            minutes = latest_call.duration // 60
            seconds = latest_call.duration % 60
            return f"{minutes}m {seconds}s"
        return "-"
    duration_display.short_description = 'Duration'

    def view_transcript_display(self, obj):
        return format_html(

            '<a href="javascript:void(0);" class="btn btn-sm btn-primary" onclick="openTranscriptModal({})">View</a>',
            obj.id
        )
    view_transcript_display.short_description = 'Transcript'



@admin.register(CallHistory)
class CallHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'id','lead', 'from_number', 'to_number', 'direction', 'call_status', 'call_id',
        'agent_id', 'call_successful', 'disconnection_reason', 'user_sentiment',
        'short_transcript', 'recording_link' ,'duration_display','outcome_tag','call_rating','created_at'
    ]
    list_filter = ['call_status', 'call_successful','created_at'] #,'batch_call'
    search_fields = ['lead__name', 'lead__phone_number', 'call_id'] #, 'batch_call__name',
    readonly_fields = ['from_number', 'to_number', 'direction', 'call_status', 'call_id',
        'agent_id', 'call_successful', 'disconnection_reason', 'user_sentiment',
        'transcript', 'recording_url','duration','outcome_tag','call_rating'
    ]#,'batch_call'

    fieldsets = (
        ('Call Information', {
            'fields': ('lead', 'call_id', 'agent_id', 'call_status', 'call_successful',
                       'disconnection_reason', 'from_number', 'to_number', 'direction','duration') #,'batch_call'
        }),
        ('Content', {
            'fields': ('transcript', 'recording_url')
        }),
        ('Analysis', {
            'fields': ('user_sentiment','outcome_tag','call_rating')
        })
    )

    def duration_display(self, obj):
        if obj.duration:
            minutes = obj.duration // 60
            seconds = obj.duration % 60
            return f"{minutes}m {seconds}s"
        return "-"
    duration_display.short_description = 'Duration'

    def short_transcript(self, obj):
        if obj.transcript:
            return obj.transcript[:40] + '...' if len(obj.transcript) > 40 else obj.transcript
        return "-"
    short_transcript.short_description = "Transcript"

    def recording_link(self, obj):
        if obj.recording_url:
            return format_html('<a href="{}" target="_blank">Play</a>', obj.recording_url)
        return "-"
    recording_link.short_description = "Recording"



