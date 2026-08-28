# MailingLists app URLs

from django.urls import path
from . import views

app_name = 'mailinglists'

urlpatterns = [
    # Mailing list list view
    path('', views.MailingListListView.as_view(), name='list'),
    
    # Create mailing list
    path('create/', views.MailingListCreateView.as_view(), name='create'),
    
    # Detail view
    path('<int:pk>/', views.MailingListDetailView.as_view(), name='detail'),
    
    # Update mailing list
    path('<int:pk>/edit/', views.MailingListUpdateView.as_view(), name='edit'),
    
    # Delete mailing list
    path('<int:pk>/delete/', views.MailingListDeleteView.as_view(), name='delete'),
    
    # SMTP configuration
    path('<int:mailinglist_pk>/smtp/create/', views.SmtpConfigCreateView.as_view(), name='smtp_create'),
    path('smtp/<int:pk>/edit/', views.SmtpConfigUpdateView.as_view(), name='smtp_edit'),
    
    # Manage access
    path('<int:pk>/access/', views.manage_access_view, name='manage_access'),
]