from django.db.models.signals import post_delete, post_save, pre_save
from django.db.models import FileField
from django.dispatch import receiver

from tagtrack.models import Album, Artist, Song


def delete_file_fields(sender, instance, **kwargs):
    if sender._meta.app_label == 'tagtrack':
        for field in instance._meta.get_fields():
            if issubclass(field.__class__, FileField):
                ff = field.name
                getattr(instance, ff).delete(save=False)


def update_retag_field(sender, instance, created, **kwargs):
    if not created:
        if isinstance(instance, Album):
            Song.objects.filter(album_id=instance.pk).update(retag=True)
        elif isinstance(instance, Artist):
            Song.objects.filter(artists__id=instance.pk).update(
                retag=True)


@receiver(pre_save, sender=Song)
def before_song_save(sender, instance, **kwargs):
    if instance.pk:
        instance.retag = True


post_delete.connect(delete_file_fields)
post_save.connect(update_retag_field)
