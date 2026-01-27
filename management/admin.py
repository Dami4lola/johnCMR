from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Client, Worker, Job, Timesheet, Invoice, Receipt
from simple_history.admin import SimpleHistoryAdmin
# Register your models here.


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'email', 'address')
    search_fields = ('name', 'phone_number', 'email')
    fields = ('name', 'phone_number', 'email', 'address')

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('client', 'description_preview', 'scheduled_date', 'scheduled_time', 'is_completed', 'workers_assigned', 'invoice_link')
    list_filter = ('is_completed', 'client', 'scheduled_date')
    search_fields = ('client__name', 'description')
    filter_horizontal = ('assigned_workers',)
    date_hierarchy = 'scheduled_date'
    actions = ['generate_invoices']
    fieldsets = (
        ('Job Information', {
            'fields': ('client', 'description', 'estimate_amount')
        }),
        ('Scheduling', {
            'fields': ('scheduled_date', 'scheduled_time', 'estimated_duration')
        }),
        ('Assignment', {
            'fields': ('assigned_workers', 'is_completed')
        }),
    )

    def description_preview(self, obj):
        return obj.description[:75] + '...' if len(obj.description) > 75 else obj.description
    description_preview.short_description = 'Description'

    def workers_assigned(self, obj):
        return ", ".join([w.name for w in obj.assigned_workers.all()]) or "None"
    workers_assigned.short_description = 'Workers'

    def invoice_link(self, obj):
        """Show invoice status with link"""
        if hasattr(obj, 'invoice'):
            invoice = obj.invoice
            view_url = reverse('view_invoice', args=[invoice.id])
            download_url = reverse('download_invoice', args=[invoice.id])
            return format_html(
                '<a href="{}" target="_blank">{}</a> '
                '(<a href="{}">PDF</a>)',
                view_url, invoice.invoice_number, download_url
            )
        else:
            create_url = reverse('create_invoice', args=[obj.id])
            return format_html('<a href="{}" class="button">Create Invoice</a>', create_url)
    invoice_link.short_description = 'Invoice'

    def generate_invoices(self, request, queryset):
        """Generate invoices for selected jobs"""
        from decimal import Decimal
        from datetime import date, timedelta

        created = 0
        skipped = 0

        for job in queryset:
            if hasattr(job, 'invoice'):
                skipped += 1
                continue

            subtotal = job.estimate_amount or Decimal('0.00')
            hst_amount = subtotal * Decimal('0.13')
            total = subtotal + hst_amount

            Invoice.objects.create(
                job=job,
                subtotal=subtotal,
                hst_amount=hst_amount,
                total=total,
                due_date=date.today() + timedelta(days=30),
                notes="Payment due within 30 days."
            )
            created += 1

        self.message_user(
            request,
            f'Created {created} invoice(s). Skipped {skipped} job(s) that already have invoices.'
        )
    generate_invoices.short_description = 'Generate invoices for selected jobs'

@admin.register(Worker)
class WorkerAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'user', 'hourly_rate', 'charges_hst', 'is_employee')
    list_filter = ('charges_hst', 'is_employee')
    search_fields = ('name', 'user__username')
    history_list_display = ['hourly_rate', 'charges_hst']  # Show these fields in history

class ReceiptInline(admin.TabularInline):
    """Inline display of receipts on timesheet admin"""
    model = Receipt
    extra = 0
    readonly_fields = ('image_preview', 'uploaded_at')
    fields = ('image_preview', 'image', 'description', 'amount', 'uploaded_at')

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-height: 80px; max-width: 120px;" />'
                '</a>',
                obj.image.url, obj.image.url
            )
        return "-"
    image_preview.short_description = 'Preview'


