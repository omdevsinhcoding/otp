# Firebase URL Pattern Analysis Report

## Overview
This report contains patterns and analysis derived from probing common Firebase Realtime Database structures used by Android payload bots and cloning apps.

## Common Data Structures

### 1. `user_data` (Device Management Branch)
Most databases store active target devices under `user_data/{Device_ID}`.
**Key Properties Found:**
* `status`: "online" | "offline"
* `battery`: e.g. "85%"
* `brand`: "Samsung Galaxy..." 
* `simSlots`: List of operator and numbers.
* `command`: Pushed by C2, e.g. "send message"
* `phoneNumber`, `messageText`, `simSlot`: Associated with outgoing SMS commands.

### 2. `user_sms` / `sms` / `messages` (Interception Branch)
Often formatted as `user_sms/{Device_ID}/{Push_ID}`.
**Key Properties Found:**
* `sender`: The origin number (e.g. "+91XXXXXXXX")
* `body`: The actual intercepted message context.
* `timestamp`: Epoch Unix milli time.
* `date`: Human readable string.

### 3. Phishing / Forwarding Branches (login, page2, page4)
* `login`: Primary PII (name, mobile, dob, motherName, etc.)
* `page2`: PAN, Aadhar identifiers.
* `page4`: Financial identifiers (UPI, Banking PIN).

## Error Response Patterns Handled

1. **Permission Denied** (`401`, `403`): Captured when Firebase security rules are locked and deny unauthenticated `GET` queries.
2. **Deactivated Database** (`423`, or HTML response with "deactivated"): Captured when abuse prevents further Firebase access by Google.
3. **Empty Null Data** (`200 OK` return `null`): Captured when database path simply has no pushed nodes yet. 
4. **Bucket URLs** (`.firebasestorage.app` variants): Flagged as incorrect parameter since it's cloud bucket, not RTDB endpoint. 
5. **JSON Malformation**: Failsafe JSON decode exception catch.
6. **Network Timed out / Refusal**: Gracefully handles network partition and unreachable node errors via backoffs/timeouts.

This knowledge supports stable polling and safe injection patches.
