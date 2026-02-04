import random
import requests

from utils import settings


class QwenTTS:
    """
    A Text-to-Speech engine that uses the Qwen3 TTS API endpoint to generate audio from text.

    This TTS provider connects to a Qwen TTS server and authenticates using email/password
    to obtain a bearer token, then sends TTS requests.

    Attributes:
        max_chars (int): Maximum number of characters allowed per API call.
        api_base_url (str): Base URL for the Qwen TTS API server.
        email (str): Email for authentication.
        password (str): Password for authentication.
        token (str): Bearer token obtained after login.
        available_voices (list): List of supported Qwen TTS voices.
    """

    # Available Qwen TTS speakers
    AVAILABLE_SPEAKERS = [
        "Chelsie",
        "Ethan",
        "Vivian",
        "Asher",
        "Aria",
        "Oliver",
        "Emma",
        "Noah",
        "Sophia",
    ]

    # Available languages
    AVAILABLE_LANGUAGES = [
        "English",
        "Chinese",
        "Spanish",
        "French",
        "German",
        "Japanese",
        "Korean",
        "Portuguese",
        "Russian",
        "Italian",
        "Arabic",
        "Hindi",
    ]

    def __init__(self):
        self.max_chars = 5000
        self.token = None

        # Get configuration
        tts_config = settings.config["settings"]["tts"]

        self.api_base_url = tts_config.get("qwen_api_url", "http://localhost:8080")
        if self.api_base_url.endswith("/"):
            self.api_base_url = self.api_base_url[:-1]

        self.email = tts_config.get("qwen_email")
        self.password = tts_config.get("qwen_password")

        if not self.email or not self.password:
            raise ValueError(
                "Qwen TTS requires 'qwen_email' and 'qwen_password' in settings! "
                "Please configure these in your config.toml file."
            )

        self.available_voices = self.AVAILABLE_SPEAKERS
        self._authenticate()

    def _authenticate(self):
        """
        Authenticate with the Qwen TTS server and obtain a bearer token.
        """
        login_url = f"{self.api_base_url}/api/agent/api/auth/login"
        payload = {"email": self.email, "password": self.password}
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(login_url, json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Qwen TTS authentication failed: {response.status_code} {response.text}"
                )

            data = response.json()
            self.token = data.get("access_token")
            if not self.token:
                raise RuntimeError("Qwen TTS authentication failed: No access_token in response")

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to connect to Qwen TTS server: {str(e)}")

    def get_available_voices(self):
        """
        Return a list of supported voices for Qwen TTS.
        """
        return self.AVAILABLE_SPEAKERS

    def randomvoice(self):
        """
        Select and return a random voice from the available voices.
        """
        return random.choice(self.available_voices)

    def run(self, text: str, filepath: str, random_voice: bool = False):
        """
        Convert the provided text to speech and save the resulting audio to the specified filepath.

        Args:
            text (str): The input text to convert.
            filepath (str): The file path where the generated audio will be saved.
            random_voice (bool): If True, select a random voice from the available voices.
        """
        tts_config = settings.config["settings"]["tts"]

        # Choose voice based on configuration or randomly if requested
        if random_voice:
            speaker = self.randomvoice()
        else:
            speaker = tts_config.get("qwen_speaker", "Vivian")

        # Get language and instruct settings
        language = tts_config.get("qwen_language", "English")
        instruct = tts_config.get("qwen_instruct", "Warm, friendly, conversational.")

        # Build TTS request
        tts_url = f"{self.api_base_url}/api/qwen-tts"
        payload = {
            "text": text,
            "language": language,
            "speaker": speaker,
            "instruct": instruct,
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(tts_url, json=payload, headers=headers, timeout=120)

            # Handle token expiration - re-authenticate and retry
            if response.status_code == 401:
                self._authenticate()
                headers["Authorization"] = f"Bearer {self.token}"
                response = requests.post(tts_url, json=payload, headers=headers, timeout=120)

            if response.status_code != 200:
                raise RuntimeError(
                    f"Qwen TTS generation failed: {response.status_code} {response.text}"
                )

            # Write the audio response to file
            with open(filepath, "wb") as f:
                f.write(response.content)

        except requests.exceptions.Timeout:
            raise RuntimeError("Qwen TTS request timed out. The server may be overloaded.")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to generate audio with Qwen TTS: {str(e)}")
