# MailConveyor - Current Development Plan

This file tracks the current state of development and next steps for the MailConveyor Django project. Future agent sessions should update this file as they work on tasks and move completed items to `FEATURES.md`.

## Project Overview

The MailConveyor system will be organized into **4 main Django apps**, each with specific responsibilities:

---

## 📋 App Architecture & Responsibilities

### 1. `accounts` App (User Management & Authentication)
**Responsibility**: User authentication, registration, profile management, and role-based access control.

**Models**:
- Uses Django's built-in `User` model
  - Fields: username (email), first_name, last_name, is_active, date_joined
  - Roles: Implemented via Django groups (Admin, Manager, User)
  - Extended with role utility methods via `accounts.apps.py`

**Views**:
- User registration (admin-only)
- User profile management
- Login/Logout
- User list (with filtering by role)

**Permissions**:
- ADMIN: Can create/delete all user types
- MANAGER: Can view all users, edit own profile
- USER: Can edit own profile only

**Status**: ✅ Complete

---

### 2. `mailinglists` App (Mailing List Management)
**Responsibility**: Management of mailing lists, their settings, and access control.

**Models**:
- `MailingList`
  - Fields: name, description, created_at, updated_at, created_by (ForeignKey to User, see 1. `accounts` app)
  - Relationship: Many-to-many to User (users_with_access)
  
- `SmtpConfig`
  - Fields: host, port, username, password (encrypted), use_tls, use_ssl, default_from_email
  - Relationship: One-to-one to MailingList (each list has its own SMTP config)

**Views**:
- List all mailing lists (filtered by user access)
- Create/edit mailing list (MANAGER+)
- Mailing list detail view
- SMTP configuration management (MANAGER+)

**Permissions**:
- ADMIN: Full CRUD on all lists
- MANAGER: Can create/edit lists they have access to
- USER: Can view lists they have access to

**Status**: ✅ Complete

---

### 3. `recipients` App (Recipient Management)
**Responsibility**: Management of email recipients and their association with mailing lists.

**Models**:
- `Recipient`
  - Fields: first_name, last_name, email, created_at, updated_at, created_by (ForeignKey to User)
  - Relationship: Many-to-many to MailingList (mailing_lists)
  - Constraints: (first_name, last_name, email) must be unique (AD-005)
- `RecipientImportLog`
  - Fields: file_name, uploaded_by, status, total_records, successful_records, failed_records, error_message, created_at, completed_at

**Views**:
- RecipientListView: List all recipients (filtered by mailing list access)
- RecipientCreateView: Create new recipient
- RecipientUpdateView: Edit existing recipient
- RecipientDetailView: View recipient details
- RecipientDeleteView: Delete recipient
- import_recipients_view: Import recipients from CSV
- export_recipients_view: Export recipients to CSV
- manage_recipient_mailing_lists_view: Manage which mailing lists a recipient belongs to

**Permissions**:
- ADMIN: Full CRUD on all recipients
- MANAGER: Can create/edit recipients for lists they have access to
- USER: Can view recipients for lists they have access to

**Status**: ✅ Complete

---

### 4. `emails` App (Email Composition & Sending)
**Responsibility**: Email composition, sending, and history tracking.

**Models**:
- `EmailTemplate`
  - Fields: name, subject, body (HTML), created_at, updated_at, created_by
  - Relationship: ForeignKey to MailingList (optional, for list-specific templates)
  
- `Email`
  - Fields: subject, body, from_email, status (DRAFT, SENT, FAILED), sent_at, created_at
  - Relationship: ForeignKey to CustomUser (sender), Many-to-many to Recipient/MailingList (recipients)
  
- `EmailAttachment`
  - Fields: file, filename, created_at
  - Relationship: ForeignKey to Email

**Views**:
- Email composer (with recipient selection from accessible lists)
- Email history/sent items
- Email detail view
- Template management

