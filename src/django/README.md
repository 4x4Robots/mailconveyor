# MailConveyor - Django Email Management System

A Django-based web application for managing email lists and sending emails to arbitrary addresses or predefined recipient lists.

## Quick Start

To start an asynchronous development server, run:

```bash
uv run uvicorn mailconveyor.asgi:application --reload
```

The application will be available at `http://localhost:8000`

## Project Specification

### User Management
- **User**: Can access assigned mailing lists, add/remove recipients, and send emails
- **Manager**: Same permissions as users plus can update mailing list settings
- **Admin**: Can access all mailing lists and settings. Additionally can create and delete users, managers, and other admins

### Core Features

#### Recipient Management
- Recipients are stored in a database table with:
  - Name
  - Email address
  - Associated mailing lists

#### Mailing Lists
- Each mailing list has:
  - A settings page for SMTP server configuration
  - Access control (which users can view/edit)
  - List of associated recipients

#### Permissions
- Users can only see and edit recipients of lists they have access to
- Managers can additionally update mailing list settings (SMTP configuration)
- Admins have full access to all user and list management features

#### Email Composition
- Users can write emails in a web interface to:
  - Arbitrary email addresses
  - Predefined lists they have access to

## Project Structure

```
mailconveyor/
├── manage.py
├── mailconveyor/
│   ├── settings.py
│   ├── urls.py
│   └── ...
└── db.sqlite3
```

## Next Steps

1. Create Django apps for users, mailing lists, and email management
2. Set up models for Users, Recipients, MailingLists, and SMTP configurations
3. Implement permission system
4. Build web interface for email composition
5. Configure SMTP integration

## 📚 Project Documentation

- **[ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md)** - All architectural decisions with unique IDs for reference
- **[CURRENTLY_WORKING_ON.md](./CURRENTLY_WORKING_ON.md)** - Current development status and next tasks
- **[FEATURES.md](./FEATURES.md)** - Completed features (will be created when first feature is implemented)
