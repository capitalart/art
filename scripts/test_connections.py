#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtNarrator Connection Tester
===============================================================
This script checks all external API and service connections
defined in the project's .env file to ensure keys and credentials
are working correctly. It also verifies access to specific AI models.
"""

import os
import sys
import base64
import smtplib
import requests
from dotenv import load_dotenv

# Ensure the project root is in the Python path to find modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Try to import required libraries and provide helpful errors if they're missing
try:
    import openai
    import google.generativeai as genai
    import config  # Import the application's config
except ImportError as e:
    print(f"❌ Error: A required library is missing. Please run 'pip install {e.name}'")
    sys.exit(1)

# --- Configuration ---
# Load environment variables from the .env file in the project root
load_dotenv(os.path.join(project_root, '.env'))

# --- UI Helpers ---
def print_status(service: str, success: bool, message: str = "") -> None:
    """Prints a formatted status line for a service check."""
    if success:
        print(f"✅ {service:<20} Connection successful. {message}")
    else:
        print(f"❌ {service:<20} FAILED. {message}")

# --- Test Functions ---

def test_openai() -> None:
    """Tests the OpenAI API key and access to specific models."""
    print("\n--- Testing OpenAI ---")
    api_key = config.OPENAI_API_KEY
    if not api_key:
        print_status("OpenAI", False, "OPENAI_API_KEY not found.")
        return

    try:
        client = openai.OpenAI(api_key=api_key)
        client.models.list()  # Basic connection test
        print_status("OpenAI API Key", True, "Key is valid.")

        # Test specific models from config
        models_to_check = {
            "Main Model": config.OPENAI_MODEL,
            "Vision Model": config.OPENAI_VISION_MODEL
        }
        
        errors = []
        for name, model_id in models_to_check.items():
            if not model_id: continue
            try:
                client.models.retrieve(model_id)
                print(f"  - ✅ {name} ({model_id}): Access confirmed.")
            except Exception as e:
                errors.append(f"  - ❌ {name} ({model_id}): FAILED! Error: {e}")
        
        if errors:
            print("\n".join(errors))
            print_status("OpenAI Models", False, "One or more models are inaccessible.")

    except openai.AuthenticationError:
        print_status("OpenAI API Key", False, "AuthenticationError: The API key is incorrect.")
    except Exception as e:
        print_status("OpenAI API Key", False, f"An unexpected error occurred: {e}")

def test_google_gemini() -> None:
    """Tests the Google Gemini API key and access to the specific vision model."""
    print("\n--- Testing Google Gemini ---")
    api_key = config.GEMINI_API_KEY
    if not api_key:
        print_status("Google Gemini", False, "GEMINI_API_KEY not found.")
        return

    try:
        genai.configure(api_key=api_key)
        
        # Test the specific vision model from config
        model_name = config.GOOGLE_GEMINI_PRO_VISION_MODEL_NAME
        if model_name:
             # The genai library requires the 'models/' prefix for get_model
            model_name_for_check = model_name if model_name.startswith('models/') else f'models/{model_name}'
            genai.get_model(model_name_for_check)
            print_status("Google Gemini", True, f"Key is valid and has access to {model_name}.")
        else:
            # Fallback to a general check if no specific model is set
            genai.list_models()
            print_status("Google Gemini", True, "Key is valid (general check).")

    except Exception as e:
        print_status("Google Gemini", False, f"An error occurred: {e}")

def test_sellbrite() -> None:
    """Tests Sellbrite API credentials by making a simple request."""
    print("\n--- Testing Sellbrite ---")
    token = config.SELLBRITE_ACCOUNT_TOKEN
    secret = config.SELLBRITE_SECRET_KEY
    api_base = config.SELLBRITE_API_BASE_URL

    if not token or not secret:
        print_status("Sellbrite", False, "Credentials not found in .env file.")
        return

    try:
        creds = f"{token}:{secret}".encode("utf-8")
        encoded_creds = base64.b64encode(creds).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded_creds}"}
        url = f"{api_base}/warehouses?limit=1"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            print_status("Sellbrite", True)
        else:
            print_status("Sellbrite", False, f"API returned status {response.status_code}. Check credentials.")
    except requests.RequestException as e:
        print_status("Sellbrite", False, f"A network error occurred: {e}")

def test_smtp() -> None:
    """Tests the SMTP server connection and login credentials."""
    # This test is disabled by default. Uncomment the call in main() to run it.
    print("\n--- Testing SMTP ---")
    server = config.SMTP_SERVER
    port = config.SMTP_PORT
    username = config.SMTP_USERNAME
    password = config.SMTP_PASSWORD

    if not all([server, port, username, password]):
        print_status("SMTP", False, "One or more SMTP environment variables are missing.")
        return

    try:
        with smtplib.SMTP(server, port, timeout=10) as connection:
            connection.starttls()
            connection.login(username, password)
        print_status("SMTP", True)
    except smtplib.SMTPAuthenticationError:
        print_status("SMTP", False, "AuthenticationError. Check username/password (or app password).")
    except Exception as e:
        print_status("SMTP", False, f"An unexpected error occurred: {e}")

# --- Main Execution ---
def main() -> None:
    """Runs all connection tests."""
    print("--- 🔑 ArtNarrator API Connection Tester ---")
    test_openai()
    test_google_gemini()
    test_sellbrite()
    # test_smtp() # Uncomment this line if you need to test the SMTP connection
    print("\n--- ✅ All tests complete ---")

if __name__ == "__main__":
    main()