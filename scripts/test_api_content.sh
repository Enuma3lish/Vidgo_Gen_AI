#!/bin/bash
# Test API response CONTENT (keys + values) and frontend service.
# Run after backend and frontend are up and seed_test_user has been run.
# Usage: API_BASE=http://localhost:8001 FRONTEND_URL=http://localhost:8501 ./scripts/test_api_content.sh
set -e
BASE="${API_BASE:-http://localhost:8001}"
FRONTEND_BASE="${FRONTEND_URL:-http://localhost:8501}"
RESP="/tmp/api_content_resp.json"
FAILED=0

# Assert key exists in last response (in $RESP). Usage: content_ok "key" or content_ok ".key.sub"
# Uses jq if available, else Python.
content_ok() {
  local key="$1"
  local ok=0
  if command -v jq >/dev/null 2>&1; then
    jq -e "$key" "$RESP" >/dev/null 2>&1 && ok=1
  else
    python3 -c "
import sys, json
with open(sys.argv[1]) as fp:
    d = json.load(fp)
key = sys.argv[2].lstrip('.')
parts = key.replace('[', '.').replace(']', '.').split('.')
parts = [p for p in parts if p]
for p in parts:
    if p.isdigit():
        d = d[int(p)]
    else:
        d = d.get(p)
    if d is None:
        sys.exit(1)
sys.exit(0)
" "$RESP" "$key" 2>/dev/null && ok=1
  fi
  if [ "$ok" -eq 0 ]; then
    echo "  CONTENT FAIL: expected key $key in response"
    echo "  Response (first 300 chars): $(cat "$RESP" 2>/dev/null | head -c 300)"
    FAILED=$((FAILED+1))
    return 1
  fi
  return 0
}

# GET and check status then content. Returns 0 only if all content checks pass.
get_and_check() {
  local path="$1"
  shift
  local code
  code=$(curl -s -o "$RESP" -w "%{http_code}" --connect-timeout 10 "$BASE$path" 2>/dev/null || echo "000")
  if [ "$code" != "200" ] && [ "$code" != "201" ]; then
    echo "  HTTP FAIL: $path (code $code)"
    FAILED=$((FAILED+1))
    return 1
  fi
  local ok=0
  for key in "$@"; do content_ok "$key" && true || ok=1; done
  return $ok
}

