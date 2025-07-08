from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets,status
import json
from .models import ChatHistory,ChatUser,FAQ
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import action
from .serializers import FAQSerializer
from django.conf import settings
import requests



def add_faqs(request):
    return render(request,'AI_Assistant/FAQ.html')

def chatbot(request):
    return render(request,'AI_Assistant/index6.html')

# @admin.site.admin_view
def custom_llm(request):
    return render(request,'AI_Assistant/custom_llm.html')

# @admin.site.admin_view
def AI_Assistant_knowledgebase(request):
    return render(request,'AI_Assistant/knowledgebase.html')


@csrf_exempt
def save_chat(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))

        user_id = data.get('user_id')
        session_id = data.get('session_id')
        transcript = data.get('transcript')

        if not user_id or not session_id or not transcript:
            return JsonResponse({'error': 'Missing fields'}, status=400)

        user, _ = ChatUser.objects.get_or_create(user_id=user_id)
        obj, created = ChatHistory.objects.update_or_create(
            user=user,
            session_id=session_id,
            defaults={'transcript': transcript}
        )

        return JsonResponse({'status': 'success', 'created': created})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
        

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
        
class FAQViewSet(viewsets.ModelViewSet):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    
    def list(self, request):
        """Get paginated FAQs"""
        page = self.paginate_queryset(self.get_queryset())
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'success': True,
                'data': serializer.data
            })

        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    def create(self, request):
        """Create new FAQ"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'FAQ created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def retrieve(self, request, pk=None):
        """Get single FAQ"""
        try:
            faq = self.get_object()
            serializer = self.get_serializer(faq)
            return Response({
                'success': True,
                'data': serializer.data
            })
        except FAQ.DoesNotExist:
            return Response({
                'success': False,
                'message': 'FAQ not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def update(self, request, pk=None):
        """Update FAQ"""
        try:
            faq = self.get_object()
            serializer = self.get_serializer(faq, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'success': True,
                    'message': 'FAQ updated successfully',
                    'data': serializer.data
                })
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except FAQ.DoesNotExist:
            return Response({
                'success': False,
                'message': 'FAQ not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def destroy(self, request, pk=None):
        """Delete FAQ"""
        try:
            faq = self.get_object()
            faq.delete()
            return Response({
                'success': True,
                'message': 'FAQ deleted successfully'
            })
        except FAQ.DoesNotExist:
            return Response({
                'success': False,
                'message': 'FAQ not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple FAQs at once"""
        faqs_data = request.data.get('faqs', [])
        
        if not faqs_data:
            return Response({
                'success': False,
                'message': 'No FAQs provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        created_faqs = []
        errors = []
        
        for idx, faq_data in enumerate(faqs_data):
            serializer = self.get_serializer(data=faq_data)
            if serializer.is_valid():
                faq = serializer.save()
                created_faqs.append(serializer.data)
            else:
                errors.append({
                    'index': idx,
                    'errors': serializer.errors
                })
        
        if errors:
            return Response({
                'success': False,
                'message': 'Some FAQs could not be created',
                'created': created_faqs,
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': f'{len(created_faqs)} FAQs created successfully',
            'data': created_faqs
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search FAQs by question or answer"""
        query = request.query_params.get('q', '')
        
        if not query:
            return Response({
                'success': False,
                'message': 'Search query is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        faqs = FAQ.objects.filter(
            models.Q(question__icontains=query) | 
            models.Q(answer__icontains=query)
        )
        
        serializer = self.get_serializer(faqs, many=True)
        return Response({
            'success': True,
            'count': faqs.count(),
            'query': query,
            'data': serializer.data
        })
    



VOICEFLOW_API_KEY = settings.VOICEFLOW_API_KEY
TABLE_UPLOAD_URL = "https://api.voiceflow.com/v1/knowledge-base/docs/upload/table"

def upload_faqs_to_voiceflow(request):
    try:
        # Step 1: Get all FAQs
        faq_objects = FAQ.objects.all()
        if not faq_objects.exists():
            return JsonResponse({"success": False, "message": "No FAQs available to upload."}, status=400)

        # Step 2: Prepare FAQ items
        faq_items = [
            {
                "id": faq.id,
                "question": faq.question,
                "answer": faq.answer,
                "created_at": faq.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            for faq in faq_objects
        ]

        # Step 3: Prepare payload
        payload = {
            "data": {
                "name": "FAQ Knowledgebase",
                "schema": {
                    "searchableFields": ["question", "answer"],
                    "metadataFields": ["created_at","id"]
                },
                "items": faq_items
            }
        }

        # Step 4: Make POST request to Voiceflow
        headers = {
            "Authorization": f"{VOICEFLOW_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        params = {"overwrite": "true"}

        response = requests.post(TABLE_UPLOAD_URL, json=payload, headers=headers, params=params)

        # Step 5: Handle response
        if response.status_code == 200:
            return JsonResponse({"success": True, "message": "FAQs uploaded successfully.", "response": response.json()})
        else:
            return JsonResponse({"success": False, "message": "Upload failed", "error": response.text}, status=response.status_code)

    except Exception as e:
        return JsonResponse({"success": False, "message": "Something went wrong", "error": str(e)}, status=500)
    

