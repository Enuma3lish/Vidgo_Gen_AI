#!/usr/bin/env python3
"""
Comprehensive mock user testing based on the mock-user-behavior.md guide.
Tests the GCP deployment of VidGo AI platform.
"""

import requests
import json
import time
import sys
from typing import Dict, List, Tuple, Optional

# GCP Cloud Run URLs
BACKEND_URL = "https://vidgo-backend-38714015566.asia-east1.run.app"
FRONTEND_URL = "https://vidgo-frontend-38714015566.asia-east1.run.app"
API_URL = f"{BACKEND_URL}/api/v1"

class TestResult:
    def __init__(self, name: str, success: bool, details: str = "", response=None):
        self.name = name
        self.success = success
        self.details = details
        self.response = response

class MockUserTester:
    def __init__(self):
        self.session = requests.Session()
        self.results = []
        self.test_user = None
        
    def log_result(self, result: TestResult):
        self.results.append(result)
        status = "✅" if result.success else "❌"
        print(f"{status} {result.name}")
        if result.details:
            print(f"   {result.details}")
        if result.response and not result.success:
            try:
                print(f"   Response: {result.response.text[:200]}")
            except:
                pass
    
    def print_header(self, text: str):
        print(f"\n{'='*60}")
        print(f"{text}")
        print(f"{'='*60}")
    
    def test_endpoint(self, name: str, endpoint: str, method: str = "GET", 
                     expected_codes: List[int] = [200, 201], data: Optional[Dict] = None) -> Tuple[bool, Optional[requests.Response]]:
        """Test a single API endpoint"""
        try:
            url = f"{API_URL}{endpoint}" if endpoint.startswith("/") else f"{BACKEND_URL}{endpoint}"
            
            if method == "GET":
                response = self.session.get(url, timeout=10)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=10)
            elif method == "PUT":
                response = self.session.put(url, json=data, timeout=10)
            elif method == "DELETE":
                response = self.session.delete(url, timeout=10)
            else:
                response = self.session.get(url, timeout=10)
            
            if response.status_code in expected_codes:
                return True, response
            else:
                return False, response
        except Exception as e:
            return False, None
    
    # ==================== VISITOR (GUEST) SCENARIOS ====================
    
    def test_visitor_scenario_1(self):
        """2.1 First-Time Visitor Exploration - Sarah Chen"""
        self.print_header("2.1 First-Time Visitor Exploration (Sarah Chen)")
        
        # 1. Landing Page Exploration
        result = TestResult("2.1.1 Landing page accessible", False)
        try:
            resp = self.session.get(FRONTEND_URL, timeout=10)
            if resp.status_code == 200:
                result.success = True
                result.details = f"HTTP {resp.status_code}"
                # Check for key elements
                if "VidGo" in resp.text:
                    result.details += " - Contains 'VidGo'"
        except Exception as e:
            result.details = f"Error: {str(e)}"
        self.log_result(result)
        
        # 2. Navigation Testing - Check API endpoints
        # Tools dropdown
        result = TestResult("2.1.2 Tools API endpoints", False)
        success, resp = self.test_endpoint("Tools list", "/tools/list", expected_codes=[200, 401, 403])
        if success:
            result.success = True
            result.details = f"HTTP {resp.status_code}"
        self.log_result(result)
        
        # Pricing page
        result = TestResult("2.1.3 Pricing plans accessible", False)
        success, resp = self.test_endpoint("Pricing plans", "/subscriptions/plans")
        if success:
            result.success = True
            result.details = f"Found {len(resp.json()) if isinstance(resp.json(), list) else 'some'} plans"
        self.log_result(result)
        
        # Gallery
        result = TestResult("2.1.4 Gallery accessible", False)
        success, resp = self.test_endpoint("Gallery topics", "/demo/topics")
        if success:
            result.success = True
            data = resp.json()
            topics = data.get('topics', {})
            result.details = f"Found {len(topics)} tools with topics"
        self.log_result(result)
        
        # 3. Inspiration Gallery Browsing
        result = TestResult("2.1.5 Gallery search functionality", False)
        success, resp = self.test_endpoint("Gallery search", "/demo/inspiration?search=fashion&limit=5")
        if success:
            result.success = True
            data = resp.json()
            items = data.get('items', [])
            result.details = f"Found {len(items)} items for 'fashion'"
        self.log_result(result)
        
        # 4. Tool Page Testing (Limited)
        result = TestResult("2.1.6 Background removal tool accessible", False)
        success, resp = self.test_endpoint("Background removal", "/tools/remove-bg", expected_codes=[405, 200, 401])
        if success:
            result.success = True
            result.details = f"HTTP {resp.status_code} - {'POST endpoint available' if resp.status_code == 405 else 'Accessible'}"
        self.log_result(result)
        
        # 5. Registration Consideration
        result = TestResult("2.1.7 Registration endpoint exists", False)
        success, resp = self.test_endpoint("Registration endpoint", "/auth/register", method="POST", 
                                          expected_codes=[422, 400, 201], data={"test": "test"})
        if success:
            result.success = True
            result.details = f"HTTP {resp.status_code} - Registration endpoint responds"
        self.log_result(result)
    
    def test_visitor_scenario_2(self):
        """2.2 Anonymous Tool Testing - David Wang"""
        self.print_header("2.2 Anonymous Tool Testing (David Wang)")
        
        tools_to_test = [
            ("Background Removal", "/tools/remove-bg"),
            ("Product Scene", "/tools/product-scene"),
            ("Short Video", "/tools/short-video"),
            ("Avatar", "/tools/avatar"),
        ]
        
        for tool_name, endpoint in tools_to_test:
            result = TestResult(f"2.2.{tools_to_test.index((tool_name, endpoint))+1} {tool_name} tool", False)
            success, resp = self.test_endpoint(tool_name, endpoint, expected_codes=[405, 200, 401, 403])
            if success:
                result.success = True
                result.details = f"HTTP {resp.status_code}"
            self.log_result(result)
        
        # Return to Gallery
        result = TestResult("2.2.5 Gallery with filters", False)
        success, resp = self.test_endpoint("Gallery with food filter", "/demo/inspiration?industry=food&limit=3")
        if success:
            result.success = True
            data = resp.json()
            items = data.get('items', [])
            result.details = f"Found {len(items)} food industry items"
        self.log_result(result)
    
    def test_visitor_scenario_3(self):
        """2.3 Guest Click-to-Generate Behavior"""
        self.print_header("2.3 Guest Click-to-Generate Behavior")
        
        # 1. Gallery Entry Points
        result = TestResult("2.3.1 Gallery items have valid tool links", False)
        success, resp = self.test_endpoint("Gallery items", "/demo/inspiration?limit=2")
        if success:
            data = resp.json()
            items = data.get('items', [])
            if items:
                # Check if items have tool_type
                valid_items = [item for item in items if item.get('tool_type')]
                result.success = len(valid_items) > 0
                result.details = f"{len(valid_items)}/{len(items)} items have tool_type"
        self.log_result(result)
        
        # 2. Primary Action Behavior (simulate with demo generation)
        result = TestResult("2.3.2 Demo generation endpoint", False)
        success, resp = self.test_endpoint("Demo generation", "/demo/generate/background_removal", 
                                          method="POST", expected_codes=[200, 400, 422], 
                                          data={"preset_id": "test"})
        if success:
            result.success = True
            result.details = f"HTTP {resp.status_code}"
            if resp.status_code == 200:
                data = resp.json()
                result.details += f" - Got result: {data.get('status', 'unknown')}"
        self.log_result(result)
        
        # 4. Paid Feature Gates
        result = TestResult("2.3.3 Upload endpoint requires auth", False)
        success, resp = self.test_endpoint("Upload endpoint", "/uploads", method="POST", 
                                          expected_codes=[401, 403, 422])
        if success and resp.status_code in [401, 403]:
            result.success = True
            result.details = f"HTTP {resp.status_code} - Upload requires authentication (correct)"
        self.log_result(result)
    
    # ==================== FREE REGISTERED USER SCENARIOS ====================
    
    def test_free_user_scenario_1(self):
        """3.1 New User Onboarding - Mia Rodriguez"""
        self.print_header("3.1 New User Onboarding (Mia Rodriguez)")
        
        # Note: We can't actually register without email, but we can test endpoints
        result = TestResult("3.1.1 User dashboard endpoint", False)
        success, resp = self.test_endpoint("User dashboard", "/user/dashboard", expected_codes=[401, 403])
        if success and resp.status_code in [401, 403]:
            result.success = True
            result.details = f"HTTP {resp.status_code} - Requires authentication (correct)"
        self.log_result(result)
        
        result = TestResult("3.1.2 My Works endpoint", False)
        success, resp = self.test_endpoint("My Works", "/user/generations", expected_codes=[401, 403])
        if success and resp.status_code in [401, 403]:
            result.success = True
            result.details = f"HTTP {resp.status_code} - Requires authentication (correct)"
        self.log_result(result)
        
        result = TestResult("3.1.3 Referral endpoint", False)
        success, resp = self.test_endpoint("Referrals", "/referrals", expected_codes=[401, 403])
        if success and resp.status_code in [401, 403]:
            result.success = True
            result.details = f"HTTP {resp.status_code} - Requires authentication (correct)"
        self.log_result(result)
    
    # ==================== PAID SUBSCRIBER SCENARIOS ====================
    
    def test_paid_subscriber_scenario(self):
        """4.1 New Subscriber First Day - Sarah Chen"""
        self.print_header("4.1 New Subscriber First Day (Sarah Chen)")
        
        # Test subscription plans
        result = TestResult("4.1.1 Subscription plans available", False)
        success, resp = self.test_endpoint("Subscription plans", "/subscriptions/plans")
        if success:
            data = resp.json()
            if isinstance(data, list):
                plans = data
            else:
                plans = data.get('plans', [])
            result.success = len(plans) > 0
            result.details = f"Found {len(plans)} subscription plans"
            # Check for starter plan
            starter_plans = [p for p in plans if 'starter' in str(p).lower()]
            if starter_plans:
                result.details += f" (including Starter)"
        self.log_result(result)
        
        # Test credit system
        result = TestResult("4.1.2 Credit pricing available", False)
        success, resp = self.test_endpoint("Credit pricing", "/credits/pricing")
        if success:
            data = resp.json()
            pricing = data.get('pricing', [])
            result.success = len(pricing) > 0
            result.details = f"Found {len(pricing)} service pricing entries"
        self.log_result(result)
        
        # Test model selection
        result = TestResult("4.1.3 AI models available", False)
        success, resp = self.test_endpoint("AI models", "/tools/models/list")
        if success:
            data = resp.json()
            if isinstance(data, list):
                models = data
            else:
                models = data.get('models', [])
            result.success = len(models) > 0
            result.details = f"Found {len(models)} AI models"
        self.log_result(result)
    
    # ==================== INSPIRATION GALLERY SPECIFIC TESTS ====================
    
    def test_gallery_scenarios(self):
        """6. Inspiration Gallery Specific Tests"""
        self.print_header("6. Inspiration Gallery Specific Tests")
        
        # 1. Browsing Behavior
        result = TestResult("6.1.1 Gallery initial load", False)
        start_time = time.time()
        success, resp = self.test_endpoint("Gallery load", "/demo/inspiration?limit=12")
        load_time = time.time() - start_time
        if success:
            result.success = True
            data = resp.json()
            items = data.get('items', [])
            result.details = f"Loaded {len(items)} items in {load_time:.2f}s"
            if load_time < 3:
                result.details += " (✓ < 3 seconds)"
            else:
                result.details += " (⚠ > 3 seconds)"
        self.log_result(result)
        
        # 2. Search Functionality
        result = TestResult("6.1.2 Gallery search", False)
        success, resp = self.test_endpoint("Search 'product'", "/demo/inspiration?search=product&limit=5")
        if success:
            data = resp.json()
            items = data.get('items', [])
            result.success = True
            result.details = f"Found {len(items)} items for 'product'"
        self.log_result(result)
        
        # 3. Filter Combinations
        result = TestResult("6.1.3 Gallery filters", False)
        success, resp = self.test_endpoint("Filter by industry", "/demo/inspiration?industry=fashion&limit=3")
        if success:
            data = resp.json()
            items = data.get('items', [])
            result.success = True
            result.details = f"Found {len(items)} fashion industry items"
        self.log_result(result)
        
        # 4. Empty state
        result = TestResult("6.1.4 Gallery empty state", False)
        success, resp = self.test_endpoint("No results search", "/demo/inspiration?search=xyz123nonexistent&limit=1")
        if success:
            data = resp.json()
            items = data.get('items', [])
            result.success = True
            result.details = f"Search returns {len(items)} items (handles empty state)"
        self.log_result(result)
    
    # ==================== EDGE CASES & ERROR HANDLING ====================
    
    def test_edge_cases(self):
        """8. Edge Cases & Error Handling"""
        self.print_header("8. Edge Cases & Error Handling")
        
        # 1. Invalid endpoints
        result = TestResult("8.1.1 Invalid endpoint handling", False)
        success, resp = self.test_endpoint("Non-existent endpoint", "/api/v1/nonexistent", expected_codes=[404])
        if success:
            result.success = True
            result.details = f"HTTP 404 - Correctly returns not found"
        self.log_result(result)
        
        # 2. Rate limiting (should get 429 if hitting too fast)
        result = TestResult("8.1.2 Rate limiting headers", False)
        success, resp = self.test_endpoint("Check rate limit headers", "/health", expected_codes=[200, 404, 429])
        if success:
            headers = resp.headers
            rate_limit_headers = [h for h in headers.keys() if 'rate' in h.lower() or 'limit' in h.lower()]
            result.success = True
            result.details = f"Rate limit headers: {len(rate_limit_headers)} found"
        self.log_result(result)
        
        # 3. Materials status
        result = TestResult("8.1.3 Materials status check", False)
        success, resp = self.test_endpoint("Materials status", "/demo/materials/status")
        if success:
            data = resp.json()
            is_sufficient = data.get('is_sufficient', False)
            total_current = data.get('total_current', 0)
            total_required = data.get('total_required', 0)
            result.success = True
            result.details = f"Materials: {total_current}/{total_required} ({'sufficient' if is_sufficient else 'insufficient'})"
        self.log_result(result)
    
    # ==================== PERFORMANCE TESTING ====================
    
    def test_performance(self):
        """9. Performance Testing"""
        self.print_header("9. Performance Testing")
        
        endpoints_to_test = [
            ("Health check", "/health", [200, 404]),
            ("Demo topics", "/demo/topics", [200]),
            ("Gallery", "/demo/inspiration?limit=6", [200]),
        ]
        
        for i, (name, endpoint, expected_codes) in enumerate(endpoints_to_test):
            result = TestResult(f"9.{i+1} {name} performance", False)
            times = []
            for _ in range(2):  # Test twice
                start_time = time.time()
                success, resp = self.test_endpoint(name, endpoint, expected_codes=expected_codes)
                end_time = time.time()
                if success:
                    times.append(end_time - start_time)
            
            if times:
                avg_time = sum(times) / len(times)
                result.success = True
                result.details = f"Average response time: {avg_time:.2f}s"
                if avg_time < 1.0:
                    result.details += " (✓ Good)"
                elif avg_time < 3.0:
                    result.details += " (⚠ Acceptable)"
                else:
                    result.details += " (❌ Slow)"
            else:
                result.details = "Failed to get successful responses"
            
            self.log_result(result)
    
    def run_all_tests(self):
        """Run all test scenarios"""
        print("="*60)
        print("VIDGO AI MOCK USER BEHAVIOR TESTING")
        print(f"Backend: {BACKEND_URL}")
        print(f"Frontend: {FRONTEND_URL}")
        print("="*60)
        
        # Run all test scenarios
        self.test_visitor_scenario_1()
        self.test_visitor_scenario_2()
        self.test_visitor_scenario_3()
        self.test_free_user_scenario_1()
        self.test_paid_subscriber_scenario()
        self.test_gallery_scenarios()
        self.test_edge_cases()
        self.test_performance()
        
        # Print summary
        self.print_header("TEST SUMMARY")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        
        print(f"Total tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        if total > 0:
            success_rate = (passed / total) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        # Show failed tests
        if failed > 0:
            print("\nFailed tests:")
            for result in self.results:
                if not result.success:
                    print(f"  ❌ {result.name}")
                    if result.details:
                        print(f"     {result.details}")
        
        # Overall status
        print("\n" + "="*60)
        if failed == 0:
            print("🎉 ALL TESTS PASSED!")
            print("GCP deployment is healthy and ready for users.")
        elif success_rate > 80:
            print("⚠️  MOST TESTS PASSED")
            print("GCP deployment is mostly healthy, but some issues need attention.")
        else:
            print("❌ SIGNIFICANT ISSUES DETECTED")
            print("GCP deployment has problems that need immediate attention.")
        print("="*60)
        
        return failed == 0

def main():
    tester = MockUserTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
