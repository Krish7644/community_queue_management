# Darshan Seva Portal — Python migration

React + JavaScript + Bootstrap + Django REST Framework + MySQL rebuild of the existing ISKCON Tirupati PHP application. Original account login IDs, pass IDs, QR tokens, allocations and entry history are preserved from the supplied SQL export.

## Local development

Requirements: Python 3.11+, Node.js supported by Vite, MySQL 8.0.11+.

The configured local MySQL service is `MySQL80` on port 3306. Do not start XAMPP's database on the same port.

Start both project servers with one command from this folder:

```powershell
python run-dev.py
```

Open **http://127.0.0.1:5173**. Press Ctrl+C in that terminal to stop both servers. For separate terminals:

1. Start the backend in one PowerShell window:

   ```powershell
   .\start-backend.ps1
   ```

2. Start the frontend in another window:

   ```powershell
   .\start-frontend.ps1
   ```

3. Open **http://127.0.0.1:5173**. Use the existing portal login ID and password. Common login resolves the account role from matching credentials.

The frontend proxies `/api` to Django on port 8000. Session authentication and CSRF protection work on the same browser origin. Camera scanning works on localhost; use HTTPS for mobile access or deployment. The browser must grant camera access. Native sharing requires device/browser support, matching the PHP flow. Image download remains available.

Backend Python changes reload automatically, and Vite reloads frontend changes. For dependency/environment changes, stop the launcher with Ctrl+C and run `python run-dev.py` again. Stopping the launcher also stops Django's reloader child.

## Data and credentials

- `community_scanner_legacy`: local source snapshot restored from the SQL dump. The app account has SELECT access only.
- `community_scanner_dev`: migrated data and Django tables. At the owner's request, login passwords use readable storage in `portal_user.password`, with a `plaintext$` format tag followed by the original password. Legacy profile password columns retain their compatibility marker.
- `test_community_scanner_dev`: automatically created/dropped by Django tests. No test modifies the development or source schema.
- `backend/.env`: ignored local application credentials, created by setup. The application does not use the MySQL root account.
- Uploaded member photos and generated cards remain private. Original local photos are read from `LEGACY_PUBLIC`; new photos and card cache live under ignored `backend/media`.
- Never commit `.env`, the SQL dump, imported data, generated passes or real photographs. Use synthetic data in a public portfolio/demo.

