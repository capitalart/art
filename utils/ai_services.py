# utils/ai_services.py

import os
from openai import OpenAI
import config

# Initialize the OpenAI client using configuration from config.py
client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    project=config.OPENAI_PROJECT_ID,
)

def call_ai_to_generate_title(paragraph_content: str) -> str:
    """Uses AI to generate a short, compelling title for a block of text."""
    try:
        prompt = (
            f"Generate a short, compelling heading (5 words or less) for the following paragraph. "
            f"Respond only with the heading text, nothing else.\n\nPARAGRAPH:\n\"{paragraph_content}\""
        )
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        title = response.choices[0].message.content.strip().strip('"')
        return title
    except Exception as e:
        print(f"AI title generation error: {e}")
        return "AI Title Generation Failed"

def call_ai_to_rewrite(prompt: str, provider: str = "openai") -> str:
    """
    Calls the specified AI provider to rewrite text based on a prompt.
    Currently only supports OpenAI.
    """
    if provider != "openai":
        return "Error: Only OpenAI is currently supported for rewriting."

    try:
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,  # Use the primary model from config
            messages=[
                {"role": "system", "content": "You are an expert copywriter. Rewrite the following text based on the user's instruction. Respond only with the rewritten text, without any extra commentary."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        new_text = response.choices[0].message.content.strip()
        return new_text
    except Exception as e:
        print(f"AI service error: {e}")
        return f"Error during AI regeneration: {e}"
    
    