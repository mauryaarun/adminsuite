"""
Lightweight Ollama API client using urllib (no extra dependencies).
"""
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url="http://127.0.0.1:11434"):
        self.base_url = base_url.rstrip("/")
        logger.info(f"OllamaClient initialized with base_url={self.base_url}")

    def list_models(self) -> list[dict]:
        """Return list of installed models [{name, size, ...}]."""
        url = f"{self.base_url}/api/tags"
        logger.info(f"Fetching model list from {url}")
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                logger.info(f"Successfully fetched {len(models)} model(s)")
                return models
        except urllib.error.URLError as e:
            logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")
            raise ConnectionError(f"Failed to connect to Ollama at {self.base_url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching models: {e}")
            raise RuntimeError(f"Failed to fetch models: {e}")

    def ping(self) -> bool:
        """Test if Ollama is reachable."""
        url = f"{self.base_url}/api/tags"
        logger.info(f"Pinging Ollama at {url}")
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    logger.info("Ollama ping successful")
                    return True
                logger.warning(f"Ollama returned status {resp.status}")
                return False
        except Exception as e:
            logger.error(f"Ollama ping failed: {e}")
            return False

    def chat(self, model, messages, stream=False):
        url = f"{self.base_url}/api/chat"
        logger.info(f"Sending chat request to {url} with model={model}, stream={stream}")
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            if stream:
                logger.info("Using streaming response")
                return self._stream_response(req)
            else:
                logger.info("Using non-streaming response")
                with urllib.request.urlopen(req, timeout=120) as response:
                    body = response.read().decode("utf-8")
                    logger.info(f"Received response ({len(body)} bytes)")
                    return json.loads(body)
        except urllib.error.URLError as e:
            logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")
            raise ConnectionError(f"Failed to connect to Ollama at {self.base_url}: {e}")
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            raise RuntimeError(f"Ollama request failed: {e}")

    def _stream_response(self, req):
        logger.info("Starting streaming response")
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                for line in response:
                    if line:
                        try:
                            chunk = json.loads(line.decode("utf-8"))
                            yield chunk
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to decode streaming chunk: {e}")
                            continue
        except Exception as e:
            logger.error(f"Error during streaming: {e}")
            raise