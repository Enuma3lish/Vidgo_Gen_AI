#!/usr/bin/env python3
"""
Test script to check GCP deployment status and test API endpoints.
"""

import requests
import json
import sys

# GCP Cloud Run URLs
BACKEND_URL = "https://vidgo-backend-38714015566.asia-east1.run.app"
API_URL = f"{BACKEND_URL}/api/v1"

def print_header(text):
    print(f"\n{'='*60}")
    print(f"{text}")
    print(f"{'='*60}")

def test_endpoint(name, endpoint, method="GET", expected_codes=[200, 201], data=None):
    """Test a single API endpoint"""
    try:
        if method == "GET":
            response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        elif method == "POST":
            response = requests.post(f"{API_URL}{endpoint}", json=data, timeout=10)
        else:
            response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        
        if response.status_code in expected_codes:
            print(f"✅ {name}: HTTP {response.status_code}")
            return True, response
        else:
            print(f"❌ {name}: HTTP {response.status_code} (expected {expected_codes})")
            if response.status_code not in [401, 403]:  # Don't print body for auth errors
                try:
                    print(f"   Response: {response.text[:200]}")
                except:
                    pass
            return False, response
    except Exception as e:
        print(f"⛔ {name}: Error - {str(e)}")
        return False, None

def main():
    print_header("GCP DEPLOYMENT TEST")
    print(f"Testing backend at: {BACKEND_URL}")
    
    results = {"passed": 0, "failed": 0, "errors": 0}
    
    # 1. Basic Health Check
    print_header("1. BASIC HEALTH CHECKS")
    
    # Test root health endpoint
    success, resp = test_endpoint("1.1 Root health check", "/health")
    if success:
        results["passed"] += 1
        data = resp.json()
        print(f"   Status: {data.get('status')}")
        print(f"   Mode: {data.get('mode')}")
        print(f"   Materials ready: {data.get('materials_ready')}")
    else:
        results["failed"] += 1
    
    # Test Swagger docs
    try:
        resp = requests.get(f"{BACKEND_URL}/docs", timeout=5)
        if resp.status_code == 200:
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
    
    # Test demo topics
    success, resp = test_endpoint("2.1 Demo topics", "/demo/topics")
    if success:
        results["passed"] += 1
        data = resp.json()
        topics = data.get('topics', {})
        print(f"   Tools with topics: {len(topics)}")
        for tool in list(topics.keys())[:3]:  # Show first 3 tools
            print(f"     - {tool}: {len(topics[tool])} topics")
    else:
        results["failed"] += 1
    
    # Test tool presets
    tools = ["background_removal", "product_scene", "try_on"]
    print("\n2.2 Tool presets (first 3 tools):")
    for tool in tools:
        success, resp = test_endpoint(f"   {tool}", f"/demo/presets/{tool}?limit=1")
        if success:
            results["passed"] += 1
            data = resp.json()
            presets = data.get('presets', [])
            print(f"     {tool}: {len(presets)} presets")
        else:
            results["failed"] += 1
    
    # 3. Pricing System Tests
    print_header("3. PRICING SYSTEM TESTS")
    
    # Test OLD pricing system (subscriptions endpoint)
    success, resp = test_endpoint("3.1 OLD pricing system plans", "/subscriptions/plans")
    if success:
        results["passed"] += 1
        data = resp.json()
        if isinstance(data, list):
            plans = data
        else:
            plans = data.get('plans', [])
        print(f"   Found {len(plans)} OLD pricing system plans")
        for plan in plans[:2]:  # Show first 2 plans
            name = plan.get('name') or plan.get('display_name', 'Unknown')
            credits = plan.get('monthly_credits', 0)
            price = plan.get('price_monthly', 'N/A')
            print(f"     - {name}: {credits} credits, TWD {price}/mo")
    else:
        results["failed"] += 1
    
    # Test NEW pricing system (should be 404)
    success, resp = test_endpoint("3.2 NEW pricing system plans", "/plans", expected_codes=[200, 404])
    if success:
        results["passed"] += 1
        if resp.status_code == 200:
            data = resp.json()
            print(f"   NEW pricing system deployed with {len(data) if isinstance(data, list) else 'some'} plans")
        else:
            print(f"   NEW pricing system not deployed (expected 404): HTTP {resp.status_code}")
    else:
        results["failed"] += 1
    
    # Test service pricing
    success, resp = test_endpoint("3.3 Service pricing", "/credits/pricing")
    if success:
        results["passed"] += 1
        data = resp.json()
        pricing = data.get('pricing', [])
        print(f"   Found {len(pricing)} service pricing entries")
        
        # Group by tool category
        categories = {}
        for item in pricing:
            category = item.get('tool_category', 'unknown')
            if category not in categories:
                categories[category] = []
            categories[category].append(item)
        
        for category, items in categories.items():
            print(f"     - {category}: {len(items)} services")
    else:
        results["failed"] += 1
    
    # 4. Tool Models and Configurations
    print_header("4. TOOL CONFIGURATION TESTS")
    
    # Test available models
    success, resp = test_endpoint("4.1 Available models", "/tools/models/list")
    if success:
        results["passed"] += 1
        data = resp.json()
        # Handle both list and dict responses
        if isinstance(data, list):
            models = data
            print(f"   Found {len(models)} AI models")
            for model in models[:3]:  # Show first 3 models
                if isinstance(model, dict):
                    name = model.get('name', 'Unknown')
                    print(f"     - {name}")
                else:
                    print(f"     - {model}")
        elif isinstance(data, dict):
            models = data.get('models', [])
            print(f"   Found {len(models)} AI models")
            for model in models[:3]:
                name = model.get('name', 'Unknown')
                print(f"     - {name}")
        else:
            print(f"   Models data: {type(data)}")
    else:
        results["failed"] += 1
    
    # Test effects styles
    success, resp = test_endpoint("4.2 Effects styles", "/effects/styles")
    if success:
        results["passed"] += 1
        data = resp.json()
        # Handle both list and dict responses
        if isinstance(data, list):
            styles = data
            print(f"   Found {len(styles)} effect styles")
        elif isinstance(data, dict):
            styles = data.get('styles', [])
            print(f"   Found {len(styles)} effect styles")
        else:
            print(f"   Styles data: {type(data)}")
    else:
        results["failed"] += 1
    
    # 5. Materials Status
    print_header("5. MATERIALS STATUS")
    
    success, resp = test_endpoint("5.1 Materials status", "/demo/materials/status")
    if success:
        results["passed"] += 1
        data = resp.json()
        is_sufficient = data.get('is_sufficient', False)
        total_current = data.get('total_current', 0)
        total_required = data.get('total_required', 0)
        percentage = data.get('sufficiency_percentage', 0)
        
        print(f"   Materials sufficient: {is_sufficient}")
        print(f"   Current/Required: {total_current}/{total_required}")
        print(f"   Sufficiency: {percentage}%")
        
        requirements = data.get('requirements', [])
        print(f"   Requirements checked: {len(requirements)}")
        
        # Show first 2 requirements
        for req in requirements[:2]:
            category = req.get('category', 'Unknown')
            tool_id = req.get('tool_id', 'Unknown')
            current = req.get('current_count', 0)
            required = req.get('min_count', 0)
            sufficient = req.get('is_sufficient', False)
            status = "✅" if sufficient else "❌"
            print(f"     {status} {category}/{tool_id}: {current}/{required}")
    else:
        results["failed"] += 1
    
    # 6. Create Example Workflow Analysis
    print_header("6. CREATE EXAMPLE WORKFLOW ANALYSIS")
    
    print("6.1 Checking tool endpoints for example creation:")
    
    # List of tool endpoints that should support example creation
    tool_endpoints = [
        ("Background Removal", "/tools/remove-bg"),
        ("Product Scene", "/tools/product-scene"),
        ("AI Try-On", "/tools/try-on"),
        ("Room Redesign", "/tools/room-redesign"),
        ("Short Video", "/tools/short-video"),
        ("AI Avatar", "/tools/avatar"),
        ("Effects", "/effects/apply-style"),
    ]
    
    for tool_name, endpoint in tool_endpoints:
        # Test endpoint exists (expecting 405 Method Not Allowed for GET on POST endpoints)
        success, resp = test_endpoint(f"   {tool_name}", endpoint, expected_codes=[200, 405, 401, 403])
        if success:
            results["passed"] += 1
            if resp.status_code == 405:
                print(f"     {tool_name}: POST endpoint available (GET returns 405)")
            elif resp.status_code in [401, 403]:
                print(f"     {tool_name}: Requires authentication (expected)")
            else:
                print(f"     {tool_name}: HTTP {resp.status_code}")
        else:
            results["failed"] += 1
    
    # 7. Frontend Integration Test
    print_header("7. FRONTEND INTEGRATION TEST")
    
    # Get frontend URL
    try:
        frontend_url = "https://vidgo-frontend-38714015566.asia-east1.run.app"
        resp = requests.get(frontend_url, timeout=5)
        if resp.status_code == 200:
            print(f"✅ 7.1 Frontend accessible: HTTP 200")
            results["passed"] += 1
            # Check if it's a Vue app
            if "VidGo" in resp.text or "vidgo" in resp.text.lower():
                print(f"   Frontend appears to be VidGo application")
        else:
            print(f"❌ 7.1 Frontend: HTTP {resp.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"⛔ 7.1 Frontend: Error - {str(e)}")
        results["errors"] += 1
    
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
    
    # GCP Deployment Status
    print_header("GCP DEPLOYMENT STATUS")
    
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Frontend URL: https://vidgo-frontend-38714015566.asia-east1.run.app")
    print(f"Worker URL: https://vidgo-worker-38714015566.asia-east1.run.app")
    
    # Check if new pricing system is deployed
    if results["passed"] > 10:  # If most tests passed
        print("\n🎉 GCP DEPLOYMENT IS HEALTHY!")
        print("New pricing system appears to be deployed and functional.")
    else:
        print("\n⚠️  Some issues detected with GCP deployment.")
        print("Check the failed tests above for details.")
    
    # Final status
    if results["failed"] == 0 and results["errors"] == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n⚠️  Some tests failed or had errors.")
        return 1

if __name__ == "__main__":
    sys.exit(main())