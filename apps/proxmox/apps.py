from django.apps import AppConfig


class ProxmoxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.proxmox'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(self._setup_periodic_tasks, sender=self)

    def _setup_periodic_tasks(self, **kwargs):
        try:
            from apps.proxmox.scheduling import setup_polling
            setup_polling()
        except Exception:
            pass  # database may not be ready yet