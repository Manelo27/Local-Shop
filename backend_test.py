#!/usr/bin/env python3
"""
Backend API Tests for Stock Management Application
Tests all endpoints with French commerce data
"""

import requests
import json
import sys
from datetime import datetime
import uuid

class StockManagementAPITester:
    def __init__(self, base_url="https://9c19a8ee-cbd2-4c97-ba8a-814725eddddd.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.created_products = []  # Track created products for cleanup

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED {details}")
        else:
            print(f"❌ {name} - FAILED {details}")
        return success

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            
            if success:
                try:
                    response_data = response.json()
                    details = f"- Status: {response.status_code}"
                    if isinstance(response_data, dict) and len(response_data) <= 3:
                        details += f" - Response: {response_data}"
                    elif isinstance(response_data, list) and len(response_data) <= 2:
                        details += f" - Items: {len(response_data)}"
                    else:
                        details += f" - Response received"
                except:
                    details = f"- Status: {response.status_code} - Non-JSON response"
            else:
                try:
                    error_data = response.json()
                    details = f"- Expected {expected_status}, got {response.status_code} - Error: {error_data}"
                except:
                    details = f"- Expected {expected_status}, got {response.status_code} - {response.text[:100]}"

            self.log_test(name, success, details)
            return success, response.json() if success and response.content else {}

        except Exception as e:
            self.log_test(name, False, f"- Exception: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        return self.run_test("Health Check", "GET", "api/health", 200)

    def test_get_categories(self):
        """Test categories endpoint"""
        success, response = self.run_test("Get Categories", "GET", "api/categories", 200)
        if success:
            # Verify expected categories are present
            expected_categories = ["ALIMENTAIRE", "BOISSONS", "ARTISANAT"]
            categories = response.get("categories", [])
            subcategories = response.get("subcategories", {})
            
            categories_found = all(cat in categories for cat in expected_categories)
            subcats_found = "BOUCHERIE" in subcategories.get("ALIMENTAIRE", [])
            
            if categories_found and subcats_found:
                print("   ✓ Expected categories and subcategories found")
            else:
                print("   ⚠️ Some expected categories/subcategories missing")
        
        return success, response

    def test_create_product_with_custom_threshold_alert(self):
        """Test creating a product with custom threshold that should trigger alert"""
        product_data = {
            "name": "Baguette",
            "barcode": "1234567890123",
            "price": 1.20,
            "cost_price": 0.80,
            "stock_quantity": 25,
            "low_stock_threshold": 30,  # Custom threshold higher than stock
            "category": "ALIMENTAIRE",
            "subcategory": "BOULANGERIE",
            "description": "Baguette traditionnelle",
            "supplier": "Boulangerie Martin"
        }
        
        success, response = self.run_test("Create Product with Custom Threshold (Alert)", "POST", "api/products", 201, product_data)
        if success and "id" in response:
            self.created_products.append(response["id"])
            # Verify custom threshold is saved
            if response.get("low_stock_threshold") == 30:
                print("   ✓ Custom low stock threshold saved correctly")
            else:
                print(f"   ⚠️ Custom threshold issue: expected 30, got {response.get('low_stock_threshold')}")
        
        return success, response

    def test_create_product_with_custom_threshold_no_alert(self):
        """Test creating a product with custom threshold that should NOT trigger alert"""
        product_data = {
            "name": "Montre de luxe",
            "barcode": "9876543210987",
            "price": 299.99,
            "cost_price": 150.00,
            "stock_quantity": 3,
            "low_stock_threshold": 2,  # Custom threshold lower than stock
            "category": "AUTRE",
            "description": "Montre de luxe Swiss Made",
            "supplier": "Horlogerie Suisse"
        }
        
        success, response = self.run_test("Create Product with Custom Threshold (No Alert)", "POST", "api/products", 201, product_data)
        if success and "id" in response:
            self.created_products.append(response["id"])
            # Verify custom threshold is saved
            if response.get("low_stock_threshold") == 2:
                print("   ✓ Custom low stock threshold saved correctly")
            else:
                print(f"   ⚠️ Custom threshold issue: expected 2, got {response.get('low_stock_threshold')}")
        
        return success, response

    def test_create_product_default_threshold_alert(self):
        """Test creating a product with default threshold that should trigger alert"""
        product_data = {
            "name": "Légumes frais",
            "barcode": "5555666677778",
            "price": 3.50,
            "cost_price": 2.00,
            "stock_quantity": 8,
            "low_stock_threshold": 15,  # Custom threshold higher than stock
            "category": "ALIMENTAIRE",
            "subcategory": "FRUITS_LEGUMES",
            "description": "Légumes frais du jour",
            "supplier": "Maraîcher Local"
        }
        
        success, response = self.run_test("Create Product with Custom Threshold (Alert)", "POST", "api/products", 201, product_data)
        if success and "id" in response:
            self.created_products.append(response["id"])
        
        return success, response

    def test_create_product_artisanat(self):
        """Test creating an artisanat product"""
        product_data = {
            "name": "Vase fait-main",
            "barcode": "9876543210987",
            "price": 45.00,
            "cost_price": 20.00,
            "stock_quantity": 5,  # Low stock to trigger alert
            "category": "ARTISANAT",
            "subcategory": "FAIT_MAIN",
            "description": "Vase en céramique fait à la main",
            "supplier": "Atelier Céramique"
        }
        
        success, response = self.run_test("Create Artisanat Product", "POST", "api/products", 201, product_data)
        if success and "id" in response:
            self.created_products.append(response["id"])
        
        return success, response

    def test_get_products(self):
        """Test getting all products"""
        return self.run_test("Get All Products", "GET", "api/products", 200)

    def test_get_products_with_filters(self):
        """Test getting products with filters"""
        # Test category filter
        success1, _ = self.run_test("Get Products by Category", "GET", "api/products", 200, 
                                   params={"category": "ALIMENTAIRE"})
        
        # Test search filter
        success2, _ = self.run_test("Get Products by Search", "GET", "api/products", 200,
                                   params={"search": "Steak"})
        
        return success1 and success2

    def test_get_single_product(self):
        """Test getting a single product"""
        if not self.created_products:
            print("⚠️ No products created yet, skipping single product test")
            return False
        
        product_id = self.created_products[0]
        return self.run_test("Get Single Product", "GET", f"api/products/{product_id}", 200)

    def test_update_product(self):
        """Test updating a product"""
        if not self.created_products:
            print("⚠️ No products created yet, skipping update test")
            return False
        
        product_id = self.created_products[0]
        update_data = {
            "price": 28.00,
            "stock_quantity": 20
        }
        
        return self.run_test("Update Product", "PUT", f"api/products/{product_id}", 200, update_data)

    def test_dashboard_stats_with_custom_thresholds(self):
        """Test dashboard statistics with custom thresholds"""
        success, response = self.run_test("Dashboard Stats with Custom Thresholds", "GET", "api/dashboard/stats", 200)
        if success:
            expected_fields = ["total_products", "low_stock_alerts", "total_stock_value", "estimated_profit"]
            missing_fields = [field for field in expected_fields if field not in response]
            if not missing_fields:
                print("   ✓ All expected dashboard fields present")
                # Check if low stock alerts count reflects custom thresholds
                low_stock_count = response.get("low_stock_alerts", 0)
                print(f"   ✓ Low stock alerts count: {low_stock_count}")
                # Should have at least 2 alerts (Baguette and Légumes frais)
                if low_stock_count >= 2:
                    print("   ✓ Custom thresholds appear to be working in dashboard")
                else:
                    print("   ⚠️ Expected at least 2 low stock alerts with custom thresholds")
            else:
                print(f"   ⚠️ Missing dashboard fields: {missing_fields}")
        
        return success, response

    def test_low_stock_alerts_with_custom_thresholds(self):
        """Test low stock alerts with custom thresholds"""
        success, response = self.run_test("Low Stock Alerts with Custom Thresholds", "GET", "api/alerts/low-stock", 200)
        if success and isinstance(response, list):
            print(f"   ✓ Found {len(response)} low stock alerts")
            
            # Check for specific products that should be in alerts
            alert_names = [alert.get("name", "") for alert in response]
            alert_details = {alert.get("name"): {"stock": alert.get("current_stock"), "threshold": alert.get("threshold")} for alert in response}
            
            # Baguette should be in alerts (stock: 25, threshold: 30)
            if "Baguette" in alert_names:
                baguette_alert = alert_details["Baguette"]
                if baguette_alert["stock"] == 25 and baguette_alert["threshold"] == 30:
                    print("   ✓ Baguette correctly identified with custom threshold")
                else:
                    print(f"   ⚠️ Baguette alert data incorrect: {baguette_alert}")
            else:
                print("   ⚠️ Baguette not found in alerts (should be there)")
            
            # Légumes frais should be in alerts (stock: 8, threshold: 15)
            if "Légumes frais" in alert_names:
                legumes_alert = alert_details["Légumes frais"]
                if legumes_alert["stock"] == 8 and legumes_alert["threshold"] == 15:
                    print("   ✓ Légumes frais correctly identified with custom threshold")
                else:
                    print(f"   ⚠️ Légumes frais alert data incorrect: {legumes_alert}")
            else:
                print("   ⚠️ Légumes frais not found in alerts (should be there)")
            
            # Montre de luxe should NOT be in alerts (stock: 3, threshold: 2)
            if "Montre de luxe" in alert_names:
                print("   ⚠️ Montre de luxe found in alerts (should NOT be there)")
            else:
                print("   ✓ Montre de luxe correctly NOT in alerts")
        
        return success, response

    def test_update_product_threshold(self):
        """Test updating a product's low stock threshold"""
        if not self.created_products:
            print("⚠️ No products created yet, skipping threshold update test")
            return False
        
        product_id = self.created_products[0]
        update_data = {
            "low_stock_threshold": 50,  # Change threshold to trigger alert
            "stock_quantity": 40  # Stock below new threshold
        }
        
        success, response = self.run_test("Update Product Threshold", "PUT", f"api/products/{product_id}", 200, update_data)
        if success:
            if response.get("low_stock_threshold") == 50:
                print("   ✓ Low stock threshold updated correctly")
            else:
                print(f"   ⚠️ Threshold update issue: expected 50, got {response.get('low_stock_threshold')}")
        
        return success, response

    def test_export_products(self):
        """Test product export"""
        success, response = self.run_test("Export Products", "GET", "api/export/products", 200)
        if success:
            # Verify export format
            expected_fields = ["export_info", "products"]
            if all(field in response for field in expected_fields):
                print("   ✓ Export format correct")
                export_info = response.get("export_info", {})
                if "timestamp" in export_info and "standard" in export_info:
                    print("   ✓ Export metadata present")
            else:
                print("   ⚠️ Export format incomplete")
        
        return success, response

    def test_delete_product(self):
        """Test deleting a product"""
        if not self.created_products:
            print("⚠️ No products created yet, skipping delete test")
            return False
        
        product_id = self.created_products.pop()  # Remove from tracking
        return self.run_test("Delete Product", "DELETE", f"api/products/{product_id}", 200)

    def cleanup_remaining_products(self):
        """Clean up any remaining test products"""
        print(f"\n🧹 Cleaning up {len(self.created_products)} remaining test products...")
        for product_id in self.created_products:
            try:
                response = requests.delete(f"{self.base_url}/api/products/{product_id}")
                if response.status_code == 200:
                    print(f"   ✓ Cleaned up product {product_id}")
                else:
                    print(f"   ⚠️ Failed to clean up product {product_id}")
            except Exception as e:
                print(f"   ❌ Error cleaning up product {product_id}: {e}")

    def run_all_tests(self):
        """Run all API tests in sequence"""
        print("🚀 Starting Stock Management API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)

        # Basic connectivity tests
        self.test_health_check()
        self.test_get_categories()

        # Product CRUD tests
        self.test_create_product_boucherie()
        self.test_create_product_artisanat()
        self.test_get_products()
        self.test_get_products_with_filters()
        self.test_get_single_product()
        self.test_update_product()

        # Dashboard and analytics tests
        self.test_dashboard_stats()
        self.test_low_stock_alerts()
        self.test_export_products()

        # Cleanup test
        self.test_delete_product()

        # Final cleanup
        self.cleanup_remaining_products()

        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"   Tests Run: {self.tests_run}")
        print(f"   Tests Passed: {self.tests_passed}")
        print(f"   Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"   Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("⚠️ SOME TESTS FAILED!")
            return 1

def main():
    """Main test runner"""
    tester = StockManagementAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())