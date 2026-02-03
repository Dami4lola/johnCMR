from django import forms
from .models import Timesheet, Job, Worker, Receipt
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class WorkerSignUpForm(UserCreationForm):
    # This field is "extra" (not in the User DB), so we define it explicitly
    full_name = forms.CharField(max_length=100, help_text="Enter your First and Last Name")
    email = forms.EmailField(
        required=True,
        help_text="Required. We'll send a verification email to this address."
    )

    class Meta:
        model = User
        # ONLY include fields that actually exist in the Django User table
        fields = ['username', 'email']
        # Note: 'full_name' is removed from here, but stays above.

    def clean_email(self):
        """Ensure email is unique"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already registered.")
        return email

class TimesheetForm(forms.ModelForm):
    class Meta:
        model = Timesheet
        fields = ['job', 'date', 'hours_worked', 'round_trip_kms',
                  'used_company_truck', 'worked_at_hq',
                  'company_materials', 'personal_materials',
                  'receipts_total']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'company_materials': 'Company Materials ($)',
            'personal_materials': 'Personal Materials ($)',
        }

    def __init__(self, user, *args, **kwargs):
        # We accept 'user' as the first argument
        super(TimesheetForm, self).__init__(*args, **kwargs)
        
        # FILTER: Only show jobs assigned to THIS worker
        if user.is_authenticated:
            try:
                # Find the Worker profile linked to this User
                worker_profile = Worker.objects.get(user=user)
                # Filter the 'job' dropdown
                self.fields['job'].queryset = Job.objects.filter(assigned_workers=worker_profile, is_completed=False)
            except Worker.DoesNotExist:
                # If Jon logs in but hasn't made himself a "Worker", show nothing
                self.fields['job'].queryset = Job.objects.none()


class ReceiptForm(forms.ModelForm):
    """Form for uploading receipt images"""
    class Meta:
        model = Receipt
        fields = ['image', 'description', 'amount']
        widgets = {
            'description': forms.TextInput(attrs={'placeholder': 'e.g., Home Depot - lumber'}),
            'amount': forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
        }
        labels = {
            'image': 'Receipt Photo',
            'description': 'Description (optional)',
            'amount': 'Amount (optional)',
        }