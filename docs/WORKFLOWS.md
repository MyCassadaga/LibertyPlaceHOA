# Admin Workflow Map (Plain-English)

This document explains the **current** workflows visible in the Liberty Place HOA system. It is written for Admin and non-technical stakeholders and reflects the behaviors visible in the running application today. If a detail is unclear in the existing system, it is called out as **“Current behavior unclear / needs confirmation.”**

Each module below uses the same structure:
- Purpose
- Primary Actors
- Key States / Statuses
- Triggers
- Workflow Steps
- Side Effects
- Permissions / Access Control
- Failure / Edge Cases

---

## Account

### Purpose
Provide login, profile management, password changes, and two-factor authentication (2FA) for users. Also governs how new user accounts and roles are created by admins.

### Primary Actors
- Homeowner
- Board / Treasurer / Secretary
- SYSADMIN
- System (authentication services)

### Key States / Statuses
- **User.is_active**: active vs. archived/inactive (archived users cannot log in).
- **Two-factor**: enabled vs. disabled.
- **Roles**: each user has one or more roles and a designated primary role.

### Triggers
- User login or refresh token request.
- User self-service profile update.
- Password change request.
- 2FA setup, enable, or disable actions.
- SYSADMIN registers a new user or updates roles.

### Workflow Steps
1. **Login**
   - User submits email + password.
   - If credentials are valid and user is active, system checks whether 2FA is enabled.
   - If 2FA is enabled, user must supply a valid OTP code.
   - Successful login returns access + refresh tokens.
2. **Refresh token**
   - User submits a refresh token.
   - System validates token type, user identity, and active status.
   - New access + refresh tokens are returned.
3. **Self-service profile update**
   - User submits changes to name and/or email.
   - If changing email, the current password is required.
   - System updates the record and logs the change.
4. **Password change**
   - User submits current and new password.
   - System validates current password and updates stored hash.
5. **2FA setup and enable**
   - User requests a 2FA setup secret (QR/OTP URI returned).
   - User enables 2FA by confirming a valid OTP code.
   - User can later disable 2FA with a valid OTP code.
6. **Admin user registration**
   - SYSADMIN creates a user with selected roles.
   - Roles are validated and assigned; highest-priority role becomes the primary role.
   - If the new user is a homeowner, the system ensures they are linked to an Owner record (creating a placeholder Owner if needed).
7. **Role updates**
   - SYSADMIN updates role assignments.
   - System ensures at least one active SYSADMIN remains.

### Side Effects
- Audit log entries for user creation, role updates, profile updates, and password changes.
- Homeowner users are automatically linked to an Owner record when created or updated.

### Permissions / Access Control
- **Login / refresh / 2FA / self-service**: any authenticated user.
- **Register new users & update roles**: SYSADMIN only.
- **List users**: Board, Treasurer, Secretary, or SYSADMIN.

### Failure / Edge Cases
- Invalid credentials or OTP codes block login.
- Email changes require the current password and unique email.
- Role updates are blocked if they would remove the last active SYSADMIN.
- Archived/inactive users cannot log in.

---

## ARC Requests

### Purpose
Track architectural review requests submitted by homeowners and reviewed by ARC/Board members.

### Primary Actors
- Homeowner (requester)
- ARC member / Board / Secretary / Treasurer / SYSADMIN (reviewers/managers)
- System (notifications)

### Key States / Statuses
ARC request statuses:
- **DRAFT**: request created but not yet submitted.
- **SUBMITTED**: submitted for review.
- **IN_REVIEW**: under active review.
- **REVISION_REQUESTED**: applicant must revise and resubmit.
- **REVIEW_COMPLETE**: review finished; awaiting final transition.
- **PASSED / FAILED**: outcome from ARC vote threshold.
- **APPROVED / APPROVED_WITH_CONDITIONS / DENIED**: final decision states.
- **COMPLETED**: work completed.
- **ARCHIVED**: closed/archived.

ARC review decisions:
- **PASS** or **FAIL** (individual reviewer vote).

ARC condition status:
- **OPEN** or **RESOLVED**.

Inspection results:
- **PASSED / FAILED / N/A**.

