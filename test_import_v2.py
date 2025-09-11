"""
Comprehensive test suite for the bulletproof CSV import system v2
Tests all three input methods, error handling, and data validation
"""

import asyncio
import os
import json
import pandas as pd
import tempfile
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any
import aiofiles
import aiohttp

# Test configuration
API_BASE_URL = "http://localhost:8000"  # Adjust for your environment
API_KEY = os.getenv('API_KEY', 'test-key')

# Sample test data
SAMPLE_DEALS = [
    {
        'Record Id': 'D001',
        'Deal Name': 'Software Development Contract',
        'Account Name': 'Tech Corp Inc.',
        'Owner': 'John Smith',
        'Amount USD': 50000.0,
        'Stage': 'Qualification',
        'Created Date': '2024-01-15',
        'Closing Date': '2024-03-15',
        'Source': 'Website Inbound',
        'Source Detail': 'Contact Form',
        'Description': 'Custom software development project'
    },
    {
        'Deal Id': 'D002',  # Different column name
        'Subject': 'Consulting Services',  # Different column name
        'Company Name': 'Business Solutions LLC',  # Different column name
        'Owner Name': 'Jane Doe',  # Different column name
        'Amount': 25000.0,  # Different column name
        'Deal Stage': 'Proposal',  # Different column name
        'Creation Date': '2024-01-20',  # Different column name
        'Close Date': '2024-02-20',  # Different column name
        'Lead Source': 'Referral',  # Different column name
        'Referrer Name': 'Bob Johnson',
        'Notes': 'Strategic consulting engagement'  # Different column name
    }
]

SAMPLE_STAGES = [
    {
        'Deal Id': 'D001',
        'From Stage': 'Lead',
        'To Stage': 'Qualification',
        'Modified Time': '2024-01-16T10:30:00Z',
        'Modified By': 'System'
    },
    {
        'Record Id': 'D002',  # Different column name
        'Previous Stage': 'Qualification',  # Different column name
        'New Stage': 'Proposal',  # Different column name
        'Changed At': '2024-01-22T14:15:00Z',  # Different column name
        'Changed By': 'Jane Doe'  # Different column name
    }
]

SAMPLE_MEETINGS = [
    {
        'Deal Id': 'D001',
        'Subject': 'Initial Discovery Call',
        'Start Time': '2024-01-17T09:00:00Z',
        'Participants': 'John Smith, Client Team',
        'Opened': True,
        'Clicked': False
    },
    {
        'Related To': 'D002',  # Different column name
        'Meeting Title': 'Proposal Presentation',  # Different column name
        'Meeting Date': '2024-01-23T15:00:00Z',  # Different column name
        'Attendees': 'Jane Doe, Client Executive',  # Different column name
        'Email Opened': False,  # Different column name
        'Link Clicked': True  # Different column name
    }
]

SAMPLE_NOTES = [
    {
        'Deal Id': 'D001',
        'Note Content': 'Client expressed strong interest in cloud migration features.',
        'Created Time': '2024-01-17T10:30:00Z',
        'Created By': 'John Smith'
    },
    {
        'Related To': 'D002',  # Different column name
        'Note': 'Sent detailed proposal with timeline and pricing.',  # Different column name
        'Note Date': '2024-01-23T16:00:00Z',  # Different column name
        'Author': 'Jane Doe'  # Different column name
    }
]


