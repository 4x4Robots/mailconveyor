# Emails app URLs

from django.urls import path
from . import views

app_name = 'emails'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.email_dashboard_view, name='dashboard'),
    
    # Email Templates
    path('templates/', views.EmailTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.EmailTemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/', views.EmailTemplateDetailView.as_view(), name='template_detail'),
    path('templates/<int:pk>/edit/', views.EmailTemplateUpdateView.as_view(), name='template_edit'),
    path('templates/<int:pk>/delete/', views.EmailTemplateDeleteView.as_view(), name='template_delete'),
    
    # Emails
    path('', views.EmailListView.as_view(), name='list'),
    path('create/', views.EmailCreateView.as_view(), name='create'),
    path('<int:pk>/', views.EmailDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.EmailUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.EmailDeleteView.as_view(), name='delete'),
    path('<int:pk>/send/', views.email_send_view, name='send'),
    
    # Email Attachments
    path('<int:email_pk>/attachments/add/', views.EmailAttachmentCreateView.as_view(), name='attachment_create'),
    path('attachments/<int:pk>/delete/', views.EmailAttachmentDeleteView.as_view(), name='attachment_delete'),
    
    # Queue Management
    path('queue/', views.EmailQueueListView.as_view(), name='queue_list'),
    path('queue/process/', views.process_queue_view, name='process_queue'),
    path('queue/retry/', views.retry_failed_view, name='retry_failed'),
    
    # Logs
    path('logs/', views.EmailLogListView.as_view(), name='log_list'),
    path('logs/<int:email_pk>/', views.EmailLogListView.as_view(), name='email_logs'),
    
    # AJAX endpoints
    path('api/queue/status/', views.queue_status_view, name='queue_status'),
]
