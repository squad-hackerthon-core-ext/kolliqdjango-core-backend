from django.apps import AppConfig
 
 
class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    label = 'users'
 
    def ready(self):
        # This import MUST happen here — it registers the signal handlers
        # Without this line, post_save on User never triggers wallet creation
        import apps.users.signals  # noqa: F401
 
