# Recipients app URLs

from django.urls import path
from . import views

app_name = 'recipients'

urlpatterns = [
    # Recipient list view
    path('', views.RecipientListView.as_view(), name='list'),
    
    # Create recipient
    path('create/', views.RecipientCreateView.as_view(), name='create'),
    
    # Detail view
    path('<int:pk>/', views.RecipientDetailView.as_view(), name='detail'),
    
    # Update recipient
    path('<int:pk>/edit/', views.RecipientUpdateView.as_view(), name='edit'),
    
    # Delete recipient
    path('<int:pk>/delete/', views.RecipientDeleteView.as_view(), name='delete'),
    
    # Import recipients from CSV
    path('import/', views.import_recipients_view, name='import'),
    
    # Export recipients to CSV
    path('export/', views.export_recipients_view, name='export'),
    
    # Manage recipient's mailing lists
    path('<int:pk>/mailing-lists/', views.manage_recipient_mailing_lists_view, name='manage_mailing_lists'),
]
