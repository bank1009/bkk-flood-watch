"""
AI Flood Insight Analyzer using Google Gemini.
Provides smart, natural-language explanation of flood probabilities and underlying reasons in Thai.
"""

__author__ = "Bank Chavalit Tirakitti"
__copyright__ = "Copyright (c) 2026 Bank Chavalit Tirakitti"

import os
import logging
from typing import Optional, Dict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("bkk_flood_watch.ai")

# In-memory cache for generated AI insights to optimize performance and quota
_INSIGHT_CACHE: Dict[str, str] = {}

# Fallback message as specified by requirements
DEFAULT_FALLBACK = "AI Analysis unavailable. Please configure API key."


def get_api_key() -> Optional[str]:
    """Retrieves GEMINI_API_KEY from environment variables or .env file."""
    if "GEMINI_API_KEY" in os.environ:
        val = os.environ.get("GEMINI_API_KEY", "").strip()
        return val if val else None

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if api_key:
                            os.environ["GEMINI_API_KEY"] = api_key
                            return api_key
        except Exception as e:
            logger.warning("Could not parse .env file: %s", e)
    return None


def generate_flood_insight(
    location_name: str,
    peak_rain: float,
    cumulative_3hr: float,
    risk_tier: str,
    lang: str = "th"
) -> str:
    """
    Generates a natural-language flood risk explanation in Thai or English using Google Gemini.

    Args:
        location_name: Name of the monitored district or selected coordinates.
        peak_rain: Peak hourly rainfall rate in mm/hr.
        cumulative_3hr: Maximum 3-hour cumulative rainfall in mm.
        risk_tier: BMA drainage risk tier ('GREEN', 'YELLOW', 'ORANGE', 'RED').
        lang: Target language ('th' or 'en', default 'th').

    Returns:
        Concise 2-3 sentence analysis in the requested language, or fallback message if unavailable.
    """
    api_key = get_api_key()
    if not api_key:
        logger.info("GEMINI_API_KEY not configured. Returning fallback.")
        return DEFAULT_FALLBACK

    target_lang = "en" if lang.lower() == "en" else "th"

    # Cache key incorporating target language to avoid collisions
    cache_key = f"{location_name}_{round(float(peak_rain), 1)}_{round(float(cumulative_3hr), 1)}_{risk_tier}_{target_lang}"
    if cache_key in _INSIGHT_CACHE:
        return _INSIGHT_CACHE[cache_key]

    if target_lang == "en":
        prompt = (
            f"You are a professional Bangkok flood risk analyst. "
            f"Based on the following forecast for {location_name}: "
            f"Peak Rain = {peak_rain:.1f} mm/hr, 3-Hr Cumulative = {cumulative_3hr:.1f} mm, and BMA System Status = {risk_tier}. "
            f"Write a concise, 2-3 sentence analysis in English explaining the probability of flooding and the primary reason "
            f"(e.g., heavy sudden downpour vs. prolonged accumulation). Keep the tone informative and helpful."
        )
    else:
        prompt = (
            f"You are a professional Bangkok flood risk analyst. "
            f"Based on the following forecast for {location_name}: "
            f"Peak Rain = {peak_rain:.1f} mm/hr, 3-Hr Cumulative = {cumulative_3hr:.1f} mm, and BMA System Status = {risk_tier}. "
            f"Write a concise, 2-3 sentence analysis in Thai explaining the probability of flooding and the primary reason "
            f"(e.g., heavy sudden downpour vs. prolonged accumulation). Keep the tone informative and helpful."
        )

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Try gemini-1.5-flash as requested, with fallback cascade to available flash models
        models_to_try = [
            "gemini-1.5-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-flash-latest"
        ]
        last_error = None

        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response and response.text:
                    insight = response.text.strip()
                    _INSIGHT_CACHE[cache_key] = insight
                    logger.info("Generated AI insight using %s for %s", model_name, location_name)
                    return insight
            except Exception as ex:
                last_error = ex
                err_str = str(ex).lower()
                # Continue to next model if model not found or quota exhausted
                if "404" in err_str or "not found" in err_str or "429" in err_str or "quota" in err_str or "resourceexhausted" in err_str:
                    continue
                else:
                    break

        if last_error:
            logger.warning("Gemini generation failed: %s", last_error)
            return DEFAULT_FALLBACK

    except Exception as e:
        logger.warning("AI insight generation error: %s", e)
        return DEFAULT_FALLBACK

    return DEFAULT_FALLBACK
