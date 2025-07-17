"""Thin wrappers around external AI service APIs."""

import os
from openai import OpenAI
from .openai_utils import get_openai_model
# import google.generativeai as genai  # Uncomment when you add the Gemini library

# --- LOAD API KEYS ---
# Make sure these are in your .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- INITIALIZE CLIENTS ---
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
# genai.configure(api_key=GEMINI_API_KEY)  # Uncomment for Gemini


def call_openai_api(prompt: str) -> str:
    """Sends a prompt to the OpenAI API and returns the rewritten text."""
    if not OPENAI_API_KEY:
        return "OpenAI API key not configured. Please set it in your .env file."
    global openai_client
    if openai_client is None:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    try:
        model_to_use = get_openai_model()
        response = openai_client.chat.completions.create(
            model=model_to_use,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert copywriter. Rewrite the user's text based on their instruction. "
                        "Be creative and professional. Only return the rewritten text, with no extra commentary."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return f"Error from OpenAI: {e}"


def call_gemini_api(prompt: str) -> str:
    """Sends a prompt to the Gemini API and returns the rewritten text."""
    if not GEMINI_API_KEY:
        return "Gemini API key not configured. Please set it in your .env file."
    # TODO: Implement the actual Gemini API call here
    # model = genai.GenerativeModel('gemini-1.5-pro')
    # response = model.generate_content(prompt)
    # return response.text
    return f"(Gemini response for: '{prompt}')"  # Mock response


def call_ai_to_rewrite(prompt: str, provider: str) -> str:
    """Master function to call the appropriate AI provider."""
    if provider == "openai":
        return call_openai_api(prompt)
    elif provider == "gemini":
        return call_gemini_api(prompt)
    # Add logic for 'random' or 'combined' if desired
    else:
        return call_openai_api(prompt)  # Default to OpenAI