### Triggers
- Homeowner or staff creates an ARC request.
- Homeowner submits the request (DRAFT → SUBMITTED).
- Reviewers submit PASS/FAIL reviews.
- Reviewer or manager transitions status (e.g., IN_REVIEW → APPROVED).
- Reviewer adds conditions or inspections.
- System sends decision emails on PASS/FAIL if templates exist.

### Workflow Steps
1. **Create request**
   - A draft request is created for an owner address.
   - Homeowners may only create requests for linked owner records.
2. **Submit request**
   - Homeowner submits a DRAFT request, moving it to SUBMITTED.
3. **Review phase**
   - ARC/Board reviewers submit PASS or FAIL decisions.
   - The system counts eligible reviewers and moves the request to PASSED or FAILED when a threshold is met.
   - Managers can also directly transition states within allowed status transitions.
4. **Decision notification**
   - When a request becomes PASSED or FAILED, the system attempts to email the applicant using ARC templates.
5. **Post-decision**
   - Managers can move requests into APPROVED, APPROVED_WITH_CONDITIONS, DENIED, COMPLETED, or ARCHIVED as appropriate.
6. **Reopen**
   - Closed requests (approved/denied/completed/archived, etc.) can be reopened as a new IN_REVIEW request with copied attachments and conditions.

### Side Effects
- Audit logs for request creation, updates, status transitions, reviews, conditions, inspections, and reopen actions.
- Email notification on PASS/FAIL if templates are configured.

### Permissions / Access Control
- **Homeowners**: can view and modify their own requests (while in DRAFT) and submit them.
- **ARC/Board/Secretary/Treasurer/SYSADMIN**: can view, update, review, add conditions/inspections, and transition statuses.

### Failure / Edge Cases
- Invalid status transitions are rejected.
- Homeowners cannot submit for unlinked addresses.
- Decision notifications are skipped if no recipient email or missing templates.

---

## Billing

### Purpose
Manage homeowner invoices, payments, late fees, billing policy, and overdue escalations.

### Primary Actors
- Homeowner
- Board / Treasurer / SYSADMIN
- Auditor (read-only access to some reports)
- System (late fee automation, autopay jobs)

### Key States / Statuses
Invoices:
- **OPEN** (default)
- **PAID** (set when fully paid via Stripe or autopay)
- **VOID** is referenced for validations, but no explicit void workflow is defined (current behavior unclear / needs confirmation).

Autopay enrollment:
- **PENDING** (initial enrollment)
- **CANCELLED**
- Provider status fields may include **PENDING_PROVIDER**, **CANCELLED**, or other provider statuses.

Vendor payments:
- **PENDING** → **SUBMITTED** → **PAID** (with **FAILED** allowed for retries).

Late fees:
- Late fee tiers define triggers by days past grace period.

### Triggers
- Admin creates or updates invoices.
- Homeowner or staff records payments.
- Manual late fee application.
- System auto-applies late fees when listing invoices or summaries.
- Autopay job runs daily (Render cron) to pay eligible invoices.
- Overdue notice or attorney escalation actions.

### Workflow Steps
1. **Invoice creation**
   - Staff creates an invoice for an owner (must be active/not archived).
   - The invoice is recorded in the ledger.
2. **Payment recording**
   - Homeowner or staff records a payment (manual) OR Stripe webhook records a payment.
   - Ledger is updated; invoice may move to PAID if fully covered.
3. **Late fees**
   - Billing policy defines grace period and late fee tiers.
   - Late fees are automatically applied when invoice lists or summaries are requested.
   - Staff can also apply a manual late fee.
4. **Autopay**
   - Homeowner (or staff) sets up autopay enrollment.
   - Daily autopay job checks OPEN invoices older than 30 days and issues autopay payments.
5. **Overdue escalation**
   - Staff can contact overdue owners via in-app notifications.
   - Staff can generate an attorney packet (PDF) and notify attorney role.
6. **Vendor payments**
   - Staff create vendor payments (optionally tied to contracts).
   - Payments move from PENDING → SUBMITTED → PAID.

