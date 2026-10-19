import { useEffect, useState } from 'react';
import ProofreadingTools from './ProofreadingTools';
import { api, timestamp } from './api';
import type { GroupingPreview, OperationHistory, Transcript } from './api';

const messageOf = (error: unknown) => error instanceof Error ? error.message : 'The local request failed. Please try again.';
type Props = { transcript: Transcript; dirty: boolean; saving: boolean; onBusy: (value: boolean) => void; onSaved: (value: Transcript) => void };

export default function TranscriptTools({ transcript, dirty, saving, onBusy, onSaved }: Props) {
  const [preview, setPreview] = useState<GroupingPreview | null>(null);
  const [scope, setScope] = useState('entire'); const [first, setFirst] = useState(0); const [last, setLast] = useState(transcript.segments.length - 1);
  const [error, setError] = useState(''); const [feedback, setFeedback] = useState('');
  const [history, setHistory] = useState<OperationHistory | null>(null); const [historyError, setHistoryError] = useState(''); const [retry, setRetry] = useState(0);
  useEffect(() => { setPreview(null); }, [transcript.jobId, transcript.revision, dirty, scope, first, last]);
  useEffect(() => {
    let disposed = false; setHistory(null); setHistoryError('');
    api.history(transcript.jobId).then(value => { if (!disposed) setHistory(value); }).catch(error => { if (!disposed) setHistoryError(messageOf(error)); });
    return () => { disposed = true; };
  }, [transcript.jobId, transcript.revision, retry]);
  const selection = scope === 'selection' ? transcript.segments.slice(first, last + 1).map(segment => segment.id) : undefined;
  const disabled = dirty || saving;
  const invalidSelection = scope === 'selection' && first > last;
  async function runPreview() {
    onBusy(true); setError(''); setFeedback('');
    try { setPreview(await api.previewGrouping(transcript.jobId, transcript.revision, selection)); }
    catch (error) { setError(messageOf(error)); }
    finally { onBusy(false); }
  }
  async function mutate(action: 'apply' | 'undo' | 'redo') {
    onBusy(true); setError(''); setFeedback('');
    try {
      const saved = action === 'apply' ? await api.applyGrouping(transcript.jobId, preview!.revision, selection) : await api.moveHistory(transcript.jobId, action, transcript.revision);
      setPreview(null); onSaved(saved); setFeedback(action === 'apply' ? saved.revision === transcript.revision ? 'Grouping is unchanged. No history operation was added.' : 'All groups saved as one operation.' : `${action === 'undo' ? 'Undo' : 'Redo'} saved as revision ${saved.revision}.`);
    } catch (error) { setError(messageOf(error)); }
    finally { onBusy(false); }
  }
  const currentHistory = history?.revision === transcript.revision;
  return <div className="cleanup-tools">
    <p className="inspector-hint">Group adjacent segments from the same speaker. No AI; original words and timings stay intact.</p>
    {dirty && <p role="status" className="notice warning">Save or discard your manual edits before grouping or Undo/Redo.</p>}
    <label>Grouping scope<select aria-label="Grouping scope" value={scope} disabled={saving} onChange={event => setScope(event.target.value)}><option value="entire">Entire recording</option><option value="selection">Selection</option></select></label>
    {scope === 'selection' && <div className="selection-fields">{([['First source segment', first, setFirst], ['Last source segment', last, setLast]] as const).map(([label, value, setter]) => <label key={label}>{label}<select aria-label={label} value={value} disabled={saving} onChange={event => setter(Number(event.target.value))}>{transcript.segments.map((segment, index) => <option key={segment.id} value={index}>{index + 1} · {timestamp(segment.start)} · {segment.id}</option>)}</select></label>)}</div>}
    {invalidSelection && <p role="status">The last segment must follow the first.</p>}
    <button className="button secondary full" type="button" disabled={disabled || invalidSelection || !transcript.segments.length} onClick={runPreview}>Preview grouping</button>
    {error && <p role="alert" className="notice error">{error} Saved transcript and drafts remain available. Reload only after saving or discarding drafts.</p>}
    {preview && <section role="region" aria-label="Grouping preview" className="grouping-preview">
      <strong>{scope === 'entire' ? transcript.segments.length : selection!.length} segments · {preview.beforeCount} → {preview.afterCount} blocks</strong>
      <p className="inspector-hint">Preview only — saved text and exports have not changed.{!preview.changed && ' No grouping changes are needed.'}</p>
      <ol className="preview-blocks">{preview.blocks.map(block => <li key={block.id}><span>{timestamp(block.start)}–{timestamp(block.end)} · {block.segmentIds.length} segments</span><p>{block.text}</p></li>)}</ol>
      <div className="cleanup-actions"><button type="button" className="button primary" disabled={disabled || !preview.changed} onClick={() => mutate('apply')}>Apply all</button><button type="button" className="button secondary" disabled={saving} onClick={() => setPreview(null)}>Cancel grouping</button></div>
    </section>}
    <ProofreadingTools transcript={transcript} dirty={dirty} saving={saving} onBusy={onBusy} onSaved={onSaved} />
    <div className="operation-history">
      <h4>Changes &amp; history</h4>
      <div className="cleanup-actions"><button type="button" className="button secondary" aria-label="Undo saved operation" disabled={disabled || !currentHistory || !history?.canUndo} onClick={() => mutate('undo')}>Undo</button><button type="button" className="button secondary" aria-label="Redo saved operation" disabled={disabled || !currentHistory || !history?.canRedo} onClick={() => mutate('redo')}>Redo</button></div>
      {historyError && <p role="alert">{historyError} <button className="text-button" onClick={() => setRetry(value => value + 1)}>Retry history</button></p>}
      {history && !currentHistory && <p role="status" className="notice warning">The saved revision changed in another tab. Reload after saving or discarding drafts.</p>}
      <details><summary>Saved operations ({history?.operations.length ?? 0})</summary><ol className="history-operations">{history?.operations.map(operation => <li key={operation.id} className={operation.applied ? '' : 'undone'}><strong>{({ manual_save: 'Manual save', grouping: 'Group speaker segments', split: 'Split speaker block', proofreading: 'Accept AI corrections' } as Record<string, string>)[operation.type] || operation.type}</strong><span>Revision {operation.baseRevision} → {operation.resultRevision}{!operation.applied && ' · Undone'}</span></li>)}</ol></details>
      <p className="inspector-hint">One accepted batch is one Undo. History survives restart. A new edit clears Redo.</p>
    </div>
    {feedback && <p role="status">{feedback}</p>}
  </div>;
}
