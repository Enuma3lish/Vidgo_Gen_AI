#!/usr/bin/env python3
"""
Comprehensive test of VidGo AI Platform with New Pricing Tiers
Based on current API architecture and mock-user-behavior.md
"""

import requests
import json
import sys
import time

BASE_URL = "http://localhost:8001"
API_URL = f"{BASE_URL}/api/v1"

def print_header(text):
    print(f"\n{'='*60}")
    print(f"{text}")
    print(f"{'='*60}")

def test_endpoint(name, endpoint, method="GET", expected_codes=[200, 201], auth=False):
    """Test a single API endpoint"""
    try:
        if method == "GET":
            response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        elif method == "POST":
            response = requests.post(f"{API_URL}{endpoint}", timeout=10)
        else:
            response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        
        if response.status_code in expected_codes:
            print(f"✅ {name}: HTTP {response.status_code}")
            return True, response
        else:
            print(f"❌ {name}: HTTP {response.status_code} (expected {expected_codes})")
            return False, response
    except Exception as e:
        print(f"⛔ {name}: Error - {str(e)}")
        return False, None

def main():
    print_header("VIDGO AI PLATFORM - COMPREHENSIVE TEST")
    print("Testing based on current API architecture with new pricing tiers")
    
    results = {"passed": 0, "failed": 0, "errors": 0}
    
    # 1. Core Infrastructure
    print_header("1. CORE INFRASTRUCTURE TESTS")
    
    # Health check - try both paths
    success, resp = test_endpoint("1.1 Health check", "/health", expected_codes=[200, 404])
    if success and resp.status_code == 200:
        results["passed"] += 1
        data = resp.json()
        print(f"   Status: {data.get('status')}")
        print(f"   Mode: {data.get('mode')}")
        print(f"   Materials ready: {data.get('materials_ready')}")
    else:
        # Try alternative path
        success2, resp2 = test_endpoint("1.1 Health check (alt)", "/api/v1/health", expected_codes=[200, 404])
        if success2 and resp2.status_code == 200:
            results["passed"] += 1
            data = resp2.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Mode: {data.get('mode')}")
            print(f"   Materials ready: {data.get('materials_ready')}")
        else:
            results["failed"] += 1
            print(f"   Note: Health endpoint not found at /health or /api/v1/health")
    
    # Swagger docs
    try:
        resp = requests.get(f"{BASE_URL}/docs", timeout=5)
        if resp.status_code == 200 and "Swagger UI" in resp.text:
            print("✅ 1.2 Swagger documentation: HTTP 200")
            results["passed"] += 1
        else:
            print(f"❌ 1.2 Swagger documentation: HTTP {resp.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"⛔ 1.2 Swagger documentation: Error - {str(e)}")
        results["errors"] += 1
    
    # 2. Demo/Preset Mode Tests
    print_header("2. DEMO/PRESET MODE TESTS")
    
    # Demo topics
    success, resp = test_endpoint("2.1 Demo topics", "/demo/topics")
    if success:
        results["passed"] += 1
        data = resp.json()
        topics = data.get('topics', {})
        print(f"   Tools with topics: {len(topics)}")
        for tool in topics:
            print(f"     {tool}: {len(topics[tool])} topics")
    else:
        results["failed"] += 1
    
    # Tool presets
    tools = [
        "background_removal",
        "product_scene",
        "try_on",
        "room_redesign",
        "short_video",
        "ai_avatar",
        "pattern_generate",
        "effect"
    ]
    
    print("\n2.2 Tool presets:")
    for tool in tools:
        success, resp = test_endpoint(f"   {tool}", f"/demo/presets/{tool}?limit=1")
        if success:
            results["passed"] += 1
            data = resp.json()
            presets = data.get('presets', [])
            print(f"     Presets count: {len(presets)}")
        else:
            results["failed"] += 1
    
    # 3. New Pricing Tiers & Plans Tests
    print_header("3. NEW PRICING TIERS & PLANS TESTS")
    
    plans_tests = [
        ("3.1 Plans list", "/plans"),
        ("3.2 Plan comparison", "/plans/comparison"),
        ("3.3 Service pricing", "/credits/pricing"),
        ("3.4 Active promotions", "/promotions/active"),
    ]
    
    for name, endpoint in plans_tests:
        success, resp = test_endpoint(name, endpoint)
        if success:
            results["passed"] += 1
            if "plans" in endpoint:
                data = resp.json()
                if isinstance(data, list):
                    plans = data
                else:
                    plans = data.get('plans', [])
                print(f"   Available plans: {len(plans)}")
                for plan in plans[:3]:  # Show first 3 plans
                    name = plan.get('name') or plan.get('display_name', 'Unknown')
                    price = plan.get('price_twd') or plan.get('price', 'N/A')
                    credits = plan.get('monthly_credits', 0)
                    print(f"     - {name}: TWD {price}/mo, {credits} credits")
        else:
            results["failed"] += 1
    
    # 4. Credit System Tests
    print_header("4. CREDIT SYSTEM TESTS")
    
    # Test credit service endpoints
    credit_tests = [
        ("4.1 Credit packages", "/credits/packages"),
        ("4.2 Credit transactions", "/credits/transactions"),
        ("4.3 Credit balance", "/credits/balance"),
    ]
    
    for name, endpoint in credit_tests:
        success, resp = test_endpoint(name, endpoint, expected_codes=[200, 401, 403])
        if success:
            results["passed"] += 1
            if resp.status_code == 200:
                data = resp.json()
                if "packages" in endpoint:
                    packages = data.get('packages', [])
                    print(f"   Credit packages: {len(packages)}")
                elif "balance" in endpoint:
                    print(f"   Balance: {data.get('total', 0)} credits")
        else:
            results["failed"] += 1
    
    # 5. Tools & Generation Tests
    print_header("5. TOOLS & GENERATION TESTS")
    
    tools_tests = [
        ("5.1 Tools models", "/tools/models/list"),
        ("5.2 Tools voices", "/tools/voices/list"),
        ("5.3 Effects styles", "/effects/styles"),
        ("5.4 Service status", "/generate/service-status"),
    ]
    
    for name, endpoint in tools_tests:
        success, resp = test_endpoint(name, endpoint)
        if success:
            results["passed"] += 1
            data = resp.json()
            if "models" in endpoint:
                models = data.get('models', [])
                print(f"   Available models: {len(models)}")
            elif "styles" in endpoint:
                styles = data.get('styles', [])
                print(f"   Effect styles: {len(styles)}")
        else:
            results["failed"] += 1
    
    # 6. Authentication Flow Test
    print_header("6. AUTHENTICATION FLOW TEST")
    
    # Test registration endpoint
    try:
        resp = requests.post(f"{API_URL}/auth/register", json={
            "email": "test@example.com",
            "password": "Test123!",
            "password_confirm": "Test123!"
        }, timeout=5)
        # Expecting validation error (400/422) or conflict (409) - endpoint exists
        if resp.status_code in [400, 422, 409]:
            print("✅ 6.1 Auth registration endpoint: HTTP {}".format(resp.status_code))
            results["passed"] += 1
        else:
            print(f"❌ 6.1 Auth registration endpoint: HTTP {resp.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"⛔ 6.1 Auth registration endpoint: Error - {str(e)}")
        results["errors"] += 1
    
    # Test mailpit
    try:
        resp = requests.get("http://localhost:8025/api/v1/messages", timeout=5)
        if resp.status_code == 200:
            print("✅ 6.2 Mailpit email service: HTTP 200")
            results["passed"] += 1
            data = resp.json()
            print(f"   Messages in mailpit: {data.get('total', 0)}")
        else:
            print(f"❌ 6.2 Mailpit email service: HTTP {resp.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"⛔ 6.2 Mailpit email service: Error - {str(e)}")
        results["errors"] += 1
    
    # 7. New Plan Features Tests
    print_header("7. NEW PLAN FEATURES TESTS")
    
    # Test plan permission checking
    success, resp = test_endpoint("7.1 Plan permission check", "/plans/check-permission?service_type=image_to_video_wan", expected_codes=[200, 401, 403])
    if success:
        results["passed"] += 1
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Has permission: {data.get('has_permission', False)}")
            print(f"   Service type: {data.get('service_type')}")
            print(f"   Credit cost: {data.get('credit_cost', 0)}")
    else:
        results["failed"] += 1
    
    # Test concurrent limit checking
    success, resp = test_endpoint("7.2 Concurrent limit check", "/plans/check-concurrent", expected_codes=[200, 401, 403])
    if success:
        results["passed"] += 1
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Within limit: {data.get('within_limit', False)}")
            print(f"   Current count: {data.get('current_count', 0)}")
            print(f"   Max concurrent: {data.get('max_concurrent', 1)}")
    else:
        results["failed"] += 1
    
    # 8. Materials Analysis
    print_header("8. MATERIALS ANALYSIS")
    
    try:
        resp = requests.get(f"{API_URL}/demo/materials/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Overall materials ready: {data.get('is_sufficient', False)}")
            print(f"Total required: {data.get('total_required', 0)}")
            print(f"Total current: {data.get('total_current', 0)}")
            print(f"Total missing: {data.get('total_missing', 0)}")
            print(f"Sufficiency percentage: {data.get('sufficiency_percentage', 0)}%")
            
            requirements = data.get('requirements', [])
            print(f"Requirements checked: {len(requirements)}")
            
            for req in requirements[:3]:  # Show first 3 requirements
                category = req.get('category', 'Unknown')
                tool_id = req.get('tool_id', 'Unknown')
                current = req.get('current_count', 0)
                required = req.get('min_count', 0)
                sufficient = req.get('is_sufficient', False)
                status = "✅" if sufficient else "❌"
                print(f"   {status} {category}/{tool_id}: {current}/{required}")
        else:
            print(f"Failed to get materials status: HTTP {resp.status_code}")
    except Exception as e:
        print(f"Error getting materials details: {str(e)}")
    
    # Summary
    print_header("TEST SUMMARY")
    
    total = results["passed"] + results["failed"] + results["errors"]
    print(f"Total tests: {total}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⛔ Errors: {results['errors']}")
    
    # Calculate percentage
    if total > 0:
        percentage = (results["passed"] / total) * 100
        print(f"Success rate: {percentage:.1f}%")
    
    # Final status
    if results["failed"] == 0 and results["errors"] == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n⚠️  Some tests failed or had errors.")
        return 1

if __name__ == "__main__":
    sys.exit(main())