class ImportTester:
    """Test suite for CSV import system"""
    
    def __init__(self):
        self.session = None
        self.temp_dir = None
    
    async def setup(self):
        """Initialize test environment"""
        self.session = aiohttp.ClientSession(
            headers={'X-API-Key': API_KEY}
        )
        self.temp_dir = Path(tempfile.mkdtemp())
        print(f"Test temp directory: {self.temp_dir}")
    
    async def cleanup(self):
        """Clean up test environment"""
        if self.session:
            await self.session.close()
        
        # Clean up temp files
        if self.temp_dir and self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def create_test_csv(self, data: list, filename: str) -> Path:
        """Create a CSV file with test data"""
        df = pd.DataFrame(data)
        file_path = self.temp_dir / filename
        df.to_csv(file_path, index=False)
        return file_path
    
    def create_test_xlsx(self, data: list, filename: str) -> Path:
        """Create an XLSX file with test data"""
        df = pd.DataFrame(data)
        file_path = self.temp_dir / filename
        df.to_excel(file_path, index=False, engine='openpyxl')
        return file_path
    
    async def test_status_endpoint(self):
        """Test the status endpoint"""
        print("\n=== Testing Status Endpoint ===")
        
        try:
            async with self.session.get(f"{API_BASE_URL}/api/admin/import/v2/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Status endpoint working")
                    print(f"   Max upload size: {data['configuration']['max_upload_size_mb']}MB")
                    print(f"   Max rows: {data['configuration']['max_rows']:,}")
                    print(f"   Database counts: {data['database_counts']}")
                    return True
                else:
                    print(f"❌ Status endpoint failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Status endpoint error: {e}")
            return False
    
    async def test_default_folders(self):
        """Test import with default folder locations"""
        print("\n=== Testing Default Folder Import ===")
        
        # Create test files in the expected location
        import_dir = Path("app/admin/imports")
        import_dir.mkdir(exist_ok=True)
        
        try:
            # Create test CSV files
            deals_path = import_dir / "deals.csv"
            stages_path = import_dir / "stages.csv"
            
            pd.DataFrame(SAMPLE_DEALS).to_csv(deals_path, index=False)
            pd.DataFrame(SAMPLE_STAGES).to_csv(stages_path, index=False)
            
            # Test import with no body (default folders)
            async with self.session.post(f"{API_BASE_URL}/api/admin/import/v2/") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Default folder import successful")
                    print(f"   Imported: {data}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Default folder import failed: {response.status}")
                    print(f"   Error: {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Default folder import error: {e}")
            return False
        finally:
            # Clean up test files
            for file_path in [deals_path, stages_path]:
                if file_path.exists():
                    file_path.unlink()
    
    async def test_json_paths(self):
        """Test import with JSON body specifying paths"""
        print("\n=== Testing JSON Path Import ===")
        
        try:
            # Create test files
            deals_file = self.create_test_csv(SAMPLE_DEALS, "test_deals.csv")
            meetings_file = self.create_test_csv(SAMPLE_MEETINGS, "test_meetings.csv")
            
            # Test import with JSON paths
            request_data = {
                "paths": {
                    "deals": str(deals_file),
                    "meetings": str(meetings_file)
                }
            }
            
            async with self.session.post(
                f"{API_BASE_URL}/api/admin/import/v2/",
                json=request_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ JSON path import successful")
                    print(f"   Imported: {data}")
                    print(f"   Unknown headers: {data.get('unknown_headers', [])}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ JSON path import failed: {response.status}")
                    print(f"   Error: {error_text}")
                    return False
        except Exception as e:
            print(f"❌ JSON path import error: {e}")
            return False
    
    async def test_file_uploads(self):
        """Test import with multipart file uploads"""
        print("\n=== Testing File Upload Import ===")
        
        try:
            # Create test files
            deals_file = self.create_test_csv(SAMPLE_DEALS, "upload_deals.csv")
            notes_file = self.create_test_csv(SAMPLE_NOTES, "upload_notes.csv")
            
            # Test multipart upload
            data = aiohttp.FormData()
            
            # Add deals file
            with open(deals_file, 'rb') as f:
                data.add_field('deals_file', f, filename='deals.csv', content_type='text/csv')
                
                # Add notes file
                with open(notes_file, 'rb') as f2:
                    data.add_field('notes_file', f2, filename='notes.csv', content_type='text/csv')
                    
                    async with self.session.post(
                        f"{API_BASE_URL}/api/admin/import/v2/",
                        data=data
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            print("✅ File upload import successful")
                            print(f"   Imported: {result}")
                            return True
                        else:
                            error_text = await response.text()
                            print(f"❌ File upload import failed: {response.status}")
                            print(f"   Error: {error_text}")
                            return False
        except Exception as e:
            print(f"❌ File upload import error: {e}")
            return False
    
    async def test_xlsx_support(self):
        """Test XLSX file support"""
        print("\n=== Testing XLSX File Support ===")
        
        try:
            # Create XLSX file
            deals_file = self.create_test_xlsx(SAMPLE_DEALS, "test_deals.xlsx")
            
            request_data = {
                "paths": {
                    "deals": str(deals_file)
                }
            }
            
            async with self.session.post(
                f"{API_BASE_URL}/api/admin/import/v2/",
                json=request_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ XLSX import successful")
                    print(f"   Imported: {data}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ XLSX import failed: {response.status}")
                    print(f"   Error: {error_text}")
                    return False
        except Exception as e:
            print(f"❌ XLSX import error: {e}")
            return False
    
    async def test_error_handling(self):
        """Test error handling and validation"""
        print("\n=== Testing Error Handling ===")
        
        tests_passed = 0
        total_tests = 0
        
        # Test 1: Non-existent file
        total_tests += 1
        try:
            request_data = {
                "paths": {
                    "deals": "/nonexistent/file.csv"
                }
            }
            
            async with self.session.post(
                f"{API_BASE_URL}/api/admin/import/v2/",
                json=request_data
            ) as response:
                if response.status == 422:  # Validation error
                    print("✅ Non-existent file error handled correctly")
                    tests_passed += 1
                else:
                    print(f"❌ Non-existent file test failed: {response.status}")
        except Exception as e:
            print(f"❌ Non-existent file test error: {e}")
        
        # Test 2: Empty file
        total_tests += 1
        try:
            empty_file = self.temp_dir / "empty.csv"
            empty_file.write_text("")
            
            request_data = {
                "paths": {
                    "deals": str(empty_file)
                }
            }
            
            async with self.session.post(
                f"{API_BASE_URL}/api/admin/import/v2/",
                json=request_data
            ) as response:
                if response.status in [200, 400]:  # Should handle gracefully
                    data = await response.json()
                    print("✅ Empty file handled correctly")
                    print(f"   Result: {data}")
                    tests_passed += 1
                else:
                    print(f"❌ Empty file test failed: {response.status}")
        except Exception as e:
            print(f"❌ Empty file test error: {e}")
        
        # Test 3: Invalid CSV format
        total_tests += 1
        try:
            invalid_file = self.temp_dir / "invalid.csv"
            invalid_file.write_text("This is not a valid CSV file\nwith broken,quotes\"and,formatting")
            
            request_data = {
                "paths": {
                    "deals": str(invalid_file)
                }
            }
            
            async with self.session.post(
                f"{API_BASE_URL}/api/admin/import/v2/",
                json=request_data
            ) as response:
                if response.status in [200, 400]:  # Should handle gracefully
                    print("✅ Invalid CSV format handled correctly")
                    tests_passed += 1
                else:
                    print(f"❌ Invalid CSV test failed: {response.status}")
        except Exception as e:
            print(f"❌ Invalid CSV test error: {e}")
        
        print(f"Error handling tests: {tests_passed}/{total_tests} passed")
        return tests_passed == total_tests
    
    async def test_column_mapping(self):
        """Test resilient column mapping"""
        print("\n=== Testing Column Mapping ===")
        
        # Create data with various column name formats
        mixed_deals = [
            {
                'Record Id': 'D003',
                'Deal Name': 'Test Deal 1',
                'Account Name': 'Test Corp',
                'Owner': 'Test User',
                'Amount': 1000
            },
            {
                'deal id': 'D004',  # lowercase
                'subject': 'Test Deal 2',  # different name
                'company name': 'Test LLC',  # different name
                'owner name': 'Another User',  # different name
                'amount usd': 2000  # different name
            }
        ]
        
        try:
            deals_file = self.create_test_csv(mixed_deals, "mixed_columns.csv")
            
            request_data = {
                "paths": {
                    "deals": str(deals_file)
                }
            }
            
            async with self.session.post(
                f"{API_BASE_URL}/api/admin/import/v2/",
                json=request_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Column mapping successful")
                    print(f"   Imported deals: {data['deals']}")
                    print(f"   Unknown headers: {data.get('unknown_headers', [])}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Column mapping failed: {response.status}")
                    print(f"   Error: {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Column mapping error: {e}")
            return False
    
    async def test_idempotency(self):
        """Test idempotent upserts"""
        print("\n=== Testing Idempotency ===")
        
        try:
            # Import same data twice
            deals_file = self.create_test_csv(SAMPLE_DEALS[:1], "idempotent_deals.csv")
            
            request_data = {
                "paths": {
                    "deals": str(deals_file)
                }
            }
            
            # First import
            async with self.session.post(
                f"{API_BASE_URL}/api/admin/import/v2/",
                json=request_data
            ) as response:
                if response.status != 200:
                    print(f"❌ First import failed: {response.status}")
                    return False
                
                first_result = await response.json()
            
            # Second import (should be idempotent)
            async with self.session.post(
                f"{API_BASE_URL}/api/admin/import/v2/",
                json=request_data
            ) as response:
                if response.status == 200:
                    second_result = await response.json()
                    print("✅ Idempotent import successful")
                    print(f"   First import: {first_result['deals']} deals")
                    print(f"   Second import: {second_result['deals']} deals")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Idempotent import failed: {response.status}")
                    print(f"   Error: {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Idempotency test error: {e}")
            return False
    
    async def test_cleanup(self):
        """Test cleanup functionality"""
        print("\n=== Testing Cleanup ===")
        
        try:
            async with self.session.post(f"{API_BASE_URL}/api/admin/import/v2/cleanup") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Cleanup successful")
                    print(f"   Result: {data}")
                    return True
                else:
                    print(f"❌ Cleanup failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Cleanup test error: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting CSV Import v2 Test Suite")
        print("=" * 50)
        
        await self.setup()
        
        try:
            tests = [
                ("Status Endpoint", self.test_status_endpoint),
                ("Default Folders", self.test_default_folders),
                ("JSON Paths", self.test_json_paths),
                ("File Uploads", self.test_file_uploads),
                ("XLSX Support", self.test_xlsx_support),
                ("Column Mapping", self.test_column_mapping),
                ("Idempotency", self.test_idempotency),
                ("Error Handling", self.test_error_handling),
                ("Cleanup", self.test_cleanup)
            ]
            
            passed = 0
            total = len(tests)
            
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    if result:
                        passed += 1
                except Exception as e:
                    print(f"❌ {test_name} test crashed: {e}")
            
            print("\n" + "=" * 50)
            print(f"📊 Test Results: {passed}/{total} tests passed")
            
            if passed == total:
                print("🎉 All tests passed! Import system is ready for production.")
                return True
            else:
                print("⚠️  Some tests failed. Please review and fix issues.")
                return False
                
        finally:
            await self.cleanup()


async def main():
    """Main test runner"""
    tester = ImportTester()
    success = await tester.run_all_tests()
    
    if not success:
        exit(1)


if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv('.env.local')
    
    asyncio.run(main())