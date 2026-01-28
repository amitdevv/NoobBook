/**
 * IconsSection Component
 * Educational Note: Manages brand icons with upload functionality.
 */
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui/button';
import { Plus, CircleNotch, SquaresFour } from '@phosphor-icons/react';
import { brandAPI, type BrandAsset } from '../../../lib/api/brand';
import { BrandAssetCard } from '../BrandAssetCard';
import { BrandAssetUploader } from '../BrandAssetUploader';

interface IconsSectionProps {
  projectId: string;
}

export const IconsSection: React.FC<IconsSectionProps> = ({ projectId }) => {
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploaderOpen, setUploaderOpen] = useState(false);

  const loadAssets = async () => {
    try {
      setLoading(true);
      const response = await brandAPI.listAssets(projectId, 'icon');
      if (response.data.success) {
        setAssets(response.data.assets);
      }
    } catch (error) {
      console.error('Failed to load icons:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAssets();
  }, [projectId]);

  const handleDelete = async (assetId: string) => {
    try {
      const response = await brandAPI.deleteAsset(projectId, assetId);
      if (response.data.success) {
        loadAssets();
      }
    } catch (error) {
      console.error('Failed to delete asset:', error);
    }
  };

  const handleSetPrimary = async (assetId: string) => {
    try {
      const response = await brandAPI.setAssetPrimary(projectId, assetId);
      if (response.data.success) {
        loadAssets();
      }
    } catch (error) {
      console.error('Failed to set primary:', error);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Icons</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Upload brand icons for use in generated content.
          </p>
        </div>
        <Button onClick={() => setUploaderOpen(true)} className="gap-2">
          <Plus size={16} />
          Upload Icon
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <CircleNotch size={24} className="animate-spin text-muted-foreground" />
        </div>
      ) : assets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <SquaresFour size={48} className="text-muted-foreground mb-4" />
          <p className="text-muted-foreground mb-4">No icons uploaded yet</p>
          <Button variant="soft" onClick={() => setUploaderOpen(true)}>
            Upload your first icon
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {assets.map((asset) => (
            <BrandAssetCard
              key={asset.id}
              asset={asset}
              projectId={projectId}
              onDelete={handleDelete}
              onSetPrimary={handleSetPrimary}
            />
          ))}
        </div>
      )}

      <BrandAssetUploader
        projectId={projectId}
        assetType="icon"
        open={uploaderOpen}
        onOpenChange={setUploaderOpen}
        onUploaded={loadAssets}
        acceptedTypes="image/svg+xml,image/png,image/x-icon"
      />
    </div>
  );
};
