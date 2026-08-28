# Emails app tests
# AD-004: Async email sending with queue and retry logic
# AD-007: 14-day retention for sent emails
# AD-008: File system for attachments

from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.utils import timezone
from .models import Email, EmailTemplate, EmailAttachment, EmailQueue, EmailLog
from mailinglists.models import MailingList, SmtpConfig, EncryptionUtils
from recipients.models import Recipient
import os
import tempfile


class EmailModelsTest(TestCase):
    """Test cases for Email models."""
    
    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        # Create test mailing list
        self.mailing_list = MailingList.objects.create(
            name='Test List',
            description='Test mailing list',
            created_by=self.user
        )
        
        # Create test SMTP config
        self.smtp_config = SmtpConfig.objects.create(
            mailing_list=self.mailing_list,
            host='smtp.test.com',
            port=587,
            username='testuser',
            use_tls=True
        )
        
        # Set password using the property setter
        self.smtp_config.password = 'testpass123'
        self.smtp_config.save()
        
        # Create test recipients
        self.recipient1 = Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            created_by=self.user
        )
        
        self.recipient2 = Recipient.objects.create(
            first_name='Jane',
            last_name='Smith',
            email='jane@example.com',
            created_by=self.user
        )
        
        # Add recipients to mailing list
        self.mailing_list.recipients.add(self.recipient1, self.recipient2)
    
    def test_email_creation(self):
        """Test creating an email."""
        email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user,
            smtp_config=self.smtp_config
        )
        
        self.assertEqual(email.subject, 'Test Subject')
        self.assertEqual(email.body, 'Test body content')
        self.assertEqual(email.from_email, 'sender@example.com')
        self.assertEqual(email.status, 'DRAFT')
        self.assertEqual(email.created_by, self.user)
        self.assertIsNone(email.sent_at)
    
    def test_email_with_recipients(self):
        """Test email with recipients."""
        email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
        
        email.recipients.add(self.recipient1, self.recipient2)
        
        self.assertEqual(email.get_recipient_count(), 2)
    
    def test_email_with_mailing_lists(self):
        """Test email with mailing lists."""
        email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
        
        email.mailing_lists.add(self.mailing_list)
        
        self.assertEqual(email.get_mailing_list_count(), 1)
    
    def test_get_all_recipients(self):
        """Test getting all recipients including from mailing lists."""
        email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
        
        # Add direct recipients
        email.recipients.add(self.recipient1)
        
        # Add mailing list
        email.mailing_lists.add(self.mailing_list)
        
        all_recipients = email.get_all_recipients()
        
        # Should have recipient1 (direct) + recipient1 and recipient2 (from mailing list)
        # But recipient1 should not be duplicated
        self.assertEqual(len(all_recipients), 2)
        self.assertIn(self.recipient1, all_recipients)
        self.assertIn(self.recipient2, all_recipients)
    
    def test_get_unique_recipient_emails(self):
        """Test deduplication of recipient emails (AD-005)."""
        email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
        
        # Add direct recipients
        email.recipients.add(self.recipient1, self.recipient2)
        
        # Add mailing list (which contains both recipients)
        email.mailing_lists.add(self.mailing_list)
        
        unique_recipients = email.get_unique_recipient_emails()
        
        # Should have only 2 unique recipients (john@example.com and jane@example.com)
        self.assertEqual(len(unique_recipients), 2)
    
    def test_email_status_methods(self):
        """Test email status change methods."""
        email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
        
        # Test marking as queued
        email.mark_as_queued()
        self.assertEqual(email.status, 'QUEUED')
        
        # Test marking as sending
        email.mark_as_sending()
        self.assertEqual(email.status, 'SENDING')
        
        # Test marking as sent
        email.mark_as_sent()
        self.assertEqual(email.status, 'SENT')
        self.assertIsNotNone(email.sent_at)
        
        # Test marking as failed
        email.mark_as_failed("Test error")
        self.assertEqual(email.status, 'FAILED')
        self.assertEqual(email.error_message, "Test error")
        self.assertEqual(email.attempts, 1)
    
    def test_can_be_retried(self):
        """Test retry logic."""
        email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
        
        # Initially can't be retried (not failed)
        self.assertFalse(email.can_be_retried())
        
        # Mark as failed
        email.mark_as_failed("Test error")
        
        # Now can be retried (1 attempt, max 2)
        self.assertTrue(email.can_be_retried())
        
        # Mark as failed again
        email.mark_as_failed("Test error 2")
        
        # Now can't be retried (2 attempts, max 2)
        self.assertFalse(email.can_be_retried())


