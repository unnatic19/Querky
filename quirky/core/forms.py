from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import Upload
class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
class UploadForm(forms.ModelForm):
    passkey_file = forms.FileField(label='Upload Passkey JSON File')
    project_id = forms.CharField(label='Google Cloud Project ID', max_length=100)
    dataset_id = forms.CharField(label='BigQuery Dataset ID', max_length=100)

    class Meta:
        model = Upload
        fields = ['passkey_file']
