# MailConveyor - Current Development Plan

This file tracks the current state of development and next steps for the MailConveyor Django project. Future agent sessions should update this file as they work on tasks and move completed items to `FEATURES.md`.

## Project Overview

The MailConveyor system will be organized into **4 main Django apps**, each with specific responsibilities:

---

## 📋 App Architecture & Responsibilities

### 1. `accounts` App (User Management & Authentication)
**Responsibility**: User authentication, registration, profile management, and role-based access control.

**Models**:
- `CustomUser` (extends Django's AbstractUser)
  - Fields: email, first_name, last_name, is_active, date_joined
  - Role field: USER, MANAGER, ADMIN (using choices or groups)
  - Methods: get_role(), has_perm() overrides

**Views**:
- User registration (admin-only)
- User profile management
- Login/Logout
- User list (with filtering by role)

**Permissions**:
- ADMIN: Can create/delete all user types
- MANAGER: Can view all users, edit own profile
- USER: Can edit own profile only

**Status**: ⬜ Not started

---

### 2. `mailinglists` App (Mailing List Management)
**Responsibility**: Management of mailing lists, their settings, and access control.

**Models**:
- `MailingList`
  - Fields: name, description, created_at, updated_at, created_by (ForeignKey to CustomUser)
  - Relationship: Many-to-many to CustomUser (users_with_access)
  
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

**Status**: ⬜ Not started

---

### 3. `recipients` App (Recipient Management)
**Responsibility**: Management of email recipients and their association with mailing lists.

**Models**:
- `Recipient`
  - Fields: first_name, last_name, email, created_at, updated_at, created_by (ForeignKey to CustomUser)
  - Relationship: Many-to-many to MailingList (mailing_lists)
  - Constraints: email must be unique

**Views**:
- Recipient list (filtered by mailing list access)
- Add/remove recipients from lists
- Create/edit recipient details
- Import/export recipients (CSV)

**Permissions**:
- ADMIN: Full CRUD on all recipients
- MANAGER/USER: Can add/remove/edit recipients for lists they have access to

**Status**: ⬜ Not started

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
2. ⬜ Create `accounts` app with CustomUser model
3. ⬜ Set up authentication and basic user management
4. ⬜ Create `mailinglists` app with MailingList and SmtpConfig models
5. ⬜ Create `recipients` app with Recipient model
6. ⬜ Set up basic permissions system

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
- **Current Focus**: Project planning and architecture design
- **Next Immediate Task**: Create the 4 Django apps and their models

---

## 🔄 Workflow for Future Agents

1. Read this file to understand current state
2. Update the status of tasks you're working on (change ⬜ to 🔄)
3. Move completed tasks to `FEATURES.md` with implementation details
4. Update the "Current Focus" and "Next Immediate Task" sections
5. Update the "Last Updated" date

---

## 📚 Related Files

- `README.md` - Project overview and specification
- `FEATURES.md` - Completed features and implementation details (create when first feature is done)
