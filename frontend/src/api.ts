export type Warning = { code: string; message: string };
export type Options = { language: 'auto' | 'en' | 'pl'; profile: 'fast' | 'quality'; diarization: boolean; speakerCount: number | null };
export type LocalFiles = {
  directory: string; status: 'ready' | 'pending' | 'missing' | 'error'; files: string[];
  revision: number | null; savedRevision: number | null; attempt: number | null;
  message: string | null; error: { code: string; message: string } | null;
};
export type Job = {
  id: string; name: string; status: string; options: Options; warnings: Warning[];
  error: { code: string; message: string } | null; attempt: number;
  createdAt: string | number; startedAt?: string | number | null; elapsedSeconds?: number; duration?: number;
  localFiles?: LocalFiles;
};
export type Segment = { id: string; start: number; end: number; speakerId: string | null; text: string; editedText: string | null; overlap: boolean };
export type Speaker = { id: string; displayName: string };
export type TranscriptBlock = { id: string; segmentIds: string[]; start: number; end: number; speakerId: string | null; text: string };
export type Grouping = { blocks: TranscriptBlock[]; manualSplits: string[] };
export type GroupingPreview = { revision: number; beforeCount: number; afterCount: number; changed: boolean; blocks: TranscriptBlock[] };
export type Transcript = { schemaVersion: 1; jobId: string; revision: number; language: string | null; duration?: number; segments: Segment[]; speakers: Speaker[]; warnings: Warning[]; provenance: Record<string, unknown>; grouping?: Grouping };
export type ProofreadingSuggestion = { id: string; old: string; new: string; uncertain: boolean; diff: { kind: string; old: string; new: string }[] };
export type ProofreadingTask = { id: string; revision: number; status: string; stale: boolean; progress: number; glossary: string[]; suggestions: ProofreadingSuggestion[]; error: string | null };
export type OperationHistory = { revision: number; canUndo: boolean; canRedo: boolean; operations: { id: string; type: string; createdAt: number; baseRevision: number; resultRevision: number; applied: boolean }[] };
export type ModelReadiness = { ready: boolean; message?: string; missing?: string[] };
export type Health = {
  status: string; ready: boolean;
  dependencies: Record<string, boolean>;
  models: { fast?: ModelReadiness; quality?: ModelReadiness; diarization?: ModelReadiness; message?: string };
  storage?: { availableBytes: number; dataRoot?: string }; activeJob?: string | null;
  worker?: { running: boolean; message: string | null } | null;
};

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

