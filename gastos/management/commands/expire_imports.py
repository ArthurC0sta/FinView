from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from gastos.import_service import remove_raw_file
from gastos.models import ImportBatch


class Command(BaseCommand):
    help = 'Expira lotes aguardando revisão há mais de 24 horas e remove o arquivo bruto.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=24)
        batches = ImportBatch.objects.filter(status=ImportBatch.Status.AWAITING_REVIEW, created_at__lt=cutoff)
        count = 0
        for batch in batches.iterator():
            remove_raw_file(batch)
            batch.status = ImportBatch.Status.EXPIRED
            batch.finalized_at = timezone.now()
            batch.save()
            count += 1
        self.stdout.write(self.style.SUCCESS(f'{count} lote(s) expirado(s).'))
