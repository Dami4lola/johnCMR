from django.db import models
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from django.conf import settings
import math
import requests

# Office address for distance calculations
OFFICE_ADDRESS = "244 Bell Street North, K1R 5T7, Ottawa, Ontario, Canada"

class Client(models.Model):
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True, help_text="Client contact number")
    email = models.EmailField(blank=True)
    address = models.TextField()

    def __str__(self):
        return self.name



class Worker(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    name = models.CharField(max_length=100)
    hourly_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[
            MinValueValidator(0, message="Hourly rate cannot be negative"),
            MaxValueValidator(999.99, message="Hourly rate seems unreasonably high")
        ],
        help_text="Hourly rate in dollars (max $999.99)"
    )
    charges_hst = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=False)

    # Audit logging - tracks all changes to worker records
    history = HistoricalRecords()

    def __str__(self):
        return self.name

class Job(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE)
    description = models.TextField(help_text="Detailed job description and scope of work")

    # Jon selects who works on this.
    assigned_workers = models.ManyToManyField(Worker, related_name='assigned_jobs', blank=True)

    # Scheduling fields for calendar
    scheduled_date = models.DateField(null=True, blank=True, help_text="When the job is scheduled")
    scheduled_time = models.TimeField(null=True, blank=True, help_text="Start time for the job")
    estimated_duration = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text="Estimated hours to complete"
    )

    is_completed = models.BooleanField(default=False)
    estimate_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Auto-calculated distance from office to job site (round trip)
    calculated_distance_km = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Auto-calculated round trip distance from office (km)"
    )

    def __str__(self):
        return f"{self.client.name} - {self.description[:50]}"

    def calculate_distance(self):
        """Calculate round trip distance from office to job site using Google Maps API"""
        api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
        if not api_key:
            return None

        destination = self.client.address
        if not destination:
            return None

        try:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                'origins': OFFICE_ADDRESS,
                'destinations': destination,
                'key': api_key,
                'units': 'metric'
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data['status'] == 'OK':
                element = data['rows'][0]['elements'][0]
                if element['status'] == 'OK':
                    # Distance in meters, convert to km and double for round trip
                    distance_m = element['distance']['value']
                    round_trip_km = (distance_m / 1000) * 2
                    return round(round_trip_km, 2)
        except Exception:
            pass
        return None

    def save(self, *args, **kwargs):
        # Auto-calculate distance if not set and API key exists
        if self.calculated_distance_km is None:
            distance = self.calculate_distance()
            if distance:
                self.calculated_distance_km = distance
        super().save(*args, **kwargs)


class Invoice(models.Model):
    """Invoice generated for a job"""
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='invoice')
    invoice_number = models.CharField(max_length=20, unique=True)
    created_date = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)

    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    hst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')

    # Payment terms
    notes = models.TextField(blank=True, help_text="Additional notes or payment instructions")

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.job.client.name}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Generate invoice number: INV-YYYY-NNNN
            from datetime import date
            year = date.today().year
            last_invoice = Invoice.objects.filter(
                invoice_number__startswith=f'INV-{year}-'
            ).order_by('-invoice_number').first()

            if last_invoice:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1

            self.invoice_number = f'INV-{year}-{new_num:04d}'

        super().save(*args, **kwargs)

# ... Timesheet model stays the same ...

class Timesheet(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    date = models.DateField()

    # Inputs with validation
    hours_worked = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[
            MinValueValidator(0.01, message="Hours worked must be greater than 0"),
            MaxValueValidator(24, message="Hours worked cannot exceed 24 hours in a day")
        ],
        help_text="Actual hours on site (0.01 - 24.00)"
    )
    round_trip_kms = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0, message="Kilometers cannot be negative"),
            MaxValueValidator(9999.99, message="Distance seems unreasonably high")
        ],
        help_text="Round trip distance in kilometers"
    )

    # Flags for Logic
    used_company_truck = models.BooleanField(default=False)
    worked_at_hq = models.BooleanField(default=False, help_text="Working at Jon's place?")

    # Expenses with validation - Materials split into Company and Personal
    company_materials = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0, message="Amount cannot be negative"),
            MaxValueValidator(99999.99, message="Amount seems unreasonably high")
        ],
        help_text="Materials purchased with company card/account"
    )
    personal_materials = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0, message="Amount cannot be negative"),
            MaxValueValidator(99999.99, message="Amount seems unreasonably high")
        ],
        help_text="Materials purchased with personal funds (will be reimbursed)"
    )
    receipts_total = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0, message="Receipts total cannot be negative"),
            MaxValueValidator(99999.99, message="Receipts total seems unreasonably high")
        ],
        help_text="Out of pocket purchases"
    )
    receipt_card_digits = models.CharField(
        max_length=4,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\d{4}$',
                message="Enter exactly 4 digits",
                code='invalid_card_digits'
            )
        ],
        help_text="Last 4 digits of card used (numbers only)"
    )

    # Calculated Fields (We store these so they don't change later if rates change)
    calculated_pay = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # Audit logging - tracks all changes to timesheet records (critical for financial disputes)
    history = HistoricalRecords()

    def clean(self):
        """Custom validation for business rules"""
        super().clean()

        # Allow empty receipt_card_digits, but if provided must be exactly 4 digits
        if self.receipt_card_digits and not self.receipt_card_digits.isdigit():
            raise ValidationError({
                'receipt_card_digits': 'Card digits must contain only numbers'
            })

        if self.receipt_card_digits and len(self.receipt_card_digits) != 4:
            raise ValidationError({
                'receipt_card_digits': 'Enter exactly 4 digits'
            })

    def save(self, *args, **kwargs):
        self.full_clean()  # Run validators before saving
        self.calculated_pay = self.calculate_payout()
        super().save(*args, **kwargs)

    def calculate_payout(self):
        total = Decimal(0.0)
        
        # 1. Round hours to nearest 0.25
        rounded_hours = round(float(self.hours_worked) * 4) / 4
        payable_hours = max(rounded_hours, 4.0)

        # 2. Labor Cost
        labor = Decimal(payable_hours) * self.worker.hourly_rate
        if self.worker.charges_hst:
            labor *= Decimal(1.13) # Add 13% HST
        total += labor

        # 3. KMs Logic (.50 per km, but 0 if company truck or at HQ)
        if not self.used_company_truck and not self.worked_at_hq:
            total += self.round_trip_kms * Decimal(0.50)

        # 4. Personal Materials (worker pays, gets reimbursed)
        total += self.personal_materials

        # 5. Reimbursements (Check for company card '5564')
        if self.receipt_card_digits != '5564':
            total += self.receipts_total

        # Note: company_materials is NOT added to worker pay (company already paid)

        return round(total, 2)