### Side Effects
- Audit log entries for invoice creation/updates, payment recording, late fee application, policy updates, autopay changes, and vendor payment updates.
- Ledger entries are created for invoices, payments, and adjustments.
- Overdue contact creates notifications for homeowners.
- Attorney escalation creates a PDF and notifies the ATTORNEY role.

### Permissions / Access Control
- **Homeowners**: view their own invoices/ledger; record payments for their own account; manage autopay.
- **Board/Treasurer/SYSADMIN**: full billing management, policies, and vendor payments.
- **Auditor**: can view invoices and billing summaries.

### Failure / Edge Cases
- Archived owners cannot receive invoices or payments.
- Stripe payments are skipped if invoice is already paid or void.
- Autopay only runs for active enrollments and invoices older than 30 days.
- Billing policy updates replace tiers not included in the update.

---

## Documents

### Purpose
Maintain a governance document library with folders and downloadable files.

### Primary Actors
- Board / Treasurer / Secretary / SYSADMIN (managers)
- Homeowners (view/download)

### Key States / Statuses
- No explicit status fields for folders or documents.

### Triggers
- Manager creates/updates/deletes folders.
- Manager uploads or deletes documents.
- Any logged-in user downloads a document.

### Workflow Steps
1. **Folder management**
   - Managers create, rename, or delete folders.
   - On folder deletion, child folders and documents are moved up to the parent.
2. **Document upload**
   - Manager uploads a file and assigns it to a folder (or leave uncategorized).
3. **Document download**
   - Any authenticated user can download documents.

### Side Effects
- Files are stored in the configured storage backend.
- No explicit audit logs in the document routes (current behavior unclear / needs confirmation).

### Permissions / Access Control
- **Manage folders/documents**: Board, Treasurer, Secretary, SYSADMIN.
- **View/download**: any authenticated user.

### Failure / Edge Cases
- Upload fails if file is empty.
- Download fails if document not found.

---

## Elections

### Purpose
Run community elections with candidate lists, ballots, and vote tallying.

### Primary Actors
- Board / Secretary / SYSADMIN (election managers)
- Homeowners (voters)
- System (notifications)

### Key States / Statuses
Election status values observed:
- **DRAFT**
- **SCHEDULED**
- **OPEN**
- **CLOSED**
- **ARCHIVED**

Ballot status fields:
- **issued_at** (issued)
- **voted_at** (used)
- **invalidated_at** (invalidated)

### Triggers
- Manager creates/updates elections.
- Manager adds/removes candidates.
- Manager generates ballots (tokens) for owners.
- Homeowner votes via authenticated portal or token link.
- Manager updates election status (OPEN/CLOSED/etc.).

### Workflow Steps
1. **Create election**
   - Manager creates a new election (default DRAFT unless specified).
2. **Manage candidates**
   - Manager adds or removes candidates.
3. **Issue ballots**
   - Manager generates ballots; tokens are created for each active owner.
4. **Open voting**
   - Manager updates status to OPEN; homeowners can vote.
   - System can notify homeowners when an election opens.
5. **Voting**
   - Homeowners vote via authenticated portal or public token link.
   - Each ballot can be used once; a vote records the selection or write-in.
6. **Close election**
   - Manager changes status to CLOSED; results are available to managers.
7. **Results and reports**
   - Results can be viewed in-app or exported as CSV.

### Side Effects
- Notifications sent when election status changes (OPEN/SCHEDULED/CLOSED).
- Voting records stored for tallying and reporting.

### Permissions / Access Control
- **Manage elections/candidates/ballots**: Board, Secretary, SYSADMIN.
- **Vote**: authenticated homeowners for OPEN elections; token links for public voting.
- **Results and stats**: manager roles only.

### Failure / Edge Cases
- Voting is blocked if election is not OPEN.
- Ballots cannot be reused or used after invalidation.
- Candidate ID must belong to the election.

---

## Meetings

### Purpose
Schedule HOA meetings and publish minutes.

### Primary Actors
- Board / Treasurer / Secretary / SYSADMIN (managers)
- Homeowners (viewers)

### Key States / Statuses
- No explicit status field; meetings are determined by date/time.