export type UploadProgress = { loaded: number; total: number | null };
let sessionToken: string | null = null;
async function token(): Promise<string> {
  if (!sessionToken) {
    const response = await fetch('/api/session', { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Cannot initialize the local session. Reload the application.');
    sessionToken = ((await response.json()) as { token: string }).token;
  }
  return sessionToken;
}
async function upload(file: File, options: Options, onProgress?: (value: UploadProgress) => void, retrySession = true): Promise<Job> {
  const localToken = await token();
  const form = new FormData(); form.append('file', file); form.append('options', JSON.stringify(options));
  onProgress?.({ loaded: 0, total: null });
  return new Promise<Job>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/jobs');
    xhr.setRequestHeader('X-LocalScribe-Token', localToken);
    xhr.upload.onprogress = event => onProgress?.({ loaded: event.loaded, total: event.lengthComputable ? event.total : null });
    xhr.onerror = () => reject(new Error('The local upload connection failed. Your file has not been queued. Try again.'));
    xhr.onabort = () => reject(new Error('The upload was stopped before completion.'));
    xhr.onload = () => {
      let body;
      try { body = JSON.parse(xhr.responseText); } catch { reject(new Error('The local upload returned an invalid response.')); return; }
      if (xhr.status >= 200 && xhr.status < 300) { resolve(body as Job); return; }
      const error = body.error || { code: 'upload_failed', message: `Upload failed (${xhr.status}).` };
      if (error.code === 'invalid_session' && retrySession) {
        sessionToken = null;
        upload(file, options, onProgress, false).then(resolve, reject);
      } else reject(new ApiError(error.code, error.message, xhr.status));
    };
    xhr.send(form);
  });
}
async function request<T>(path: string, init: RequestInit = {}, retrySession = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.method && !['GET', 'HEAD'].includes(init.method)) {
    headers.set('X-LocalScribe-Token', await token());
  }
  const response = await fetch(path, { ...init, headers, credentials: 'same-origin' });
  if (!response.ok) {
    let error = { code: 'request_failed', message: `Local request failed (${response.status}).` };
    try { const body = await response.json(); error = body.error || error; } catch { /* Keep a readable fallback for non-JSON failures. */ }
    if (error.code === 'invalid_session' && retrySession) {
      sessionToken = null;
      return request<T>(path, init, false);
    }
    throw new ApiError(error.code, error.message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
const idPath = (id: string) => `/api/jobs/${encodeURIComponent(id)}`;
export const api = {
  health: () => request<Health>('/api/health'),
  jobs: (offset = 0) => request<{ jobs: Job[]; total: number }>(`/api/jobs?limit=50&offset=${offset}`),
  job: (id: string) => request<Job>(idPath(id)),
  transcript: (id: string) => request<Transcript>(`${idPath(id)}/transcript`),
  import: upload,
  action: (id: string, action: 'cancel' | 'retry') => request<Job>(`${idPath(id)}/${action}`, { method: 'POST' }),
  syncLocalFiles: (id: string) => request<Job>(`${idPath(id)}/local-files`, { method: 'POST' }),
  save: (id: string, revision: number, texts: Record<string, string | null>, names: Record<string, string>) => request<Transcript>(`${idPath(id)}/transcript`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision, texts, names }) }),
  previewGrouping: (id: string, expectedRevision: number, segmentIds?: string[]) => request<GroupingPreview>(`${idPath(id)}/grouping/preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expectedRevision, segmentIds }) }),
  applyGrouping: (id: string, expectedRevision: number, segmentIds?: string[]) => request<Transcript>(`${idPath(id)}/grouping/apply`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expectedRevision, segmentIds }) }),
  splitGrouping: (id: string, expectedRevision: number, beforeSegmentId: string) => request<Transcript>(`${idPath(id)}/grouping/split`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expectedRevision, beforeSegmentId }) }),
  history: (id: string) => request<OperationHistory>(`${idPath(id)}/history`),
  moveHistory: (id: string, action: 'undo' | 'redo', expectedRevision: number) => request<Transcript>(`${idPath(id)}/history/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expectedRevision }) }),
  proofreadingReadiness: () => request<{ ready: boolean; model?: string; message?: string; heavyWorkBlocked?: boolean; recovery?: string | null }>('/api/proofreading/readiness'),
  proofreading: (id: string) => request<ProofreadingTask | null>(`${idPath(id)}/proofreading`),
  startProofreading: (id: string, expectedRevision: number, segmentIds?: string[], glossary: string[] = []) => request<ProofreadingTask>(`${idPath(id)}/proofreading`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expectedRevision, segmentIds, glossary }) }),
  cancelProofreading: (id: string, task: string) => request<ProofreadingTask>(`${idPath(id)}/proofreading/${encodeURIComponent(task)}/cancel`, { method: 'POST' }),
  applyProofreading: (id: string, task: string, expectedRevision: number, segmentIds: string[]) => request<Transcript>(`${idPath(id)}/proofreading/${encodeURIComponent(task)}/apply`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expectedRevision, segmentIds }) }),
  rejectProofreading: (id: string, task: string, expectedRevision: number, segmentIds: string[]) => request<ProofreadingTask>(`${idPath(id)}/proofreading/${encodeURIComponent(task)}/reject`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expectedRevision, segmentIds }) }),
  delete: (id: string) => request<void>(idPath(id), { method: 'DELETE' }),
  media: (id: string) => `${idPath(id)}/media`,
  export: (id: string, format: string, source = 'current', layout = 'grouped') => `${idPath(id)}/export?format=${encodeURIComponent(format)}&source=${encodeURIComponent(source)}&layout=${encodeURIComponent(layout)}`,
};
export const activeStatuses = new Set(['queued', 'preparing', 'transcribing', 'diarizing', 'assembling', 'cancelling']);
export const completedStatuses = new Set(['completed', 'completed_with_warnings']);
export function readableStatus(status: string): string {
  return ({ queued: 'Queued', preparing: 'Preparing audio', transcribing: 'Transcribing', diarizing: 'Finding speakers', assembling: 'Assembling transcript', cancelling: 'Cancelling', cancelled: 'Cancelled', deleting: 'Deleting', deletion_failed: 'Deletion needs retry', failed: 'Failed', completed: 'Completed', completed_with_warnings: 'Completed with warnings' } as Record<string, string>)[status] || status;
}
export function timestamp(seconds: number): string {
  const value = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(value / 3600); const m = Math.floor(value % 3600 / 60); const s = value % 60;
  return `${h ? `${h}:` : ''}${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}
/** Timestamp with tenths of a second, used where editors need finer positions. */
export function preciseTimestamp(seconds: number): string {
  const tenths = Math.floor(Math.max(0, seconds || 0) * 10 + 1e-6) % 10;
  return `${timestamp(seconds)}.${tenths}`;
}
export function languageName(code: string | null | undefined): string {
  return code === 'pl' ? 'Polish' : code === 'en' ? 'English' : code === 'auto' ? 'Auto detect' : code || 'Unknown';
}
export function createdDate(job: Job): Date {
  return new Date(typeof job.createdAt === 'number' ? job.createdAt * 1000 : job.createdAt);
}
