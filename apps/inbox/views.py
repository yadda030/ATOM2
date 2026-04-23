from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from .models import Conversation, Message

User = get_user_model()


def _get_conversations(user):
    conversations = user.conversations.prefetch_related(
        'participants', 'messages'
    ).order_by('-updated_at')
    for conv in conversations:
        conv.other_user = conv.other_participant(user)
        conv.unread = conv.unread_count(user)
        conv.last_message = conv.messages.last()
    return conversations


@login_required
def inbox(request, pk=None):
    conversations = _get_conversations(request.user)
    total_unread = sum(c.unread for c in conversations)

    active_conv = None
    thread_messages = []
    other_user = None
    presence = ''

    if pk:
        active_conv = get_object_or_404(Conversation, pk=pk)

        if not request.user.is_staff and request.user not in active_conv.participants.all():
            messages.error(request, 'You do not have permission to view this conversation.')
            return redirect('inbox')

        # Mark messages as read
        active_conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

        thread_messages = active_conv.messages.select_related('sender').all()
        other_user = active_conv.other_participant(request.user)
        presence = other_user.presence_display if other_user else ''

    return render(request, 'inbox/inbox.html', {
        'conversations': conversations,
        'total_unread': total_unread,
        'active_conv': active_conv,
        'thread_messages': thread_messages,
        'other_user': other_user,
        'presence': presence,
    })


@login_required
def thread_partial(request, pk):
    """HTMX partial — returns just the thread panel for a given conversation."""
    conv = get_object_or_404(Conversation, pk=pk)

    if not request.user.is_staff and request.user not in conv.participants.all():
        return HttpResponse(status=403)

    conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    thread_messages = conv.messages.select_related('sender').all()
    other_user = conv.other_participant(request.user)
    presence = other_user.presence_display if other_user else ''

    return render(request, 'inbox/thread_partial.html', {
        'conv': conv,
        'thread_messages': thread_messages,
        'other_user': other_user,
        'presence': presence,
    })


@login_required
def send_message(request, pk):
    """POST only — sends a message and returns the updated thread partial."""
    conv = get_object_or_404(Conversation, pk=pk)

    if not request.user.is_staff and request.user not in conv.participants.all():
        return HttpResponse(status=403)

    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            msg = Message.objects.create(
                conversation=conv,
                sender=request.user,
                body=body,
            )
            conv.save()
            _push_message(conv, msg)

    thread_messages = conv.messages.select_related('sender').all()
    other_user = conv.other_participant(request.user)
    presence = other_user.presence_display if other_user else ''

    return render(request, 'inbox/thread_partial.html', {
        'conv': conv,
        'thread_messages': thread_messages,
        'other_user': other_user,
        'presence': presence,
    })


@login_required
def new_conversation(request):
    users = User.objects.exclude(pk=request.user.pk).exclude(is_active=False).order_by('username')

    if request.method == 'POST':
        recipient_id = request.POST.get('recipient')
        body = request.POST.get('body', '').strip()

        if not recipient_id or not body:
            messages.error(request, 'Please select a recipient and enter a message.')
            return redirect('new_conversation')

        recipient = get_object_or_404(User, pk=recipient_id)
        conv, created = Conversation.get_or_create_between(request.user, recipient)

        msg = Message.objects.create(
            conversation=conv,
            sender=request.user,
            body=body,
        )
        conv.save()
        _push_message(conv, msg)

        return redirect('conversation', pk=conv.pk)

    return render(request, 'inbox/new_conversation.html', {
        'users': users,
    })


def _push_message(conv, msg):
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        recipient = conv.other_participant(msg.sender)

        if not recipient:
            return

        payload = {
            'type': 'new_message',
            'data': {
                'event': 'new_message',
                'conversation_id': conv.id,
                'sender': msg.sender.username,
                'body': msg.body,
                'created_at': msg.created_at.strftime('%H:%M'),
                'unread_count': conv.unread_count(recipient),
            }
        }

        async_to_sync(channel_layer.group_send)(
            f'inbox_{recipient.id}',
            payload,
        )

        async_to_sync(channel_layer.group_send)(
            f'dashboard_{recipient.id}',
            {
                'type': 'vm_status_update',
                'data': {
                    'event': 'unread_messages',
                    'unread_count': _total_unread(recipient),
                }
            }
        )
    except Exception:
        pass


def _total_unread(user):
    return Message.objects.filter(
        conversation__participants=user,
        is_read=False,
    ).exclude(sender=user).count()