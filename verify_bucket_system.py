import requests
import os
import time

# Configuration
PDF_API_URL = "http://localhost:8003/knowledge/extract/pdf"
TEXT_API_URL = "http://localhost:8003/knowledge/extract/text"
FILE_PATH = "testfileforknowledgesystem/Sathish_Jayabalan_Resume.pdf"
USER_ID = "00000000-0000-0000-0000-000000000000"

def test_text_upload():
    print("\n--- Testing Text Upload ---")
    data = {
        "user_id": USER_ID,
        "text": "This is a test note about Quantum Physics and AI. It should be categorized nicely.",
        "title": "Quantum AI Note",
        "tags": ["science", "ai"],
        "auto_create_bucket": True
    }
    try:
        start = time.time()
        response = requests.post(TEXT_API_URL, json=data)
        duration = time.time() - start
        print(f"Status: {response.status_code} (took {duration:.2f}s)")
        print("Response:", response.json())
    except Exception as e:
        print(f"Text test failed: {e}")

def test_pdf_upload():
    print("\n--- Testing PDF Upload ---")
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    print(f"Uploading {FILE_PATH}...")
    with open(FILE_PATH, 'rb') as f:
        files = {'file': f}
        # Note: 'auto_create_bucket' passed as boolean string in form data
        data = {
            'user_id': USER_ID,
            'title': 'Sathish Resume Test',
            'tags': 'resume,test',
            'auto_create_bucket': 'true'
        }
        
        try:
            start = time.time()
            response = requests.post(PDF_API_URL, files=files, data=data)
            duration = time.time() - start
            print(f"Status: {response.status_code} (took {duration:.2f}s)")
            print("Response:", response.json())
        except Exception as e:
            print(f"PDF Request failed: {e}")

if __name__ == "__main__":
    print("Verifying Knowledge System Persistence...")
    test_text_upload()
    test_pdf_upload()
