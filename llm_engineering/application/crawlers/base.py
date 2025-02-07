import time
from abc import ABC, abstractmethod  # Abstract Base Class
from tempfile import mkdtemp

import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from llm_engineering.domain.documents import NoSQLBaseDocument

# Check if the current version of chromedriver exists
# and if it doesn't exist, download it automatically,
# then add chromedriver to path
chromedriver_autoinstaller.install()


class BaseCrawler(ABC):  # cannot create an instance of BaseCrawler
    model: type[NoSQLBaseDocument]  # model must be a subclass of NoSQLBaseDocument

    @abstractmethod  # every subclass must implemenet this method
    def extract(self, link: str, **kwargs) -> None: ...

# used for LinkedIn and Medium (need Selenium to collect the data, automating browsers)
class BaseSeleniumCrawler(BaseCrawler, ABC):  # inherits from BaseCrawler to maintain abstract structure requiring extract()
    def __init__(self, scroll_limit: int = 5) -> None:
        options = webdriver.ChromeOptions()  # creates a Chrome Webdriver instance

        options.add_argument("--no-sandbox")  # disables sandboxing (needed to run inside containers)
        options.add_argument("--headless=new")  # runs Chrome without a visible UI
        options.add_argument("--disable-dev-shm-usage")  # prevents shared memory crashes in Docker/Linux
        options.add_argument("--log-level=3")  # reduces logging output from Chrome
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--ignore-certificate-errors")  # ignore SSL errors on insecure sites
        options.add_argument(f"--user-data-dir={mkdtemp()}")
        options.add_argument(f"--data-path={mkdtemp()}")
        options.add_argument(f"--disk-cache-dir={mkdtemp()}")
        options.add_argument("--remote-debugging-port=9226")

        self.set_extra_driver_options(options)

        self.scroll_limit = scroll_limit
        self.driver = webdriver.Chrome(
            options=options,
        )
    
    # calls a placeholder method that can be overridden by subclasses to add more configurations
    def set_extra_driver_options(self, options: Options) -> None:
        pass

    # can be overridden by subclasses to handle authentication
    def login(self) -> None:
        pass

    def scroll_page(self) -> None:
        """Scroll through a webpage based on the scroll limit."""
        current_scroll = 0
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height or (self.scroll_limit and current_scroll >= self.scroll_limit):
                break
            last_height = new_height
            current_scroll += 1
