from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import WorkStb, WorkReport

@receiver(post_save, sender=WorkStb)
def create_work_report(sender, instance, created, **kwargs):
    if created:
        WorkReport.objects.create(work=instance)