### Triggers
- Manager creates or updates meeting details.
- Manager uploads meeting minutes.
- Users list or download minutes.

### Workflow Steps
1. **Create meeting**
   - Manager creates a meeting with date/time/location/Zoom link.
2. **Update meeting**
   - Manager edits meeting details as needed.
3. **Upload minutes**
   - After the meeting, manager uploads minutes; download link becomes available.

### Side Effects
- Uploaded minutes are stored in the configured file storage.
- No explicit audit logs in the meeting routes (current behavior unclear / needs confirmation).

### Permissions / Access Control
- **Create/update/delete meetings or upload minutes**: Board, Treasurer, Secretary, SYSADMIN.
- **View meetings and download minutes**: any authenticated user.

### Failure / Edge Cases
- Minutes upload fails if file is empty.
- Download fails if minutes file is missing.

---

## Violations

### Purpose
Track covenant violations, notices, fines, hearings, and appeals.

### Primary Actors
- Board / Secretary / SYSADMIN (managers)
- Treasurer / Attorney (view and notification recipients)
- Homeowners (view/respond)
- System (notices, notifications, invoices)

### Key States / Statuses
Violation status values:
- **NEW**
- **UNDER_REVIEW**
- **WARNING_SENT**
- **HEARING**
- **FINE_ACTIVE**
- **RESOLVED**
- **ARCHIVED**

Appeal status values:
- **PENDING** (default)
- Decision values are stored as free-text status when decided.

### Triggers
- Manager creates a violation.
- Manager transitions a violation status.
- Manager issues additional fines.
- Homeowner submits an appeal.
- Board decides an appeal.

### Workflow Steps
1. **Create violation**
   - Manager creates a violation for an owner (or a user, which can create a placeholder owner).
2. **Status transitions**
   - Violations move through allowed transitions (e.g., NEW → UNDER_REVIEW → WARNING_SENT → HEARING → FINE_ACTIVE → RESOLVED → ARCHIVED).
   - Each transition can generate notices or fines depending on the new status.
3. **Notices and fines**
   - WARNING_SENT, HEARING, and FINE_ACTIVE trigger templated notices and a PDF notice file.
   - FINE_ACTIVE creates a payable invoice; additional fines can be added while in FINE_ACTIVE.
4. **Appeals**
   - Homeowners can submit appeals.
   - Board reviews and records a decision.
5. **Messages**
   - Both managers and homeowners can post messages on a violation thread.

### Side Effects
- Audit logs for creation, updates, status transitions, messages, appeals, and fines.
- Notifications to homeowners and managers on status changes.
- Violation notices generate PDFs and emails (if homeowner email exists).
- Fines create invoices and ledger entries.

### Permissions / Access Control
- **Create/update/transition**: Board, Secretary, SYSADMIN.
- **View**: managers can view all; homeowners only their own.
- **Appeals**: homeowners for their own violations; Board decides.
- **Messages**: homeowners can message their own violations; managers can message all.

### Failure / Edge Cases
- Invalid status transitions are blocked.
- FINE_ACTIVE requires a fine amount.
- Notices are skipped if required data (e.g., email) is missing.
- Appeals can only be submitted for the homeowner’s own violation.

---

## Announcements

### Purpose
Send community announcements and broadcast messages to owners via email or printed packets.

### Primary Actors
- Board / Secretary / SYSADMIN
- System (email and PDF generation)

### Key States / Statuses
- No explicit status field for announcements or messages.

### Triggers
- Admin creates an announcement, broadcast, or communication message.

### Workflow Steps
1. **Announcements**
   - Admin selects delivery methods (email, print).
   - System builds a recipient list and optionally generates a PDF packet.
   - Email deliveries are queued in a background task.
2. **Broadcast messages**
   - Admin chooses a segment (all owners, delinquent owners, rental owners).
   - System builds recipient list for the segment.
   - Broadcast record is created (email delivery only).
3. **Communication messages**
   - Admin sends a broadcast (segment-based) or general announcement (delivery methods).

### Side Effects
- Audit logs for announcement, broadcast, and communication message creation.
- Optional PDF packet generation for print delivery.
- Emails are sent asynchronously.

