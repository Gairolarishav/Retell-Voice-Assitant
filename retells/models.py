from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.
class Lead(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('CONTACTED', 'Contacted')
    ]

     # New: Add call outcome field
    CALL_OUTCOME_CHOICES = [
        ('user_hangup', 'User hangup'),
        ('agent_hangup', 'Agent hangup'),
        ('call_transfer', 'Call transferred'),
        ('voicemail_reached', 'Voicemail reached'),
        ('inactivity', 'Inactivity timeout'),
        ('machine_detected', 'Machine detected'),
        ('max_duration_reached', 'Max duration reached'),
        ('concurrency_limit_reached', 'Concurrency limit reached'),
        ('no_valid_payment', 'No valid payment'),
        ('scam_detected', 'Scam detected'),
        ('error_inbound_webhook', 'Inbound webhook error'),
        ('dial_busy', 'Dial busy'),
        ('dial_failed', 'Dial failed'),
        ('dial_no_answer', 'Dial no answer'),
        ('error_llm_websocket_open', 'LLM websocket open error'),
        ('error_llm_websocket_lost_connection', 'LLM websocket lost'),
        ('error_llm_websocket_runtime', 'LLM websocket runtime error'),
        ('error_llm_websocket_corrupt_payload', 'LLM corrupt payload'),
        ('error_no_audio_received', 'No audio received'),
        ('error_asr', 'ASR error'),
        ('error_retell', 'Retell internal error'),
        ('error_unknown', 'Unknown error'),
        ('error_user_not_joined', 'User didn’t join web call'),
        ('registered_call_timeout', 'Registered call timeout'),
    ]

    lead_name = models.CharField(max_length=100, blank=True, null=True)
    phone = PhoneNumberField(region=None, unique=True,help_text="Enter the full number in international format (e.g., +919876543210)")  # Allows full international numbers
    call_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    call_outcome = models.CharField(max_length=50, choices=CALL_OUTCOME_CHOICES, blank=True, null=True, help_text="Detailed Retell call outcome")
    agent_id = models.CharField(max_length=255, blank=True, help_text="Retell AI Agent ID")
    agent_name = models.CharField(max_length=255,blank=True)
    call_now = models.BooleanField(default=False, help_text="Check this to initiate the call immediately.")
    scheduled_time = models.DateTimeField(blank=True, null=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Suggested field for outcome tag (you can rename if needed)
    outcome_tag = models.JSONField(null=True, blank=True,help_text="Short outcome summary like 'Interested', 'Wrong number', 'No interest'")  # ✅ This is correct

    # Rating: can be 0 or blank/null if no rating
    call_rating = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="Call rating from 1 to 5, or 0 if not applicable"
    )
    call_retry = models.IntegerField(default=0)  # Retry count

    def __str__(self):
        return f"{self.lead_name or 'Lead'} - {self.phone}"

class CallHistory(models.Model):
    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)
    direction = models.CharField(max_length=20, default='outbound')
    # Relationships
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='call_history')
    # batch_call = models.ForeignKey(BatchCall,on_delete=models.SET_NULL,related_name='batch_call_histories',null=True,blank=True)

    # Call Identification
    call_id = models.CharField(max_length=255, unique=True, help_text="Retell API Call ID")
    agent_id = models.CharField(max_length=255, blank=True, help_text="Retell Agent ID")
    call_status = models.CharField(max_length=50, default='ongoing')
    call_successful = models.CharField(max_length=20)
    disconnection_reason = models.CharField(max_length=20)
    user_sentiment = models.CharField(max_length=20)
    duration = models.PositiveBigIntegerField(null=True, blank=True, help_text="Call duration")
    # Call Content
    transcript = models.TextField(blank=True, help_text="Call transcript from Retell") 
    # Suggested field for outcome tag (you can rename if needed)
    outcome_tag = models.JSONField(null=True, blank=True,help_text="Short outcome summary like 'Interested', 'Wrong number', 'No interest'")  # ✅ This is correct

    # Rating: can be 0 or blank/null if no rating
    call_rating = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="Call rating from 1 to 5, or 0 if not applicable"
    )

    recording_url = models.URLField(blank=True, help_text="URL to call recording")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Convert duration from ms to sec before saving
        if self.duration is not None:
            self.duration = round(self.duration / 1000)  # Convert to seconds
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Call History"
        verbose_name_plural = "Call History"

