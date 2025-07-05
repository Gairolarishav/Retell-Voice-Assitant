from django.contrib import admin
from .models import Lead,CallHistory
from django.utils.html import format_html
from django import forms
from django.conf import settings
from retell import Retell
from django.utils import timezone
import pytz
from datetime import timedelta
from django.db.models import Count, Avg, Q, Sum
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin

class MyAdminSite(admin.AdminSite):

    def index(self, request, extra_context=None):
        # Add your custom data here
        # Initialize extra_context
        extra_context = extra_context or {}

        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Basic Stats
        total_leads = Lead.objects.count()
        total_calls_today = CallHistory.objects.filter(created_at__date=today).count()
        
        # Success rate calculation
        successful_calls = CallHistory.objects.filter(
            call_successful='True',
            created_at__date=today
        ).count()

        success_rate = (successful_calls / total_calls_today * 100) if total_calls_today > 0 else 0
        
        # Average call duration (in minutes)
        avg_duration = CallHistory.objects.aggregate(
            avg_duration=Avg('duration')
        )['avg_duration'] or 0
        avg_duration_minutes = round(avg_duration / 60, 1) if avg_duration else 0
        
        # Weekly comparison
        calls_this_week = CallHistory.objects.filter(created_at__date__gte=week_ago).count()
        calls_last_week = CallHistory.objects.filter(
            created_at__date__gte=week_ago - timedelta(days=7),
            created_at__date__lt=week_ago
        ).count()
        
        weekly_growth = 0
        if calls_last_week > 0:
            weekly_growth = round(((calls_this_week - calls_last_week) / calls_last_week) * 100, 1)
        
        # Main metrics for the metric cards
        extra_context.update({
            'total_leads': total_leads,
            'total_calls_today': total_calls_today,
            'weekly_growth': weekly_growth,  # positive growth
            'success_rate': success_rate,
            'avg_duration_minutes': avg_duration_minutes,
        })

        # Agent performance
        agent_performance = CallHistory.objects.values('agent_id').annotate(
            total_calls=Count('id'),
            successful_calls=Count('id', filter=Q(call_successful='True'))
        ).order_by('-successful_calls')[:5]
        
        # Agent performance data
        client = Retell(api_key=settings.RETELL_API_KEY)
        agents = client.agent.list()

        # Step 1: Get latest version of each agent
        agent_map = {}
        for agent in agents:
            if (agent.agent_id not in agent_map) or (agent.version > agent_map[agent.agent_id].version):
                agent_map[agent.agent_id] = agent

        # Step 2: Prepare the performance list
        agent_perf_list = []
        for entry in agent_performance:
            agent_id = entry['agent_id']
            info = agent_map.get(agent_id)

            agent_perf_list.append({
                "agent_id": agent_id,
                "agent_name": getattr(info, "agent_name", "Unknown"),
                "total_calls": entry['total_calls'],
                "successful_calls": entry['successful_calls']
            })

        # Step 3: Add to context
        extra_context['agent_performance'] = agent_perf_list

        # Daily call volume for chart (last 7 days)
        extra_context['daily_calls'] = []
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            count = CallHistory.objects.filter(created_at__date=date).count()
            extra_context['daily_calls'].append({
                'date': date.strftime('%m/%d'),
                'count': count
            })
        
        # Call outcomes distribution for pie chart
        # Call outcome distribution
        call_outcomes = CallHistory.objects.values('disconnection_reason').annotate(
            count=Count('id')
        ).order_by('-count')
        extra_context['call_outcomes'] = call_outcomes
        
        # Sample lead names and phone numbers
        # Recent call history
        recent_calls = CallHistory.objects.select_related('lead').order_by('-created_at')[:5]
        
        extra_context['recent_calls'] = recent_calls

        return super().index(request, extra_context)

# Register your admin site
custom_admin_site = MyAdminSite(name='myadmin')
custom_admin_site.register(User, UserAdmin)
custom_admin_site.register(Group, GroupAdmin)

