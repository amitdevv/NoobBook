/**
 * Editor-assist + image-upload API clients used by the document
 * editor's selection toolbar and drop/paste handlers.
 */
import axios from 'axios';
import { API_BASE_URL } from './client';
import { createLogger } from '@/lib/logger';

const log = createLogger('editor-api');

export type AssistAction = 'improve' | 'continue' | 'summarize';

export async function assistText(action: AssistAction, text: string): Promise<string> {
  try {
    const response = await axios.post(`${API_BASE_URL}/editor/assist`, { action, text });
    return response.data.result as string;
  } catch (error) {
    log.error({ err: error, action }, 'editor assist failed');
    throw error;
  }
}

export interface UploadedEditorImage {
  url: string;
  path: string;
  filename: string;
}

export async function uploadEditorImage(
  projectId: string,
  file: File,
): Promise<UploadedEditorImage> {
  const form = new FormData();
  form.append('file', file);
  const response = await axios.post(
    `${API_BASE_URL}/editor/${projectId}/images`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return {
    url: response.data.url,
    path: response.data.path,
    filename: response.data.filename,
  };
}
