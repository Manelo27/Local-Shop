#!/usr/bin/env python3
"""
Local Shop Pro - Backend API Testing Suite
Tests authentication, merchant isolation, product management, and new features
"""

import requests
import json
import sys
from datetime import datetime
import time

class LocalShopProTester:
    def __init__(self, base_url="https://9c19a8ee-cbd2-4c97-ba8a-814725eddddd.preview.emergentagent.com"):
        self.base_url = base_url
        self.merchant1_token = None
        self.merchant2_token = None
        self.merchant1_id = None
        self.merchant2_id = None
        self.test_product_id = None
        self.tests_run = 0
        self.tests_passed = 0
        
        print(f"🏪 Local Shop Pro API Testing Suite")
        print(f"🌐 Testing against: {base_url}")
        print("=" * 60)

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
        if details:
            print(f"   {details}")

    def api_call(self, endpoint, method="GET", data=None, token=None, expected_status=200):
        """Make API call with error handling"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)

            success = response.status_code == expected_status
            return success, response.json() if response.content else {}, response.status_code

        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}, 0
        except json.JSONDecodeError:
            return False, {"error": "Invalid JSON response"}, response.status_code

    def test_health_check(self):
        """Test API health endpoint"""
        success, data, status = self.api_call("api/health")
        self.log_test("Health Check", success and data.get("status") == "healthy", 
                     f"Status: {status}, Service: {data.get('service', 'Unknown')}")
        return success

    def test_categories_endpoint(self):
        """Test categories endpoint with new extended categories"""
        success, data, status = self.api_call("api/categories")
        
        expected_categories = [
            "BOULANGERIE_PATISSERIE", "BOUCHERIE_CHARCUTERIE", "POISSONNERIE",
            "BIJOUTERIE_HORLOGERIE", "PHARMACIE_PARAPHARMACIE", "OPTIQUE",
            "ELECTRONIQUE_INFORMATIQUE", "AUTOMOBILE_MOTO", "FLEURS_PLANTES"
        ]
        
        categories_found = data.get("categories", [])
        new_categories_present = all(cat in categories_found for cat in expected_categories)
        has_subcategories = bool(data.get("subcategories"))
        
        test_success = success and len(categories_found) >= 26 and new_categories_present and has_subcategories
        
        self.log_test("Extended Categories (26 categories)", test_success,
                     f"Found {len(categories_found)} categories, Subcategories: {has_subcategories}")
        return test_success

    def test_merchant_registration(self, merchant_num=1):
        """Test merchant registration with geolocation"""
        timestamp = int(time.time())
        registration_data = {
            "email": f"merchant{merchant_num}_{timestamp}@test.com",
            "password": "TestPass123!",
            "profile": {
                "business_name": f"Test Commerce {merchant_num}",
                "business_type": "Boulangerie artisanale" if merchant_num == 1 else "Boucherie traditionnelle",
                "phone": f"012345678{merchant_num}",
                "location": {
                    "address": "123 rue de Rivoli" if merchant_num == 1 else "456 avenue des Champs",
                    "city": "Paris",
                    "postal_code": "75001",
                    "country": "France"
                },
                "description": f"Commerce de test {merchant_num}"
            }
        }

        success, data, status = self.api_call("api/auth/register", "POST", registration_data, expected_status=200)
        
        if success and data.get("access_token"):
            if merchant_num == 1:
                self.merchant1_token = data["access_token"]
                self.merchant1_id = data.get("merchant_id")
            else:
                self.merchant2_token = data["access_token"]
                self.merchant2_id = data.get("merchant_id")
            
            self.log_test(f"Merchant {merchant_num} Registration", True,
                         f"Business: {data.get('business_name')}, ID: {data.get('merchant_id')[:8]}...")
            return True
        else:
            self.log_test(f"Merchant {merchant_num} Registration", False,
                         f"Status: {status}, Error: {data.get('detail', 'Unknown error')}")
            return False

    def test_merchant_login(self, email, password, merchant_num=1):
        """Test merchant login"""
        login_data = {"email": email, "password": password}
        success, data, status = self.api_call("api/auth/login", "POST", login_data, expected_status=200)
        
        if success and data.get("access_token"):
            if merchant_num == 1:
                self.merchant1_token = data["access_token"]
                self.merchant1_id = data.get("merchant_id")
            
            self.log_test(f"Merchant {merchant_num} Login", True,
                         f"Business: {data.get('business_name')}")
            return True
        else:
            self.log_test(f"Merchant {merchant_num} Login", False,
                         f"Status: {status}, Error: {data.get('detail', 'Unknown error')}")
            return False

    def test_profile_access(self, merchant_num=1):
        """Test merchant profile access"""
        token = self.merchant1_token if merchant_num == 1 else self.merchant2_token
        success, data, status = self.api_call("api/auth/profile", token=token)
        
        has_profile = bool(data.get("profile"))
        has_location = bool(data.get("profile", {}).get("location"))
        
        self.log_test(f"Merchant {merchant_num} Profile Access", success and has_profile,
                     f"Business: {data.get('profile', {}).get('business_name')}, Location: {has_location}")
        return success and has_profile

    def test_unauthorized_access(self):
        """Test that endpoints require authentication"""
        endpoints_to_test = [
            "api/products",
            "api/dashboard/stats", 
            "api/alerts/low-stock",
            "api/export/products"
        ]
        
        all_blocked = True
        for endpoint in endpoints_to_test:
            success, data, status = self.api_call(endpoint, expected_status=401)
            if status != 401:
                all_blocked = False
                break
        
        self.log_test("Unauthorized Access Protection", all_blocked,
                     "All protected endpoints require authentication")
        return all_blocked

    def test_product_creation(self, merchant_num=1):
        """Test product creation with new categories"""
        token = self.merchant1_token if merchant_num == 1 else self.merchant2_token
        
        product_data = {
            "name": f"Pain de campagne {merchant_num}",
            "barcode": f"123456789012{merchant_num}",
            "price": 2.50,
            "cost_price": 1.20,
            "stock_quantity": 50,
            "low_stock_threshold": 5,
            "category": "BOULANGERIE_PATISSERIE",
            "subcategory": "PAIN",
            "description": f"Pain artisanal du commerce {merchant_num}",
            "supplier": f"Fournisseur {merchant_num}",
            "is_available": True
        }

        success, data, status = self.api_call("api/products", "POST", product_data, token=token, expected_status=200)
        
        if success and merchant_num == 1:
            self.test_product_id = data.get("id")
        
        self.log_test(f"Product Creation (Merchant {merchant_num})", success,
                     f"Product: {data.get('name')}, Category: {data.get('category')}")
        return success

    def test_product_listing(self, merchant_num=1):
        """Test product listing and merchant isolation"""
        token = self.merchant1_token if merchant_num == 1 else self.merchant2_token
        success, data, status = self.api_call("api/products", token=token)
        
        products_count = len(data) if isinstance(data, list) else 0
        
        self.log_test(f"Product Listing (Merchant {merchant_num})", success,
                     f"Found {products_count} products")
        return success, products_count

    def test_merchant_isolation(self):
        """Test that merchants only see their own products"""
        if not (self.merchant1_token and self.merchant2_token):
            self.log_test("Merchant Isolation", False, "Need both merchants registered")
            return False

        # Get products for both merchants
        success1, products1_count = self.test_product_listing(1)
        success2, products2_count = self.test_product_listing(2)
        
        # Each merchant should only see their own products
        isolation_works = success1 and success2 and products1_count > 0 and products2_count > 0
        
        self.log_test("Merchant Data Isolation", isolation_works,
                     f"Merchant 1: {products1_count} products, Merchant 2: {products2_count} products")
        return isolation_works

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        success, data, status = self.api_call("api/dashboard/stats", token=self.merchant1_token)
        
        has_stats = all(key in data for key in [
            "total_products", "low_stock_alerts", "total_stock_value", "merchant_info"
        ])
        
        merchant_info = data.get("merchant_info", {})
        has_merchant_info = bool(merchant_info.get("business_name"))
        
        self.log_test("Dashboard Statistics", success and has_stats and has_merchant_info,
                     f"Products: {data.get('total_products')}, Business: {merchant_info.get('business_name')}")
        return success and has_stats

    def test_low_stock_alerts(self):
        """Test low stock alerts"""
        success, data, status = self.api_call("api/alerts/low-stock", token=self.merchant1_token)
        
        is_list = isinstance(data, list)
        
        self.log_test("Low Stock Alerts", success and is_list,
                     f"Found {len(data) if is_list else 0} low stock alerts")
        return success and is_list

    def test_product_update(self):
        """Test product update"""
        if not self.test_product_id:
            self.log_test("Product Update", False, "No product ID available")
            return False

        update_data = {
            "price": 3.00,
            "stock_quantity": 25,
            "description": "Pain artisanal mis à jour"
        }

        success, data, status = self.api_call(f"api/products/{self.test_product_id}", "PUT", 
                                            update_data, token=self.merchant1_token)
        
        updated_correctly = success and data.get("price") == 3.00 and data.get("stock_quantity") == 25
        
        self.log_test("Product Update", updated_correctly,
                     f"New price: {data.get('price')}€, New stock: {data.get('stock_quantity')}")
        return updated_correctly

    def test_export_functionality(self):
        """Test product export"""
        success, data, status = self.api_call("api/export/products", token=self.merchant1_token)
        
        has_export_info = bool(data.get("export_info"))
        has_products = bool(data.get("products"))
        has_merchant_location = bool(data.get("export_info", {}).get("merchant", {}).get("location"))
        
        export_works = success and has_export_info and has_products and has_merchant_location
        
        self.log_test("Export Functionality", export_works,
                     f"Products: {len(data.get('products', []))}, Has location: {has_merchant_location}")
        return export_works

    def test_public_search_endpoint(self):
        """Test public search endpoint (future customer app)"""
        params = {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "radius_km": 10,
            "category": "BOULANGERIE_PATISSERIE"
        }
        
        url = f"api/public/search?latitude={params['latitude']}&longitude={params['longitude']}&radius_km={params['radius_km']}&category={params['category']}"
        success, data, status = self.api_call(url)
        
        has_search_params = bool(data.get("search_params"))
        is_ready = "prêt" in data.get("message", "").lower()
        
        self.log_test("Public Search Endpoint", success and has_search_params and is_ready,
                     f"Ready for customer app: {is_ready}")
        return success

    def run_all_tests(self):
        """Run complete test suite"""
        print("\n🔍 PHASE 1: Basic API Health & Categories")
        print("-" * 40)
        self.test_health_check()
        self.test_categories_endpoint()
        
        print("\n🔐 PHASE 2: Authentication & Registration")
        print("-" * 40)
        self.test_unauthorized_access()
        
        # Register two merchants for isolation testing
        merchant1_registered = self.test_merchant_registration(1)
        merchant2_registered = self.test_merchant_registration(2)
        
        if merchant1_registered:
            self.test_profile_access(1)
        if merchant2_registered:
            self.test_profile_access(2)
        
        print("\n📦 PHASE 3: Product Management & Isolation")
        print("-" * 40)
        if merchant1_registered:
            self.test_product_creation(1)
        if merchant2_registered:
            self.test_product_creation(2)
        
        if merchant1_registered and merchant2_registered:
            self.test_merchant_isolation()
        
        print("\n📊 PHASE 4: Dashboard & Analytics")
        print("-" * 40)
        if merchant1_registered:
            self.test_dashboard_stats()
            self.test_low_stock_alerts()
        
        print("\n✏️ PHASE 5: Product Operations")
        print("-" * 40)
        if merchant1_registered:
            self.test_product_update()
            self.test_export_functionality()
        
        print("\n🌐 PHASE 6: Public API (Future Customer App)")
        print("-" * 40)
        self.test_public_search_endpoint()
        
        # Final results
        print("\n" + "=" * 60)
        print(f"📊 TEST RESULTS SUMMARY")
        print(f"✅ Tests Passed: {self.tests_passed}/{self.tests_run}")
        print(f"📈 Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL TESTS PASSED! Local Shop Pro API is working correctly.")
            return 0
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed. Check the details above.")
            return 1

def main():
    """Main test execution"""
    tester = LocalShopProTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())