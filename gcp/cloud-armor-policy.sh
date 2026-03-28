#!/bin/bash
# Cloud Armor Security Policy for VidGo
# Spec Section 四: Cloud Armor 擋惡意刷點 + /auth/* rate limit
#
# Usage: bash gcp/cloud-armor-policy.sh <PROJECT_ID>

set -euo pipefail

PROJECT_ID="${1:?Usage: $0 <PROJECT_ID>}"
POLICY_NAME="vidgo-security-policy"

echo "Creating Cloud Armor security policy: ${POLICY_NAME}"

# Create the security policy
gcloud compute security-policies create "${POLICY_NAME}" \
  --project="${PROJECT_ID}" \
  --description="VidGo WAF and rate limiting policy"

# Rule 1: Rate limit /auth/* endpoints (100 requests/min per IP)
gcloud compute security-policies rules create 1000 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="request.path.matches('/auth/.*') || request.path.matches('/api/v1/auth/.*')" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=100 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=300 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Rate limit auth endpoints: 100 req/min per IP, ban 5min on exceed"

# Rule 2: Rate limit /api/v1/generate/* (50 requests/min per IP)
gcloud compute security-policies rules create 2000 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="request.path.matches('/api/v1/generate/.*')" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=50 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=600 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Rate limit generation endpoints: 50 req/min per IP"

# Rule 3: Rate limit /api/v1/tools/* (30 requests/min per IP)
gcloud compute security-policies rules create 3000 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="request.path.matches('/api/v1/tools/.*')" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=30 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=600 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Rate limit tool endpoints: 30 req/min per IP"

# Rule 4: Block common attack patterns (SQLi, XSS)
gcloud compute security-policies rules create 4000 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('sqli-v33-stable')" \
  --action=deny-403 \
  --description="Block SQL injection attacks"

gcloud compute security-policies rules create 4100 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="evaluatePreconfiguredExpr('xss-v33-stable')" \
  --action=deny-403 \
  --description="Block XSS attacks"

# Rule 5: Block known bad user agents (scanners, bots)
gcloud compute security-policies rules create 5000 \
  --project="${PROJECT_ID}" \
  --security-policy="${POLICY_NAME}" \
  --expression="request.headers['user-agent'].matches('.*sqlmap.*|.*nikto.*|.*nmap.*|.*masscan.*')" \
  --action=deny-403 \
  --description="Block known malicious scanners"

echo ""
echo "Cloud Armor policy '${POLICY_NAME}' created successfully."
echo ""
echo "To attach to your backend service:"
echo "  gcloud compute backend-services update vidgo-backend-service \\"
echo "    --security-policy=${POLICY_NAME} \\"
echo "    --project=${PROJECT_ID} \\"
echo "    --global"
