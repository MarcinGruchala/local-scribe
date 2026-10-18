import { useCallback, useEffect, useRef, useState } from 'react';
import type { DragEvent, FormEvent, ReactNode } from 'react';
import { api, activeStatuses, completedStatuses, createdDate, languageName, readableStatus, timestamp } from './api';
import type { Health, Job, Options, Transcript, UploadProgress } from './api';
import TranscriptEditor, { InspectorSection } from './TranscriptEditor';
import TranscriptHistory from './TranscriptHistory';
import { IconArrowLeft, IconCheck, IconCopy, IconFile, IconFolder, IconHistory, IconLock, IconPlus, IconRetry, IconTrash, IconUpload, IconWave, IconX } from './icons';

const messageOf = (error: unknown) => error instanceof Error ? error.message : 'The local request failed. Please try again.';
function readRoute(hash = window.location.hash) {
  const params = new URLSearchParams(hash.slice(1));
  return { job: params.get('job'), history: params.get('page') === 'history', fromHistory: params.get('from') === 'history' };
}
const sizeLabel = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)} MB`;
const statusTone = (job: Job) => activeStatuses.has(job.status) ? 'active' : completedStatuses.has(job.status) ? job.warnings?.length ? 'warning' : 'done' : ['failed', 'deletion_failed'].includes(job.status) ? 'failed' : 'idle';
function relativeDate(date: Date) {
  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 60 * 24 && date.getDate() === new Date().getDate()) return `Today, ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  return date.toLocaleDateString([], { day: 'numeric', month: 'short', year: date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
}

function LocalPath({ label, path }: { label: string; path: string }) {
  const input = useRef<HTMLInputElement>(null); const [feedback, setFeedback] = useState('');
  useEffect(() => { setFeedback(''); }, [path]);
  async function copy() {
    try { await navigator.clipboard.writeText(path); setFeedback('Path copied.'); }
    catch { input.current?.focus(); input.current?.select(); setFeedback('Select and copy this path.'); }
  }
  return <div className="local-path">
    <label>{label}<span className="path-field"><IconFolder size={14} /><input ref={input} value={path} title={path} readOnly onFocus={event => event.currentTarget.select()} /></span></label>
    <button className="icon-button bordered" type="button" onClick={copy} aria-label={`Copy ${label.toLowerCase()}`} title="Copy path">{feedback === 'Path copied.' ? <IconCheck size={15} /> : <IconCopy size={15} />}</button>
    {feedback && <span role="status">{feedback}</span>}
  </div>;
}

function ImportForm({ health, onImported }: { health: Health | null; onImported: (job: Job) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [options, setOptions] = useState<Options>({ language: 'auto', profile: 'fast', diarization: true, speakerCount: null });
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const selectedReady = Boolean(health?.models[options.profile]?.ready);
  const diarizationReady = !options.diarization || Boolean(health?.models.diarization?.ready);
  const toolsReady = Boolean(health?.dependencies.ffmpeg && health?.dependencies.ffprobe);
  function rejectFile(message: string) {
    setFile(null); if (input.current) input.current.value = ''; setError(message);
  }
  function choose(next: File | undefined) {
    if (busy) return;
    setError('');
    if (!next) return;
    if (next.size === 0) { rejectFile('This file is empty. Choose an audio or video recording.'); return; }
    if (next.size > 2 * 1024 ** 3) { rejectFile('The file exceeds the 2 GiB import limit.'); return; }
    setFile(next);
  }
  function drop(event: DragEvent) {
    event.preventDefault(); setDragging(false); if (busy) return;
    if (event.dataTransfer.files.length !== 1) { rejectFile('Choose one recording per import.'); return; }
    choose(event.dataTransfer.files[0]);
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!file || busy) return;
    setBusy(true); setError(''); setProgress({ loaded: 0, total: null });
    try { const job = await api.import(file, options, setProgress); setFile(null); if (input.current) input.current.value = ''; onImported(job); }
    catch (error) { setError(messageOf(error)); } finally { setBusy(false); setProgress(null); }
  }
  const percent = progress?.total ? Math.round(progress.loaded / progress.total * 100) : null;
  return <section className="card import-panel" aria-labelledby="import-title">
    <div className="card-heading"><div><h2 id="import-title">Import a recording</h2><p>English or Polish audio and video, up to 2 GiB or 2 hours.</p></div></div>
    <form onSubmit={submit}>
      <div className={`drop-zone${dragging ? ' dragging' : ''}${file ? ' has-file' : ''}`} onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}>
        <span className="upload-icon" aria-hidden="true">{file ? <IconFile size={22} /> : <IconUpload size={22} />}</span>
        <strong>{file ? file.name : 'Drop your recording here'}</strong>
        <span>{file ? sizeLabel(file.size) : 'WAV, MP3, M4A, FLAC, OGG, MP4 or MOV'}</span>
        <button className="button secondary" type="button" onClick={() => input.current?.click()} disabled={busy}>{file ? 'Choose another file' : 'Choose a file'}</button>
        <input ref={input} className="visually-hidden" type="file" aria-label="Choose a recording" accept=".wav,.mp3,.m4a,.flac,.ogg,.mp4,.mov" onChange={event => choose(event.target.files?.[0])} disabled={busy} />
      </div>
      <fieldset disabled={busy} className="option-fields"><legend className="visually-hidden">Transcription options</legend>
        <label>Language<select aria-label="Language" value={options.language} onChange={event => setOptions({ ...options, language: event.target.value as Options['language'] })}><option value="auto">Auto detect</option><option value="en">English</option><option value="pl">Polish</option></select></label>
        <label>Model profile<select aria-label="Model profile" value={options.profile} onChange={event => setOptions({ ...options, profile: event.target.value as Options['profile'] })}><option value="fast">Fast{health?.models.fast?.ready ? '' : ' — setup required'}</option>{health?.models.quality?.ready && <option value="quality">Quality</option>}</select></label>
        <label>Speaker count<select aria-label="Speaker count" value={options.speakerCount ?? ''} disabled={!options.diarization} onChange={event => setOptions({ ...options, speakerCount: event.target.value ? Number(event.target.value) : null })}><option value="">Automatic</option>{Array.from({ length: 10 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}</select></label>
        <label className="switch option-switch"><input type="checkbox" checked={options.diarization} onChange={event => setOptions({ ...options, diarization: event.target.checked, speakerCount: event.target.checked ? options.speakerCount : null })} /><span>Identify speaker turns<small>Anonymous labels within this recording</small></span></label>
      </fieldset>
      {busy && progress && <div className="upload-progress" role="status"><label htmlFor="upload-progress">{progress.total && progress.loaded === progress.total ? 'Upload complete. Validating recording…' : progress.total ? `Uploading ${percent}%` : 'Uploading recording…'}</label><progress id="upload-progress" max={progress.total || 1} value={progress.total ? progress.loaded : undefined} /></div>}
      {error && <p role="alert" className="notice error">{error}</p>}
      {!busy && health && (!selectedReady || !diarizationReady || !toolsReady) && <p className="notice warning">{!toolsReady ? 'Install FFmpeg and FFprobe before importing.' : !selectedReady ? 'Set up the selected local transcription model before importing.' : 'Speaker model setup is required. You can turn off speaker turns to transcribe without them.'}</p>}
      <div className="form-footer"><p><IconLock size={13} />Original files stay on this Mac until you delete their job.</p><button className="button primary large" type="submit" disabled={!file || busy || !selectedReady || !diarizationReady || !toolsReady}>{busy ? 'Importing and validating…' : 'Transcribe recording'}</button></div>
    </form>
  </section>;
}

function Readiness({ health, error, onRefresh }: { health: Health | null; error: string; onRefresh: () => void }) {
  const items = health ? [
    ['FFmpeg and FFprobe', Boolean(health.dependencies.ffmpeg && health.dependencies.ffprobe)],
    ['Fast transcription', Boolean(health.models.fast?.ready)],
    ['Speaker turns', Boolean(health.models.diarization?.ready)],
  ] as const : [];
  return <section className="card readiness" aria-label="Local readiness">
    <div className="readiness-head">
      <strong><span className={`status-dot ${health ? health.ready ? 'ready' : 'missing' : ''}`} />{health ? health.ready ? 'Local engine ready' : 'Setup needed' : 'Checking local engine…'}</strong>
      <button type="button" className="button ghost small" onClick={onRefresh}><IconRetry size={13} />Refresh</button>
    </div>
    <p className="muted">{health?.storage ? `${(health.storage.availableBytes / 1024 ** 3).toFixed(1)} GB available on this Mac` : 'Everything runs on this Mac'}</p>
    <ul className="readiness-items">{items.map(([label, ready]) => <li key={label} className={ready ? 'check-good' : 'check-missing'}>{ready ? <IconCheck size={14} /> : <IconX size={14} />}{label}</li>)}</ul>
    {health?.storage?.dataRoot && <LocalPath label="Recordings and transcripts folder" path={health.storage.dataRoot} />}
    {error && <p role="alert" className="notice error">{error}</p>}
    {health && !health.ready && <p className="readiness-help">{health.worker?.running === false ? health.worker.message || 'Local worker stopped. Restart the application to recover interrupted work.' : <>Run the explicit model setup and <code>make doctor</code> from the repository. Runtime never downloads models.</>}</p>}
  </section>;
}

function LocalTranscriptFiles({ job, onUpdated }: { job: Job; onUpdated: (job: Job) => void }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const files = job.localFiles;
  if (!files || !completedStatuses.has(job.status)) return null;
  async function retry() {
    setBusy(true); setError('');
    try {
      const value = await api.syncLocalFiles(job.id); onUpdated(value);
      if (value.localFiles?.status !== 'ready') setError(value.localFiles?.message || 'Local transcript files could not be updated. Try again or use the export buttons.');
    } catch (error) { setError(messageOf(error)); } finally { setBusy(false); }
  }
  return <InspectorSection title="Local transcript files" className="local-files">
      {files.status === 'ready' ? <p className="inspector-hint">TXT, SRT, VTT and JSON are saved here automatically. Saving edits updates these files.</p> : <p className="notice warning" role="status">{files.message || (files.status === 'pending' ? 'Updating the local transcript files…' : 'Local transcript files are unavailable. You can still use the export buttons.')}</p>}
      <LocalPath label="Transcript folder" path={files.directory} />
      {files.status === 'ready' && <div className="local-file-names">{files.files.map(file => <span key={file}>{file.split(/[\\/]/).pop()}</span>)}</div>}
      {files.status !== 'ready' && <><p className="local-files-fallback inspector-hint">Your saved transcript remains available through the export buttons.</p><button className="button secondary" disabled={busy} onClick={retry}>{busy ? 'Updating local files…' : 'Retry local files'}</button></>}
      {error && <p role="alert" className="notice error">{error}</p>}
  </InspectorSection>;
}

function Modal({ title, id, tone, children, actions, onClose }: { title: string; id: string; tone?: 'danger'; children: ReactNode; actions: ReactNode; onClose: () => void }) {
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close);
  }, [onClose]);
  return <div className="modal-backdrop" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className={`modal confirmation${tone ? ` ${tone}` : ''}`} role="alertdialog" aria-modal="true" aria-labelledby={id}>
      <h3 id={id}>{title}</h3>{children}<div className="modal-actions">{actions}</div>
    </div>
  </div>;
}

