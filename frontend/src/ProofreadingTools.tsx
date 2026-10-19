import { memo, useEffect, useMemo, useRef, useState } from 'react';
import { api, preciseTimestamp, timestamp } from './api';
import type { ProofreadingTask, Transcript } from './api';

export type ReviewSummary = { corrections: number; listening: number; status: string; stale: boolean };
type Props = {
  transcript: Transcript; dirty: boolean; saving: boolean; visible: boolean;
  onBusy: (value: boolean) => void; onSaved: (value: Transcript) => void;
  onSummary: (value: ReviewSummary) => void; onLocate: (id: string, listen: boolean) => void;
};
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'The local proofreading request failed. Try again.';
const active = new Set(['queued', 'running', 'cancelling']);
const plural = (count: number, singular: string, multiple = `${singular}s`) => `${count} ${count === 1 ? singular : multiple}`;

export default memo(function ProofreadingTools({ transcript, dirty, saving, visible, onBusy, onSaved, onSummary, onLocate }: Props) {
  const [task, setTask] = useState<ProofreadingTask | null>(null);
  const [error, setError] = useState('');
  const [scope, setScope] = useState('entire');
  const [blockIndex, setBlockIndex] = useState(0);
  const [glossary, setGlossary] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(true);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [readiness, setReadiness] = useState<{ ready: boolean; message?: string; model?: string; heavyWorkBlocked?: boolean; recovery?: string | null } | null>(null);
  const [retry, setRetry] = useState(0);
  const [focused, setFocused] = useState<string | null>(null);
  const cards = useRef<HTMLOListElement>(null);
  const jobId = transcript.jobId;
  useEffect(() => {
    let disposed = false;
    setTask(null); setSelected(new Set()); setError(''); setReadiness(null); setFocused(null);
    let timer: ReturnType<typeof setTimeout>;
    let firstPoll = true;
    async function poll() {
      try {
        const value = await api.proofreading(jobId);
        if (disposed) return;
        setTask(value); setError('');
        if (firstPoll) {
          setGlossary(value?.glossary.join(', ') ?? '');
          setSettingsOpen(!value || !['ready', 'running', 'queued', 'cancelling'].includes(value.status));
          firstPoll = false;
        }
        if (value && active.has(value.status)) timer = setTimeout(poll, 800);
      } catch (error) {
        if (!disposed) { setError(messageOf(error)); timer = setTimeout(poll, 2500); }
      }
    }
    void poll();
    api.proofreadingReadiness().then(value => { if (!disposed) setReadiness(value); }).catch(error => { if (!disposed) setError(messageOf(error)); });
    return () => { disposed = true; clearTimeout(timer); };
  }, [jobId, retry]);
  const blocks = transcript.grouping?.blocks ?? transcript.segments.map(s => ({ ...s, segmentIds: [s.id] }));
  const selectedBlock = blocks[blockIndex];
  useEffect(() => { setBlockIndex(0); }, [jobId, transcript.revision]);
  const busy = !!task && active.has(task.status);
  const stale = !!task && (task.status === 'stale' || (task.status === 'ready' && (task.stale || task.revision !== transcript.revision)));
  const reviewable = task?.status === 'ready' && !stale;
  const disabled = dirty || saving;
  const sourceById = useMemo(() => {
    const speakers = new Map(transcript.speakers.map(speaker => [speaker.id, speaker.displayName]));
    return new Map(transcript.segments.map((source, index) => [source.id, { source, index, speaker: speakers.get(source.speakerId ?? '') ?? 'Speaker unavailable' }]));
  }, [transcript.segments, transcript.speakers]);
  const suggestions = useMemo(() => reviewable ? [...task.suggestions].sort((a, b) => (sourceById.get(a.id)?.index ?? 0) - (sourceById.get(b.id)?.index ?? 0)) : [], [reviewable, task?.suggestions, sourceById]);
  const corrections = suggestions.filter(s => !s.uncertain);
  const listening = suggestions.filter(s => s.uncertain);
  useEffect(() => { onSummary({ corrections: corrections.length, listening: listening.length, status: task?.status ?? '', stale }); }, [corrections.length, listening.length, task?.status, stale, onSummary]);
  const filtered = suggestions.filter(s => (filter === 'all' || (filter === 'listening') === s.uncertain) && `${s.old} ${s.new}`.toLocaleLowerCase().includes(query.toLocaleLowerCase().trim()));
  const focusedIndex = Math.max(0, filtered.findIndex(s => s.id === focused));
  const current = filtered[focusedIndex];
  useEffect(() => {
    if (visible && focused) cards.current?.querySelector<HTMLElement>(`[data-suggestion="${CSS.escape(focused)}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [focused, visible]);
  async function start() {
    if (scope === 'block' && !selectedBlock) { setError('Select an available saved block.'); return; }
    onBusy(true); setError('');
    try {
      await api.startProofreading(jobId, transcript.revision, scope === 'block' ? selectedBlock.segmentIds : undefined, glossary.split(/[,\n]/).map(s => s.trim()).filter(Boolean));
      setSelected(new Set()); setFilter('all'); setQuery(''); setRetry(value => value + 1);
    } catch (error) { setError(messageOf(error)); }
    finally { onBusy(false); }
  }
  async function decide(action: 'apply' | 'reject', ids: string[]) {
    if (!task) return;
    onBusy(true); setError('');
    try {
      if (action === 'apply') { onSaved(await api.applyProofreading(jobId, task.id, task.revision, ids)); setRetry(value => value + 1); }
      else setTask(await api.rejectProofreading(jobId, task.id, task.revision, ids));
      setSelected(new Set());
    } catch (error) { setError(messageOf(error)); }
    finally { onBusy(false); }
  }
  async function cancel() {
    if (!task) return;
    try { setTask(await api.cancelProofreading(jobId, task.id)); } catch (error) { setError(messageOf(error)); }
  }
  return <section className="proofreading-tools" aria-label="AI proofreading" hidden={!visible}>
    <header className="review-heading"><div><h3>Review AI suggestions</h3><p>Compare the saved text, listen to the recording, then choose what to keep.</p></div><button type="button" className="button secondary" disabled={saving || busy} onClick={() => setSettingsOpen(value => !value)}>{settingsOpen ? 'Hide preview settings' : 'New preview'}</button></header>
    {dirty && <p className="notice warning" role="status">Save or discard manual edits before proofreading or accepting suggestions.</p>}
    {readiness && !readiness.ready && <p className="notice warning" role="status">{readiness.message}</p>}
    {readiness?.heavyWorkBlocked && <p className="notice warning" role="status">{readiness.recovery}</p>}
    {error && <p className="notice error" role="alert">{error} Saved text and manual drafts remain available.</p>}
    <div className="review-scroll">
      <div className="review-setup" hidden={!settingsOpen}>
        <div className="review-setup-fields"><label>Proofreading scope<select aria-label="Proofreading scope" value={scope} disabled={saving || busy} onChange={event => setScope(event.target.value)}><option value="entire">Entire recording</option><option value="block">Saved block</option></select></label>
        {scope === 'block' && <label>Source block<select aria-label="Proofreading block" value={blockIndex} disabled={saving || busy} onChange={event => setBlockIndex(Number(event.target.value))}>{blocks.map((block, index) => <option key={block.id} value={index}>{index + 1} · {timestamp(block.start)} · {block.segmentIds.length} segments</option>)}</select></label>}
        <label className="review-glossary">Protected spellings (optional)<textarea aria-label="Proofreading glossary" value={glossary} maxLength={700} disabled={saving || busy} placeholder="Names or terms, separated by commas" onChange={event => setGlossary(event.target.value)} /></label></div>
        <div className="review-setup-actions"><button className="button primary" type="button" disabled={disabled || busy || !transcript.segments.length || !readiness?.ready || readiness.heavyWorkBlocked || (scope === 'block' && !selectedBlock)} onClick={start}>Preview AI corrections</button><span className="inspector-hint">Spelling, punctuation and capitalization only. Saved text stays unchanged until you accept.</span></div>
      </div>
      {busy && <div className="review-progress" role="status"><strong>{task.status === 'cancelling' ? 'Stopping safely…' : task.status === 'queued' ? 'Waiting for the local worker…' : 'Reviewing your transcript…'}</strong><p>{task.progress} chunks completed. You can keep reading the transcript while this runs.</p><button className="button secondary" type="button" disabled={task.status === 'cancelling'} onClick={cancel}>Cancel proofreading</button>{task.status === 'cancelling' && <p>Waiting for the current model response to finish safely. No corrections will be published.</p>}</div>}
      {task && !busy && <>
        <p className={`review-status${stale ? ' notice warning' : ''}`} role="status">{stale ? 'Suggestions are stale. Start a new preview for the saved revision.' : task.status === 'applied' ? 'Accepted corrections saved as one history operation.' : task.status === 'ready' ? `${plural(task.suggestions.length, 'suggestion')}. Pending suggestions are excluded from exports.` : `Proofreading ${task.status}.`}</p>
        {task.error && <p className="notice warning" role="alert">{task.error}</p>}
      </>}
      {reviewable && <>
        <div className="review-counts"><strong>{plural(corrections.length, 'correction')}</strong><strong className="listening-count">{plural(listening.length, 'passage', 'passages')} to listen to</strong></div>
        <div className="review-filters" role="group" aria-label="Filter suggestions">{[['all', `All (${suggestions.length})`], ['corrections', `Corrections (${corrections.length})`], ['listening', `Needs listening (${listening.length})`]].map(([value, label]) => <button type="button" key={value} className={`review-filter${filter === value ? ' active' : ''}`} aria-pressed={filter === value} onClick={() => { setFilter(value); setFocused(null); }}>{label}</button>)}<input type="search" aria-label="Search suggestions" placeholder="Find a word in suggestions" value={query} onChange={event => { setQuery(event.target.value); setFocused(null); }} /></div>
        {filtered.length > 0 && <div className="review-navigation"><span>{focusedIndex + 1} of {filtered.length} shown</span><button type="button" className="button secondary" disabled={focusedIndex === 0} onClick={() => setFocused(filtered[focusedIndex - 1].id)}>Previous suggestion</button><button type="button" className="button secondary" disabled={focusedIndex === filtered.length - 1} onClick={() => setFocused(filtered[focusedIndex + 1].id)}>Next suggestion</button><button type="button" className="text-button" onClick={() => current && onLocate(current.id, false)}>Show current in transcript</button></div>}
        {!suggestions.length && <div className="review-empty"><h4>No suggestions to review</h4><p>The local model did not propose changes within the conservative proofreading scope. This does not mean the transcript has no recognition errors.</p></div>}
        {suggestions.length > 0 && !filtered.length && <p className="review-empty">No suggestions match this filter. Try All or another search.</p>}
        <ol className="proofreading-suggestions" ref={cards}>{visible && filtered.map(suggestion => {
          const entry = sourceById.get(suggestion.id);
          const index = entry?.index ?? -1;
          const source = entry?.source;
          const speaker = entry?.speaker ?? 'Speaker unavailable';
          const previous = transcript.segments[index - 1];
          return <li key={suggestion.id} data-suggestion={suggestion.id} className={`suggestion-card${suggestion.uncertain ? ' uncertain' : ''}${current?.id === suggestion.id ? ' current' : ''}`} onFocus={() => setFocused(suggestion.id)}>
            <header className="suggestion-card-header"><span className={`suggestion-kind${suggestion.uncertain ? ' listening' : ''}`}>{suggestion.uncertain ? 'Listen before editing' : 'Suggested correction'}</span><span className="suggestion-speaker">{speaker}</span>{source && <button type="button" className="suggestion-time" onClick={() => onLocate(suggestion.id, true)} aria-label={`Listen from ${timestamp(source.start)}`}>▶ {preciseTimestamp(source.start)}–{preciseTimestamp(source.end)}</button>}</header>
            {previous && <p className="suggestion-context"><span>Before this passage</span>{previous.editedText ?? previous.text}</p>}
            <div className={`suggestion-comparison${suggestion.uncertain ? ' single' : ''}`}><div><h4>Saved text</h4><p>{suggestion.old}</p></div>{!suggestion.uncertain && <div><h4>Suggested text</h4><p className="correction-diff">{suggestion.diff.map((part, i) => <span key={i}>{part.kind === 'equal' ? part.old : <><del>{part.old}</del><ins>{part.new}</ins></>}</span>)}</p></div>}</div>
            {suggestion.uncertain && <p className="listening-explanation">No replacement will be applied. Listen to this passage, then edit the transcript if needed.{suggestion.reason && ` ${suggestion.reason}`}</p>}
            <div className="suggestion-card-actions"><button className="button secondary" type="button" onClick={() => onLocate(suggestion.id, false)}>Show in transcript</button>{!suggestion.uncertain && <><label className="suggestion-select"><input type="checkbox" aria-label={`Select correction ${suggestion.id}`} checked={selected.has(suggestion.id)} disabled={disabled} onChange={event => setSelected(previous => { const next = new Set(previous); if (event.target.checked) next.add(suggestion.id); else next.delete(suggestion.id); return next; })} />Include in accepted batch</label><button className="button secondary" type="button" disabled={disabled} onClick={() => decide('apply', [suggestion.id])}>Accept correction</button></>}<button className="text-button" type="button" disabled={disabled} onClick={() => decide('reject', [suggestion.id])}>Reject suggestion</button></div>
          </li>;
        })}</ol>
      </>}
      <details className="review-model"><summary>Local model &amp; refresh</summary><p>{readiness?.ready ? `Loaded model: ${readiness.model}` : 'Local model is not ready.'}</p><button className="text-button" type="button" disabled={saving} onClick={() => setRetry(value => value + 1)}>Refresh model &amp; suggestions</button></details>
    </div>
    {reviewable && suggestions.length > 0 && <footer className="review-batch"><div><strong>{corrections.length ? `${selected.size} selected` : 'Listening review'}</strong><p>{corrections.length ? 'One accepted batch is one Undo. Remaining suggestions become stale after saving.' : 'No automatic replacements are proposed. Listen and edit the source if needed.'}</p></div><div className="review-batch-buttons">{corrections.length > 0 && <><button className="text-button" type="button" disabled={disabled} onClick={() => setSelected(new Set(corrections.map(s => s.id)))}>Select all corrections</button><button className="text-button" type="button" disabled={disabled || !selected.size} onClick={() => setSelected(new Set())}>Clear selection</button><button className="button primary" type="button" disabled={disabled || !selected.size} onClick={() => decide('apply', [...selected])}>Accept selected corrections</button><button className="button secondary" type="button" disabled={disabled || !selected.size} onClick={() => decide('reject', [...selected])}>Reject selected suggestions</button></>}<button className="text-button" type="button" disabled={disabled} onClick={() => decide('reject', suggestions.map(s => s.id))}>Reject all suggestions</button></div></footer>}
  </section>;
});