@admin.register(Timesheet)
class TimesheetAdmin(SimpleHistoryAdmin):
    list_display = ('date', 'worker', 'job', 'hours_worked', 'total_materials', 'calculated_pay', 'receipt_count', 'receipt_thumbnails')
    list_filter = ('worker', 'date', 'job')
    readonly_fields = ('calculated_pay', 'receipt_gallery')
    actions = ['recalculate_payments']
    history_list_display = ['hours_worked', 'calculated_pay', 'company_materials', 'personal_materials', 'receipts_total']
    inlines = [ReceiptInline]

    fieldsets = (
        ('Timesheet Info', {
            'fields': ('worker', 'job', 'date', 'hours_worked', 'round_trip_kms')
        }),
        ('Options', {
            'fields': ('used_company_truck', 'worked_at_hq')
        }),
        ('Expenses', {
            'fields': ('company_materials', 'personal_materials', 'receipts_total', 'receipt_card_digits')
        }),
        ('Calculated', {
            'fields': ('calculated_pay',)
        }),
        ('Uploaded Receipts', {
            'fields': ('receipt_gallery',),
            'description': 'Photos of receipts submitted with this timesheet'
        }),
    )

    def total_materials(self, obj):
        return obj.company_materials + obj.personal_materials
    total_materials.short_description = 'Materials'

    def receipt_count(self, obj):
        count = obj.receipts.count()
        if count > 0:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 3px 8px; border-radius: 10px;">{}</span>',
                count
            )
        return format_html(
            '<span style="color: #999;">0</span>'
        )
    receipt_count.short_description = 'Receipts'

    def receipt_thumbnails(self, obj):
        receipts = obj.receipts.all()[:3]  # Show first 3 thumbnails
        if not receipts:
            return "-"

        html = '<div style="display: flex; gap: 5px;">'
        for receipt in receipts:
            if receipt.image:
                html += format_html(
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="height: 40px; width: 40px; object-fit: cover; border-radius: 4px;" />'
                    '</a>',
                    receipt.image.url, receipt.image.url
                )

        total = obj.receipts.count()
        if total > 3:
            html += f'<span style="padding: 10px; color: #666;">+{total - 3} more</span>'

        html += '</div>'
        return format_html(html)
    receipt_thumbnails.short_description = 'Preview'

    def receipt_gallery(self, obj):
        """Large gallery view of all receipts for the detail page"""
        receipts = obj.receipts.all()
        if not receipts:
            return "No receipts uploaded"

        html = '<div style="display: flex; flex-wrap: wrap; gap: 15px; padding: 10px;">'
        for receipt in receipts:
            if receipt.image:
                desc = receipt.description or "No description"
                amt = f"${receipt.amount}" if receipt.amount else "No amount"
                html += format_html(
                    '<div style="text-align: center; border: 1px solid #ddd; padding: 10px; border-radius: 8px;">'
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="max-height: 150px; max-width: 200px; border-radius: 4px;" />'
                    '</a>'
                    '<div style="margin-top: 8px; font-size: 12px;">'
                    '<strong>{}</strong><br/>{}'
                    '</div>'
                    '</div>',
                    receipt.image.url, receipt.image.url, desc, amt
                )
        html += '</div>'
        return format_html(html)
    receipt_gallery.short_description = 'Receipt Images'

    def recalculate_payments(self, request, queryset):
        """Recalculate payments for selected timesheets based on current worker rates"""
        updated = 0
        for timesheet in queryset:
            old_pay = timesheet.calculated_pay
            timesheet.calculated_pay = timesheet.calculate_payout()
            timesheet.save()
            updated += 1

        self.message_user(
            request,
            f'Successfully recalculated {updated} timesheet(s) based on current worker rates.'
        )
    recalculate_payments.short_description = 'Recalculate payments for selected timesheets'


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'job_client', 'created_date', 'due_date', 'total', 'status', 'pdf_links')
    list_filter = ('status', 'created_date')
    search_fields = ('invoice_number', 'job__client__name')
    readonly_fields = ('invoice_number', 'created_date')
    date_hierarchy = 'created_date'

    fieldsets = (
        ('Invoice Details', {
            'fields': ('invoice_number', 'job', 'created_date', 'due_date', 'status')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'hst_amount', 'total')
        }),
        ('Additional Info', {
            'fields': ('notes',)
        }),
    )

    def job_client(self, obj):
        return obj.job.client.name
    job_client.short_description = 'Client'

    def pdf_links(self, obj):
        view_url = reverse('view_invoice', args=[obj.id])
        download_url = reverse('download_invoice', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank">View</a> | '
            '<a href="{}">Download</a>',
            view_url, download_url
        )
    pdf_links.short_description = 'PDF'


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('timesheet', 'description', 'amount', 'image_preview', 'uploaded_at')
    list_filter = ('timesheet__worker', 'uploaded_at')
    search_fields = ('description', 'timesheet__worker__name')
    readonly_fields = ('image_preview_large', 'uploaded_at')

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 40px;" />',
                obj.image.url
            )
        return "-"
    image_preview.short_description = 'Preview'

    def image_preview_large(self, obj):
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-height: 300px;" />'
                '</a>',
                obj.image.url, obj.image.url
            )
        return "-"
    image_preview_large.short_description = 'Image'