function ProcessingCard({ job, busy, onCancel }: { job: Job; busy: boolean; onCancel: () => void }) {
  const stages = ['preparing', 'transcribing', ...(job.options.diarization ? ['diarizing'] : []), 'assembling'];
  const current = stages.indexOf(job.status);
  return <div className="processing">
    <div className="processing-head">
      <span className="spinner" aria-hidden="true" />
      <div><strong>{readableStatus(job.status)}</strong><p>{job.status === 'queued' ? 'Waiting for the local worker. One recording is processed at a time.' : job.status === 'cancelling' ? 'Stopping the active process…' : `Elapsed ${timestamp(job.elapsedSeconds || 0)}. You can refresh or return later.`}</p></div>
      {job.status !== 'cancelling' && <button className="button secondary" disabled={busy} onClick={onCancel}>Cancel job</button>}
    </div>
    <ol className="stage-steps" aria-hidden="true">{stages.map((stage, index) => <li key={stage} className={index < current ? 'done' : index === current ? 'current' : ''}><span />{readableStatus(stage)}</li>)}</ol>
  </div>;
}

function JobDetail({ id, onChange, onDeleted, onDirtyChange }: { id: string; onChange: () => void; onDeleted: () => void; onDirtyChange: (dirty: boolean) => void }) {
  const [job, setJob] = useState<Job | null>(null); const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [deleting, setDeleting] = useState(false); const [confirmRetry, setConfirmRetry] = useState(false);
  const terminalLoaded = useRef(false); const [reload, setReload] = useState(0);
  useEffect(() => {
    let disposed = false; let timer: ReturnType<typeof setTimeout> | undefined;
    setJob(null); setTranscript(null); setError(''); terminalLoaded.current = false;
    async function load() {
      try {
        const value = await api.job(id); if (disposed) return; setJob(value);
        if (completedStatuses.has(value.status) && !terminalLoaded.current) {
          const result = await api.transcript(id); if (disposed) return; setTranscript(result); terminalLoaded.current = true; onChange();
        }
        if (activeStatuses.has(value.status) || (completedStatuses.has(value.status) && value.localFiles?.status === 'pending')) timer = setTimeout(load, 1000); else onChange();
      } catch (error) { if (!disposed) setError(messageOf(error)); }
    }
    void load(); return () => { disposed = true; if (timer) clearTimeout(timer); };
  }, [id, onChange, reload]);
  const closeRetry = useCallback(() => setConfirmRetry(false), []);
  const closeDelete = useCallback(() => setDeleting(false), []);
  async function action(kind: 'cancel' | 'retry') {
    setBusy(true); setError(''); setConfirmRetry(false);
    try {
      const value = await api.action(id, kind); setJob(value); onChange();
      if (activeStatuses.has(value.status)) setReload(current => current + 1);
    } catch (error) { setError(messageOf(error)); } finally { setBusy(false); }
  }
  async function remove() {
    setBusy(true); setError('');
    try { await api.delete(id); onDirtyChange(false); onDeleted(); } catch (error) { setError(messageOf(error)); setBusy(false); setDeleting(false); setTranscript(null); api.job(id).then(setJob).catch(() => { /* Keep the deletion failure visible if status cannot be refreshed. */ }); }
  }
  function saved(value: Transcript) {
    setTranscript(value); onChange();
    api.job(id).then(setJob).catch(error => setError(messageOf(error)));
  }
  if (!job) return <section className="detail-panel simple" aria-labelledby="detail-title">
    <header className="studio-header"><div className="studio-title"><h2 id="detail-title">Recording</h2></div></header>
    <div className="detail-content">{error ? <><p className="notice error">{error}</p><button className="button secondary" onClick={() => setReload(current => current + 1)}>Try again</button></> : <div className="loading-block"><span className="spinner" aria-hidden="true" />Loading recording…</div>}</div>
  </section>;

  const heading = <>
    <a href="#page=history" className="history-back" aria-label="Back to transcript history" title="Back to transcript history"><IconArrowLeft size={16} /></a>
    <div className="title-block">
      <div className="title-row"><h2 id="detail-title" title={job.name}>{job.name}</h2><span className={`status-badge ${job.status}${job.warnings?.length ? ' with-warnings' : ''}`}>{job.status === 'completed' && job.warnings?.length ? 'Completed with warnings' : readableStatus(job.status)}</span></div>
      <div className="job-meta"><span>{job.options.language === 'auto' ? 'Auto language' : languageName(job.options.language)}</span><span>{job.options.profile === 'quality' ? 'Quality' : 'Fast'} model</span><span>{job.options.diarization ? 'Speaker turns enabled' : 'Text only'}</span>{job.duration != null && <span>{timestamp(job.duration)} recording</span>}<span>Attempt {job.attempt}</span></div>
    </div>
  </>;
  const notices = <>
    {job.error && <p role="alert" className="notice error"><strong>{job.error.code === 'interrupted' ? 'Processing was interrupted. ' : ''}</strong>{job.error.message}</p>}
    {[...(job.warnings || []), ...(transcript?.warnings || [])].filter((warning, index, warnings) => warnings.findIndex(other => other.code === warning.code && other.message === warning.message) === index).map(warning => <p key={warning.code} className="notice warning">{warning.message}</p>)}
    {error && <p role="alert" className="notice error">{error}</p>}
  </>;
  const actions = !activeStatuses.has(job.status) && <div className="job-actions">
    {['failed', 'cancelled'].includes(job.status) && <button className="button secondary" disabled={busy} onClick={() => setConfirmRetry(true)}><IconRetry size={14} />Retry job</button>}
    <button className="button danger-ghost" disabled={busy} onClick={() => setDeleting(true)}><IconTrash size={14} />{['deleting', 'deletion_failed'].includes(job.status) ? 'Retry deletion' : 'Delete recording'}</button>
  </div>;
  const dialogs = <>
    {confirmRetry && <Modal id="retry-title" title="Retry this recording?" onClose={closeRetry} actions={<><button className="button secondary" onClick={closeRetry} autoFocus>Keep current result</button><button className="button primary" disabled={busy} onClick={() => action('retry')}>Retry recording</button></>}><p>A new attempt uses the same model settings. A successful replacement discards any previous text and speaker-name edits.</p></Modal>}
    {deleting && <Modal id="delete-title" tone="danger" title="Delete this recording permanently?" onClose={closeDelete} actions={<><button className="button secondary" onClick={closeDelete} disabled={busy} autoFocus>Keep recording</button><button className="button destructive" onClick={remove} disabled={busy}>{busy ? 'Deleting…' : 'Delete permanently'}</button></>}><p>This permanently deletes “<strong>{job.name}</strong>”, including its original media, playback audio, transcript, edits and all attempts from the active LocalScribe data folder. Shared models remain available.</p></Modal>}
  </>;

  if (transcript) return <section className="detail-panel" aria-labelledby="detail-title">
    <TranscriptEditor key={id} job={job} transcript={transcript} heading={heading} notices={notices} onSaved={saved} onDirtyChange={onDirtyChange}
      inspectorExtras={<>
        <LocalTranscriptFiles job={job} onUpdated={value => { setJob(value); onChange(); }} />
        {actions && <div className="inspector-section danger-zone">{actions}</div>}
      </>} />
    {dialogs}
  </section>;
  return <section className="detail-panel simple" aria-labelledby="detail-title">
    <header className="studio-header"><div className="studio-title">{heading}</div></header>
    <div className="detail-content">
      {notices}
      {activeStatuses.has(job.status) && <ProcessingCard job={job} busy={busy} onCancel={() => action('cancel')} />}
      {completedStatuses.has(job.status) && !error && <div className="loading-block"><span className="spinner" aria-hidden="true" />Loading transcript…</div>}
      <LocalTranscriptFiles job={job} onUpdated={value => { setJob(value); onChange(); }} />
      {actions}
    </div>
    {dialogs}
  </section>;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null); const [healthError, setHealthError] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]); const [total, setTotal] = useState(0); const [listError, setListError] = useState(''); const [route, setRoute] = useState(readRoute);
  const selected = route.job;
  const dirtyDraft = useRef(false); const acceptedHash = useRef(window.location.hash); const historyPages = useRef(1);
  const onDirtyChange = useCallback((dirty: boolean) => { dirtyDraft.current = dirty; }, []);
  const refreshHealth = useCallback(() => { setHealthError(''); api.health().then(setHealth).catch(error => setHealthError(messageOf(error))); }, []);
  const refreshJobs = useCallback(() => {
    const pageCount = historyPages.current;
    Promise.all(Array.from({ length: pageCount }, (_, page) => api.jobs(page * 50))).then(results => {
      if (pageCount !== historyPages.current) return;
      setJobs(Array.from(new Map<string, Job>(results.flatMap(result => result.jobs).map(job => [job.id, job])).values()));
      setTotal(results[0].total); setListError('');
    }).catch(error => setListError(messageOf(error)));
  }, []);
  useEffect(() => { refreshHealth(); refreshJobs(); const handler = () => {
      const nextHash = window.location.hash;
      if (nextHash === acceptedHash.current) return;
      const nextRoute = readRoute(nextHash); const previousRoute = readRoute(acceptedHash.current);
      const leavingRecording = nextRoute.job !== previousRoute.job;
      if (leavingRecording && dirtyDraft.current && !window.confirm('Discard unsaved transcript changes? Your last saved version will be kept.')) {
        window.history.replaceState(null, '', window.location.pathname + window.location.search + acceptedHash.current);
        return;
      }
      if (leavingRecording) dirtyDraft.current = false;
      acceptedHash.current = nextHash; setRoute(nextRoute);
      if (leavingRecording || nextRoute.history !== previousRoute.history) window.scrollTo(0, 0);
    }; window.addEventListener('hashchange', handler); return () => window.removeEventListener('hashchange', handler); }, [refreshHealth, refreshJobs]);
  useEffect(() => { if (!jobs.some(job => activeStatuses.has(job.status))) return; const timer = setInterval(refreshJobs, 1000); return () => clearInterval(timer); }, [jobs, refreshJobs]);
  const select = (id: string, fromHistory = route.fromHistory) => {
    const params = new URLSearchParams({ job: id });
    if (fromHistory) params.set('from', 'history');
    window.location.hash = params.toString();
  };
  const home = !selected && !route.history;
  return <div className={`app-shell${selected ? ' detail-route' : ''}`}>
    <aside className="sidebar">
      <a href="#" className="brand" aria-label="LocalScribe home"><span className="brand-symbol" aria-hidden="true"><IconWave size={18} /></span><span>LocalScribe</span></a>
      <nav className="app-navigation" aria-label="Main navigation">
        <a href="#" className="nav-item new-recording" aria-current={home ? 'page' : undefined}><IconPlus size={16} />New recording</a>
        <a href="#page=history" className="nav-item" aria-current={route.history || route.fromHistory ? 'page' : undefined}><IconHistory size={16} />Transcript history</a>
      </nav>
      <section className="recordings" aria-labelledby="recordings-title">
        <div className="sidebar-heading"><h2 id="recordings-title">Recordings</h2><span className="count">{total}</span></div>
        {listError && <p role="alert" className="notice error">{listError}</p>}
        {jobs.length === 0 ? <p className="empty">Your recordings will appear here after import.</p> : <ul className="job-list">{jobs.map(job => <li key={job.id}><button className={selected === job.id ? 'selected' : ''} aria-current={selected === job.id ? 'true' : undefined} onClick={() => select(job.id)}>
          <span className={`job-dot ${statusTone(job)}`} aria-hidden="true" />
          <strong>{job.name}</strong>
          <span>{readableStatus(job.status)}{job.warnings?.length && job.status === 'completed' ? ' with warnings' : ''}</span>
          <small>{relativeDate(createdDate(job))}</small>
        </button></li>)}</ul>}
        {total > jobs.length && <button className="text-button load-more" onClick={() => { historyPages.current += 1; refreshJobs(); }}>Load older recordings</button>}
      </section>
      <p className="privacy-note"><IconLock size={13} />Private on this Mac<span className={`status-dot ${health ? health.ready ? 'ready' : 'missing' : ''}`} title={health ? health.ready ? 'Local engine ready' : 'Setup needed' : 'Checking local engine'} /></p>
    </aside>
    <main className="main-panel">
      {selected ? <JobDetail key={selected} id={selected} onDirtyChange={onDirtyChange} onChange={refreshJobs} onDeleted={() => { window.location.hash = route.fromHistory ? 'page=history' : ''; refreshJobs(); }} />
        : route.history ? <div className="page"><TranscriptHistory onReview={id => select(id, true)} /></div>
          : <div className="page">
            <div className="page-intro"><span className="eyebrow">Offline transcription · English &amp; Polish</span><h1>Make every conversation readable.</h1><p>Transcribe recordings on this Mac, follow the speakers, and make the words your own.</p></div>
            <div className="home-grid"><ImportForm health={health} onImported={job => { refreshJobs(); select(job.id); }} /><Readiness health={health} error={healthError} onRefresh={refreshHealth} /></div>
            <footer>Runs locally. No cloud inference. No external assets. <span>LocalScribe MVP</span></footer>
          </div>}
    </main>
  </div>;
}
