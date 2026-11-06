# Local migration status

The application in this workspace is a Python/React rebuild of the PHP application at repository commit `31158f87ba2a8934680410c3ba22621ec921fa37`. It uses the supplied MySQL dump, not a production database connection.

## Migrated

- 18 legacy tables, including original primary keys, QR tokens, pass state, allocations and history.
- All 32 account logins retain their original login values. At the owner's explicit request, original passwords were recovered from the SQL snapshot, verified against the old hashes and restored to readable storage.
- React dashboard, HOD/Brahmachari and congregation management, permissions, additional allocation, gates and scanners.
- Imported member records and supporting APIs remain in the backend; extra member-management navigation is removed to follow the active PHP screens.
- Immediate passes; five-member, VVIP, volunteer and congregation combined pass types.
- CSV batches, recipient editing, original PNG templates and native sharing. Congregation supports selected native sharing of up to 24 passes per page.
- Administrator batch downloads and deactivation retaining history. Extra bulk ZIP and desktop shared-marking controls are removed from the UI.
- QR/manual lookup, physical confirmation, exact limits, unlimited entries, result audio and volunteer-only Community Card family entry for the configured total group size.
- Reports with filters, last-entry timestamps and genuine Excel/CSV exports; administrator entry/audit logs and own profile/card. Other profiles are read-only. Event editing and scanner profile/history screens are removed.

## Data baseline

The imported snapshot contains 27 authorities, 4 scanners, 11 community members, 482 HOD passes, 987 congregation combined passes, 152 volunteer passes, 5 immediate passes, 61 entry logs and 254 audit logs. Empty tables, including VVIP batches/passes, are also migrated. See `migration-verification.json` for the field-level comparison excluding replaced legacy password columns.

## Deliberate changes

- Centralized admission rules with row locking and idempotent requests. The legacy volunteer counter and client-controlled unlimited-entry issues are corrected.
- Password storage now uses readable text as explicitly requested by the owner. The `plaintext$` format tag supports Django's existing login/session/password-change APIs without one-way hashing. Temple Authority can view assigned credentials through the card's View password control. Other roles cannot access those endpoints. Existing hashes were matched to originals in the backup, not reversed; new password changes remain readable.
- Management deletion deactivates records. Automatic approval review rejected permanent deletion because it could erase profiles, linked members, accounts and batches; restoring those Delete actions is pending explicit approval.
- Pass cards use the unchanged original repository artwork, bundled fonts, dimensions and field positions through Python/Pillow. PHP is not required at runtime. Dynamic lettering and QR mask patterns can differ between rendering libraries.
- Event date/timing and gate labels remain printed configuration. The source did not establish a validated requirement to block admissions by event time or printed gate.

## Validation and limits

- Django checks, migration drift checks, 41 MySQL integration tests and the React production build run locally. Password tests cover readable values, restoration without overwriting changed credentials, normal login, long/special-character passwords, changes and administrator-only viewing.
- Local HTTP login/read checks cover imported admin, HOD, congregation and scanner accounts without admissions or business edits.
- Live authenticated HTTP review covered those four roles' Home/Profile/Shared screens where applicable. Other management screens and volunteer/Brahmachari flows were checked in source code. No active volunteer or Brahmachari account was present in the supplied snapshot, so those roles were not logged into live.
- Offline synthetic PHP/Python cards match dimensions and protected header pixels; four artwork assets are byte-identical to the repository. HOD/combined/VVIP/volunteer cards are 1087 x 1447; cropped Community Cards are 1042 x 1322. See `scripts/check_template_parity.py` and ignored `backend/media/template-comparison`.
- HOD/congregation navigation is Profile, Home and Shared Passes; scanner navigation is Home and Logout. Admin management opens through dashboard tiles. Pass galleries use two phone columns, three from 576px, four from 768px and six from 992px; volunteer batch galleries stay at two until 768px.
- Management profile cards follow the supplied reference: avatar/photo, name, role badge, profile ID, mobile, status, member access and outlined actions. Congregation totals count active combined passes from both issue sources; HOD totals show all assigned five-member passes and active unshared passes available. Counts come from database records and refresh after allocation edits. Directory layouts use three desktop columns, two tablet columns and one phone column.
- Browser automation is unavailable because its Windows sandbox process fails at startup. Responsive layout, physical camera scanning, webcam capture and native sharing need interactive device QA.
- No production deployment, production connection, GitHub push or changes to the original PHP application were performed.
- The development launchers now reload Python code automatically; the combined launcher cleans up Django's reloader child when stopped. The stale local app was restarted with the user's explicit approval, and the exact Temple Authority credentials were verified through common login on port 5173 (HTTP 200). Running-app checks also cover pass counts, credential viewing and four imported roles.
- This is a working local migration. Before replacing the live system, perform user acceptance testing against the operating guide, verify deployment configuration and backups, and test the actual gate devices.
