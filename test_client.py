#!/usr/bin/env python3
"""
Simple test client for Legal Document Splitter API
"""
import requests
import time
import sys
from pathlib import Path
from typing import List


API_URL = "http://localhost:8000"


def upload_files(file_paths: List[Path], merge_mode: bool = False) -> str:
    """Upload files and get job ID."""
    files = []
    for file_path in file_paths:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        files.append(
            ('files', (file_path.name, open(file_path, 'rb'), 'application/octet-stream'))
        )
    
    print(f"📤 Uploading {len(files)} file(s) (merge_mode={merge_mode})...")
    
    response = requests.post(
        f"{API_URL}/upload",
        files=files,
        data={'merge_mode': str(merge_mode).lower()}
    )
    
    if response.status_code != 200:
        raise Exception(f"Upload failed: {response.text}")
    
    data = response.json()
    job_id = data['job_id']
    print(f"✅ Job created: {job_id}")
    return job_id


def wait_for_completion(job_id: str, poll_interval: int = 2) -> dict:
    """Poll job status until completion."""
    print(f"⏳ Waiting for job completion...")
    
    while True:
        response = requests.get(f"{API_URL}/status/{job_id}")
        if response.status_code != 200:
            raise Exception(f"Status check failed: {response.text}")
        
        status_data = response.json()
        status = status_data['status']
        progress = status_data['progress']
        message = status_data['message']
        
        print(f"   [{progress:3d}%] {status.upper()}: {message}")
        
        if status == 'completed':
            print(f"✅ Processing completed!")
            if status_data.get('total_articles'):
                print(f"   Total articles extracted: {status_data['total_articles']}")
            return status_data
        elif status == 'failed':
            error = status_data.get('error', 'Unknown error')
            raise Exception(f"Processing failed: {error}")
        
        time.sleep(poll_interval)


def download_result(job_id: str, output_path: Path = None) -> Path:
    """Download the result ZIP file."""
    if output_path is None:
        output_path = Path(f"results_{job_id}.zip")
    
    print(f"⬇️  Downloading results...")
    
    response = requests.get(f"{API_URL}/download/{job_id}", stream=True)
    if response.status_code != 200:
        raise Exception(f"Download failed: {response.text}")
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    file_size = output_path.stat().st_size / 1024 / 1024
    print(f"✅ Downloaded: {output_path} ({file_size:.2f} MB)")
    return output_path


def check_health() -> dict:
    """Check API health."""
    response = requests.get(f"{API_URL}/health")
    if response.status_code != 200:
        raise Exception(f"Health check failed: {response.text}")
    return response.json()


def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print("Usage: python test_client.py <file1.docx> [file2.pdf] [--merge]")
        print("\nExample:")
        print("  python test_client.py document.docx")
        print("  python test_client.py doc1.pdf doc2.docx --merge")
        sys.exit(1)
    
    # Parse arguments
    files = []
    merge_mode = False
    
    for arg in sys.argv[1:]:
        if arg == '--merge':
            merge_mode = True
        else:
            files.append(Path(arg))
    
    if not files:
        print("❌ No files specified")
        sys.exit(1)
    
    try:
        # Check health
        print("🏥 Checking API health...")
        health = check_health()
        print(f"   Status: {health['status']}")
        print(f"   SpaCy model loaded: {health['spacy_model_loaded']}")
        print(f"   Active jobs: {health['active_jobs']}\n")
        
        # Process workflow
        job_id = upload_files(files, merge_mode)
        wait_for_completion(job_id)
        result_file = download_result(job_id)
        
        print(f"\n🎉 Success! Results saved to: {result_file}")
        print(f"   Extract with: unzip {result_file}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
