from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json


def setup_polling():
    """
    Creates a periodic task to poll Proxmox for all users every 30 seconds.
    Safe to run multiple times - won't create duplicates.
    """
    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=30,
        period=IntervalSchedule.SECONDS,
    )

    PeriodicTask.objects.get_or_create(
        name='Poll Proxmox VMs for all users',
        defaults={
            'task': 'apps.proxmox.tasks.poll_all_users',
            'interval': schedule,
            'args': json.dumps([]),
        }
    )