### Permissions / Access Control
- **Create/list announcements, broadcasts, and messages**: Board, Secretary, SYSADMIN.

### Failure / Edge Cases
- Empty subject/body is rejected.
- Broadcasts fail if no recipients have emails for the selected segment.

---

## Budget

### Purpose
Plan and approve the annual HOA budget, including reserve planning and attachments.

### Primary Actors
- Board / Treasurer / SYSADMIN (managers)
- Homeowners (view approved budgets)
- System (notifications)

### Key States / Statuses
Budget status values:
- **DRAFT** (default)
- **APPROVED** (locked)

### Triggers
- Create/update budget and line items.
- Board approvals.
- Manual lock/unlock actions.

### Workflow Steps
1. **Draft budget**
   - Managers create a budget or update draft details.
2. **Line items & reserves**
   - Managers add/edit/delete budget line items and reserve plan items.
3. **Approvals**
   - Board members approve the budget.
   - When required approval count is reached, budget auto-locks and becomes APPROVED.
4. **Lock/Unlock**
   - Managers can manually lock a budget if required approvals are satisfied.
   - SYSADMIN can unlock an approved budget (returns to DRAFT and clears approvals).

### Side Effects
- Audit logs for budget creation, updates, line items, approvals, lock/unlock, and attachments.
- Notifications sent to homeowners when a budget is approved.

### Permissions / Access Control
- **Create/update/approve**: Board, Treasurer, SYSADMIN.
- **Unlock approved budget**: SYSADMIN only.
- **View**: homeowners can view approved budgets; managers can view drafts.

### Failure / Edge Cases
- Budgets cannot be locked without line items.
- Approved budgets cannot be edited except by SYSADMIN unlock.

---

## Contracts

### Purpose
Store vendor contracts, including attachments and renewal metadata.

### Primary Actors
- Treasurer / SYSADMIN (editors)
- Board / Secretary / Attorney / Auditor / Legal (viewers)

### Key States / Statuses
- No explicit status field for contracts.

### Triggers
- Create/update contracts.
- Upload/download contract attachments.

### Workflow Steps
1. **Create contract**
   - Treasurer or SYSADMIN adds contract details.
2. **Update contract**
   - Editors modify contract data (dates, renewal options, etc.).
3. **Attach files**
   - Editors upload a PDF attachment; old files are replaced.

### Side Effects
- Audit logs for contract creation and updates.
- Files stored in storage backend.

### Permissions / Access Control
- **Create/update/attach**: Treasurer, SYSADMIN.
- **View**: Board, Treasurer, Secretary, SYSADMIN, Attorney, Auditor, Legal.

### Failure / Edge Cases
- Attachments must be PDFs; empty file uploads are rejected.

---

## Legal

### Purpose
Send formal legal communications to contract contacts using legal templates.

### Primary Actors
- Legal role users
- SYSADMIN
- System (email dispatch)

### Key States / Statuses
- No explicit status field for legal messages.

### Triggers
- Legal/SYSADMIN sends a legal message tied to a contract.

### Workflow Steps
1. **Choose template and contract**
   - Legal user chooses a template and contract contact.
2. **Send message**
   - System dispatches the email using the legal sender address.

### Side Effects
- Audit log entry for each legal message sent.

### Permissions / Access Control
- **View legal templates & send messages**: Legal role or SYSADMIN.

### Failure / Edge Cases
- Contract must have a contact email.
- Subject/body cannot be empty.

---

## Owners

### Purpose
Maintain owner records and link them to user accounts.

### Primary Actors
- Board / Treasurer / Secretary / SYSADMIN
- Homeowners (self-service updates)
- System (USPS welcome notice creation)

### Key States / Statuses
Owner archival status:
- **is_archived = false** (active)
- **is_archived = true** (archived)

Owner update request status:
- **PENDING**
- **APPROVED**
- **REJECTED**

### Triggers
- Create/update owner records.
- Homeowner submits update request (proposal).
- Board reviews and approves/rejects proposals.
- SYSADMIN archives or restores owners.
- SYSADMIN links/unlinks users to owners.

