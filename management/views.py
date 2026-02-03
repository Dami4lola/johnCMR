from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from .models import Timesheet, Job, Worker, Invoice, Receipt, PurchaseListItem, JobInspection, InspectionPhoto
from .forms import TimesheetForm, WorkerSignUpForm, ReceiptForm
from datetime import datetime, timedelta
import calendar

def custom_logout(request):
    """Custom logout view that handles both GET and POST requests"""
    logout(request)
    return redirect('welcome')

def welcome(request):
    # If the user is already logged in, don't show the welcome screen
    # Just send them straight to their dashboard
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('manager_dashboard') # Send Jon to Manager View
        return redirect('submit_timesheet')      # Send Workers to Worker View

    return render(request, 'management/welcome.html')
    
    
def register(request):
    if request.method == 'POST':
        form = WorkerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data.get('email')
            user.is_active = True  # Account active immediately (email verification optional for internal team)
            user.save()

            # AUTOMATICALLY CREATE WORKER PROFILE
            # We set rate to 0 initially so Jon can fix it later
            full_name = form.cleaned_data.get('full_name')
            Worker.objects.create(
                user=user,
                name=full_name,
                hourly_rate=0.00  # Placeholder
            )

            # Success message with email confirmation note
            messages.success(
                request,
                f'Account created successfully! A confirmation has been sent to {user.email}. '
                f'Please verify your email to ensure you receive important notifications.'
            )

            # Log the user in immediately
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # Redirect to worker dashboard after successful registration
            return redirect('submit_timesheet')
    else:
        form = WorkerSignUpForm()
    return render(request, 'management/register.html', {'form': form})
    


# This decorator ensures only Jon (Admin) can see this page
@staff_member_required
def manager_dashboard(request):
    # 1. Get all Timesheets ordered by date
    timesheets = Timesheet.objects.all().order_by('-date')
    
    # 2. Calculate Total Payroll Owed (The "Big Number")
    total_payroll = timesheets.aggregate(Sum('calculated_pay'))['calculated_pay__sum'] or 0
    
    # 3. Group data by Worker (Optional, but helpful for Jon)
    # We can do this simply in the template or use advanced queries.
    # For MVP, let's just list the logs.

    return render(request, 'management/dashboard.html', {
        'timesheets': timesheets,
        'total_payroll': total_payroll
    })
    
 
# 1. Force users to login to see this page
@login_required
def submit_timesheet(request):
    if request.user.is_superuser:
        return redirect('manager_dashboard')
    try:
        worker = request.user.worker
    except Worker.DoesNotExist:
        return render(request, 'management/error.html', {'message': 'You are not set up as a Worker yet. Ask Jon.'})

    # Fetch the list of active jobs for this worker
    my_jobs = Job.objects.filter(assigned_workers=worker, is_completed=False)

    if request.method == 'POST':
        form = TimesheetForm(request.user, request.POST)
        if form.is_valid():
            timesheet = form.save(commit=False)
            timesheet.worker = worker
            timesheet.save()

            # Handle receipt uploads
            receipt_files = request.FILES.getlist('receipts')
            for receipt_file in receipt_files:
                Receipt.objects.create(
                    timesheet=timesheet,
                    image=receipt_file
                )

            receipt_count = len(receipt_files)
            if receipt_count > 0:
                messages.success(request, f"Timesheet submitted with {receipt_count} receipt(s)!")
            else:
                messages.success(request, "Timesheet submitted successfully!")
            return redirect('submit_timesheet')
    else:
        form = TimesheetForm(request.user)

    return render(request, 'management/submit_timesheet.html', {
        'form': form,
        'my_jobs': my_jobs
    })


# ===================================
# FUTURE FEATURES: Edit/Delete with Authorization
# ===================================
# These views are not currently used but implement proper security for future features

