/**
 * LogosSection Component
 * Educational Note: Manages brand logos with upload and primary selection.
 */
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui/button';
import { Plus, CircleNotch, Image } from '@phosphor-icons/react';
import { brandAPI, type BrandAsset } from '../../../lib/api/brand';
import { BrandAssetCard } from '../BrandAssetCard';
import { BrandAssetUploader } from '../BrandAssetUploader';

interface LogosSectionProps {
  projectId: string;
}

export const LogosSection: React.FC<LogosSectionProps> = ({ projectId }) => {
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploaderOpen, setUploaderOpen] = useState(false);

  const loadAssets = async () => {
    try {
      setLoading(true);
      const response = await brandAPI.listAssets(projectId, 'logo');
      if (response.data.success) {
        setAssets(response.data.assets);
      }
    } catch (error) {
      console.error('Failed to load logos:', error);
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
          <h2 className="text-xl font-semibold">Logos</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Upload your brand logos. SVG format is recommended for scalability.
          </p>
        </div>
        <Button onClick={() => setUploaderOpen(true)} className="gap-2">
          <Plus size={16} />
          Upload Logo
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <CircleNotch size={24} className="animate-spin text-muted-foreground" />
        </div>
      ) : assets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Image size={48} className="text-muted-foreground mb-4" />
          <p className="text-muted-foreground mb-4">No logos uploaded yet</p>
          <Button variant="soft" onClick={() => setUploaderOpen(true)}>
            Upload your first logo
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
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
        assetType="logo"
        open={uploaderOpen}
        onOpenChange={setUploaderOpen}
        onUploaded={loadAssets}
        acceptedTypes="image/svg+xml,image/png,image/jpeg,image/webp"
      />
    </div>
  );
};
