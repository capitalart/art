#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtNarrator Connection Tester
===============================================================
This script checks all external API and service connections
defined in the project's .env file to ensure keys and credentials
are working correctly. It also verifies access to specific AI models.

INDEX
-----
1.  Imports
2.  Configuration & Setup
3.  UI & Logging Helpers
4.  Connection Test Functions
5.  Main Execution
"""

# ===========================================================================
# 1. Imports
# ===========================================================================
import os
import sys
import base64
import smtplib
import requests
from dotenv import load_dotenv

# Ensure the project root is in the Python path to find modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
    import openai
    import google.generativeai as genai
    import config
    from utils.logger_utils import setup_logger
except ImportError as e:
    print(f"❌ Error: A required library is missing. Please run 'pip install {e.name}'")
    sys.exit(1)


# ===========================================================================
# 2. Configuration & Setup
# ===========================================================================
load_dotenv(os.path.join(project_root, '.env'))
logger = setup_logger(__name__, "DEFAULT") # Use the default logger for a persistent record


# ===========================================================================
# 3. UI & Logging Helpers
# ===========================================================================
def print_status(service: str, success: bool, message: str = "") -> None:
    """Prints a formatted status line and writes to the log file."""
    if success:
        log_message = f"✅ {service:<20} Connection successful. {message}"
        print(f"✅ {service:<20} Connection successful. {message}")
        logger.info(log_message)
    else:
        log_message = f"❌ {service:<20} FAILED. {message}"
        print(f"❌ {service:<20} FAILED. {message}")
        logger.error(log_message)


# ===========================================================================
# 4. Connection Test Functions
# ===========================================================================

# --- [ 4.1: OpenAI Test ] ---
def test_openai() -> None:
    """Tests the OpenAI API key and access to specific models."""
    print("\n--- Testing OpenAI ---")
    if not config.OPENAI_API_KEY:
        print_status("OpenAI", False, "OPENAI_API_KEY not found in config.")
        return

    try:
        client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        client.models.list()
        print_status("OpenAI API Key", True, "Key is valid.")

        models_to_check = {
            "Main Model": config.OPENAI_MODEL,
            "Vision Model": config.OPENAI_MODEL
        }
        for name, model_id in models_to_check.items():
            if not model_id: continue
            try:
                client.models.retrieve(model_id)
                print(f"  - ✅ {name} ({model_id}): Access confirmed.")
            except Exception as e:
                print(f"  - ❌ {name} ({model_id}): FAILED! Error: {e}")
                logger.error(f"Failed to retrieve OpenAI model {model_id}: {e}")

    except openai.AuthenticationError:
        print_status("OpenAI API Key", False, "AuthenticationError: The API key is incorrect.")
    except Exception as e:
        print_status("OpenAI API Key", False, f"An unexpected error occurred: {e}")


# --- [ 4.2: Google Gemini Test ] ---
def test_google_gemini() -> None:
    """Tests the Google Gemini API key and access to the vision model."""
    print("\n--- Testing Google Gemini ---")
    api_key = config.GEMINI_API_KEY or config.GOOGLE_API_KEY
    if not api_key:
        print_status("Google Gemini", False, "GEMINI_API_KEY or GOOGLE_API_KEY not found.")
        return

    try:
        genai.configure(api_key=api_key)
        model_name = config.GEMINI_MODEL
        if model_name:
            model_name_for_check = f'models/{model_name}' if not model_name.startswith('models/') else model_name
            genai.get_model(model_name_for_check)
            print_status("Google Gemini", True, f"Key is valid and has access to {model_name}.")
        else:
            genai.list_models()
            print_status("Google Gemini", True, "Key is valid (general check).")
    except Exception as e:
        print_status("Google Gemini", False, f"An error occurred: {e}")


# --- [ 4.3: Sellbrite Test ] ---
def test_sellbrite() -> None:
    """Tests Sellbrite API credentials by making a simple request."""
    print("\n--- Testing Sellbrite ---")
    token, secret = config.SELLBRITE_ACCOUNT_TOKEN, config.SELLBRITE_SECRET_KEY
    if not token or not secret:
        print_status("Sellbrite", False, "Credentials not found in config.")
        return

    try:
        creds = f"{token}:{secret}".encode("utf-8")
        encoded_creds = base64.b64encode(creds).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded_creds}"}
        url = f"{config.SELLBRITE_API_BASE_URL}/warehouses?limit=1"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            print_status("Sellbrite", True)
        else:
            print_status("Sellbrite", False, f"API returned status {response.status_code}. Check credentials.")
    except requests.RequestException as e:
        print_status("Sellbrite", False, f"A network error occurred: {e}")


# --- [ 4.4: SMTP Test ] ---
def test_smtp() -> None:
    """Tests the SMTP server connection and login credentials."""
    print("\n--- Testing SMTP ---")
    server, port = config.SMTP_SERVER, config.SMTP_PORT
    username, password = config.SMTP_USERNAME, config.SMTP_PASSWORD

    if not all([server, port, username, password]):
        print_status("SMTP", False, "One or more SMTP variables are missing from config.")
        return

    try:
        with smtplib.SMTP(server, port, timeout=10) as connection:
            connection.starttls()
            connection.login(username, password)
        print_status("SMTP", True)
    except smtplib.SMTPAuthenticationError:
        print_status("SMTP", False, "AuthenticationError. Check username/password.")
    except Exception as e:
        print_status("SMTP", False, f"An unexpected error occurred: {e}")


# ===========================================================================
# 5. Main Execution
# ===========================================================================
def main() -> None:
    """Runs all connection tests."""
    print("--- 🔑 ArtNarrator API Connection Tester ---")
    logger.info("--- Starting API Connection Test Suite ---")
    
    test_openai()
    test_google_gemini()
    test_sellbrite()
    # test_smtp() # Uncomment this line to test the SMTP connection
    
    print("\n--- ✅ All tests complete ---")
    logger.info("--- API Connection Test Suite Finished ---")


if __name__ == "__main__":
    main()