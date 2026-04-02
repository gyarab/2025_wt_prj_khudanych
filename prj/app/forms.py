from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['display_name', 'profile_picture']
        labels = {
            'display_name': _('Display Name'),
            'profile_picture': _('Profile Picture'),
        }
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
