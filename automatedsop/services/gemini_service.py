import json
import time
import requests
from django.conf import settings


class GeminiService:
    """Centralized Gemini API service"""

    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    API_KEY = "AIzaSyC4GFljfImdJ39uzkyj2vLZqbjqZ3fNGjg"

    @classmethod
    def call_api(cls, prompt, retries=5, delay=5):
        """Make API call to Gemini with retry logic"""

        headers = {"Content-Type": "application/json"}
        params = {"key": cls.API_KEY}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        for attempt in range(retries):
            try:
                response = requests.post(cls.API_URL, headers=headers, params=params, json=payload)
                response.raise_for_status()

                result = response.json()
                raw_text = result['candidates'][0]['content']['parts'][0]['text']
                return cls._clean_model_output(raw_text)

            except requests.exceptions.HTTPError as http_err:
                if response.status_code == 429:
                    print(f"Rate limit hit. Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    return f"Error: {http_err}"

            except Exception as err:
                print(f"Unexpected error: {err}")
                return "Error: Unable to process the request."

        return "Error: Failed after retries."

    @staticmethod
    def _clean_model_output(text):
        """Clean Gemini output from markdown formatting"""

        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        return text.strip()