@login_required
def edit_timesheet(request, timesheet_id):
    """
    SECURITY: Edit timesheet with proper authorization checks.
    Workers can only edit their own timesheets. Staff can edit any timesheet.
    """
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)

    # CRITICAL AUTHORIZATION CHECK
    # Only allow workers to edit their own timesheets, or allow staff to edit any
    if timesheet.worker.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to edit this timesheet.")
        return HttpResponseForbidden(
            "<h1>403 Forbidden</h1><p>You don't have permission to edit this timesheet.</p>"
        )

    if request.method == 'POST':
        form = TimesheetForm(request.user, request.POST, instance=timesheet)
        if form.is_valid():
            form.save()
            messages.success(request, "Timesheet updated successfully!")
            return redirect('submit_timesheet')
    else:
        form = TimesheetForm(request.user, instance=timesheet)

    return render(request, 'management/edit_timesheet.html', {
        'form': form,
        'timesheet': timesheet
    })


@login_required
def delete_timesheet(request, timesheet_id):
    """
    SECURITY: Delete timesheet with proper authorization checks.
    Workers can only delete their own timesheets. Staff can delete any timesheet.
    Requires POST request to prevent CSRF attacks.
    """
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)

    # CRITICAL AUTHORIZATION CHECK
    if timesheet.worker.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to delete this timesheet.")
        return HttpResponseForbidden(
            "<h1>403 Forbidden</h1><p>You don't have permission to delete this timesheet.</p>"
        )

    # SECURITY: Only allow POST to prevent accidental deletion via GET
    if request.method == 'POST':
        timesheet.delete()
        messages.success(request, "Timesheet deleted successfully!")
        return redirect('submit_timesheet')

    # If GET request, show confirmation page
    return render(request, 'management/delete_confirm.html', {
        'timesheet': timesheet
    })


# ===================================
# CALENDAR VIEW FOR WORKERS
# ===================================

@login_required
def worker_calendar(request):
    """Calendar view showing scheduled jobs for the worker"""
    try:
        worker = request.user.worker
    except Worker.DoesNotExist:
        return render(request, 'management/error.html', {'message': 'You are not set up as a Worker yet. Ask Jon.'})

    # Get month/year from query params or use current
    today = datetime.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    # Get first and last day of month
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, calendar.monthrange(year, month)[1])

    # Get jobs scheduled for this worker in this month
    scheduled_jobs = Job.objects.filter(
        assigned_workers=worker,
        scheduled_date__gte=first_day.date(),
        scheduled_date__lte=last_day.date(),
        is_completed=False
    ).order_by('scheduled_date', 'scheduled_time')

    # Build calendar data
    cal = calendar.Calendar(firstweekday=6)  # Start week on Sunday
    month_days = cal.monthdayscalendar(year, month)

    # Create dict of jobs by date
    jobs_by_date = {}
    for job in scheduled_jobs:
        date_str = job.scheduled_date.strftime('%Y-%m-%d')
        if date_str not in jobs_by_date:
            jobs_by_date[date_str] = []
        jobs_by_date[date_str].append(job)

    # Previous/Next month links
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    context = {
        'month_days': month_days,
        'jobs_by_date': jobs_by_date,
        'current_month': first_day,
        'today': today.date(),
        'year': year,
        'month': month,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'upcoming_jobs': scheduled_jobs[:5],  # Show next 5 upcoming jobs
    }

    return render(request, 'management/calendar.html', context)


@login_required
def calendar_events_json(request):
    """API endpoint for calendar events (for JavaScript calendar libraries)"""
    try:
        worker = request.user.worker
    except Worker.DoesNotExist:
        return JsonResponse({'error': 'Worker not found'}, status=404)

    # Get jobs for this worker
    jobs = Job.objects.filter(
        assigned_workers=worker,
        scheduled_date__isnull=False,
        is_completed=False
    )

    events = []
    for job in jobs:
        event = {
            'id': job.id,
            'title': f"{job.client.name} - {job.description[:30]}",
            'start': job.scheduled_date.isoformat(),
            'client': job.client.name,
            'address': job.client.address,
            'description': job.description,
        }
        if job.scheduled_time:
            event['time'] = job.scheduled_time.strftime('%H:%M')
        if job.estimated_duration:
            event['duration'] = str(job.estimated_duration)
        events.append(event)

    return JsonResponse(events, safe=False)


# ===================================
# INVOICE VIEWS
# ===================================

