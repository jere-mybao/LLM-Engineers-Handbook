import os
import shutil
import subprocess  # allows running system commands (e.g., executing git commands: cloning repos or running CLI tools)
import tempfile

from loguru import logger

from llm_engineering.domain.documents import RepositoryDocument

from .base import BaseCrawler


class GithubCrawler(BaseCrawler):
    model = RepositoryDocument

    def __init__(self, ignore=(".git", ".toml", ".lock", ".png")) -> None:
        super().__init__()  # ensures that BaseCrawler is properly initalized
        self._ignore = ignore

    def extract(self, link: str, **kwargs) -> None:
        old_model = self.model.find(link=link)
        if old_model is not None:
            logger.info(f"Repository already exists in the database: {link}")

            return

        logger.info(f"Starting scrapping GitHub repository: {link}")

        repo_name = link.rstrip("/").split("/")[-1]

        local_temp = tempfile.mkdtemp()

        try:
            os.chdir(local_temp)
            subprocess.run(["git", "clone", link])

            repo_path = os.path.join(local_temp, os.listdir(local_temp)[0])  # noqa: PTH118

            tree = {}
            for root, _, files in os.walk(repo_path):  # walks through all directories and files inside repo_path and returns tuple(root dir, subdirs, root files)
                dir = root.replace(repo_path, "").lstrip("/")  # removes the base path: /tmp/tmp123xyz/MyRepo/assets/ -> "assets"
                if dir.startswith(self._ignore):
                    continue

                for file in files:
                    if file.endswith(self._ignore):
                        continue
                    file_path = os.path.join(dir, file)  # noqa: PTH118
                    with open(os.path.join(root, file), "r", errors="ignore") as f:  # noqa: PTH123, PTH118, read mode "r"
                        tree[file_path] = f.read().replace(" ", "")  # removes spaces and stores cleaned content

            user = kwargs["user"]
            
            # stores repo content and metadata
            instance = self.model(
                content=tree,
                name=repo_name,
                link=link,
                platform="github",
                author_id=user.id,
                author_full_name=user.full_name,
            )
            instance.save()  # saves the record in MongoDB

        except Exception:
            raise
        finally:
            shutil.rmtree(local_temp)  # delete a folder and its contents

        logger.info(f"Finished scrapping GitHub repository: {link}")