### Workflow Steps
1. **Owner creation**
   - Board/Treasurer/SYSADMIN creates an owner record.
   - System attempts to create a USPS welcome notice for the new owner.
2. **Owner update requests**
   - Homeowner proposes updates; request remains PENDING.
   - Board/Secretary/SYSADMIN approves (changes applied) or rejects.
3. **Archive/restore**
   - SYSADMIN archives an owner (lot renamed with ARCHIVED suffix and linked users deactivated).
   - SYSADMIN restores an owner (lot restored if no conflict; optional user reactivation).
4. **Link/unlink users**
   - SYSADMIN links a user to an owner (homeowners may only link to one active property).

### Side Effects
- Audit logs for owner creation, updates, proposals, archive/restore, and user link/unlink.
- Archiving deactivates linked user accounts.
- USPS welcome notice creation can create a Notice and Paperwork item.

### Permissions / Access Control
- **Create/update owners**: Board, Treasurer, Secretary, SYSADMIN.
- **Archive/restore, link/unlink users**: SYSADMIN only.
- **Propose updates**: homeowner for their record; Board/Secretary/SYSADMIN for any record.
- **View**: managers can view all; homeowners only their own.

### Failure / Edge Cases
- Archived owners cannot receive invoices or new ARC/violation filings.
- Restore fails if another active owner already uses the original lot.

---

## Reconciliation

### Purpose
Import bank statements and match transactions to payments/invoices.

### Primary Actors
- Board / Treasurer / SYSADMIN
- System (automatic matching)

### Key States / Statuses
Bank transaction status values:
- **PENDING** (imported)
- **MATCHED**
- **UNMATCHED**

### Triggers
- Upload bank statement CSV.
- Review transactions and reconciliations.

### Workflow Steps
1. **Import statement**
   - Admin uploads a CSV statement.
   - System parses transactions and stores them.
2. **Automatic matching**
   - System attempts to match transactions to payments (priority) or invoices (fallback) by amount and date proximity.
3. **Review**
   - Admin views reconciliations and transactions, filtered by status as needed.

### Side Effects
- Audit logs for imports and reconciliation views.
- Stored copy of the uploaded statement in file storage.

### Permissions / Access Control
- **Import and view**: Board, Treasurer, SYSADMIN.

### Failure / Edge Cases
- CSV must include date, description, and amount headers.
- Invalid CSV format rejects import.
- Matching is best-effort; unmatched transactions remain for manual review.

---

## Reports

### Purpose
Generate financial and compliance CSV reports.

### Primary Actors
- Board / SYSADMIN

### Key States / Statuses
- No explicit report status; reports are generated on demand.

### Triggers
- Admin requests report exports or data endpoints.

### Workflow Steps
1. **Generate report**
   - System aggregates report data and returns CSV.
2. **Audit access**
   - Each report request logs an audit entry.

### Side Effects
- Audit log entries for each report access.

### Permissions / Access Control
- **Export reports**: Board, SYSADMIN.

### Failure / Edge Cases
- Current behavior unclear / needs confirmation for report timeouts or large data sets.

---

## USPS

### Purpose
Create and manage postal notices, including USPS welcome packets and paper mail dispatch workflows.

### Primary Actors
- Board / Treasurer / Secretary / SYSADMIN
- System (notice creation, PDF generation)
- External mail providers (Click2Mail, Certified Mail)

### Key States / Statuses
Notice status values:
- **PENDING**
- **SENT_EMAIL**
- **IN_PAPERWORK**
- **MAILED**

Paperwork item status values:
- **PENDING**
- **CLAIMED**
- **MAILED**

### Triggers
- Owner creation (creates USPS welcome notice).
- Board creates a notice manually.
- Board dispatches paper mail through Click2Mail or Certified Mail.

### Workflow Steps
1. **Notice creation**
   - Admin creates a notice (or system creates a USPS welcome notice).
   - Delivery channel is resolved based on notice type and owner preferences.
2. **Email delivery**
   - If email delivery is allowed, the notice is emailed and marked SENT_EMAIL.
3. **Paperwork queue**
   - If paper delivery is required, a Paperwork item is created and linked to the notice.