# POST JSON and check. Returns 0 only if all content checks pass.
post_and_check() {
  local path="$1"
  local body="$2"
  shift 2
  local code
  code=$(curl -s -o "$RESP" -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$body" --connect-timeout 10 "$BASE$path" 2>/dev/null || echo "000")
  if [ "$code" != "200" ] && [ "$code" != "201" ]; then
    echo "  HTTP FAIL: POST $path (code $code)"
    cat "$RESP" | jq . 2>/dev/null || cat "$RESP"
    FAILED=$((FAILED+1))
    return 1
  fi
  local ok=0
  for key in "$@"; do content_ok "$key" && true || ok=1; done
  return $ok
}

# GET with Bearer token. Returns 0 only if all content checks pass.
get_auth_and_check() {
  local token="$1"
  local path="$2"
  shift 2
  local code
  code=$(curl -s -o "$RESP" -w "%{http_code}" -H "Authorization: Bearer $token" --connect-timeout 10 "$BASE$path" 2>/dev/null || echo "000")
  if [ "$code" != "200" ] && [ "$code" != "201" ]; then
    echo "  HTTP FAIL: $path (code $code)"
    FAILED=$((FAILED+1))
    return 1
  fi
  local ok=0
  for key in "$@"; do content_ok "$key" && true || ok=1; done
  return $ok
}

# Assert key has expected value (or value matches pattern). Usage: content_value_ok ".key" "expected" or ".key" "regex:.*"
content_value_ok() {
  local key="$1"
  local expected="$2"
  local actual
  if command -v jq >/dev/null 2>&1; then
    actual=$(jq -r "$key" "$RESP" 2>/dev/null)
  else
    actual=$(python3 -c "
import sys, json
d = json.load(open(sys.argv[1]))
key = sys.argv[2].lstrip('.')
parts = key.replace('[', '.').replace(']', '.').split('.')
parts = [p for p in parts if p]
for p in parts:
    d = d.get(p) if isinstance(d, dict) else (d[int(p)] if p.isdigit() else None)
    if d is None: break
print(d if d is not None else '')
" "$RESP" "$key" 2>/dev/null)
  fi
  if [[ "$expected" == regex:* ]]; then
    pattern="${expected#regex:}"
    if [[ "$actual" =~ $pattern ]]; then
      return 0
    fi
  else
    if [[ "$actual" == "$expected" ]]; then
      return 0
    fi
  fi
  echo "  VALUE FAIL: $key expected '$expected' got '$actual'"
  FAILED=$((FAILED+1))
  return 1
}

# Assert key is a number >= 0
content_number_ok() {
  local key="$1"
  local val
  if command -v jq >/dev/null 2>&1; then
    val=$(jq -r "$key" "$RESP" 2>/dev/null)
  else
    val=$(python3 -c "
import sys, json
d = json.load(open(sys.argv[1]))
key = sys.argv[2].lstrip('.')
parts = key.replace('[', '.').replace(']', '.').split('.')
parts = [p for p in parts if p]
for p in parts:
    d = d.get(p) if isinstance(d, dict) else (d[int(p)] if p.isdigit() else None)
    if d is None: break
print(d if d is not None else '')
" "$RESP" "$key" 2>/dev/null)
  fi
  if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -ge 0 ]]; then
    return 0
  fi
  echo "  VALUE FAIL: $key expected non-negative number got '$val'"
  FAILED=$((FAILED+1))
  return 1
}

echo "=========================================="
echo "VidGo API CONTENT tests (keys + values)"
echo "=========================================="
echo ""

# 1. Health: must have status and value is ok/healthy
echo "1. Health"
get_and_check "/health" ".status" && content_value_ok ".status" "ok" && echo "  OK: health .status is ok" || true
echo ""

# 2. Credits pricing: array with items, credit_cost is number
echo "2. Credits pricing (public)"
get_and_check "/api/v1/credits/pricing" ".pricing" ".pricing[0].service_type" ".pricing[0].credit_cost" && content_number_ok ".pricing[0].credit_cost" && echo "  OK: pricing content valid" || true
echo ""

# 3. Demo inspiration: success true and examples array
echo "3. Demo inspiration"
get_and_check "/api/v1/demo/inspiration?count=2" ".success" ".examples" && content_value_ok ".success" "regex:^(true|True)$" && echo "  OK: inspiration content valid" || true
echo ""

# 4. Login with test user to get token
echo "4. Auth login (test user)"
post_and_check "/api/v1/auth/login" '{"email":"test@example.com","password":"TestPass123!"}' ".user" ".user.email" ".tokens.access" ".tokens.refresh"
# Also accept flat token format (only check if nested .tokens.access was missing)
if command -v jq >/dev/null 2>&1; then
  if ! jq -e '.tokens.access' "$RESP" >/dev/null 2>&1; then
    content_ok ".access_token"
    content_ok ".refresh_token"
  fi
fi
if command -v jq >/dev/null 2>&1; then
  TOKEN=$(jq -r '.tokens.access // .access_token' "$RESP")
else
  TOKEN=$(python3 -c "
import sys, json
d = json.load(open(sys.argv[1]))
t = d.get('tokens') or {}
print(t.get('access') or d.get('access_token') or '')
" "$RESP" 2>/dev/null)
fi
if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "  CONTENT FAIL: no access token in login response"
  FAILED=$((FAILED+1))
else
  echo "  OK: login returned user and token"
fi
content_value_ok ".user.email" "test@example.com" && echo "  OK: login .user.email is test@example.com" || true
echo ""

# 5. Authenticated: credits balance (total is number)
echo "5. Credits balance (auth)"
get_auth_and_check "$TOKEN" "/api/v1/credits/balance" ".total" ".subscription" ".purchased" ".bonus"
content_number_ok ".total" && echo "  OK: balance content valid" || true
echo ""

# 6. Authenticated: credits packages (packages is array)
echo "6. Credits packages (auth)"
get_auth_and_check "$TOKEN" "/api/v1/credits/packages" ".packages"
echo "  OK: packages has .packages array"
echo ""

# 7. Authenticated: /me (email matches test user)
echo "7. Auth /me (auth)"
get_auth_and_check "$TOKEN" "/api/v1/auth/me" ".id" ".email" ".email_verified"
content_value_ok ".email" "test@example.com" && echo "  OK: /me .email is test@example.com" || true
echo ""

# 8. Referrals code (referral_code non-empty string)
echo "8. Referrals code (auth)"
get_auth_and_check "$TOKEN" "/api/v1/referrals/code" ".referral_code" ".referral_url"
content_value_ok ".referral_code" "regex:^[A-Za-z0-9_-]*$" && echo "  OK: referral_code format valid" || true
echo ""

# 9. Referrals stats (numbers)
echo "9. Referrals stats (auth)"
get_auth_and_check "$TOKEN" "/api/v1/referrals/stats" ".referral_count" ".credits_earned"
content_number_ok ".referral_count" && content_number_ok ".credits_earned" && echo "  OK: referrals stats numbers valid" || true
echo ""

# 10. Uploads models (tool_type matches)
echo "10. Uploads models (auth)"
get_auth_and_check "$TOKEN" "/api/v1/uploads/models/background_removal" ".tool_type" ".models"
content_value_ok ".tool_type" "background_removal" && echo "  OK: uploads/models content valid" || true
echo ""

# 11. Frontend service
echo "11. Frontend service"
FRONT_CODE=$(curl -s -o /tmp/frontend_resp.html -w "%{http_code}" --connect-timeout 10 "$FRONTEND_BASE/" 2>/dev/null || echo "000")
if [ "$FRONT_CODE" != "200" ]; then
  echo "  HTTP FAIL: frontend $FRONTEND_BASE/ (code $FRONT_CODE)"
  FAILED=$((FAILED+1))
else
  if grep -q -i "VidGo\|vidgo\|<!DOCTYPE\|root" /tmp/frontend_resp.html 2>/dev/null; then
    echo "  OK: frontend returns 200 and app content"
  else
    echo "  OK: frontend returns 200 (content not inspected)"
  fi
fi
echo ""

echo "=========================================="
if [ "$FAILED" -gt 0 ]; then
  echo "RESULT: $FAILED content check(s) FAILED"
  exit 1
fi
echo "RESULT: All API content checks PASSED"
exit 0
