"""Scrape a website"""

from ...component_base import ComponentBase
from ....common.log import log

info = {
    "class_name": "WebScraper",
    "description": "Scrape javascript based websites.",
    "config_parameters": [
        {
            "name": "timeout",
            "required": False,
            "description": "The timeout for the browser in milliseconds.",
            "default": 30000,
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the website to scrape.",
            }
        },
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The title of the website."},
            "content": {"type": "string", "description": "The content of the website."},
        },
    },
}


class WebScraper(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.timeout = self.get_config("timeout", 30000)

    def invoke(self, message, data):
        url = data["url"]
        if type(url) != str or not url:
            raise ValueError("No URL provided")
        content = self.scrape(url)
        return content

    # Scrape a website
    def scrape(self, url):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            err_msg = "Please install playwright by running 'pip install playwright' and 'playwright install'."
            log.error(err_msg)
            raise ValueError(err_msg) from e

        with sync_playwright() as p:
            try:
                # Launch a Chromium browser instance
                browser = p.chromium.launch(
                    headless=True,
                    timeout=self.timeout,
                )  # Set headless=False to see the browser in action
            except ImportError as e:
                err_msg = "Failed to launch the Chromium instance. Please install the browser binaries by running 'playwright install'"
                log.error(err_msg)
                raise ValueError(err_msg) from e
            page = browser.new_page()
            page.goto(url)

            # Wait for the page to fully load
            page.wait_for_load_state("networkidle")

            # Scrape the text content of the page
            title = page.title()
            content = page.evaluate("document.body.innerText")
            resp = {"title": title, "content": content}
            browser.close()

            return resp