@staff_member_required
def create_invoice(request, job_id):
    """Create an invoice for a job"""
    from decimal import Decimal
    from datetime import date, timedelta

    job = get_object_or_404(Job, id=job_id)

    # Check if invoice already exists
    if hasattr(job, 'invoice'):
        messages.info(request, f"Invoice {job.invoice.invoice_number} already exists for this job.")
        return redirect('download_invoice', invoice_id=job.invoice.id)

    # Calculate amounts
    subtotal = job.estimate_amount or Decimal('0.00')
    hst_amount = subtotal * Decimal('0.13')
    total = subtotal + hst_amount

    # Create invoice
    invoice = Invoice.objects.create(
        job=job,
        subtotal=subtotal,
        hst_amount=hst_amount,
        total=total,
        due_date=date.today() + timedelta(days=30),
        notes="Payment due within 30 days."
    )

    messages.success(request, f"Invoice {invoice.invoice_number} created successfully!")
    return redirect('download_invoice', invoice_id=invoice.id)


@staff_member_required
def download_invoice(request, invoice_id):
    """Download invoice as PDF"""
    from .invoice_pdf import generate_invoice_pdf

    invoice = get_object_or_404(Invoice, id=invoice_id)

    # Generate PDF
    pdf_content = generate_invoice_pdf(invoice)

    # Create response
    response = HttpResponse(pdf_content, content_type='application/pdf')
    filename = f"Invoice_{invoice.invoice_number}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@staff_member_required
def view_invoice(request, invoice_id):
    """View invoice in browser (inline PDF)"""
    from .invoice_pdf import generate_invoice_pdf

    invoice = get_object_or_404(Invoice, id=invoice_id)

    # Generate PDF
    pdf_content = generate_invoice_pdf(invoice)

    # Create response - inline displays in browser
    response = HttpResponse(pdf_content, content_type='application/pdf')
    filename = f"Invoice_{invoice.invoice_number}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    return response


# ===================================
# PWA OFFLINE VIEW
# ===================================

def offline_view(request):
    """Offline fallback page for PWA"""
    return render(request, 'management/offline.html')


def service_worker(request):
    """Serve service worker from root path for proper scope"""
    import os
    from django.conf import settings

    sw_path = os.path.join(
        settings.BASE_DIR,
        'management/static/management/sw.js'
    )

    with open(sw_path, 'r') as f:
        sw_content = f.read()

    return HttpResponse(sw_content, content_type='application/javascript')


@login_required
def pending_timesheets(request):
    """Page to view and manage offline pending timesheets"""
    return render(request, 'management/pending_timesheets.html')


@login_required
def get_job_distance(request, job_id):
    """API endpoint to get the calculated distance for a job"""
    try:
        worker = request.user.worker
    except Worker.DoesNotExist:
        return JsonResponse({'error': 'Worker not found'}, status=404)

    # Verify job is assigned to this worker
    job = get_object_or_404(Job, id=job_id, assigned_workers=worker)

    # If distance not calculated yet, try to calculate it
    if job.calculated_distance_km is None:
        distance = job.calculate_distance()
        if distance:
            job.calculated_distance_km = distance
            job.save()

    return JsonResponse({
        'job_id': job.id,
        'distance_km': float(job.calculated_distance_km) if job.calculated_distance_km else None,
        'client_address': job.client.address
    })


# ===================================
# PURCHASE LIST VIEWS
# ===================================

@login_required
def purchase_list(request):
    """View the team shopping/purchase list"""
    # Get items split by status
    needed_items = PurchaseListItem.objects.filter(status='needed')
    purchased_items = PurchaseListItem.objects.filter(status='purchased').order_by('-purchased_at')[:20]

    context = {
        'needed_items': needed_items,
        'purchased_items': purchased_items,
    }
    return render(request, 'management/purchase_list.html', context)


