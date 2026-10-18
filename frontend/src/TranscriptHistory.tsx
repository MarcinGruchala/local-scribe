import { useEffect, useState } from 'react';
import { api, completedStatuses, timestamp } from './api';
import type { Job } from './api';

export default function TranscriptHistory({ onReview }: { onReview: (id: string) => void }) {
  const [jobs, setJobs] = useState<Job[]>([]); const [loading, setLoading] = useState(true);
  const [error, setError] = useState(''); const [reload, setReload] = useState(0);
  const [query, setQuery] = useState(''); const [language, setLanguage] = useState('all');
  useEffect(() => {
    let disposed = false;
    setLoading(true); setError(''); setJobs([]);
    async function load() {
      const collected = new Map<string, Job>(); let offset = 0;
      try {
        // Load every metadata page so older transcripts are searchable too.
        while (!disposed) {
          const page = await api.jobs(offset);
          if (disposed) return;
          page.jobs.filter(job => completedStatuses.has(job.status)).forEach(job => collected.set(job.id, job));
          setJobs([...collected.values()]);
          offset += page.jobs.length;
          if (offset >= page.total || page.jobs.length === 0) break;
        }
      } catch (error) {
        if (!disposed) setError(error instanceof Error ? error.message : 'Transcript history could not be loaded. Try again.');
      } finally { if (!disposed) setLoading(false); }
    }
    void load(); return () => { disposed = true; };
  }, [reload]);
  const needle = query.trim().toLocaleLowerCase();
  const filtered = jobs.filter(job => job.name.toLocaleLowerCase().includes(needle) && (language === 'all' || job.options.language === language));
  return <section className="panel transcript-history" aria-labelledby="history-title">
    <div className="section-heading"><div><span className="eyebrow">SAVED TRANSCRIPTS</span><h2 id="history-title">Transcript history</h2></div><button className="button secondary" disabled={loading} onClick={() => setReload(value => value + 1)}>Refresh history</button></div>
    <p className="history-description">Revisit completed recordings. Listen alongside the saved transcript, edit words, and rename speakers.</p>
    <div className="history-filters"><label>Search recordings<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by file name…" /></label><label>Transcription language<select aria-label="Filter by transcription language" value={language} onChange={event => setLanguage(event.target.value)}><option value="all">All languages</option><option value="pl">Polish</option><option value="en">English</option><option value="auto">Auto detect</option></select></label></div>
    {loading && <p role="status" className="history-summary">Loading transcript history… {jobs.length} saved recordings found.</p>}
    {error && <p role="alert" className="notice error">{error} The list may be incomplete. Refresh history to try again.</p>}
    {!loading && !error && <p className="history-summary" role="status">{filtered.length} of {jobs.length} saved recordings · newest first</p>}
    {filtered.length > 0 ? <ul className="history-recordings">{filtered.map(job => <li key={job.id}>
      <div className="history-recording-info"><h3>{job.name}</h3><div className="history-recording-meta"><time dateTime={new Date(typeof job.createdAt === 'number' ? job.createdAt * 1000 : job.createdAt).toISOString()}>{new Date(typeof job.createdAt === 'number' ? job.createdAt * 1000 : job.createdAt).toLocaleString()}</time>{job.duration != null && <span>{timestamp(job.duration)}</span>}<span>{job.options.language === 'pl' ? 'Polish' : job.options.language === 'en' ? 'English' : 'Auto language'}</span><span>{job.options.diarization ? 'Speaker turns' : 'Text only'}</span></div>{(job.status === 'completed_with_warnings' || job.warnings?.length > 0) && <span className="tag warning-tag">Review warnings</span>}</div>
      <button className="button primary" onClick={() => onReview(job.id)} aria-label={`Listen & review ${job.name}`}>Listen &amp; review <span aria-hidden="true">→</span></button>
    </li>)}</ul> : !loading && !error && <div className="history-empty"><h3>{jobs.length ? 'No matching recordings' : 'No saved transcripts yet'}</h3><p>{jobs.length ? 'Try a different file name or language filter.' : 'Completed recordings will appear here automatically.'}</p>{jobs.length ? <button className="button secondary" onClick={() => { setQuery(''); setLanguage('all'); }}>Clear filters</button> : <a className="button primary" href="#">Import a recording</a>}</div>}
  </section>;
}