def receipt_upload_path(instance, filename):
    """Generate upload path: receipts/worker_id/YYYY-MM/filename"""
    import os
    from datetime import date
    worker_id = instance.timesheet.worker.id
    today = date.today()
    return f'receipts/{worker_id}/{today.strftime("%Y-%m")}/{filename}'


class Receipt(models.Model):
    """Receipt image uploaded with a timesheet"""
    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name='receipts')
    image = models.ImageField(upload_to=receipt_upload_path)
    description = models.CharField(max_length=200, blank=True, help_text="Brief description of the receipt")
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount on receipt (optional)"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Receipt for {self.timesheet.worker.name} - {self.timesheet.date}"

    class Meta:
        ordering = ['-uploaded_at']


class PurchaseListItem(models.Model):
    """Item on the team shopping/purchase list"""
    PRIORITY_CHOICES = [
        ('1_high', 'High - Urgent'),
        ('2_medium', 'Medium'),
        ('3_low', 'Low'),
    ]

    STATUS_CHOICES = [
        ('needed', 'Needed'),
        ('purchased', 'Purchased'),
    ]

    name = models.CharField(max_length=200, help_text="Item name/description")
    quantity = models.CharField(max_length=50, blank=True, help_text="e.g., '2 boxes', '5 bags'")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='2_medium')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='needed')
    notes = models.TextField(blank=True, help_text="Additional details (brand, size, where to buy, etc.)")

    # Who added it and when
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='purchase_items_added')
    added_at = models.DateTimeField(auto_now_add=True)

    # Who purchased it (if purchased)
    purchased_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_items_bought')
    purchased_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.get_priority_display()})"

    class Meta:
        ordering = ['priority', '-added_at']  # 1_high < 2_medium < 3_low


def inspection_photo_path(instance, filename):
    """Generate upload path: inspections/job_id/type/filename"""
    job_id = instance.inspection.job.id
    inspection_type = instance.inspection.inspection_type
    return f'inspections/{job_id}/{inspection_type}/{filename}'


class JobInspection(models.Model):
    """Pre or Post inspection form for a job"""
    INSPECTION_TYPE_CHOICES = [
        ('pre', 'Pre-Inspection'),
        ('post', 'Post-Inspection'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('completed', 'Completed'),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='inspections')
    inspection_type = models.CharField(max_length=4, choices=INSPECTION_TYPE_CHOICES)
    inspector = models.ForeignKey(Worker, on_delete=models.SET_NULL, null=True, related_name='inspections')

    # When
    inspection_date = models.DateField()
    inspection_time = models.TimeField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')

    # General fields (always present)
    site_conditions = models.TextField(blank=True, help_text="Overall site conditions observed")
    safety_hazards = models.TextField(blank=True, help_text="Any safety hazards identified")
    notes = models.TextField(blank=True, help_text="Additional observations or comments")

    # Pre-inspection specific
    client_present = models.BooleanField(default=False, help_text="Was the client present during inspection?")
    access_issues = models.TextField(blank=True, help_text="Any access or entry issues")
    existing_damage = models.TextField(blank=True, help_text="Pre-existing damage to document")

    # Post-inspection specific
    work_completed = models.TextField(blank=True, help_text="Description of work completed")
    quality_check_passed = models.BooleanField(default=True)
    client_satisfied = models.BooleanField(null=True, blank=True, help_text="Client satisfaction if present")
    followup_required = models.BooleanField(default=False)
    followup_notes = models.TextField(blank=True, help_text="Details of any follow-up work needed")

    # Client signature (base64 or file path - for later implementation)
    client_signature = models.TextField(blank=True, help_text="Client signature data")
    client_name_signed = models.CharField(max_length=100, blank=True, help_text="Printed name of client who signed")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-inspection_date', '-created_at']
        # Prevent duplicate inspections of same type for a job
        unique_together = ['job', 'inspection_type']

    def __str__(self):
        return f"{self.get_inspection_type_display()} - {self.job.client.name} ({self.inspection_date})"

    def save(self, *args, **kwargs):
        # Set completed_at when status changes to completed
        if self.status == 'completed' and not self.completed_at:
            from django.utils import timezone
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)


class InspectionPhoto(models.Model):
    """Photos attached to an inspection"""
    inspection = models.ForeignKey(JobInspection, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to=inspection_photo_path)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.inspection}"

    class Meta:
        ordering = ['uploaded_at']