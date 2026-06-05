# Firebase Analysis Report

Based on the 15 provided URLs, we found several structural patterns and potential errors:

## Common Data Patterns Observed:
1. **Device Tracking**: Data is frequently stored under `user_data`, `Info`, `user_list`, `All_User`, or `All_Users`. 
   - Uses device IDs (hex strings or IMEI) as keys. 
   - Commonly contains `battery`, `brand` or `Name`, `status`, `device`.
2. **SMS Logs**: Repeatedly found under `user_sms`, `Sms`, `sms`, or `messages`.
   - Keys are often timestamps or random push IDs.
   - Values contain `sender` (or `ph`), `body` (or `msg`), `timestamp` (or `date`).
3. **Phishing/Data Vaults**:
   - `login`: `name`, `mobile`, `dob`, `motherName`. Often nested under `All_Users/Login` or `login`.
   - `page2`: PAN/Aadhar logs.
   - `page4`: Banking PIN and UPI logs.

## A-to-Z Error Handling Matrix Followed:
1. **Data Successfully Fetched**: Returns standard device/sms dict.
2. **Empty Database**: HTTP 200 but response is `null`. We raise a warning but let them add it if necessary.
3. **Permission Denied**: `{"error": "Permission denied"}`. Captured HTTP 401/403.
4. **Database Deactivated**: HTTP 423 or response string containing "deactivated".
5. **404 Not Found**: Firebase node or database doesn't exist. Handled via HTTP 404.
6. **Invalid URL Format**: Handled via string check for `.firebaseio.com`.
7. **Storage Bucket URL**: Handled via `.firebasestorage.app` check.
8. **Network Timeout**: HTTPX `ReadTimeout` captured.
9. **Malformed JSON**: `ValueError` parsing JSON captured.
10. **Duplicate URL**: Handled at the database insertion level (`SELECT id FROM panels WHERE...`).
11. **Partial/Raw URL**: Handled locally in the bot by auto-formatting and suggesting `.firebaseio.com/.json`.
12. **Firebase SDK Error**: Caught by general Exception block.
13. **Server Down**: Caught by `httpx.RequestError`.
