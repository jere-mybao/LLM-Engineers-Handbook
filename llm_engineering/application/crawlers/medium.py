from bs4 import BeautifulSoup

from loguru import logger

from llm_engineering.domain.documents import ArticleDocument

from .base import BaseSeleniumCrawler

# Selenium + BeautifulSoup vs. AsyncHtmlLoader + Html2TextTransformer

# Selenium + BeautifulSoup:
#    - Used for JavaScript-rendered pages (e.g., Medium, LinkedIn).
#    - Requires scrolling to load dynamic content.
#    - Extracts specific elements like titles and paragraphs.

# AsyncHtmlLoader + Html2TextTransformer**:
#    - Ideal for static HTML pages** (e.g., Wikipedia, News sites).
#    - Works faster than Selenium (no browser overhead).
#    - Automatically extracts metadata

# When to Use Which?
# - Use Selenium for dynamic sites (Medium, Facebook, LinkedIn).
# - Use AsyncHtmlLoader for static sites (Wikipedia, blogs, news articles).

class MediumCrawler(BaseSeleniumCrawler):
    model = ArticleDocument

    def set_extra_driver_options(self, options) -> None:
        options.add_argument(r"--profile-directory=Profile 2")

    def extract(self, link: str, **kwargs) -> None:
        old_model = self.model.find(link=link)
        if old_model is not None:
            logger.info(f"Article already exists in the database: {link}")

            return

        logger.info(f"Starting scrapping Medium article: {link}")

        self.driver.get(link)
        self.scroll_page()

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        title = soup.find_all("h1", class_="pw-post-title")
        subtitle = soup.find_all("h2", class_="pw-subtitle-paragraph")

        data = {
            # <h1 class="pw-post-title">The Future of AI</h1> -> "The Future of AI"
            "Title": title[0].string if title else None, 
            "Subtitle": subtitle[0].string if subtitle else None,
            "Content": soup.get_text(),
        }

        self.driver.close()

        user = kwargs["user"]
        instance = self.model(
            platform="medium",
            content=data,
            link=link,
            author_id=user.id,
            author_full_name=user.full_name,
        )
        instance.save()

        logger.info(f"Successfully scraped and saved article: {link}")