class LeadForm(forms.ModelForm):
    call_now = forms.BooleanField(required=False, label="Call Now",help_text="Check this to initiate the call immediately.")
    agent_id = forms.ChoiceField(label="Select Agent", choices=[], required=True)
     # Add timezone field - will be auto-detected from browser
    timezone_field = forms.CharField(
        widget=forms.HiddenInput(),
        initial='UTC',
        required=True
    )
    scheduled_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label="Scheduled Time",
        help_text="Enter the time in your local timezone. It will be automatically converted to UTC after submission."

    )

    class Meta:
        model = Lead
        exclude = ['agent_name','call_outcome','call_status','outcome_tag','call_rating','call_retry']
        widgets = {
            'phone': forms.TextInput(attrs={'placeholder': '+919876543210'}),
        }
        

    def __init__(self, *args, **kwargs):
        # Extract user timezone from request if available
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

         # Convert UTC time back to local time for editing
        if self.instance and self.instance.pk and self.instance.scheduled_time:
            # We'll convert this in JavaScript once timezone is detected
            pass

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
        user_timezone = cleaned_data.get("timezone_field")

        from .api import RetellCallConcurrency  # or wherever you defined it

        if call_now and RetellCallConcurrency() >= 20:
            raise forms.ValidationError("⚠️ Concurrency limit reached. Please wait until ongoing calls complete.")

        if call_now and scheduled_time:
            raise forms.ValidationError("You cannot select both 'Call Now' and a 'Scheduled Time'. Please choose one.")

        if not call_now and not scheduled_time:
            raise forms.ValidationError("Please select either 'Call Now' or set a 'Scheduled Time'.")

        if scheduled_time:
            # Convert scheduled time to UTC for validation
            try:
                user_tz = pytz.timezone(user_timezone)
                
                # The datetime-local input gives us a naive datetime
                # We need to treat this as being in the user's timezone
                if timezone.is_naive(scheduled_time):
                    # This is the correct case - treat as user's local time
                    localized_time = user_tz.localize(scheduled_time)
                    print(f"🕒 User input (naive): {scheduled_time}")
                    print(f"🌍 User timezone: {user_timezone}")
                    print(f"🔄 Localized time: {localized_time}")
                else:
                    # If it's already timezone-aware, we need to interpret it correctly
                    # The datetime-local input shouldn't give us timezone-aware datetime
                    # But if it does, we need to convert it properly
                    print(f"⚠️ Received timezone-aware datetime: {scheduled_time}")
                    
                    # Remove the timezone info and treat as user's local time
                    naive_time = scheduled_time.replace(tzinfo=None)
                    localized_time = user_tz.localize(naive_time)
                    print(f"🔄 Stripped timezone and localized: {localized_time}")
                
                # Convert to UTC for comparison and storage
                utc_time = localized_time.astimezone(pytz.UTC)
                print(f"⏰ Final UTC time: {utc_time}")
                
                # Check if scheduled time is in the past
                if utc_time < timezone.now():
                    raise forms.ValidationError(f"Scheduled time cannot be in the past. Your time: {utc_time}")
                
                # Store the UTC time for saving
                cleaned_data['scheduled_time_utc'] = utc_time
                
            except pytz.exceptions.UnknownTimeZoneError:
                raise forms.ValidationError("Invalid timezone selected.")
            except Exception as e:
                print(f"❌ Error in timezone conversion: {str(e)}")
                raise forms.ValidationError(f"Error processing scheduled time: {str(e)}")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        selected_agent_id = self.cleaned_data.get("agent_id")
        if isinstance(selected_agent_id, list):
            selected_agent_id = selected_agent_id[0]
        instance.agent_id = selected_agent_id

        # Handle timezone conversion for scheduled time
        scheduled_time = self.cleaned_data.get("scheduled_time")
        user_timezone = self.cleaned_data.get("timezone_field")
        
        if scheduled_time:
            try:
                user_tz = pytz.timezone(user_timezone)
                
                # Get the UTC time from cleaned_data (processed in clean method)
                utc_time = self.cleaned_data.get('scheduled_time_utc')
                if utc_time:
                    instance.scheduled_time = utc_time
                    print(f"✅ Scheduled time saved in UTC: {utc_time}")
                else:
                    # Fallback conversion - treat the input as user's local time
                    if timezone.is_naive(scheduled_time):
                        # Treat naive datetime as user's local time
                        localized_time = user_tz.localize(scheduled_time)
                        print(f"🔄 Fallback: Treating {scheduled_time} as {user_timezone} time")
                    else:
                        # If timezone-aware, strip timezone and treat as user's local time
                        naive_time = scheduled_time.replace(tzinfo=None)
                        localized_time = user_tz.localize(naive_time)
                        print(f"🔄 Fallback: Stripped timezone from {scheduled_time} and treating as {user_timezone} time")
                    
                    # Convert to UTC
                    utc_time = localized_time.astimezone(pytz.UTC)
                    instance.scheduled_time = utc_time
                    print(f"✅ Fallback: Scheduled time saved in UTC: {utc_time}")
                    print(f"📍 Original time in {user_timezone}: {localized_time}")
                    
            except Exception as e:
                print(f"❌ Error converting timezone: {e}")
                # Last resort - save as is
                instance.scheduled_time = scheduled_time

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
        'scheduled_time_display', 'outcome_tag_display', 'call_rating_display','call_retry_display','created_at_display'
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
                    from_number=settings.RETELL_PHONE,
                    to_number=str(obj.phone),
                    retell_llm_dynamic_variables={"name": f"{str(obj.lead_name)}"}
                )
                obj.call_status = 'CONTACTED'
                obj.call_retry = '0'
                
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
    lead_name_display.short_description = 'Lead name'

    def phone_display(self, obj): return obj.phone or "-"
    phone_display.short_description = 'Phone'

    def call_status_display(self, obj):
        return obj.get_call_status_display()
    call_status_display.short_description = 'Call status'

    def call_outcome_display(self, obj): return obj.call_outcome or "-"
    call_outcome_display.short_description = 'Call outcome'

    def agent_name_display(self, obj): return obj.agent_name or "-"
    agent_name_display.short_description = 'Agent name'

    def scheduled_time_display(self, obj):
        if obj.call_now:
            return "Instant"
        return obj.scheduled_time.strftime('%Y-%m-%d %H:%M UTC') if obj.scheduled_time else "-"
    scheduled_time_display.short_description = 'Scheduled'

    def outcome_tag_display(self, obj): return obj.outcome_tag or "-"
    outcome_tag_display.short_description = 'Outcome tag'

    def call_rating_display(self, obj): return obj.call_rating or "-"
    call_rating_display.short_description = 'Call rating'
    
    def call_retry_display(self, obj): return obj.call_retry or "-"
    call_retry_display.short_description = 'Call retry'

    def created_at_display(self, obj): return obj.created_at.strftime('%Y-%m-%d %H:%M UTC') or "-"
    created_at_display.short_description = 'Created at'


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

custom_admin_site.register(Lead, LeadAdmin)



@admin.register(CallHistory)
class CallHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'id','lead', 'from_number', 'to_number', 'direction', 'call_status', 'call_id',
        'agent_id', 'call_successful', 'disconnection_reason', 'user_sentiment',
        'short_transcript', 'recording_link' ,'duration_display','outcome_tag','call_rating','created_at_display'
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

    def created_at_display(self, obj): return obj.created_at.strftime('%Y-%m-%d %H:%M UTC') or "-"
    created_at_display.short_description = 'Created at'

    # ❌ Disable add permission
    def has_add_permission(self, request):
        return False

    # ❌ Disable edit permission
    def has_change_permission(self, request, obj=None):
        return False
    
# ✅ Register your model WITH the admin class
custom_admin_site.register(CallHistory, CallHistoryAdmin)