@login_required
def add_purchase_item(request):
    """Add item to the purchase list"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        quantity = request.POST.get('quantity', '').strip()
        priority = request.POST.get('priority', 'medium')
        notes = request.POST.get('notes', '').strip()

        if name:
            PurchaseListItem.objects.create(
                name=name,
                quantity=quantity,
                priority=priority,
                notes=notes,
                added_by=request.user
            )
            messages.success(request, f'"{name}" added to purchase list!')
        else:
            messages.error(request, 'Please enter an item name.')

    return redirect('purchase_list')


@login_required
def mark_item_purchased(request, item_id):
    """Mark an item as purchased"""
    from django.utils import timezone

    item = get_object_or_404(PurchaseListItem, id=item_id)
    item.status = 'purchased'
    item.purchased_by = request.user
    item.purchased_at = timezone.now()
    item.save()

    messages.success(request, f'"{item.name}" marked as purchased!')
    return redirect('purchase_list')


@login_required
def delete_purchase_item(request, item_id):
    """Delete an item from the purchase list"""
    item = get_object_or_404(PurchaseListItem, id=item_id)
    item_name = item.name
    item.delete()

    messages.success(request, f'"{item_name}" removed from list.')
    return redirect('purchase_list')


# ===================================
# JOB INSPECTION VIEWS
# ===================================

@login_required
def job_inspections(request, job_id):
    """View inspections for a specific job"""
    try:
        worker = request.user.worker
    except Worker.DoesNotExist:
        if not request.user.is_staff:
            return render(request, 'management/error.html', {'message': 'Worker profile not found.'})
        worker = None

    job = get_object_or_404(Job, id=job_id)

    # Workers can only view jobs they're assigned to
    if worker and not request.user.is_staff:
        if not job.assigned_workers.filter(id=worker.id).exists():
            return HttpResponseForbidden("You are not assigned to this job.")

    pre_inspection = job.inspections.filter(inspection_type='pre').first()
    post_inspection = job.inspections.filter(inspection_type='post').first()

    context = {
        'job': job,
        'pre_inspection': pre_inspection,
        'post_inspection': post_inspection,
    }
    return render(request, 'management/job_inspections.html', context)


@login_required
def create_inspection(request, job_id, inspection_type):
    """Create a new pre or post inspection"""
    from django.utils import timezone

    try:
        worker = request.user.worker
    except Worker.DoesNotExist:
        return render(request, 'management/error.html', {'message': 'Worker profile not found.'})

    job = get_object_or_404(Job, id=job_id)

    # Verify worker is assigned to job
    if not request.user.is_staff and not job.assigned_workers.filter(id=worker.id).exists():
        return HttpResponseForbidden("You are not assigned to this job.")

    # Check if inspection already exists
    existing = job.inspections.filter(inspection_type=inspection_type).first()
    if existing:
        messages.info(request, f'{inspection_type.title()}-inspection already exists. Redirecting to edit.')
        return redirect('edit_inspection', inspection_id=existing.id)

    if request.method == 'POST':
        # Create the inspection
        inspection = JobInspection.objects.create(
            job=job,
            inspection_type=inspection_type,
            inspector=worker,
            inspection_date=request.POST.get('inspection_date', timezone.now().date()),
            inspection_time=request.POST.get('inspection_time') or None,
            status=request.POST.get('status', 'draft'),
            site_conditions=request.POST.get('site_conditions', ''),
            safety_hazards=request.POST.get('safety_hazards', ''),
            notes=request.POST.get('notes', ''),
            client_present=request.POST.get('client_present') == 'on',
            access_issues=request.POST.get('access_issues', ''),
            existing_damage=request.POST.get('existing_damage', ''),
            work_completed=request.POST.get('work_completed', ''),
            quality_check_passed=request.POST.get('quality_check_passed', 'on') == 'on',
            client_satisfied=request.POST.get('client_satisfied') == 'on' if request.POST.get('client_satisfied') else None,
            followup_required=request.POST.get('followup_required') == 'on',
            followup_notes=request.POST.get('followup_notes', ''),
            client_name_signed=request.POST.get('client_name_signed', ''),
            client_signature=request.POST.get('client_signature', ''),
        )

        # Handle photo uploads
        photos = request.FILES.getlist('photos')
        for photo in photos:
            InspectionPhoto.objects.create(
                inspection=inspection,
                image=photo,
                caption=''
            )

        messages.success(request, f'{inspection_type.title()}-inspection created successfully!')
        return redirect('job_inspections', job_id=job.id)

    context = {
        'job': job,
        'inspection_type': inspection_type,
        'today': timezone.now().date(),
    }
    return render(request, 'management/create_inspection.html', context)


@login_required
def edit_inspection(request, inspection_id):
    """Edit an existing inspection"""
    from django.utils import timezone

    inspection = get_object_or_404(JobInspection, id=inspection_id)
    job = inspection.job

    try:
        worker = request.user.worker
    except Worker.DoesNotExist:
        if not request.user.is_staff:
            return render(request, 'management/error.html', {'message': 'Worker profile not found.'})
        worker = None

    # Authorization check
    if worker and not request.user.is_staff:
        if not job.assigned_workers.filter(id=worker.id).exists():
            return HttpResponseForbidden("You are not assigned to this job.")

    if request.method == 'POST':
        inspection.inspection_date = request.POST.get('inspection_date', inspection.inspection_date)
        inspection.inspection_time = request.POST.get('inspection_time') or None
        inspection.status = request.POST.get('status', 'draft')
        inspection.site_conditions = request.POST.get('site_conditions', '')
        inspection.safety_hazards = request.POST.get('safety_hazards', '')
        inspection.notes = request.POST.get('notes', '')
        inspection.client_present = request.POST.get('client_present') == 'on'
        inspection.access_issues = request.POST.get('access_issues', '')
        inspection.existing_damage = request.POST.get('existing_damage', '')
        inspection.work_completed = request.POST.get('work_completed', '')
        inspection.quality_check_passed = request.POST.get('quality_check_passed', 'on') == 'on'
        inspection.client_satisfied = request.POST.get('client_satisfied') == 'on' if request.POST.get('client_satisfied') else None
        inspection.followup_required = request.POST.get('followup_required') == 'on'
        inspection.followup_notes = request.POST.get('followup_notes', '')
        inspection.client_name_signed = request.POST.get('client_name_signed', '')
        inspection.client_signature = request.POST.get('client_signature', '')
        inspection.save()

        # Handle new photo uploads
        photos = request.FILES.getlist('photos')
        for photo in photos:
            InspectionPhoto.objects.create(
                inspection=inspection,
                image=photo,
                caption=''
            )

        messages.success(request, 'Inspection updated successfully!')
        return redirect('job_inspections', job_id=job.id)

    context = {
        'job': job,
        'inspection': inspection,
        'inspection_type': inspection.inspection_type,
    }
    return render(request, 'management/edit_inspection.html', context)


@login_required
def view_inspection(request, inspection_id):
    """View a completed inspection"""
    inspection = get_object_or_404(JobInspection, id=inspection_id)
    job = inspection.job

    try:
        worker = request.user.worker
    except Worker.DoesNotExist:
        if not request.user.is_staff:
            return render(request, 'management/error.html', {'message': 'Worker profile not found.'})
        worker = None

    # Authorization check
    if worker and not request.user.is_staff:
        if not job.assigned_workers.filter(id=worker.id).exists():
            return HttpResponseForbidden("You are not assigned to this job.")

    context = {
        'job': job,
        'inspection': inspection,
        'photos': inspection.photos.all(),
    }
    return render(request, 'management/view_inspection.html', context)


@login_required
def delete_inspection_photo(request, photo_id):
    """Delete a photo from an inspection"""
    photo = get_object_or_404(InspectionPhoto, id=photo_id)
    inspection = photo.inspection
    job = inspection.job

    try:
        worker = request.user.worker
    except Worker.DoesNotExist:
        if not request.user.is_staff:
            return JsonResponse({'error': 'Worker not found'}, status=404)
        worker = None

    # Authorization
    if worker and not request.user.is_staff:
        if not job.assigned_workers.filter(id=worker.id).exists():
            return JsonResponse({'error': 'Not authorized'}, status=403)

    photo.delete()
    messages.success(request, 'Photo deleted.')
    return redirect('edit_inspection', inspection_id=inspection.id)