4. **Claim and dispatch**
   - Board member can claim a paperwork item.
   - Item can be manually marked MAILED or dispatched via Click2Mail/Certified Mail.

### Side Effects
- Audit log entry for notice creation and certified-mail dispatch.
- PDF notice generated and stored.
- Provider status, tracking numbers, and delivery metadata stored when dispatched.

### Permissions / Access Control
- **Create notices and manage paperwork**: Board, Treasurer, Secretary, SYSADMIN.
- **View paperwork**: Board roles.

### Failure / Edge Cases
- Click2Mail or Certified Mail dispatch fails if not configured.
- Paperwork PDFs can be regenerated if missing, but dispatch fails if generation fails.

---

## Admin

### Purpose
Provide sysadmin tooling such as user provisioning, login background management, and runtime diagnostics.

### Primary Actors
- SYSADMIN

### Key States / Statuses
- No explicit status fields; admin actions affect system configuration and user roles.

### Triggers
- SYSADMIN uploads a login background image.
- SYSADMIN requests runtime diagnostics.
- SYSADMIN sends test email (requires admin token).

### Workflow Steps
1. **Login background**
   - SYSADMIN uploads a PNG/JPG.
   - System stores and returns the URL.
2. **Runtime diagnostics**
   - SYSADMIN requests configuration details (non-sensitive settings only).
3. **Test email**
   - SYSADMIN submits recipient + message with admin token.
   - System sends a test email using configured email backend.

### Side Effects
- Stored background image in file storage.
- Test email sent if admin token and backend are configured.

### Permissions / Access Control
- **All admin endpoints**: SYSADMIN only.

### Failure / Edge Cases
- Invalid file type for background image is rejected.
- Test email endpoint is disabled if no admin token is configured.

---

## Audit Log

### Purpose
Provide a tamper-resistant history of system changes and admin actions.

### Primary Actors
- SYSADMIN
- Auditor
- System (automatic audit middleware)

### Key States / Statuses
- No explicit status; each entry is immutable.

### Triggers
- Any mutating API request (POST/PUT/PATCH/DELETE) is logged automatically.
- Services explicitly call audit logging for significant actions.

### Workflow Steps
1. **Automatic logging**
   - Middleware records HTTP write actions (excluding the notifications WebSocket).
2. **Explicit logging**
   - Services and APIs add audit entries for key business actions.
3. **Review**
   - SYSADMIN or Auditor can list audit logs.

### Side Effects
- Audit logs stored with before/after snapshots when provided.

### Permissions / Access Control
- **View audit logs**: SYSADMIN or Auditor.

### Failure / Edge Cases
- Actor may be missing (system or unauthenticated actions); audit entries still recorded.

---

## Templates

### Purpose
Manage reusable message templates for notices, legal messages, ARC decisions, billing, and announcements.

### Primary Actors
- SYSADMIN

### Key States / Statuses
- **is_archived = false** (active)
- **is_archived = true** (archived)

### Triggers
- SYSADMIN creates, updates, or archives templates.
- SYSADMIN views template types or merge tags.

### Workflow Steps
1. **Create template**
   - SYSADMIN selects a valid template type and defines subject/body.
2. **Update template**
   - SYSADMIN edits fields or archives the template.
3. **Use template**
   - Other workflows render templates with merge tags (e.g., ARC decision emails, violation notices, legal messages).

### Side Effects
- Audit logs for template creation and updates.

### Permissions / Access Control
- **All template actions**: SYSADMIN only.

### Failure / Edge Cases
- Invalid template type codes are rejected.

---

# Future: Admin-Editable Workflows (Non-Implemented)

This section is **conceptual only** and reflects no current implementation.

- **Admin-only Workflows UI**: In the future, an Admin could open a “Workflows” page to view each module’s steps in a human-readable flow diagram or checklist.
- **Attach notification templates to steps**: Admins could select which email/PDF templates fire for a given step (e.g., “Violation → Warning Sent”).
- **Enable/disable or reorder steps**: Admins could toggle optional steps (e.g., skip hearings) or reorder steps to match local policy.
- **No schema or API definitions**: This concept intentionally avoids proposing new tables or APIs; it is meant to guide future planning only.
