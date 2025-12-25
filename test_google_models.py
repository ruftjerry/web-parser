#!/usr/bin/env python3
"""Quick test to see available Google Gemini models"""

import os
from dotenv import load_dotenv
from google import genai

# Load API key
load_dotenv()
api_key = os.getenv("GOOGLEAISTUDIO_API_KEY")

if not api_key:
    print("❌ GOOGLEAISTUDIO_API_KEY not found in .env")
    exit(1)

print("🔍 Checking available Google Gemini models...\n")

# Initialize client
client = genai.Client(api_key=api_key)

try:
    # List available models
    models = client.models.list()
    
    print("✅ Available models:\n")
    for model in models:
        print(f"  - {model.name}")
        if hasattr(model, 'display_name'):
            print(f"    Display: {model.display_name}")
        if hasattr(model, 'supported_generation_methods'):
            print(f"    Methods: {model.supported_generation_methods}")
        print()
    
except Exception as e:
    print(f"❌ Error listing models: {e}")