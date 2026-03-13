import requests
import time
import json
import re

base_url = "http://localhost:8001/api/v1"

# 1. Register
email = f"vidgo_test_{int(time.time())}@example.com"
print(f"Testing with {email}")
res = requests.post(f"{base_url}/auth/register", json={
    "email": email,
    "password": "TestPassword123!",
    "password_confirm": "TestPassword123!",
    "full_name": "Test User",
    "username": "testuser"
})
print("Register:", res.status_code, res.text)

# 2. Get code from mailpit
time.sleep(2)
mp_res = requests.get("http://localhost:8025/api/v1/messages")
messages = mp_res.json()["messages"]
code = None
for msg in messages:
    if msg["To"][0]["Address"] == email:
        # Get message details
        msg_res = requests.get(f"http://localhost:8025/api/v1/message/{msg['ID']}")
        text = msg_res.json()["Text"]
        # Find 6 digit code in text
        match = re.search(r'\b\d{6}\b', text)
        if match:
            code = match.group(0)
            break

print("Found code:", code)

# 3. Verify and login
if code:
    res = requests.post(f"{base_url}/auth/verify-code", json={
        "email": email,
        "code": code
    })
    print("Verify:", res.status_code)
    try:
        response_json = res.json()
        token = response_json["access_token"]
        
        # 4. Check credits
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(f"{base_url}/credits/balance", headers=headers)
        print("Credits:", res.status_code, json.dumps(res.json(), indent=2))
    except Exception as e:
        print("Error parsing verify response:", e)
        print("Raw response:", res.text)