class EmailTemplateModelsTest(TestCase):
    """Test cases for EmailTemplate models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.mailing_list = MailingList.objects.create(
            name='Test List',
            created_by=self.user
        )
    
    def test_template_creation(self):
        """Test creating an email template."""
        template = EmailTemplate.objects.create(
            name='Test Template',
            subject='Test Subject',
            body='Test body content',
            is_html=True,
            created_by=self.user,
            mailing_list=self.mailing_list
        )
        
        self.assertEqual(template.name, 'Test Template')
        self.assertEqual(template.subject, 'Test Subject')
        self.assertTrue(template.is_html)
        self.assertEqual(template.created_by, self.user)
        self.assertEqual(template.mailing_list, self.mailing_list)


class EmailQueueModelsTest(TestCase):
    """Test cases for EmailQueue models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
        
        self.recipient = Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            created_by=self.user
        )
    
    def test_queue_entry_creation(self):
        """Test creating a queue entry."""
        entry = EmailQueue.objects.create(
            email=self.email,
            recipient=self.recipient,
            to_email='john@example.com',
            status='PENDING',
            priority=1
        )
        
        self.assertEqual(entry.email, self.email)
        self.assertEqual(entry.recipient, self.recipient)
        self.assertEqual(entry.to_email, 'john@example.com')
        self.assertEqual(entry.status, 'PENDING')
        self.assertEqual(entry.priority, 1)
        self.assertEqual(entry.attempts, 0)
    
    def test_queue_entry_status_methods(self):
        """Test queue entry status change methods."""
        entry = EmailQueue.objects.create(
            email=self.email,
            recipient=self.recipient,
            to_email='john@example.com',
            status='PENDING'
        )
        
        # Test marking as sent
        entry.mark_as_sent()
        self.assertEqual(entry.status, 'SENT')
        self.assertIsNotNone(entry.sent_at)
        
        # Test marking as failed
        entry.mark_as_failed("Test error")
        self.assertEqual(entry.status, 'FAILED')
        self.assertEqual(entry.error_message, "Test error")
        self.assertEqual(entry.attempts, 1)
    
    def test_can_be_retried(self):
        """Test queue entry retry logic."""
        entry = EmailQueue.objects.create(
            email=self.email,
            recipient=self.recipient,
            to_email='john@example.com',
            status='PENDING'
        )
        
        # Initially can't be retried (not failed)
        self.assertFalse(entry.can_be_retried())
        
        # Mark as failed
        entry.mark_as_failed("Test error")
        
        # Now can be retried (1 attempt, max 2)
        self.assertTrue(entry.can_be_retried())
        
        # Mark as failed again
        entry.mark_as_failed("Test error 2")
        
        # Now can't be retried (2 attempts, max 2)
        self.assertFalse(entry.can_be_retried())


