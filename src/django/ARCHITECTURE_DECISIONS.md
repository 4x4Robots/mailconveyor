# Architecture Decisions Record

This file tracks all significant architectural decisions for the MailConveyor project. Each decision has a unique index for easy reference in code and discussions.

---

## Decision Index

### AD-001: Use Django Native Capabilities
**Status**: ✅ Accepted
**Date**: 2026-08-28
**Context**: Framework selection principle

**Decision**: Use Django's native capabilities wherever possible. Avoid reinventing the wheel.

**Consequences**:
- Prefer Django's built-in features over third-party packages when functionality is sufficient
- Reduces dependencies and maintenance burden
- Follows Django best practices and conventions

---

### AD-002: Authentication & Object-Level Permissions
**Status**: ✅ Accepted (Updated)
**Date**: 2026-08-28
**Context**: User access control for mailing lists

**Decision**: 
1. Use **Django's built-in User model** with username authentication
2. Use **Django groups** for role management (Admin, Manager, User)
3. Use **django-guardian** for object-level permissions

**Rationale**: 
- AD-001: Use Django native capabilities wherever possible
- Django's built-in User model is well-tested and maintained
- Groups provide a simple way to manage user roles
- Need fine-grained access control (users should only access specific mailing lists)
- Django's built-in permissions are model-level only, not object-level
- Guardian provides object-level permissions out of the box

**Consequences**:
- Use standard Django User model with username/email/first_name/last_name
- Roles are implemented as groups: Admin, Manager, User
- Add `django-guardian` as a dependency
- Users will have permissions on specific MailingList instances
- Permission checks will use Guardian's API: `user.has_perm('view_mailinglist', mailinglist)`
- Need to set up Guardian's authentication backend alongside Django's ModelBackend

**Implementation Notes**:
```python
# settings.py
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
]

# Create default groups
from django.contrib.auth.models import Group
Group.objects.get_or_create(name='Admin')
Group.objects.get_or_create(name='Manager') 
Group.objects.get_or_create(name='User')

# Check user roles
user.is_admin = user.groups.filter(name='Admin').exists()
user.is_manager = user.groups.filter(name__in=['Manager', 'Admin']).exists()
```

---

### AD-003: SMTP Password Storage
**Status**: ✅ Accepted
**Date**: 2026-08-28
**Context**: Secure storage of SMTP credentials

**Decision**: Use **Fernet symmetric encryption** with key from environment variable.

**Rationale**:
- Provides strong encryption without external services
- Key management via environment is simple and secure
- Built into Python's cryptography library (no additional dependencies)

**Consequences**:
- SMTP passwords will be encrypted at rest in the database
- Requires `FERNET_KEY` environment variable for encryption/decryption
- Need to handle key rotation procedure (for future consideration)

**Implementation Notes**:
```python
from cryptography.fernet import Fernet
import os

FERNET_KEY = os.environ.get('FERNET_KEY')
# Generate with: Fernet.generate_key()
```

---

### AD-004: Email Sending Architecture
**Status**: ✅ Accepted
**Date**: 2026-08-28
**Context**: How to handle email sending with user feedback

**Decision**: 
1. **Start with synchronous sending** for initial implementation
2. **Plan for asynchronous queue** with the following characteristics:
   - User gets immediate feedback that email is "on its way"
   - Separate view to monitor queue status (planned, sent, failed counts)
   - Persistent SMTP connection for one job (sending to multiple recipients)
   - Failed emails: retry once, then log failure
   - Queue model to track all planned and accomplished operations

**Rationale**:
- Sync is simpler to implement initially
- Async provides better UX for larger recipient lists
- Persistent connection improves performance for bulk sends
- Single retry balances reliability with complexity

**Consequences**:
- Initial implementation: direct SMTP sending on request
- Future migration: introduce EmailQueue model and background processing
- Need to design queue model with status tracking
- SMTP connection management for bulk sends

**Queue Model Requirements**:
```python
class EmailQueue(models.Model):
    email = models.ForeignKey(Email, on_delete=models.CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'), 
        ('FAILED', 'Failed'),
        ('RETRYING', 'Retrying')
    ])
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

### AD-005: Recipient Management
**Status**: ✅ Accepted (Updated 2026-08-28)
**Date**: 2026-08-28
**Context**: Recipient data constraints and validation

**Decision**:
1. **Scale**: Keep it simple - maximum 50 recipients per list
2. **Uniqueness constraint**: The combination of `first_name`, `last_name`, and `email` must be globally unique (allows same email with different names)
3. **Email deduplication**: When sending emails, ensure each email address receives only one copy, even if multiple recipients share the same email
4. **Validation**: Use pre-built email validation (Django or Pydantic)
5. **No SMTP verification**: Skip actual SMTP address verification

**Rationale**:
- Real-world data shows recipients with same email but different names
- Need to prevent duplicate name+email combinations
- Must prevent duplicate emails to the same address during sending
- Small scale means performance concerns are negligible
- Pre-built validators are well-tested and maintained
- SMTP verification adds complexity and external dependencies

**Consequences**:
- Recipient model will have `unique_together` constraint on `(first_name, last_name, email)`
- Use Django's `EmailValidator` or Pydantic's `EmailStr` for email field
- Email sending logic must deduplicate recipients by email address before sending
- Need to track which email addresses have already been sent to in a single job
- Simple many-to-many relationship between Recipient and MailingList

**Implementation Notes**:
```python
# models.py
class Recipient(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    # ... other fields
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['first_name', 'last_name', 'email'],
                name='unique_recipient_identity'
            )
        ]