## Fresh setup on another machine

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm.cmd ci
cd ..
.\.venv\Scripts\python.exe scripts\setup_local.py
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py migrate_legacy
```

`setup_local.py` prompts for the local MySQL root password. It creates only the named migration schemas and a dedicated local application user; root credentials are not saved. Set `LEGACY_SQL_DUMP` to the absolute SQL path if it differs from the original Downloads location. The importer is deliberately one-time and refuses to overwrite existing application data. Configure `LEGACY_PUBLIC` to the original application's `public` directory to reuse its media.

## Workflows

- Temple Authority: original dashboard tiles, account management, additional allocation, CSV batches, immediate passes, scanner/gates, filtered reports, entry/audit logs and own profile/card.
- HOD/Congregation: read-only profile/personal card, allocated pass galleries, recipient editing, download/native sharing and Shared Passes. Congregation supports selected sharing of up to 24 cards.
- Scanner: camera/manual lookup, physical confirmation and audio outcome. Volunteer also has a read-only profile and Community Card family-entry flow.
- HOD/VVIP: one-time five-member entry.
- Volunteer: exact configurable entry count, with 0 for unlimited.
- Congregation combined: unlimited single entry plus one family entry for five people.
- Member cards: configured single entries; volunteers can confirm the one-time family privilege for the configured total group size. Personal authority cards retain unlimited single entry.

Admission validation is centralized, uses MySQL row locks, records allowed/denied outcomes and uses request IDs to prevent duplicate consumption on a network retry. Browser-submitted entry types cannot grant unlimited access. Download/image permissions check both account role and ownership.

Pass PNGs use the original repository templates, fonts, dimensions and field positions through Python. Original QR tokens remain intact. See [migration and parity notes](MIGRATION_STATUS.md) for role comparison and review evidence.

Temple Authority can use **View password** on assigned-account cards to see login details. New and edited account passwords use readable storage. Ordinary profile/list/login responses omit credentials; the explicit password-view endpoints are restricted to administrators. Community member records do not have separate login passwords.

Existing original passwords were restored from the supplied local snapshot after matching them against their stored hashes. Hashes were not reversed. `restore_readable_passwords` previews recoverable counts; adding `--apply` restores only matching originals. Changed or missing originals are preserved and can become readable after a correct login or administrator reset. Restart the backend and sign in again after restoration.

Management controls deactivate records; reports export genuine XLSX/UTF-8 CSV. Automatic approval review blocked permanent Delete actions pending explicit approval. Event dates and gate names remain printed information.

## API overview

JSON endpoints live under `/api/`. GET `/api/auth/session/` sets a CSRF cookie. Send that value in `X-CSRFToken` for POST/PATCH/DELETE requests. Login uses POST `/api/auth/login/` with `username`, `password`, optional `role`; logout is POST `/api/auth/logout/`.

| Endpoint | Purpose |
| --- | --- |
| `dashboard/`, `options/` | Administrator counts and role-permitted form options |
| `authorities/`, `scanners/`, `gates/`, `members/` | Paginated management resources |
| `authorities/{id}/allocate/` | POST additional allocation, `count` 1–500 |
| `authorities/{id}/credentials/`, `scanners/{id}/credentials/`, `volunteers/{id}/credentials/` | Administrator-only GET assigned login details; responses are not cached |
| `profile/credentials/` | Administrator-only GET own login details |
| `members/{id}/decision/` | POST authority review, `decision` and `remarks` |
| `members/{id}/resubmit/`, `reset_family/` | Correction / administrator reset with reason |
| `passes/` | GET owned/filtered passes; administrator POST immediate or combined issue |
| `passes/{kind}/{id}/` | PATCH recipient name; POST confirm shared |
| `passes/{kind}/{id}/card/` | Private PNG; `?download=1` for attachment |
| `passes/bundle/`, `passes/share-bulk/` | POST owned selections; ZIP limit 250, sharing limit 24 |
| `batches/` | GET batches; POST multipart CSV: `file`, `kind`, `batch_name`, `entry_limit` |
| `batches/{kind}/{id}/` | GET batch ZIP; DELETE disables its passes and retains history |
| `scan/lookup/` | POST `token` or `code` |
| `scan/confirm/` | POST `kind`, `id`, `mode`, `method`, UUID `request_id` |
| `entries/`, `audit/` | Administrator-only paginated logs |
| `passes/export/` | CSV with current pass filters; `?filetype=xlsx` for Excel |
| `profile/`, `profile/card/`, `event/` | Permitted own profile/card; read-only administrator event configuration |

Pass kinds: `HOD`, `COMBINED`, `VVIP`, `VOLUNTEER`, `IMMEDIATE`, `MEMBER`. Filters: `kind`, `search`, `category`, `authority_id`, `gate_id`, `scanner_id`, `status`, `shared=yes|no`, `page`.

## Verification

```powershell
.\.venv\Scripts\python.exe backend\manage.py check
.\.venv\Scripts\python.exe backend\manage.py test portal --noinput
npm.cmd --prefix frontend run build
```

Tests cover entry limits, volunteer-only family admission, retries, role permissions, gallery source filtering, reports, CSRF, CSV batches, original artwork and concurrent scanning on MySQL. `scripts/smoke_local.py` checks imported accounts over HTTP without admissions/business edits. `scripts/check_template_parity.py` compares synthetic Python cards with offline PHP fixtures.

Browser automation fails at Windows sandbox startup. Actual mobile layouts, camera capture and native sharing need interactive device QA. Production deployment also needs host/HTTPS settings, backups, a shared rate-limit cache and a production WSGI/ASGI server.
