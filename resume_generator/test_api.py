#!/usr/bin/env python3
"""
Test script for Resume Generator API.

Usage:
    python test_api.py --candidate-id 123456
    python test_api.py --candidate-id 123456 --save
    python test_api.py --health
"""

import argparse
import requests
import json
from pathlib import Path


BASE_URL = "http://localhost:8002"


def test_health():
    """Test health endpoint."""
    print("🏥 Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_generate(candidate_id: str):
    """Test resume generation."""
    print(f"📝 Generating resume for candidate {candidate_id}...")
    response = requests.get(f"{BASE_URL}/api/resume/generate/{candidate_id}")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success!")
        print(f"Candidate: {data['candidate_name']}")
        print(f"Compressed: {data['was_compressed']}")

        # Save HTML preview
        html_file = Path(f"preview_{candidate_id}.html")
        html_file.write_text(data['html_preview'])
        print(f"📄 HTML saved to: {html_file}")

        return data
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"Response: {response.text}")
        return None


def test_preview(candidate_id: str):
    """Test HTML preview endpoint."""
    print(f"🖼️  Getting HTML preview for candidate {candidate_id}...")
    response = requests.get(f"{BASE_URL}/api/resume/preview/{candidate_id}")

    if response.status_code == 200:
        html_file = Path(f"preview_{candidate_id}.html")
        html_file.write_text(response.text)
        print(f"✅ HTML saved to: {html_file}")
        print(f"Open in browser: file://{html_file.absolute()}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"Response: {response.text}")
        return False


def test_save_direct(candidate_id: str):
    """Test direct save (generate + upload to Zoho)."""
    print(f"💾 Saving resume directly for candidate {candidate_id}...")
    response = requests.post(f"{BASE_URL}/api/resume/save-direct/{candidate_id}")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success!")
        print(f"Message: {data['message']}")
        print(f"Attachment ID: {data['attachment_id']}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"Response: {response.text}")
        return False


def test_save_custom(candidate_id: str, html_content: str):
    """Test save with custom HTML."""
    print(f"💾 Saving custom resume for candidate {candidate_id}...")

    payload = {
        "candidate_id": candidate_id,
        "html_content": html_content,
        "filename": f"Resume_{candidate_id}.pdf"
    }

    response = requests.post(
        f"{BASE_URL}/api/resume/save",
        json=payload
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success!")
        print(f"Message: {data['message']}")
        print(f"Attachment ID: {data['attachment_id']}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"Response: {response.text}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Resume Generator API")
    parser.add_argument("--health", action="store_true", help="Test health endpoint")
    parser.add_argument("--candidate-id", type=str, help="Zoho candidate ID")
    parser.add_argument("--preview", action="store_true", help="Get HTML preview")
    parser.add_argument("--save", action="store_true", help="Save resume to Zoho")
    parser.add_argument("--save-direct", action="store_true", help="Generate and save directly")

    args = parser.parse_args()

    if args.health:
        test_health()
        return

    if not args.candidate_id:
        print("❌ Error: --candidate-id required (unless using --health)")
        parser.print_help()
        return

    # Test generation
    if args.preview:
        test_preview(args.candidate_id)
    elif args.save_direct:
        test_save_direct(args.candidate_id)
    elif args.save:
        # Generate first, then save
        data = test_generate(args.candidate_id)
        if data:
            print("\n" + "="*50)
            print("Now saving to Zoho...")
            test_save_custom(args.candidate_id, data['html_preview'])
    else:
        # Just generate
        test_generate(args.candidate_id)


if __name__ == "__main__":
    main()
