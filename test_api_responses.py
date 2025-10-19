#!/usr/bin/env python3
"""
Quick test to verify API response structure
"""

from utils import api_response, api_success, api_error
import json

def test_api_helpers():
    """Test API helper functions"""

    print("Testing API Helper Functions...")
    print("=" * 50)

    # Test api_success
    print("\n1. Testing api_success():")
    response, status = api_success({'test': 'data', 'count': 5})
    body = json.loads(response.get_data(as_text=True))
    print(f"   Status: {status}")
    print(f"   Body: {json.dumps(body, indent=2)}")
    assert body['success'] == True
    assert body['data']['test'] == 'data'
    assert 'timestamp' in body
    print("   ✅ PASSED")

    # Test api_error
    print("\n2. Testing api_error():")
    response, status = api_error('Test error message', 400)
    body = json.loads(response.get_data(as_text=True))
    print(f"   Status: {status}")
    print(f"   Body: {json.dumps(body, indent=2)}")
    assert body['success'] == False
    assert body['error'] == 'Test error message'
    assert status == 400
    print("   ✅ PASSED")

    # Test api_response
    print("\n3. Testing api_response():")
    response, status = api_response(True, data={'key': 'value'}, error=None, status=200)
    body = json.loads(response.get_data(as_text=True))
    print(f"   Status: {status}")
    print(f"   Body: {json.dumps(body, indent=2)}")
    assert body['success'] == True
    assert body['data']['key'] == 'value'
    print("   ✅ PASSED")

    print("\n" + "=" * 50)
    print("✅ All API helper tests PASSED!")
    print("=" * 50)

if __name__ == '__main__':
    test_api_helpers()
