from django.contrib import admin
from retells.admin import custom_admin_site
from .models import ChatUser,ChatHistory
from django.utils.html import format_html

class ChatUserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'created_at',"view_transcript_display")
    search_fields = ('user_id',)
    ordering = ('-created_at',)

    def view_transcript_display(self, obj):
        return format_html(

            '<a href="javascript:void(0);" class="btn btn-sm btn-primary" onclick="openTranscriptModal(\'{}\')">View</a>',
            obj.user_id
        )
    view_transcript_display.short_description = 'Transcript'
custom_admin_site.register(ChatUser,ChatUserAdmin)

class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('user','session_id' ,'short_chat','created_at','updated_at')
    list_filter = ('created_at',)
    search_fields = ('user__user_id',)
    ordering = ('-created_at',)

    def short_chat(self, obj):
        if not obj.transcript:
            return "-"
        first_msg = obj.transcript[0]
        return f"{first_msg.get('source', '')}: {first_msg.get('text', '')[:50]}..."
    short_chat.short_description = 'Transcript'

custom_admin_site.register(ChatHistory,ChatHistoryAdmin)

