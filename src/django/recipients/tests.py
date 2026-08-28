# Recipients app tests
# AD-005: Recipient uniqueness by (first_name, last_name, email)
# AD-006: Users and Recipients are separate models

from django.test import TestCase
from django.contrib.auth.models import User, Group
from .models import Recipient
from mailinglists.models import MailingList


class RecipientModelTest(TestCase):
    """Test cases for the Recipient model."""
    
    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        # Create admin group and add user to it
        admin_group = Group.objects.create(name='Admin')
        self.user.groups.add(admin_group)
        
        # Create mailing list
        self.mailing_list = MailingList.objects.create(
            name='Test Mailing List',
            description='Test description',
            created_by=self.user
        )
    
    def test_recipient_creation(self):
        """Test creating a recipient."""
        recipient = Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            created_by=self.user
        )
        
        self.assertEqual(recipient.first_name, 'John')
        self.assertEqual(recipient.last_name, 'Doe')
        self.assertEqual(recipient.email, 'john.doe@example.com')
        self.assertEqual(recipient.created_by, self.user)
        self.assertEqual(str(recipient), 'John Doe <john.doe@example.com>')
    
    def test_recipient_full_name(self):
        """Test the get_full_name method."""
        recipient = Recipient.objects.create(
            first_name='Jane',
            last_name='Smith',
            email='jane.smith@example.com',
            created_by=self.user
        )
        
        self.assertEqual(recipient.get_full_name(), 'Jane Smith')
    
    def test_recipient_uniqueness_constraint(self):
        """Test that recipient uniqueness is enforced by (first_name, last_name, email)."""
        # Create first recipient
        Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            created_by=self.user
        )
        
        # Try to create duplicate - should raise IntegrityError
        with self.assertRaises(Exception):
            Recipient.objects.create(
                first_name='John',
                last_name='Doe',
                email='john.doe@example.com',
                created_by=self.user
            )
    
    def test_same_email_different_names(self):
        """Test that same email with different names is allowed."""
        # Create first recipient
        Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            created_by=self.user
        )
        
        # Create second recipient with same email but different name - should work
        recipient2 = Recipient.objects.create(
            first_name='Jane',
            last_name='Doe',
            email='john@example.com',
            created_by=self.user
        )
        
        self.assertEqual(recipient2.email, 'john@example.com')
    
    def test_recipient_mailing_lists_relationship(self):
        """Test the many-to-many relationship with MailingList."""
        recipient = Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            created_by=self.user
        )
        
        # Add recipient to mailing list
        recipient.mailing_lists.add(self.mailing_list)
        
        self.assertEqual(recipient.mailing_lists.count(), 1)
        self.assertIn(self.mailing_list, recipient.mailing_lists.all())
        
        # Check reverse relationship
        self.assertEqual(self.mailing_list.recipients.count(), 1)
        self.assertIn(recipient, self.mailing_list.recipients.all())
    
    def test_recipient_ordering(self):
        """Test that recipients are ordered correctly."""
        # Create recipients in random order
        Recipient.objects.create(
            first_name='Charlie',
            last_name='Brown',
            email='charlie@example.com',
            created_by=self.user
        )
        Recipient.objects.create(
            first_name='Alice',
            last_name='Anderson',
            email='alice@example.com',
            created_by=self.user
        )
        Recipient.objects.create(
            first_name='Bob',
            last_name='Smith',
            email='bob@example.com',
            created_by=self.user
        )
        
        # Get all recipients
        recipients = Recipient.objects.all()
        
        # Should be ordered by last_name, then first_name, then email
        self.assertEqual(recipients[0].last_name, 'Anderson')
        self.assertEqual(recipients[1].last_name, 'Brown')
        self.assertEqual(recipients[2].last_name, 'Smith')


class RecipientFormTest(TestCase):
    """Test cases for recipient forms."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        admin_group = Group.objects.create(name='Admin')
        self.user.groups.add(admin_group)
        
        self.mailing_list = MailingList.objects.create(
            name='Test Mailing List',
            created_by=self.user
        )
    
    def test_recipient_form_valid_data(self):
        """Test form with valid data."""
        from .forms import RecipientForm
        
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'mailing_lists': [self.mailing_list.pk]
        }
        
        form = RecipientForm(data=form_data, user=self.user)
        
        self.assertTrue(form.is_valid())
    
    def test_recipient_form_invalid_email(self):
        """Test form with invalid email."""
        from .forms import RecipientForm
        
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'invalid-email',
            'mailing_lists': []
        }
        
        form = RecipientForm(data=form_data, user=self.user)
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_recipient_form_duplicate(self):
        """Test form with duplicate recipient."""
        from .forms import RecipientForm
        
        # Create existing recipient
        Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            created_by=self.user
        )
        
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'mailing_lists': []
        }
        
        form = RecipientForm(data=form_data, user=self.user)
        
        self.assertFalse(form.is_valid())


class RecipientViewTest(TestCase):
    """Test cases for recipient views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User',
            password='testpass123'
        )
        
        admin_group = Group.objects.create(name='Admin')
        self.user.groups.add(admin_group)
        
        self.mailing_list = MailingList.objects.create(
            name='Test Mailing List',
            created_by=self.user
        )
        
        self.recipient = Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            created_by=self.user
        )
        self.recipient.mailing_lists.add(self.mailing_list)
    
    def test_recipient_list_view(self):
        """Test the recipient list view."""
        self.client.login(username='test@example.com', password='testpass123')
        
        response = self.client.get('/recipients/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Doe')
        self.assertContains(response, 'john.doe@example.com')
    
    def test_recipient_create_view(self):
        """Test creating a recipient."""
        self.client.login(username='test@example.com', password='testpass123')
        
        response = self.client.post('/recipients/create/', {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane.smith@example.com',
            'mailing_lists': [self.mailing_list.pk]
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that recipient was created
        self.assertTrue(Recipient.objects.filter(email='jane.smith@example.com').exists())
    
    def test_recipient_detail_view(self):
        """Test the recipient detail view."""
        self.client.login(username='test@example.com', password='testpass123')
        
        response = self.client.get(f'/recipients/{self.recipient.pk}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Doe')
        self.assertContains(response, 'john.doe@example.com')
    
    def test_recipient_export_view(self):
        """Test exporting recipients to CSV."""
        self.client.login(username='test@example.com', password='testpass123')
        
        response = self.client.get('/recipients/export/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('John', response.content.decode())
        self.assertIn('Doe', response.content.decode())
        self.assertIn('john.doe@example.com', response.content.decode())
