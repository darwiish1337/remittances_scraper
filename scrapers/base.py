import time
import logging
import requests
import random
from pathlib import Path
from datetime import datetime
from typing import Optional, Union, Any
from rich.logging import RichHandler

# Global constants for paths and configuration
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Configure professional logging - File only for detailed logs, Rich for CLI (Filtered)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / f"scraper_{datetime.now():%Y%m%d}.log", encoding='utf-8'),
    ]
)

# Create a filtered RichHandler that only shows CRITICAL messages to CLI
# This ensures the UI stays clean as requested by the user
class CLIFilter(logging.Filter):
    def filter(self, record):
        # Block everything from scrapers in the CLI to keep it clean.
        # Only errors that are NOT network-retries should show up if at all.
        return False # Completely silence the logging handlers for CLI

cli_handler = RichHandler(rich_tracebacks=True, markup=True, show_time=False, show_path=False)
cli_handler.addFilter(CLIFilter())
logging.getLogger().addHandler(cli_handler)

# Standard browser headers to mitigate 403 Forbidden responses
# Using a more comprehensive set of headers to mimic a real browser
BROWSER_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

def get_random_headers():
    return {
        "User-Agent": random.choice(BROWSER_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

class BaseScraper:
    """
    Abstract base class providing foundational HTTP capabilities for all data scrapers.
    Implements standardized error handling, exponential backoff, and session management.
    """

    SOURCE_NAME: str = "base"
    BASE_URL: str = ""

    def __init__(self, delay: float = 1.0, retries: int = 5):
        """
        Initializes the scraper with configurable rate-limiting and retry parameters.
        """
        self.delay = delay
        self.retries = retries
        self.session = requests.Session()
        
        # Add an adapter to handle connection pool issues and retries at the network level
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=20,
            max_retries=5,
            pool_block=False
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self.session.headers.update(get_random_headers())
        self.log = logging.getLogger(self.SOURCE_NAME)

    def get(self, url: str, params: Optional[dict] = None, **kwargs) -> Optional[requests.Response]:
        """
        Executes a robust GET request with retry logic and rate-limiting.
        """
        for attempt in range(1, self.retries + 1):
            try:
                # Merge base random headers with any specific headers passed in kwargs
                # This prevents "multiple values for keyword argument 'headers'" error
                request_headers = get_random_headers()
                if 'headers' in kwargs:
                    request_headers.update(kwargs.pop('headers'))

                response = self.session.get(url, params=params, timeout=30, headers=request_headers, **kwargs)
                
                if response.status_code == 403:
                    self.log.warning(f"Access Denied (403) at {url} | Attempt {attempt}/{self.retries}. Escalating delay.")
                    self._sleep(attempt * 7.0) # More aggressive backoff
                    continue
                
                response.raise_for_status()
                self._sleep()
                return response
                
            except requests.exceptions.HTTPError as err:
                code = err.response.status_code
                self.log.warning(f"HTTP Error {code} at {url} | Attempt {attempt}/{self.retries}")
                if code == 404:
                    return None
                self._sleep(attempt * 2.0)
            except requests.exceptions.RequestException as err:
                self.log.warning(f"Network failure: {err} at {url} | Attempt {attempt}/{self.retries}")
                self._sleep(attempt * 2.0)
                
        self.log.error(f"Failed to retrieve data from {url} after {self.retries} attempts")
        return None

    def get_json(self, url: str, params: Optional[dict] = None, **kwargs) -> Optional[Union[dict, list]]:
        """
        Retrieves and parses JSON data from the specified endpoint.
        """
        response = self.get(url, params=params, **kwargs)
        if response is None:
            return None
        try:
            return response.json()
        except Exception as err:
            self.log.error(f"JSON parsing failed for {url}: {err}")
            return None

    def _sleep(self, extra_wait: float = 0.0):
        """
        Introduces a randomized delay to simulate human-like behavior and respect API limits.
        """
        duration = self.delay + random.uniform(0.1, 0.7) + extra_wait
        time.sleep(duration)

    def scrape(self, **kwargs):
        """
        Orchestration method for the scraping sequence. Must be implemented by subclasses.
        """
        raise NotImplementedError("Concrete scrapers must implement the 'scrape' method.")
