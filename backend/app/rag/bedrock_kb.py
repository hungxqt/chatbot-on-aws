"""AWS Bedrock Knowledge Bases client.

Provides document storage (S3), ingestion triggering, and retrieval
via the Bedrock Agent Runtime API. Collections are simulated via S3 key prefixes.
"""

import asyncio
import logging
from typing import Any

import boto3

from app.rag.models import CollectionInfo, DocumentInfo, SearchResult

logger = logging.getLogger(__name__)


class BedrockKBClient:
    """Client for AWS Bedrock Knowledge Bases."""

    def __init__(
        self,
        knowledge_base_id: str,
        data_source_id: str,
        s3_bucket: str,
        s3_prefix: str = "rag-documents/",
        region_name: str = "us-east-1",
    ):
        self.knowledge_base_id = knowledge_base_id
        self.data_source_id = data_source_id
        self.s3_bucket = s3_bucket
        self.s3_prefix = (s3_prefix.rstrip("/") + "/") if s3_prefix else ""
        self.region_name = region_name

        self._agent_runtime = boto3.client("bedrock-agent-runtime", region_name=region_name)
        self._agent = boto3.client("bedrock-agent", region_name=region_name)
        self._s3 = boto3.client("s3", region_name=region_name)

    def _collection_prefix(self, collection_name: str) -> str:
        return f"{self.s3_prefix}{collection_name}/"

    def _s3_key(self, collection_name: str, filename: str) -> str:
        return f"{self._collection_prefix(collection_name)}{filename}"

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        collection_name: str | None = None,
    ) -> list[SearchResult]:
        """Query the Knowledge Base and return results as SearchResult objects."""

        retrieval_config: dict[str, Any] = {
            "vectorSearchConfiguration": {
                "numberOfResults": top_k,
            }
        }

        if collection_name:
            retrieval_config["vectorSearchConfiguration"]["filter"] = {
                "startsWith": {
                    "key": "x-amz-bedrock-kb-source-uri",
                    "value": f"s3://{self.s3_bucket}/{self._collection_prefix(collection_name)}",
                }
            }

        def _call() -> dict[str, Any]:
            return self._agent_runtime.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration=retrieval_config,
            )

        response = await asyncio.to_thread(_call)
        return self._map_retrieve_results(response)

    def _map_retrieve_results(self, response: dict[str, Any]) -> list[SearchResult]:
        results: list[SearchResult] = []
        for item in response.get("retrievalResults", []):
            content = item.get("content", {}).get("text", "")
            score = item.get("score", 0.0)
            location = item.get("location", {})
            s3_uri = location.get("s3Location", {}).get("uri", "")
            metadata: dict[str, Any] = item.get("metadata", {})

            filename = s3_uri.rsplit("/", 1)[-1] if s3_uri else ""
            collection = self._extract_collection_from_uri(s3_uri)

            metadata.update(
                {
                    "filename": filename,
                    "collection": collection,
                    "s3_uri": s3_uri,
                }
            )

            results.append(
                SearchResult(
                    content=content,
                    score=score,
                    metadata=metadata,
                    parent_doc_id=s3_uri,
                )
            )
        return results

    def _extract_collection_from_uri(self, s3_uri: str) -> str:
        prefix = f"s3://{self.s3_bucket}/{self.s3_prefix}"
        if s3_uri.startswith(prefix):
            remaining = s3_uri[len(prefix) :]
            return remaining.split("/", 1)[0] if "/" in remaining else ""
        return ""

    # ------------------------------------------------------------------
    # Document upload / delete (S3)
    # ------------------------------------------------------------------

    async def upload_document(self, file_data: bytes, filename: str, collection_name: str) -> str:
        key = self._s3_key(collection_name, filename)
        logger.info(
            f"Uploading to s3://{self.s3_bucket}/{key} "
            f"({len(file_data)} bytes, region={self.region_name})"
        )

        def _upload() -> None:
            self._s3.put_object(
                Bucket=self.s3_bucket,
                Key=key,
                Body=file_data,
            )

        await asyncio.to_thread(_upload)
        logger.info(f"Uploaded s3://{self.s3_bucket}/{key}")
        return key

    async def download_document(self, s3_key: str) -> bytes:
        """Download a document from S3 by its key."""

        def _download() -> bytes:
            response = self._s3.get_object(Bucket=self.s3_bucket, Key=s3_key)
            return response["Body"].read()

        return await asyncio.to_thread(_download)

    async def delete_document(self, s3_key: str) -> None:
        def _delete() -> None:
            self._s3.delete_object(Bucket=self.s3_bucket, Key=s3_key)

        await asyncio.to_thread(_delete)
        logger.info(f"Deleted s3://{self.s3_bucket}/{s3_key}")

    # ------------------------------------------------------------------
    # Ingestion jobs
    # ------------------------------------------------------------------

    async def start_ingestion_job(self) -> str:
        """Trigger a Bedrock KB ingestion sync for the data source."""

        def _start() -> dict[str, Any]:
            return self._agent.start_ingestion_job(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
            )

        response = await asyncio.to_thread(_start)
        job_id = response["ingestionJob"]["ingestionJobId"]
        logger.info(f"Started ingestion job {job_id}")
        return job_id

    # ------------------------------------------------------------------
    # Collection / document listing (S3-based)
    # ------------------------------------------------------------------

    async def list_collections(self) -> list[str]:
        def _list() -> list[str]:
            paginator = self._s3.get_paginator("list_objects_v2")
            collections: set[str] = set()
            for page in paginator.paginate(
                Bucket=self.s3_bucket,
                Prefix=self.s3_prefix,
                Delimiter="/",
            ):
                for prefix_obj in page.get("CommonPrefixes", []):
                    raw = prefix_obj["Prefix"]
                    name = raw[len(self.s3_prefix) :].strip("/")
                    if name:
                        collections.add(name)
            return sorted(collections)

        return await asyncio.to_thread(_list)

    async def list_documents(self, collection_name: str) -> list[DocumentInfo]:
        prefix = self._collection_prefix(collection_name)

        def _list() -> list[dict[str, Any]]:
            paginator = self._s3.get_paginator("list_objects_v2")
            objects: list[dict[str, Any]] = []
            for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    objects.append(obj)
            return objects

        objects = await asyncio.to_thread(_list)
        return [
            DocumentInfo(
                document_id=obj["Key"],
                filename=obj["Key"].rsplit("/", 1)[-1],
                filesize=obj.get("Size"),
                filetype=obj["Key"].rsplit(".", 1)[-1] if "." in obj["Key"] else None,
            )
            for obj in objects
            if not obj["Key"].endswith("/")
        ]

    async def get_collection_info(self, collection_name: str) -> CollectionInfo:
        docs = await self.list_documents(collection_name)
        return CollectionInfo(
            name=collection_name,
            total_vectors=len(docs),
            dim=0,
        )

    async def delete_collection(self, collection_name: str) -> None:
        prefix = self._collection_prefix(collection_name)

        def _delete_all() -> None:
            paginator = self._s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix):
                objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if objects:
                    self._s3.delete_objects(
                        Bucket=self.s3_bucket,
                        Delete={"Objects": objects},
                    )

        await asyncio.to_thread(_delete_all)
        logger.info(f"Deleted collection '{collection_name}' from S3")

    @classmethod
    def from_settings(cls) -> "BedrockKBClient":
        """Create a client from application settings."""
        from app.core.config import settings

        return cls(
            knowledge_base_id=settings.BEDROCK_KNOWLEDGE_BASE_ID,
            data_source_id=settings.BEDROCK_KB_DATA_SOURCE_ID,
            s3_bucket=settings.BEDROCK_KB_S3_BUCKET,
            s3_prefix=settings.BEDROCK_KB_S3_PREFIX,
            region_name=settings.AWS_REGION,
        )
