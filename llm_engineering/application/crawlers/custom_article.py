from urllib.parse import urlparse 

from langchain_community.document_loaders import AsyncHtmlLoader  # fetches multiple pages efficienctly
from langchain_community.document_transformers.html2text import Html2TextTransformer  # removes HTMl tags and extracts content
from loguru import logger

from llm_engineering.domain.documents import ArticleDocument

from .base import BaseCrawler


class CustomArticleCrawler(BaseCrawler):
    model = ArticleDocument

    def __init__(self) -> None:
        super().__init__()

    def extract(self, link: str, **kwargs) -> None:
        old_model = self.model.find(link=link)
        if old_model is not None:
            logger.info(f"Article already exists in the database: {link}")

            return

        logger.info(f"Starting scrapping article: {link}")

        loader = AsyncHtmlLoader([link])
        docs = loader.load()  # fetched HTMl content is stored in docs

        html2text = Html2TextTransformer()  
        docs_transformed = html2text.transform_documents(docs)  # HTMl taggs are removed
        doc_transformed = docs_transformed[0]

        # Examples of doc_transformed
        # {
        #     "page_content": "Welcome to AI Trends\nArtificial intelligence is evolving rapidly...",
        #     "metadata": {
        #         "title": "AI Trends",
        #         "description": "Latest Developments in AI",
        #         "language": "en"
        #     }
        # }

        content = {
            "Title": doc_transformed.metadata.get("title"),
            "Subtitle": doc_transformed.metadata.get("description"),
            "Content": doc_transformed.page_content,
            "language": doc_transformed.metadata.get("language"),
        }


        parsed_url = urlparse(link)
        platform = parsed_url.netloc

        user = kwargs["user"]
        instance = self.model(
            content=content,
            link=link,
            platform=platform,
            author_id=user.id,
            author_full_name=user.full_name,
        )
        instance.save()

        logger.info(f"Finished scrapping custom article: {link}")
