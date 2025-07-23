from pathlib import Path
from typing import Optional
from uuid import uuid4

from supabase import Client, create_client

from src.core.settings import settings


class StorageService:
    """
    Supabase storage service for handling file uploads and downloads.
    Manages the 'remittances' bucket for PDF files.
    """

    def __init__(self) -> None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError("Supabase configuration is required for storage service")

        self.client: Client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
        self.bucket_name = "remittances"

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        organization_id: str,
        content_type: str = "application/pdf",
    ) -> str:
        """
        Upload a file to the remittances bucket.

        Args:
            file_content: The file content as bytes
            filename: Original filename
            organization_id: Organization ID for path separation
            content_type: MIME type of the file

        Returns:
            The storage path/URL of the uploaded file

        Raises:
            Exception: If upload fails
        """
        # Generate unique filename to avoid conflicts
        file_extension = Path(filename).suffix
        unique_filename = f"{uuid4()}{file_extension}"

        # Create organization-scoped path
        storage_path = f"{organization_id}/{unique_filename}"

        try:
            # Upload file to Supabase storage
            result = self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=file_content,
                file_options={
                    "content-type": content_type,
                    "cache-control": "3600",
                    "upsert": "false",  # Don't overwrite existing files
                },
            )

            if result.error:
                raise Exception(f"Storage upload failed: {result.error}")

            return storage_path

        except Exception as e:
            raise Exception(f"Failed to upload file to storage: {str(e)}")

    async def download_file(self, storage_path: str) -> bytes:
        """
        Download a file from the remittances bucket.

        Args:
            storage_path: The storage path of the file

        Returns:
            The file content as bytes

        Raises:
            Exception: If download fails
        """
        try:
            result = self.client.storage.from_(self.bucket_name).download(storage_path)

            if isinstance(result, dict) and result.get("error"):
                raise Exception(f"Storage download failed: {result['error']}")

            return bytes(result)

        except Exception as e:
            raise Exception(f"Failed to download file from storage: {str(e)}")

    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from the remittances bucket.

        Args:
            storage_path: The storage path of the file

        Returns:
            True if deletion was successful

        Raises:
            Exception: If deletion fails
        """
        try:
            result = self.client.storage.from_(self.bucket_name).remove([storage_path])

            if result.error:
                raise Exception(f"Storage deletion failed: {result.error}")

            return True

        except Exception as e:
            raise Exception(f"Failed to delete file from storage: {str(e)}")

    async def get_file_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """
        Get a signed URL for accessing a file.

        Args:
            storage_path: The storage path of the file
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Signed URL for file access

        Raises:
            Exception: If URL generation fails
        """
        try:
            result = self.client.storage.from_(self.bucket_name).create_signed_url(
                path=storage_path, expires_in=expires_in
            )

            if result.get("error"):
                raise Exception(f"URL generation failed: {result['error']}")

            signed_url = result.get("signedURL")
            return str(signed_url) if signed_url else ""

        except Exception as e:
            raise Exception(f"Failed to generate file URL: {str(e)}")

    def get_public_url(self, storage_path: str) -> Optional[str]:
        """
        Get the public URL for a file (if bucket is public).
        For private buckets, use get_file_url() instead.

        Args:
            storage_path: The storage path of the file

        Returns:
            Public URL or None if not available
        """
        try:
            result = self.client.storage.from_(self.bucket_name).get_public_url(
                storage_path
            )
            public_url = result.get("publicURL")
            return str(public_url) if public_url else None
        except Exception:
            return None


# Global storage service instance
storage_service = (
    StorageService()
    if (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)
    else None
)