# Email sending deduplication logic
# When sending to a list of recipients, group by email address
def send_email_to_recipients(email_content, recipients):
    # Deduplicate by email address
    unique_emails = {}
    for recipient in recipients:
        if recipient.email not in unique_emails:
            unique_emails[recipient.email] = recipient
    
    # Send to each unique email only once
    for email, recipient in unique_emails.items():
        send_email(email_content, email)
```

---

### AD-006: Data Model - Users vs Recipients
**Status**: ✅ Accepted
**Date**: 2026-08-28
**Context**: Relationship between system users and email recipients

**Decision**: **Users and Recipients are separate models.**

**Rationale**:
- Users are system accounts with authentication
- Recipients are email targets, may or may not be system users
- Same email address can exist in both (e.g., admin user is also a recipient)
- Cleaner separation of concerns

**Consequences**:
- Two distinct models: `CustomUser` and `Recipient`
- No inheritance or shared base model
- Email addresses can appear in both tables independently
- Need to be careful with email validation in both places

---

### AD-007: Email History Retention
**Status**: ✅ Accepted
**Date**: 2026-08-28
**Context**: How long to keep sent email records

**Decision**: **Store sent emails for 14 days only.**

**Rationale**:
- Prevents database bloat from email history
- 14 days is sufficient for troubleshooting and auditing
- Reduces storage requirements

**Consequences**:
- Need automated cleanup (Django management command or cron job)
- Email model needs `created_at` field for age-based deletion
- Consider soft-delete pattern for safety

**Implementation Notes**:
```python
# management/commands/cleanup_emails.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from emails.models import Email

class Command(BaseCommand):
    help = 'Delete emails older than 14 days'
    
    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(days=14)
        deleted = Email.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(f"Deleted {deleted[0]} old emails")
```

---

### AD-008: Attachment Storage
**Status**: ✅ Accepted
**Date**: 2026-08-28
**Context**: Where to store email attachments

**Decision**: **Store attachments in the file system** with option to migrate to S3 later.

**Rationale**:
- Simple to implement initially
- No external dependencies for MVP
- File system is sufficient for small scale
- Can migrate to S3 without model changes (just storage backend)

**Consequences**:
- Use Django's `FileField` for attachments
- Need to configure `MEDIA_ROOT` and `MEDIA_URL`
- Consider file cleanup when emails are deleted
- Future migration path to cloud storage

---

### AD-009: Deployment & Testing
**Status**: ✅ Accepted
**Date**: 2026-08-28
**Context**: Deployment strategy and testing requirements

**Decision**:
1. **Containerization**: Deploy as Podman container
2. **Mock SMTP**: Include mock SMTP server for testing
3. **Rate limiting**: One email job per minute (to multiple recipients)
4. **Bounce handling**: Log bounce messages

**Rationale**:
- Podman provides portable, reproducible deployments
- Mock SMTP enables local development without real email sending
- Rate limiting prevents abuse and SMTP server bans
- Bounce logging helps with deliverability issues

**Consequences**:
- Need Dockerfile/Podmanfile for containerization
- Integrate mock SMTP server (e.g., `aiosmtpd` or `smtpdfix`)
- Implement rate limiting logic (probably in views)
- Design bounce message logging mechanism

**Implementation Notes**:
- Rate limiting can use Django's cache framework or `django-ratelimit`
- Mock SMTP can run as separate service in development
- Bounce messages: need to parse incoming bounce emails or use SMTP server hooks

---

## Decision Summary Table

| ID | Decision | Status | Date |
|----|----------|--------|------|
| AD-001 | Use Django native capabilities | ✅ | 2026-08-28 |
| AD-002 | Django built-in User + groups for roles + django-guardian for object-level permissions | ✅ | 2026-08-28 |
| AD-003 | Fernet encryption for SMTP passwords | ✅ | 2026-08-28 |
| AD-004 | Sync now, async queue later with retry logic | ✅ | 2026-08-28 |
| AD-005 | Recipient uniqueness by (first_name, last_name, email), deduplicate emails by address | ✅ | 2026-08-28 |
| AD-006 | Users and Recipients are separate models | ✅ | 2026-08-28 |
| AD-007 | 14-day retention for sent emails | ✅ | 2026-08-28 |
| AD-008 | File system for attachments | ✅ | 2026-08-28 |
| AD-009 | Podman deployment, mock SMTP, rate limiting, bounce logging | ✅ | 2026-08-28 |

---

## How to Use This Document

1. **Reference decisions in code**: Use decision IDs in comments
   ```python
   # AD-003: Encrypt SMTP password with Fernet
   encrypted_password = fernet.encrypt(password.encode())
   ```

2. **Add new decisions**: Append new decisions with next available index

3. **Update status**: Mark decisions as ❌ Rejected or ✅ Accepted

4. **Link to discussions**: Reference PRs, issues, or meeting notes

---

## Open Questions

None currently. All critical decisions have been made for initial implementation.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-08-28 | Initial | Created document with decisions AD-001 through AD-009 |
| 2026-08-28 | Updated | AD-005: Changed uniqueness constraint to (first_name, last_name, email) and added email deduplication requirement |
| 2026-08-28 | Updated | AD-002: Simplified to use Django built-in User model with groups for roles |
