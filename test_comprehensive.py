#!/usr/bin/env python3
"""
Comprehensive test of VidGo AI Platform
Based on docs/human_test.md
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
    print("Testing based on docs/human_test.md")
    
    results = {"passed": 0, "failed": 0, "errors": 0}
    
    # 1. Core Infrastructure
    print_header("1. CORE INFRASTRUCTURE TESTS")
    
    # Health check
    success, resp = test_endpoint("1.1 Health check", "/health")
    if success:
        results["passed"] += 1
        data = resp.json()
        print(f"   Status: {data.get('status')}")
        print(f"   Mode: {data.get('mode')}")
        print(f"   Materials ready: {data.get('materials_ready')}")
    else:
        results["failed"] += 1
    
    # Materials status
    success, resp = test_endpoint("1.2 Materials status", "/materials/status")
    if success:
        results["passed"] += 1
        data = resp.json()
        print(f"   Materials ready: {data.get('materials_ready')}")
        tools = data.get('tools', {})
        print(f"   Tools with materials: {len(tools)}")
    else:
        results["failed"] += 1
    
    # Swagger docs
    try:
        resp = requests.get(f"{BASE_URL}/docs", timeout=5)
        if resp.status_code == 200 and "Swagger UI" in resp.text:
            print("✅ 1.3 Swagger documentation: HTTP 200")
            results["passed"] += 1
        else:
            print(f"❌ 1.3 Swagger documentation: HTTP {resp.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"⛔ 1.3 Swagger documentation: Error - {str(e)}")
        results["errors"] += 1
    
    # 2. Landing Page Tests
    print_header("2. LANDING PAGE TESTS (Guest)")
    
    landing_tests = [
        ("2.1 Landing stats", "/landing/stats"),
        ("2.2 Landing features", "/landing/features"),
        ("2.3 Landing examples", "/landing/examples"),
        ("2.4 Landing pricing", "/landing/pricing"),
        ("2.5 Landing FAQ", "/landing/faq"),
    ]
    
    for name, endpoint in landing_tests:
        success, resp = test_endpoint(name, endpoint)
        if success:
            results["passed"] += 1
            if "stats" in endpoint:
                data = resp.json()
                print(f"   Total generations: {data.get('total_generations')}")
                print(f"   Total users: {data.get('total_users')}")
                print(f"   Tools count: {data.get('tools_count')}")
        else:
            results["failed"] += 1
    
    # 3. Demo/Preset Mode Tests
    print_header("3. DEMO/PRESET MODE TESTS")
    
    # Demo topics
    success, resp = test_endpoint("3.1 Demo topics", "/demo/topics")
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
    
    print("\n3.2 Tool presets:")
    for tool in tools:
        success, resp = test_endpoint(f"   {tool}", f"/demo/presets/{tool}?limit=1")
        if success:
            results["passed"] += 1
            data = resp.json()
            presets = data.get('presets', [])
            print(f"     Presets count: {len(presets)}")
        else:
            results["failed"] += 1
    
    # 4. Plans & Credits Tests
    print_header("4. PLANS & CREDITS TESTS")
    
    plans_tests = [
        ("4.1 Plans list", "/plans"),
        ("4.2 Credits pricing", "/credits/pricing"),
        ("4.3 Active promotions", "/promotions/active"),
    ]
    
    for name, endpoint in plans_tests:
        success, resp = test_endpoint(name, endpoint)
        if success:
            results["passed"] += 1
            if "plans" in endpoint:
                data = resp.json()
                plans = data.get('plans', [])
                print(f"   Available plans: {len(plans)}")
                for plan in plans:
                    print(f"     - {plan.get('name')}: ${plan.get('monthly_price')}/mo")
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
    
    # 7. Detailed Materials Analysis
    print_header("7. DETAILED MATERIALS ANALYSIS")
    
    try:
        resp = requests.get(f"{BASE_URL}/materials/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            tools = data.get('tools', {})
            
            print(f"Overall materials ready: {data.get('materials_ready')}")
            print(f"Total tools with materials: {len(tools)}")
            
            for tool, status in tools.items():
                ready = status.get('ready', False)
                count = status.get('count', 0)
                topics = status.get('topics', {})
                
                status_symbol = "✅" if ready else "❌"
                print(f"\n{status_symbol} {tool}:")
                print(f"  Ready: {ready}")
                print(f"  Total materials: {count}")
                print(f"  Topics with materials: {len(topics)}")
                
                if topics:
                    for topic, topic_data in topics.items():
                        topic_ready = topic_data.get('ready', False)
                        topic_count = topic_data.get('count', 0)
                        topic_symbol = "✓" if topic_ready else "✗"
                        print(f"    {topic_symbol} {topic}: {topic_ready} ({topic_count} materials)")
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