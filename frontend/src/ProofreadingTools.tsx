import { useEffect, useState } from 'react';
import { api, timestamp } from './api';
import type { ProofreadingTask, Transcript } from './api';

type Props = { transcript: Transcript; dirty: boolean; saving: boolean; onBusy: (value: boolean) => void; onSaved: (value: Transcript) => void };
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'The local proofreading request failed. Try again.';
const active = new Set(['queued', 'running', 'cancelling']);

export default function ProofreadingTools({ transcript, dirty, saving, onBusy, onSaved }: Props) {
  const [task, setTask] = useState<ProofreadingTask | null>(null);
  const [error, setError] = useState('');
  const [scope, setScope] = useState('entire');
  const [blockIndex, setBlockIndex] = useState(0);
  const [glossary, setGlossary] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [readiness, setReadiness] = useState<{ ready: boolean; message?: string; model?: string; heavyWorkBlocked?: boolean; recovery?: string | null } | null>(null);
  const [retry, setRetry] = useState(0);
  const jobId = transcript.jobId;
  useEffect(() => {
    let disposed = false;
    setTask(null); setSelected(new Set()); setError(''); setReadiness(null);
    let timer: ReturnType<typeof setTimeout>;
    let firstPoll = true;
    async function poll() {
      try {
        const value = await api.proofreading(jobId);
        if (disposed) return;
        setTask(value); setError('');
        if (firstPoll) { setGlossary(value?.glossary.join(', ') ?? ''); firstPoll = false; }
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
  const stale = !!task && (task.stale || task.revision !== transcript.revision);
  const reviewable = task?.status === 'ready' && !stale;
  const disabled = dirty || saving;
  async function start() {
    if (scope === 'block' && !selectedBlock) { setError('Select an available saved block.'); return; }
    onBusy(true); setError('');
    try {
      await api.startProofreading(jobId, transcript.revision, scope === 'block' ? selectedBlock.segmentIds : undefined, glossary.split(/[,\n]/).map(s => s.trim()).filter(Boolean));
      setSelected(new Set()); setRetry(value => value + 1);
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
  return <section className="proofreading-tools" aria-label="AI proofreading">
    <h4>Local AI proofreading</h4>
    <p className="inspector-hint">Review spelling, punctuation and capitalization. Listen to uncertain phrases. AI may make mistakes; nothing is saved until you accept it.</p>
    {readiness && <p role="status">{readiness.ready ? `Loaded model: ${readiness.model}` : readiness.message}</p>}
    {readiness?.heavyWorkBlocked && <p className="notice warning" role="status">{readiness.recovery}</p>}
    <button className="text-button" type="button" disabled={saving} onClick={() => setRetry(value => value + 1)}>Refresh model &amp; suggestions</button>
    {dirty && <p className="notice warning" role="status">Save or discard manual edits before proofreading or accepting suggestions.</p>}
    <label>Proofreading scope<select aria-label="Proofreading scope" value={scope} disabled={saving || busy} onChange={event => setScope(event.target.value)}><option value="entire">Entire recording</option><option value="block">Saved block</option></select></label>
    {scope === 'block' && <label>Source block<select aria-label="Proofreading block" value={blockIndex} disabled={saving || busy} onChange={event => setBlockIndex(Number(event.target.value))}>{blocks.map((block, index) => <option key={block.id} value={index}>{index + 1} · {timestamp(block.start)} · {block.segmentIds.length} segments</option>)}</select></label>}
    <label>Protected spellings (optional)<textarea aria-label="Proofreading glossary" value={glossary} maxLength={700} disabled={saving || busy} placeholder="Names or terms, separated by commas" onChange={event => setGlossary(event.target.value)} /></label>
    <button className="button secondary full" type="button" disabled={disabled || busy || !transcript.segments.length || !readiness?.ready || readiness.heavyWorkBlocked || (scope === 'block' && !selectedBlock)} onClick={start}>Preview AI corrections</button>
    {busy && <div role="status"><p>Proofreading {task.status} · {task.progress} chunks completed. Saved transcript and exports are unchanged.</p><button className="button secondary" type="button" disabled={task.status === 'cancelling'} onClick={cancel}>Cancel proofreading</button>{task.status === 'cancelling' && <p>Waiting for the current model response to finish safely. No corrections will be published.</p>}</div>}
    {error && <p className="notice error" role="alert">{error} Saved text and manual drafts remain available.</p>}
    {task && !busy && <div>
      <p role="status">{stale ? 'Suggestions are stale. Start a new preview for the saved revision.' : task.status === 'applied' ? 'Accepted corrections saved as one history operation.' : task.status === 'ready' ? `${task.suggestions.length} suggestions. Pending suggestions are excluded from exports.` : `Proofreading ${task.status}.`}</p>
      {task.error && <p className="notice warning" role="alert">{task.error}</p>}
      {reviewable && <>
        <div className="cleanup-actions"><button className="text-button" type="button" disabled={disabled} onClick={() => setSelected(new Set(task.suggestions.filter(s => !s.uncertain).map(s => s.id)))}>Select all corrections</button><button className="text-button" type="button" disabled={disabled} onClick={() => setSelected(new Set())}>Clear selection</button></div>
        <ol className="proofreading-suggestions">{task.suggestions.map(suggestion => <li key={suggestion.id}>
          <label><input type="checkbox" aria-label={`Select correction ${suggestion.id}`} checked={selected.has(suggestion.id)} disabled={disabled || suggestion.uncertain} onChange={event => setSelected(previous => { const next = new Set(previous); if (event.target.checked) next.add(suggestion.id); else next.delete(suggestion.id); return next; })} />{suggestion.id} {suggestion.uncertain && '· Listen before editing'}</label>
          <p className="correction-diff">{suggestion.diff.map((part, index) => <span key={index}>{part.kind === 'equal' ? part.old : <><del>{part.old}</del><ins>{part.new}</ins></>}</span>)}</p>
          <div className="cleanup-actions"><button className="text-button" type="button" disabled={disabled || suggestion.uncertain} onClick={() => decide('apply', [suggestion.id])}>Accept correction</button><button className="text-button" type="button" disabled={disabled} onClick={() => decide('reject', [suggestion.id])}>Reject suggestion</button></div>
        </li>)}</ol>
        <div className="cleanup-actions"><button className="button primary" type="button" disabled={disabled || !selected.size} onClick={() => decide('apply', [...selected])}>Accept selected corrections</button><button className="button secondary" type="button" disabled={disabled || !selected.size} onClick={() => decide('reject', [...selected])}>Reject selected suggestions</button><button className="button secondary" type="button" disabled={disabled || !task.suggestions.length} onClick={() => decide('reject', task.suggestions.map(s => s.id))}>Reject all suggestions</button></div>
        <p className="inspector-hint">Each accepted batch is one Undo. Remaining suggestions become stale after a save; review your selection before accepting.</p>
      </>}
    </div>}
  </section>;
}
