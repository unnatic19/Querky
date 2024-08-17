from django.db import models
from django.contrib.auth.models import User
# Create your models here.
class Upload(models.Model):
    json_file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class SchemaInfo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    table_name = models.CharField(max_length=255)
    field_name = models.CharField(max_length=255)
    field_type = models.CharField(max_length=255)
    retrieved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.table_name}: {self.field_name} ({self.field_type})"
