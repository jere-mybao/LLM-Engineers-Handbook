import uuid  # generates universally unique identifiers (UUIDs)
from abc import ABC
from typing import Generic, Type, TypeVar  # Generic (flexible type), TypeVar (generic type variable)

from loguru import logger
from pydantic import UUID4, BaseModel, Field
from pymongo import errors  # pymongo interacts with MongoDB

from llm_engineering.domain.exceptions import ImproperlyConfigured
from llm_engineering.infrastructure.db.mongo import connection
from llm_engineering.settings import settings

_database = connection.get_database(settings.DATABASE_NAME)


T = TypeVar("T", bound="NoSQLBaseDocument")  # T can stand for any NOSQLBaseDocument subclass


class NoSQLBaseDocument(BaseModel, Generic[T], ABC):  # Generic[T] (supports flexible document types), ABC (abstract base class)
    id: UUID4 = Field(default_factory=uuid.uuid4)  # every document has a unique identifier

    # enables document comparison by ids
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, self.__class__):
            return False

        return self.id == value.id

    # enables using documents in sets/dictionaries: documents = {UserDocument(id=uuid.uuid4()): "Admin"}
    def __hash__(self) -> int:
        return hash(self.id)

    @classmethod
    def from_mongo(cls: Type[T], data: dict) -> T:  # input: dictionary representing a MongoDB doc, output: instance of the calling class
        """Convert "_id" (str object) into "id" (UUID object)."""

        if not data:
            raise ValueError("Data is empty.")

        id = data.pop("_id")  # mongo_data ={"_id": "123e4567-e89b-12d3-a456-426614174000", "name": "Charlie", "email": "charlie@example.com"}

        return cls(**dict(data, id=id))  # cls(name="Charlie", email="charlie@example.com", id="123e4567-e89b-12d3-a456-426614174000")

    def to_mongo(self: T, **kwargs) -> dict:  # output: dictionary for MongoDB storage
        """Convert "id" (UUID object) into "_id" (str object)."""
        exclude_unset = kwargs.pop("exclude_unset", False)  # exclude unset fields
        by_alias = kwargs.pop("by_alias", True)  

        # self.model_dump converts an object into a python dictionary)
        parsed = self.model_dump(exclude_unset=exclude_unset, by_alias=by_alias, **kwargs)

        if "_id" not in parsed and "id" in parsed:
            parsed["_id"] = str(parsed.pop("id"))

        for key, value in parsed.items():
            if isinstance(value, uuid.UUID):
                parsed[key] = str(value)

        # user = NoSQLBaseDocument(id=uuid.uuid4(), name="Alice", email="alice@example.com")
        # parsed = user.model_dump()
        # parsed["_id"] = str(parsed.pop("id"))
        # print(parsed)

        # {
        #     "_id": "550e8400-e29b-41d4-a716-446655440000",
        #     "name": "Alice",
        #     "email": "alice@example.com"
        # }

        return parsed

    def model_dump(self: T, **kwargs) -> dict:
        dict_ = super().model_dump(**kwargs)

        for key, value in dict_.items():
            if isinstance(value, uuid.UUID):
                dict_[key] = str(value)

        return dict_

    def save(self: T, **kwargs) -> T | None:  # returns None if the document cannot be saved
        collection = _database[self.get_collection_name()]
        try:
            collection.insert_one(self.to_mongo(**kwargs))

            return self
        except errors.WriteError:
            logger.exception("Failed to insert document.")

            return None

    @classmethod
    def get_or_create(cls: Type[T], **filter_options) -> T:
        collection = _database[cls.get_collection_name()]
        try:
            instance = collection.find_one(filter_options)
            if instance:
                return cls.from_mongo(instance)

            new_instance = cls(**filter_options)
            new_instance = new_instance.save()

            return new_instance
        except errors.OperationFailure:
            logger.exception(f"Failed to retrieve document with filter options: {filter_options}")

            raise

    @classmethod
    def bulk_insert(cls: Type[T], documents: list[T], **kwargs) -> bool:
        collection = _database[cls.get_collection_name()]
        try:
            collection.insert_many(doc.to_mongo(**kwargs) for doc in documents)

            return True
        except (errors.WriteError, errors.BulkWriteError):
            logger.error(f"Failed to insert documents of type {cls.__name__}")

            return False

    @classmethod
    def find(cls: Type[T], **filter_options) -> T | None:
        collection = _database[cls.get_collection_name()]
        try:
            instance = collection.find_one(filter_options)
            if instance:
                return cls.from_mongo(instance)

            return None
        except errors.OperationFailure:
            logger.error("Failed to retrieve document")

            return None

    @classmethod
    def bulk_find(cls: Type[T], **filter_options) -> list[T]:
        collection = _database[cls.get_collection_name()]
        try:
            instances = collection.find(filter_options)
            return [document for instance in instances if (document := cls.from_mongo(instance)) is not None]
        except errors.OperationFailure:
            logger.error("Failed to retrieve documents")

            return []

    @classmethod
    def get_collection_name(cls: Type[T]) -> str:
        if not hasattr(cls, "Settings") or not hasattr(cls.Settings, "name"):
            raise ImproperlyConfigured(
                "Document should define an Settings configuration class with the name of the collection."
            )

        return cls.Settings.name