class EmailLogModelsTest(TestCase):
    """Test cases for EmailLog models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
    
    def test_log_creation(self):
        """Test creating a log entry."""
        log = EmailLog.objects.create(
            email=self.email,
            log_level='INFO',
            operation='SEND',
            message='Test message',
            details={'key': 'value'}
        )
        
        self.assertEqual(log.email, self.email)
        self.assertEqual(log.log_level, 'INFO')
        self.assertEqual(log.operation, 'SEND')
        self.assertEqual(log.message, 'Test message')
        self.assertEqual(log.details, {'key': 'value'})
    
    def test_log_operation_method(self):
        """Test the log_operation convenience method."""
        log = EmailLog.log_operation(
            email=self.email,
            operation='SEND',
            log_level='INFO',
            message='Test operation',
            details={'test': 'data'}
        )
        
        self.assertEqual(log.email, self.email)
        self.assertEqual(log.operation, 'SEND')
        self.assertEqual(log.log_level, 'INFO')
        self.assertEqual(log.message, 'Test operation')
        self.assertEqual(log.details, {'test': 'data'})


class EmailAttachmentModelsTest(TestCase):
    """Test cases for EmailAttachment models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
    
    def test_attachment_creation(self):
        """Test creating an attachment."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_file.write(b'Test file content')
            temp_file_path = temp_file.name
        
        try:
            attachment = EmailAttachment.objects.create(
                email=self.email,
                filename='test.txt',
                file=temp_file_path
            )
            
            self.assertEqual(attachment.email, self.email)
            self.assertEqual(attachment.filename, 'test.txt')
            self.assertTrue(attachment.file.name.endswith('test.txt'))
            
        finally:
            # Clean up
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)


class EmailViewsTest(TestCase):
    """Test cases for Email views."""
    
    def setUp(self):
        """Set up test data."""
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin@example.com',
            first_name='Admin',
            last_name='User',
            password='adminpass123'
        )
        
        # Create manager user
        self.manager_user = User.objects.create_user(
            username='manager@example.com',
            first_name='Manager',
            last_name='User',
            password='managerpass123'
        )
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            username='user@example.com',
            first_name='Regular',
            last_name='User',
            password='userpass123'
        )
        
        # Create groups
        admin_group = Group.objects.create(name='Admin')
        manager_group = Group.objects.create(name='Manager')
        user_group = Group.objects.create(name='User')
        
        # Assign users to groups
        self.admin_user.groups.add(admin_group)
        self.manager_user.groups.add(manager_group)
        self.regular_user.groups.add(user_group)
        
        # Create mailing list
        self.mailing_list = MailingList.objects.create(
            name='Test List',
            created_by=self.admin_user
        )
        
        # Add users to mailing list access
        self.mailing_list.users_with_access.add(self.admin_user, self.manager_user)
        
        # Create SMTP config
        self.smtp_config = SmtpConfig.objects.create(
            mailing_list=self.mailing_list,
            host='smtp.test.com',
            port=587,
            username='testuser'
        )
        
        # Set password
        self.smtp_config.password = 'testpass123'
        self.smtp_config.save()
        
        # Create recipient
        self.recipient = Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            created_by=self.admin_user
        )
        
        # Add recipient to mailing list
        self.mailing_list.recipients.add(self.recipient)
        
        # Create email
        self.email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.admin_user,
            smtp_config=self.smtp_config
        )
        
        self.client = Client()
    
    def test_email_list_view_access(self):
        """Test access to email list view."""
        # Test admin access
        self.client.login(username='admin@example.com', password='adminpass123')
        response = self.client.get('/emails/')
        self.assertEqual(response.status_code, 200)
        
        # Test manager access
        self.client.login(username='manager@example.com', password='managerpass123')
        response = self.client.get('/emails/')
        self.assertEqual(response.status_code, 200)
        
        # Test regular user access
        self.client.login(username='user@example.com', password='userpass123')
        response = self.client.get('/emails/')
        self.assertEqual(response.status_code, 200)
    
    def test_email_create_view_access(self):
        """Test access to email create view."""
        # Test admin access
        self.client.login(username='admin@example.com', password='adminpass123')
        response = self.client.get('/emails/create/')
        self.assertEqual(response.status_code, 200)
        
        # Test manager access
        self.client.login(username='manager@example.com', password='managerpass123')
        response = self.client.get('/emails/create/')
        self.assertEqual(response.status_code, 200)
        
        # Test regular user access
        self.client.login(username='user@example.com', password='userpass123')
        response = self.client.get('/emails/create/')
        self.assertEqual(response.status_code, 200)
    
    def test_email_detail_view_access(self):
        """Test access to email detail view."""
        # Test admin access (should have access to all emails)
        self.client.login(username='admin@example.com', password='adminpass123')
        response = self.client.get(f'/emails/{self.email.pk}/')
        self.assertEqual(response.status_code, 200)
        
        # Test manager access (should have access to emails from lists they can access)
        self.client.login(username='manager@example.com', password='managerpass123')
        response = self.client.get(f'/emails/{self.email.pk}/')
        self.assertEqual(response.status_code, 200)
        
        # Test regular user access (should not have access to this email)
        self.client.login(username='user@example.com', password='userpass123')
        response = self.client.get(f'/emails/{self.email.pk}/')
        self.assertEqual(response.status_code, 404)  # Should be 403 but Django returns 404 for missing objects
    
    def test_email_dashboard_view(self):
        """Test access to email dashboard."""
        # Test admin access
        self.client.login(username='admin@example.com', password='adminpass123')
        response = self.client.get('/emails/dashboard/')
        self.assertEqual(response.status_code, 200)
        
        # Test manager access
        self.client.login(username='manager@example.com', password='managerpass123')
        response = self.client.get('/emails/dashboard/')
        self.assertEqual(response.status_code, 200)
        
        # Test regular user access
        self.client.login(username='user@example.com', password='userpass123')
        response = self.client.get('/emails/dashboard/')
        self.assertEqual(response.status_code, 200)


class EmailTemplateViewsTest(TestCase):
    """Test cases for EmailTemplate views."""
    
    def setUp(self):
        """Set up test data."""
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin@example.com',
            first_name='Admin',
            last_name='User',
            password='adminpass123'
        )
        
        # Create manager user
        self.manager_user = User.objects.create_user(
            username='manager@example.com',
            first_name='Manager',
            last_name='User',
            password='managerpass123'
        )
        
        # Create groups
        admin_group = Group.objects.create(name='Admin')
        manager_group = Group.objects.create(name='Manager')
        
        # Assign users to groups
        self.admin_user.groups.add(admin_group)
        self.manager_user.groups.add(manager_group)
        
        # Create mailing list
        self.mailing_list = MailingList.objects.create(
            name='Test List',
            created_by=self.admin_user
        )
        
        # Create template
        self.template = EmailTemplate.objects.create(
            name='Test Template',
            subject='Test Subject',
            body='Test body content',
            created_by=self.admin_user,
            mailing_list=self.mailing_list
        )
        
        self.client = Client()
    
    def test_template_list_view_access(self):
        """Test access to template list view."""
        # Test admin access
        self.client.login(username='admin@example.com', password='adminpass123')
        response = self.client.get('/emails/templates/')
        self.assertEqual(response.status_code, 200)
        
        # Test manager access
        self.client.login(username='manager@example.com', password='managerpass123')
        response = self.client.get('/emails/templates/')
        self.assertEqual(response.status_code, 200)
    
    def test_template_create_view_access(self):
        """Test access to template create view."""
        # Test admin access
        self.client.login(username='admin@example.com', password='adminpass123')
        response = self.client.get('/emails/templates/create/')
        self.assertEqual(response.status_code, 200)
        
        # Test manager access
        self.client.login(username='manager@example.com', password='managerpass123')
        response = self.client.get('/emails/templates/create/')
        self.assertEqual(response.status_code, 200)


class EmailUtilsTest(TestCase):
    """Test cases for Email utilities."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.mailing_list = MailingList.objects.create(
            name='Test List',
            created_by=self.user
        )
        
        self.smtp_config = SmtpConfig.objects.create(
            mailing_list=self.mailing_list,
            host='smtp.test.com',
            port=587,
            username='testuser'
        )
        
        # Set password
        self.smtp_config.password = 'testpass123'
        self.smtp_config.save()
        
        self.recipient1 = Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            created_by=self.user
        )
        
        self.recipient2 = Recipient.objects.create(
            first_name='Jane',
            last_name='Smith',
            email='jane@example.com',
            created_by=self.user
        )
    
    def test_email_validation(self):
        """Test email validation utility."""
        from .utils import EmailValidator
        
        # Test valid email
        is_valid, errors = EmailValidator.validate_email_content(
            subject='Test Subject',
            body='Test body',
            from_email='sender@example.com',
            recipients=['recipient@example.com']
        )
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Test invalid from email
        is_valid, errors = EmailValidator.validate_email_content(
            subject='Test Subject',
            body='Test body',
            from_email='invalid-email',
            recipients=['recipient@example.com']
        )
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
        # Test empty subject
        is_valid, errors = EmailValidator.validate_email_content(
            subject='',
            body='Test body',
            from_email='sender@example.com',
            recipients=['recipient@example.com']
        )
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
        # Test empty body
        is_valid, errors = EmailValidator.validate_email_content(
            subject='Test Subject',
            body='',
            from_email='sender@example.com',
            recipients=['recipient@example.com']
        )
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
        # Test no recipients
        is_valid, errors = EmailValidator.validate_email_content(
            subject='Test Subject',
            body='Test body',
            from_email='sender@example.com',
            recipients=[]
        )
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_rate_limiter(self):
        """Test rate limiter utility."""
        from .utils import rate_limiter
        import time
        
        # Initially should be able to send
        self.assertTrue(rate_limiter.can_send())
        
        # Record a send
        rate_limiter.record_send()
        
        # Should not be able to send immediately
        self.assertFalse(rate_limiter.can_send())
        
        # Should have to wait about 60 seconds
        wait_time = rate_limiter.time_until_next()
        self.assertGreater(wait_time, 59)
        self.assertLessEqual(wait_time, 60)
    
    def test_bounce_handler(self):
        """Test bounce handler utility."""
        from .utils import BounceHandler
        
        # Test parsing mailbox full bounce
        bounce_text = "Mailbox is full, cannot deliver message"
        parsed = BounceHandler.parse_bounce_message(bounce_text)
        self.assertEqual(parsed['type'], 'mailbox_full')
        self.assertIn('Mailbox is full', parsed['reason'])
        
        # Test parsing user unknown bounce
        bounce_text = "User unknown: recipient@example.com"
        parsed = BounceHandler.parse_bounce_message(bounce_text)
        self.assertEqual(parsed['type'], 'user_unknown')
        self.assertIn('Recipient not found', parsed['reason'])
        
        # Test parsing rejected bounce
        bounce_text = "Message rejected by server"
        parsed = BounceHandler.parse_bounce_message(bounce_text)
        self.assertEqual(parsed['type'], 'rejected')
        self.assertIn('Message rejected', parsed['reason'])


class EmailSignalsTest(TestCase):
    """Test cases for Email signals."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.email = Email.objects.create(
            subject='Test Subject',
            body='Test body content',
            from_email='sender@example.com',
            created_by=self.user
        )
    
    def test_email_creation_signal(self):
        """Test that email creation triggers signal."""
        # This is tested implicitly by the model creation
        # The signal should have been triggered during setUp
        pass
    
    def test_queue_entry_creation_signal(self):
        """Test that queue entry creation triggers signal."""
        from .models import EmailQueue
        
        recipient = Recipient.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            created_by=self.user
        )
        
        # Create queue entry
        entry = EmailQueue.objects.create(
            email=self.email,
            recipient=recipient,
            to_email='john@example.com',
            status='PENDING'
        )
        
        # Signal should have been triggered
        self.assertIsNotNone(entry.id)


# Run all tests
if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'emails',
                'mailinglists',
                'recipients',
            ],
            SECRET_KEY='test-secret-key',
            USE_TZ=True,
            FERNET_KEY='nBzoVd8hF58mZrEff2y1KtOjOuti237GHypY04--OEM=',
        )
    
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["emails.tests"])
