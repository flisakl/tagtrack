from django.db.models.signals import post_delete
from django.db.models import FileField


def delete_file_fields(sender, instance, **kwargs):
    if sender._meta.app_label == 'tagtrack':
        for field in instance._meta.get_fields():
            if issubclass(field.__class__, FileField):
                ff = field.name
                getattr(instance, ff).delete(save=False)


post_delete.connect(delete_file_fields)
