# utils/ai_services.py
"""
Central module for handling all interactions with external AI services like
OpenAI and Google Gemini.

INDEX
-----
1.  Imports & Client Initialisation
2.  AI Service Callers
"""

# ===========================================================================
# 1. Imports & Client Initialisation
# ===========================================================================
import logging
from openai import OpenAI
import config

logger = logging.getLogger(__name__)

# Initialize the OpenAI client using configuration from config.py
client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    project=config.OPENAI_PROJECT_ID,
)


# ===========================================================================
# 2. AI Service Callers
# ===========================================================================

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
            max_tokens=20,
        )
        title = response.choices[0].message.content.strip().strip('"')
        logger.info(f"AI generated title: '{title}'")
        return title
    except Exception as e:
        logger.error(f"AI title generation failed: {e}")
        return "AI Title Generation Failed"


def call_ai_to_rewrite(prompt: str, provider: str = "openai") -> str:
    """Calls the specified AI provider to rewrite text based on a prompt."""
    if provider != "openai":
        return "Error: Only OpenAI is currently supported for rewriting."

    try:
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert copywriter. Rewrite the following text based on the user's instruction. Respond only with the rewritten text, without any extra commentary."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        new_text = response.choices[0].message.content.strip()
        logger.info("AI successfully rewrote text based on prompt.")
        return new_text
    except Exception as e:
        logger.error(f"AI text rewrite failed: {e}")
        return f"Error during AI regeneration: {e}"


def call_ai_to_reword_text(provider: str, artwork_description: str, generic_text: str) -> str:
    """
    Uses an AI provider to reword generic text to blend with a specific artwork description.
    """
    logger.info(f"Initiating generic text rewording with provider: {provider}")

    # This prompt is specifically crafted to meet the user's requirements
    prompt = f"""
    You are an expert SEO copywriter for digital art marketplaces. Your task is to reword the following 'Generic Text' to make it unique and blend seamlessly with the preceding 'Artwork Description'.

    Instructions:
    1.  Maintain the original word count and all key details (like file types, dimensions, etc.) from the 'Generic Text'.
    2.  Rewrite the text to flow naturally from the end of the 'Artwork Description'.
    3.  Subtly incorporate keywords and themes from the 'Artwork Description' to enhance SEO and contextual relevance.
    4.  The final output must be ONLY the reworded generic text, with no extra headings, notes, or explanations.

    ---
    Artwork Description (for context):
    "{artwork_description}"
    ---
    Generic Text to Reword:
    "{generic_text}"
    ---
    """

    if provider == "openai":
        try:
            response = client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert SEO copywriter specializing in digital art listings."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.75,
                max_tokens=1024, # Ensure enough tokens for a lengthy generic block
            )
            reworded_text = response.choices[0].message.content.strip()
            logger.info("Successfully reworded generic text with OpenAI.")
            return reworded_text
        except Exception as e:
            logger.error(f"OpenAI rewording service error: {e}")
            raise  # Re-raise the exception to be caught by the Flask route
    
    # Placeholder for Gemini integration
    elif provider == "gemini":
        logger.warning("Gemini provider for rewording is not yet implemented.")
        # In a real implementation, the call to the Gemini API would go here.
        # For now, we return the original text with a note.
        return f"(Gemini integration pending) {generic_text}"
    
    else:
        logger.error(f"Unsupported provider for rewording: {provider}")
        raise ValueError("Unsupported provider specified")