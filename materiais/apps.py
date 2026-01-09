from django.apps import AppConfig
import sys


class MateriaisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'materiais'

    def ready(self):
        """Executado quando o Django está pronto."""
        # Só inicia o scheduler se NÃO for um comando de migração ou shell
        # Evita iniciar múltiplas vezes durante desenvolvimento
        if 'runserver' in sys.argv or 'gunicorn' in sys.argv[0]:
            from . import scheduler
            scheduler.start()
