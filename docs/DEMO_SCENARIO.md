# Demonstration plan

**PulseWatch — Arabome Obadiah Ayodeji**

The purpose of the demo is to demonstrate behavior using an environment you control. Do not direct automated tests at systems without permission.

1. Start the stack and sign in as an administrator.
2. Register a simple public endpoint that you control and verify that checks appear in the Monitors view.
3. Review recorded latency and check history after several intervals.
4. Configure an alert rule pointed at a test email inbox or webhook receiver you control.
5. Change your test service to return a failing status until the configured threshold is reached.
6. Confirm one incident opens, inspect its recorded timestamp, and review alert delivery status.
7. Restore your test service; confirm recovery closes the incident and produces the configured recovery event.
8. Log in with a viewer account and confirm that modification endpoints reject write requests.

Record the selected check interval, threshold, timestamps and observed results. Screen-capture only after verifying that confidential URLs and tokens are not visible.

## Optional demo images

Create real images from a running stack and add them under `docs/screenshots/`:

- `overview.png` — health summaries with real sample data
- `monitors.png` — configured monitors and status
- `incident.png` — an opened and resolved test incident
- `alerts.png` — delivery history for your own test integration

No example screenshots have been invented or embedded in this release.
