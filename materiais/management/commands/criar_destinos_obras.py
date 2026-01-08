from django.core.management.base import BaseCommand
from materiais.models import Obra, DestinoEntrega


class Command(BaseCommand):
    help = 'Cria destinos de entrega padrão para obras existentes que não possuem'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando migração de destinos de entrega...'))
        
        obras = Obra.objects.all()
        criados = 0
        ja_existentes = 0
        
        for obra in obras:
            # Verifica se já existe um destino com o nome da obra
            destino_existe = DestinoEntrega.objects.filter(
                obra=obra,
                nome=obra.nome
            ).exists()
            
            if not destino_existe:
                DestinoEntrega.objects.create(
                    obra=obra,
                    nome=obra.nome,
                    endereco=obra.endereco
                )
                criados += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Criado destino para: {obra.nome}')
                )
            else:
                ja_existentes += 1
                self.stdout.write(
                    self.style.WARNING(f'○ Já existe destino para: {obra.nome}')
                )
        
        self.stdout.write(self.style.SUCCESS(f'\n=== MIGRAÇÃO CONCLUÍDA ==='))
        self.stdout.write(self.style.SUCCESS(f'Destinos criados: {criados}'))
        self.stdout.write(self.style.WARNING(f'Já existentes: {ja_existentes}'))
        self.stdout.write(self.style.SUCCESS(f'Total de obras: {obras.count()}'))
