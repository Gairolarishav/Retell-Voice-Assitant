from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser, BaseParser
import json
from .models import ChatHistory,ChatUser
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render


def chatbot(request):
    return render(request,'AI_Assistant/index6.html')

# @admin.site.admin_view
def custom_llm(request):
    return render(request,'AI_Assistant/custom_llm.html')

# @admin.site.admin_view
def AI_Assistant_knowledgebase(request):
    return render(request,'AI_Assistant/knowledgebase.html')


class PlainTextParser(BaseParser):
    media_type = 'text/plain'

    def parse(self, stream, media_type=None, parser_context=None):
        return stream.read().decode('utf-8')

@method_decorator(csrf_exempt, name='dispatch')
class SaveChatView(APIView):
    parser_classes = [JSONParser, PlainTextParser]

    def post(self, request):
        try:
            if isinstance(request.data, str):
                try:
                    data = json.loads(request.data)
                except json.JSONDecodeError:
                    return Response({'error': 'Invalid JSON'}, status=400)
            else:
                data = request.data

            user_id = data.get('user_id')
            session_id = data.get('session_id')
            transcript = data.get('transcript')

            if not user_id or not session_id or not transcript:
                return Response({'error': 'Missing user_id, session_id, or transcript'}, status=400)

            # Get or create ChatUser
            user, _ = ChatUser.objects.get_or_create(user_id=user_id)

            # ✅ update_or_create using (user, session_id)
            obj, created = ChatHistory.objects.update_or_create(
                user=user,
                session_id=session_id,
                defaults={'transcript': transcript}
            )

            return Response(
                {'status': 'success', 'created': created},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            print("Unexpected error in SaveChatView:", str(e))
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

def get_transcript(request):
    user_id = request.GET.get('user_id')
    session_id = request.GET.get('session_id')  # optional

    if not user_id:
        return JsonResponse({'error': 'Missing user_id'}, status=400)

    try:
        if session_id:
            chat = ChatHistory.objects.get(user__user_id=user_id, id=session_id)
        else:
            chat = ChatHistory.objects.filter(user__user_id=user_id).order_by('-created_at').first()

        if not chat:
            return JsonResponse({'transcript': []})

        return JsonResponse({'transcript': chat.transcript})
    
    except ChatHistory.DoesNotExist:
        return JsonResponse({'transcript': []})

def available_sessions(request):
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'sessions': []})

    sessions = ChatHistory.objects.filter(user__user_id=user_id).order_by('-created_at')

    print("sessions===", sessions)

    session_list = [
        {
            "id": chat.id,
            "label": chat.created_at.strftime('%B %d, %Y, %I:%M %p')
        }
        for chat in sessions
    ]
    return JsonResponse({"sessions": session_list})
        