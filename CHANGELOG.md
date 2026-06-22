# Changelog

All meaningful platform changes will be tracked here.

## v0.1.12 - Cancellation-Pending Package Choice

- Added a package-change choice for cancellation-pending subscriptions.
- Owners can keep the cancellation expiry date or keep the subscription active.
- Choosing active clears the pending cancellation and schedules the package change for the next renewal.

## v0.1.11 - Scheduled Package Changes And Settings Polish

- Added pending package changes that take effect on the next renewal date.
- Blocked immediate package switching for active and cancellation-pending accounts.
- Shows current, pending, and next-renewal package states in Billing.
- Reorganized Hotel Settings into cleaner grouped sections.

## v0.1.10 - Cancellation Expiry Display Fix

- Fixed Billing render crash after cancellation by supporting full ISO date timestamps.
- Restored package cards while cancellation is pending.
- Added package/trial expiry date display in Billing.
- Shows cancellation expiry date in the dashboard notice.

## v0.1.9 - 60-Day Cancellation Notice

- Added hotel package cancellation requests with a 60-day notice period.
- Keeps paid access active until the cancellation effective date.
- Shows cancellation policy and effective date in Billing.
- Added database fields for cancellation requested/effective timestamps.

## v0.1.8 - Private Feedback Confirmation

- Shows a clear confirmation after private feedback is submitted.
- Hides guest feedback controls after successful private submission.
- Tells the guest their feedback was sent and that they can close the page.
- Replaced corrupted guest star characters with HTML entities.

## v0.1.7 - Guest Rating Action Flow

- Updated guest feedback stars to a cleaner circular rating control.
- Removed the default 5-star selection so guests must choose a rating.
- Hid feedback/review actions until a rating is selected.
- Made the primary action depend on rating while keeping both private feedback and Google review access available.

## v0.1.6 - Stronger Background Rendering

- Added a stylesheet cache buster so browsers load the newest background CSS.
- Switched background CSS to direct local JPEG URLs for clearer rendering.
- Removed the dashboard shell overlay that was hiding the page background.
- Preserved the updated Truvora login page marketing copy.

## v0.1.5 - Visible JPEG Backgrounds

- Converted local AVIF backgrounds to JPEG for broader browser compatibility.
- Updated CSS to use clean local JPEG filenames.
- Lightened overlays so backgrounds are visible behind each page.

## v0.1.4 - Local Background Images

- Switched background images from remote URLs to local static AVIF files.
- Added the downloaded auth, dashboard, and guest page images to version control.

## v0.1.3 - Background Imagery And Message Cleanup

- Explicitly hid status outputs until JavaScript writes a real message.
- Added hospitality background imagery to auth, billing, dashboard, and guest pages.
- Preserved form/table readability with overlay gradients and solid content panels.

## v0.1.2 - Cleaner Request Form Defaults

- Removed sample placeholder values from the guest request form.
- Hid empty status message boxes so they do not appear as stray colored containers.

## v0.1.1 - Organized Guest Request Form

- Reworked the Send Review Request form into a clearer header and two-column field grid.
- Kept the layout responsive with a single-column mobile view.

## v0.1.0 - Baseline Python Platform

- Captured current Python/FastAPI platform as the rollback baseline.
- Includes hotel signup/login, forgot password, dashboard, guest feedback, Brevo/Twilio hooks, Stripe-ready billing, trial/package gating, and realtime dashboard updates.