**Services**:
- SMTP sending service (uses list-specific SMTP config)
- Async email sending (Celery or Django background tasks)
- Email validation

**Permissions**:
- ADMIN/MANAGER/USER: Can send emails to recipients/lists they have access to
- Can only use SMTP configs from lists they have access to

**Status**: ⬜ Not started

---

## 🗺️ Data Model Relationships

```
┌─────────────────┐       ┌─────────────────┐
│    CustomUser   │       │   MailingList   │
├─────────────────┤       ├─────────────────┤
│ id              │       │ id              │
│ email           │       │ name            │
│ first_name      │       │ description     │
│ last_name       │       │ created_by      │──────┐
│ role            │       │ created_at      │      │
│ is_active       │       │ updated_at      │      │
└────────┬────────┘       └────────┬────────┘      │
         │                         │               │
         │                         │ Many-to-Many  │
         │                         ▼               │
         │               ┌─────────────────┐       │
         │               │    SmtpConfig   │       │
         │               ├─────────────────┤       │
         │               │ host            │       │
         │               │ port            │       │
         │               │ username        │       │
         │               │ password        │       │
         │               │ use_tls         │       │
         │               └─────────────────┘       │
         │                         │               │
         │                         │ One-to-One    │
         │                         │               │
         │   ┌─────────────────────┴───────────────┴─────────┐
         │   │                                               │
         │   ▼                                               ▼
┌────────┴────────┐       ┌─────────────────────────────────────┐
│    Recipient    │       │           Email                     │
├─────────────────┤       ├─────────────────────────────────────┤
│ id              │       │ id                                  │
│ first_name      │       │ subject                             │
│ last_name       │       │ body                                │
│ email           │       │ from_email                          │
│ created_by      │       │ status                              │
│ created_at      │       │ sent_at                             │
└────────┬────────┘       │ created_by                          │
         │                │ created_at                          │
         │                └──────────────┬──────────────────────┘
         │                          Many-to-Many
         └───────────────────────────────┘
                  (recipients/mailing_lists)
```

---

## 🚀 Implementation Order

### Phase 1: Foundation (Priority: HIGH)
1. ✅ Create Django project structure (DONE - base project exists)
2. ✅ Create `accounts` app with Django built-in User model + groups for roles
3. ✅ Set up authentication and basic user management
4. ✅ Create `mailinglists` app with MailingList and SmtpConfig models
5. ✅ Create `recipients` app with Recipient model
6. ✅ Set up basic permissions system

### Phase 2: Core Features (Priority: HIGH)
7. ⬜ Create `emails` app with Email model
8. ⬜ Implement email sending service
9. ⬜ Build recipient management interface
10. ⬜ Build mailing list management interface

### Phase 3: User Interface (Priority: MEDIUM)
11. ⬜ Create email composer web interface
12. ⬜ Build admin dashboard
13. ⬜ Implement user profile management

### Phase 4: Advanced Features (Priority: LOW)
14. ⬜ Add email templates
15. ⬜ Implement CSV import/export for recipients
16. ⬜ Add email scheduling
17. ⬜ Implement email tracking (opens, clicks)

---

## 📝 Current Status

- **Last Updated**: 2026-08-28
- **Current Focus**: Recipients app implementation
- **Next Immediate Task**: Verify recipients app in local dev server, then proceed to emails app

---

## 🔄 Workflow for Future Agents

1. Read this file to understand current state
2. Update the status of tasks you're working on (change ⬜ to 🔄)
3. Move completed tasks to `FEATURES.md` with implementation details
4. Update the "Current Focus" and "Next Immediate Task" sections
5. Update the "Last Updated" date

---

## 📚 Related Files

- **[README.md](./README.md)** - Project overview, specification, and quick start guide
- **[ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md)** - All architectural decisions with unique IDs (AD-001, AD-002, etc.) for reference in code
- **[FEATURES.md](./FEATURES.md)** - Completed features and implementation details (create when first feature is done)
