from django.db import models
from django.conf import settings


class Conversation(models.Model):
    id = models.BigAutoField(primary_key=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        names = ', '.join(u.username for u in self.participants.all())
        return f"Conversation: {names}"

    def other_participant(self, user):
        return self.participants.exclude(pk=user.pk).first()

    def unread_count(self, user):
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    @classmethod
    def get_or_create_between(cls, user1, user2):
        """Get existing conversation between two users or create a new one."""
        existing = cls.objects.filter(
            participants=user1
        ).filter(
            participants=user2
        ).first()
        if existing:
            return existing, False
        conversation = cls.objects.create()
        conversation.participants.add(user1, user2)
        return conversation, True


class Message(models.Model):
    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_messages',
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.body[:40]}"
