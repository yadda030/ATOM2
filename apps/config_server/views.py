from django.http import HttpResponse, Http404
from django.utils import timezone
from .models import MachineConfig

def serve_script(request, mac_address):
    try:
        config = MachineConfig.objects.get(mac_address=mac_address)
        config.has_checked_in = True
        config.last_checkin = timezone.now()
        config.save()
        return HttpResponse(config.config_script, content_type='text/plain')
    except MachineConfig.DoesNotExist:
        raise Http404