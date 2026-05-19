/**
 * DownloadLogsConfirmDialog — confirmation dialog shown before the
 * support-bundle download starts.
 *
 * The dialog has one extra control beyond Cancel/Download: a checkbox
 * labelled "Delete logs from server after download". `useLogsState`
 * owns the checkbox value (so it can be remembered across opens via
 * users.settings.auto_delete_on_download) and triggers the clear after
 * the download has begun.
 */
import React from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { Checkbox } from '../ui/checkbox';
import { Download } from '@phosphor-icons/react';

interface DownloadLogsConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  deleteAfterDownload: boolean;
  onDeleteAfterDownloadChange: (next: boolean) => void;
  onConfirm: () => void;
  /** When false, the "delete after download" checkbox is hidden. The
   * `/logs/clear` endpoint is admin-only, so non-admins should never
   * see (and certainly never check) this destructive option. */
  canDelete?: boolean;
}

export const DownloadLogsConfirmDialog: React.FC<DownloadLogsConfirmDialogProps> = ({
  open,
  onOpenChange,
  deleteAfterDownload,
  onDeleteAfterDownloadChange,
  onConfirm,
  canDelete = true,
}) => {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Download log bundle</AlertDialogTitle>
          <AlertDialogDescription>
            The ZIP includes the rotating <code>backend.log</code> files
            (secrets redacted), the list of configured env-var names,
            applied migrations, and basic deployment metadata.
          </AlertDialogDescription>
        </AlertDialogHeader>

        {canDelete && (
          <label className="flex items-start gap-3 rounded-md border border-stone-200 bg-stone-50 px-3 py-3 cursor-pointer">
            <Checkbox
              checked={deleteAfterDownload}
              onCheckedChange={(value) => onDeleteAfterDownloadChange(value === true)}
              className="mt-0.5"
            />
            <span className="text-sm leading-snug text-stone-700">
              <span className="font-medium text-stone-900 block">
                Delete logs from server after download
              </span>
              Frees disk space on the deployment. The bundle in your downloads
              folder is your only copy after this. Your choice is remembered
              for next time.
            </span>
          </label>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>
            <Download size={16} className="mr-2" />
            Download
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
