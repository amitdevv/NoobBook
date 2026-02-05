"""
Brand Asset Service - Business logic for brand asset management.

Educational Note: Brand assets (logos, icons, fonts, images) are stored
per-project and used by studio agents to maintain consistent branding
across generated content.
"""
import uuid
from typing import Optional, Dict, List, Any

from app.services.integrations.supabase import get_supabase, is_supabase_enabled
from app.services.integrations.supabase import storage_service


class BrandAssetService:
    """
    Service class for managing brand assets using Supabase.

    Educational Note: Each asset has metadata stored in the database and
    the actual file stored in Supabase Storage. The file_path column
    references the storage location.
    """

    def __init__(self):
        """Initialize the brand asset service."""
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_ANON_KEY to your .env file."
            )
        self.supabase = get_supabase()
        self.table = "brand_assets"

    def list_assets(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List all brand assets for a project.

        Args:
            project_id: The project UUID

        Returns:
            List of brand assets sorted by asset_type and name
        """
        response = (
            self.supabase.table(self.table)
            .select("*")
            .eq("project_id", project_id)
            .order("asset_type")
            .order("is_primary", desc=True)
            .order("name")
            .execute()
        )
        return response.data or []

    def list_assets_by_type(
        self,
        project_id: str,
        asset_type: str
    ) -> List[Dict[str, Any]]:
        """
        List brand assets of a specific type for a project.

        Args:
            project_id: The project UUID
            asset_type: The asset type (logo, icon, font, image)

        Returns:
            List of brand assets of the specified type
        """
        response = (
            self.supabase.table(self.table)
            .select("*")
            .eq("project_id", project_id)
            .eq("asset_type", asset_type)
            .order("is_primary", desc=True)
            .order("name")
            .execute()
        )
        return response.data or []

    def get_asset(
        self,
        project_id: str,
        asset_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single brand asset by ID.

        Args:
            project_id: The project UUID
            asset_id: The brand asset UUID

        Returns:
            Brand asset data or None if not found
        """
        response = (
            self.supabase.table(self.table)
            .select("*")
            .eq("id", asset_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]

    def get_primary_asset(
        self,
        project_id: str,
        asset_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the primary asset of a specific type for a project.

        Args:
            project_id: The project UUID
            asset_type: The asset type (logo, icon, font, image)

        Returns:
            Primary brand asset or None if not found
        """
        response = (
            self.supabase.table(self.table)
            .select("*")
            .eq("project_id", project_id)
            .eq("asset_type", asset_type)
            .eq("is_primary", True)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]

    def create_asset(
        self,
        project_id: str,
        name: str,
        asset_type: str,
        file_name: str,
        file_data: bytes,
        mime_type: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_primary: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new brand asset with file upload.

        Args:
            project_id: The project UUID
            name: Display name for the asset
            asset_type: Type of asset (logo, icon, font, image)
            file_name: Original filename
            file_data: File bytes
            mime_type: MIME type of the file
            description: Optional description
            metadata: Optional metadata (dimensions, font info, etc.)
            is_primary: Whether this is the primary asset of its type

        Returns:
            Created brand asset object

        Raises:
            RuntimeError: If file upload or database insert fails
        """
        # Generate asset ID
        asset_id = str(uuid.uuid4())

        # Upload file to storage
        file_path = storage_service.upload_brand_asset(
            project_id=project_id,
            asset_id=asset_id,
            filename=file_name,
            file_data=file_data,
            content_type=mime_type
        )

        if not file_path:
            raise RuntimeError("Failed to upload brand asset file to storage")

        # If this is set as primary, unset other primary assets of this type
        if is_primary:
            self._unset_primary_for_type(project_id, asset_type)

        # Create database record
        asset_data = {
            "id": asset_id,
            "project_id": project_id,
            "name": name,
            "description": description,
            "asset_type": asset_type,
            "file_path": file_path,
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": len(file_data),
            "metadata": metadata or {},
            "is_primary": is_primary
        }

        response = (
            self.supabase.table(self.table)
            .insert(asset_data)
            .execute()
        )

        if not response.data:
            # Cleanup uploaded file on failure
            storage_service.delete_brand_asset(project_id, asset_id, file_name)
            raise RuntimeError("Failed to create brand asset record")

        print(f"Created brand asset: {name} (ID: {asset_id})")
        return response.data[0]

    def update_asset(
        self,
        project_id: str,
        asset_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_primary: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update a brand asset's metadata.

        Args:
            project_id: The project UUID
            asset_id: The brand asset UUID
            name: New name (optional)
            description: New description (optional)
            metadata: New metadata (optional)
            is_primary: New primary status (optional)

        Returns:
            Updated brand asset or None if not found
        """
        # Check if asset exists
        existing = self.get_asset(project_id, asset_id)
        if not existing:
            return None

        # Build update data
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if metadata is not None:
            update_data["metadata"] = metadata
        if is_primary is not None:
            update_data["is_primary"] = is_primary
            if is_primary:
                # Unset other primary assets of this type
                self._unset_primary_for_type(project_id, existing["asset_type"])

        if not update_data:
            return existing

        # Update the record
        response = (
            self.supabase.table(self.table)
            .update(update_data)
            .eq("id", asset_id)
            .eq("project_id", project_id)
            .execute()
        )

        if response.data:
            print(f"Updated brand asset: {asset_id}")
            return response.data[0]

        return None

    def delete_asset(self, project_id: str, asset_id: str) -> bool:
        """
        Delete a brand asset and its file.

        Args:
            project_id: The project UUID
            asset_id: The brand asset UUID

        Returns:
            True if deleted, False if not found
        """
        # Get asset to find file info
        asset = self.get_asset(project_id, asset_id)
        if not asset:
            return False

        # Delete file from storage
        storage_service.delete_brand_asset(
            project_id=project_id,
            asset_id=asset_id,
            filename=asset["file_name"]
        )

        # Delete database record
        self.supabase.table(self.table).delete().eq("id", asset_id).eq("project_id", project_id).execute()

        print(f"Deleted brand asset: {asset_id}")
        return True

    def set_primary(
        self,
        project_id: str,
        asset_id: str,
        asset_type: str
    ) -> bool:
        """
        Set a brand asset as the primary for its type.

        Args:
            project_id: The project UUID
            asset_id: The brand asset UUID
            asset_type: The asset type

        Returns:
            True if successful, False if asset not found
        """
        # Check if asset exists
        asset = self.get_asset(project_id, asset_id)
        if not asset or asset["asset_type"] != asset_type:
            return False

        # Unset other primary assets of this type
        self._unset_primary_for_type(project_id, asset_type)

        # Set this asset as primary
        self.supabase.table(self.table).update({
            "is_primary": True
        }).eq("id", asset_id).eq("project_id", project_id).execute()

        print(f"Set primary {asset_type}: {asset_id}")
        return True

    def get_asset_url(
        self,
        project_id: str,
        asset_id: str,
        expires_in: int = 3600
    ) -> Optional[str]:
        """
        Get a signed URL for downloading a brand asset.

        Args:
            project_id: The project UUID
            asset_id: The brand asset UUID
            expires_in: URL expiration time in seconds

        Returns:
            Signed URL or None if asset not found
        """
        asset = self.get_asset(project_id, asset_id)
        if not asset:
            return None

        return storage_service.get_brand_asset_url(
            project_id=project_id,
            asset_id=asset_id,
            filename=asset["file_name"],
            expires_in=expires_in
        )

    def _unset_primary_for_type(self, project_id: str, asset_type: str) -> None:
        """
        Unset primary flag for all assets of a given type.

        Args:
            project_id: The project UUID
            asset_type: The asset type to update
        """
        self.supabase.table(self.table).update({
            "is_primary": False
        }).eq("project_id", project_id).eq("asset_type", asset_type).execute()


# Singleton instance
brand_asset_service = BrandAssetService()
