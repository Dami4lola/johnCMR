"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from management.views import submit_timesheet
from django.contrib.auth import views as auth_views
from management.views import (
    submit_timesheet, register, manager_dashboard, welcome, custom_logout,
    worker_calendar, calendar_events_json, create_invoice, download_invoice, view_invoice,
    offline_view, service_worker, pending_timesheets, get_job_distance,
    purchase_list, add_purchase_item, mark_item_purchased, delete_purchase_item,
    job_inspections, create_inspection, edit_inspection, view_inspection, delete_inspection_photo
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('accounts/login/', auth_views.LoginView.as_view(template_name='management/login.html'), name='login'),
    path('accounts/logout/', custom_logout, name='logout'),
    path('register/', register, name='register'),

    # PAGES
    path('', welcome, name='welcome'),
    path('dashboard/', submit_timesheet, name='submit_timesheet'),
    path('manager/', manager_dashboard, name='manager_dashboard'),

    # Calendar
    path('calendar/', worker_calendar, name='worker_calendar'),
    path('api/calendar-events/', calendar_events_json, name='calendar_events'),
    path('api/job-distance/<int:job_id>/', get_job_distance, name='get_job_distance'),

    # Invoices
    path('invoice/create/<int:job_id>/', create_invoice, name='create_invoice'),
    path('invoice/download/<int:invoice_id>/', download_invoice, name='download_invoice'),
    path('invoice/view/<int:invoice_id>/', view_invoice, name='view_invoice'),

    # PWA
    path('offline/', offline_view, name='offline'),
    path('sw.js', service_worker, name='service_worker'),
    path('pending/', pending_timesheets, name='pending_timesheets'),

    # Purchase List
    path('purchase-list/', purchase_list, name='purchase_list'),
    path('purchase-list/add/', add_purchase_item, name='add_purchase_item'),
    path('purchase-list/purchased/<int:item_id>/', mark_item_purchased, name='mark_item_purchased'),
    path('purchase-list/delete/<int:item_id>/', delete_purchase_item, name='delete_purchase_item'),

    # Job Inspections
    path('job/<int:job_id>/inspections/', job_inspections, name='job_inspections'),
    path('job/<int:job_id>/inspection/<str:inspection_type>/create/', create_inspection, name='create_inspection'),
    path('inspection/<int:inspection_id>/edit/', edit_inspection, name='edit_inspection'),
    path('inspection/<int:inspection_id>/view/', view_inspection, name='view_inspection'),
    path('inspection/photo/<int:photo_id>/delete/', delete_inspection_photo, name='delete_inspection_photo'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

