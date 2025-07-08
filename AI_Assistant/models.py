from django.db import models

# Create your models here.

class ChatUser(models.Model):
    user_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Chat User"
        verbose_name_plural = "Chat User"

    def __str__(self):
        return self.user_id
    
class ChatHistory(models.Model):
    user = models.ForeignKey(ChatUser, on_delete=models.CASCADE, related_name='chats')
    session_id = models.CharField(max_length=255)
    transcript = models.JSONField()  # entire session turns list
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'session_id')
        verbose_name = "Chat History"
        verbose_name_plural = "Chat History"

    def __str__(self):
        return f"Session {self.session_id} for {self.user.user_id}"
    

class FAQ(models.Model):
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'faq'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"FAQ: {self.question[:50]}..."
