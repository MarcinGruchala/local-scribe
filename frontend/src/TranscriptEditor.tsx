import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react';
import { api, languageName, preciseTimestamp, timestamp } from './api';
import type { Job, Segment, Transcript } from './api';
import Avatar from './Avatar';
import Timeline from './Timeline';
import TranscriptTools from './TranscriptTools';
import ProofreadingTools from './ProofreadingTools';
import type { ReviewSummary } from './ProofreadingTools';
import type { TimelineTrack } from './Timeline';
import { IconBack, IconCheck, IconChevron, IconDownload, IconForward, IconPause, IconPlay, IconSearch } from './icons';

const speakerColors = ['#7aa2ff', '#c49bff', '#4fd1a5', '#f5b85c', '#f48fb8', '#5cc8e0', '#ff9b6a', '#a5d66f'];
const unknownColor = '#8b90a0';
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'The local request failed. Please try again.';
const colorStyle = (color: string) => ({ '--speaker-color': color } as CSSProperties);
const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

/*
 * Chromium sizes textareas to their content with `field-sizing: content` (see style.css).
 * Other browsers fall back to measuring scrollHeight after each change.
 */
const fieldSizing = typeof CSS !== 'undefined' && typeof CSS.supports === 'function' && CSS.supports('field-sizing', 'content');
function fitHeight(element: HTMLTextAreaElement | null) {
  if (!element || fieldSizing) return;
  element.style.height = 'auto';
  element.style.height = `${element.scrollHeight + 2}px`;
}
// Keyboard shortcuts must not steal keys from anything the user is typing in or operating.
const ownsKeyboard = (target: EventTarget | null) => target instanceof HTMLElement && Boolean(target.closest('input, textarea, select, button, a, [contenteditable="true"], .segments'));

type RowProps = {
  segment: Segment; value: string; name: string; color: string; continued: boolean; draft: boolean;
  playing: boolean; selected: boolean; match: boolean; dimmed: boolean; ready: boolean; saving: boolean;
  onText: (id: string, value: string) => void; onSeek: (time: number) => void; onSelect: (id: string) => void;
};

/* Each row is memoized so playback (several updates per second) only re-renders the rows whose state changed. */
const SegmentRow = memo(function SegmentRow({ segment, value, name, color, continued, draft, playing, selected, match, dimmed, ready, saving, onText, onSeek, onSelect }: RowProps) {
  const field = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => { fitHeight(field.current); }, [value]);
  const classes = ['segment', playing && 'playing', selected && 'selected', match && 'match', dimmed && 'dimmed', continued && 'continued'].filter(Boolean).join(' ');
  return <article className={classes} data-segment={segment.id} style={colorStyle(color)} onClick={() => onSelect(segment.id)}>
    <div className="segment-speaker">
      <Avatar name={name} />
      <div className="segment-meta"><strong>{name}</strong>{segment.overlap && <span className="tag warning-tag">Overlapping speech</span>}</div>
    </div>
    <div className="segment-body">
      <div className="segment-head">
        <button type="button" className="timestamp" disabled={!ready} onClick={event => { event.stopPropagation(); onSeek(segment.start); }} aria-label={`Seek to ${timestamp(segment.start)}`} title="Play from here">{preciseTimestamp(segment.start)}</button>
        {draft ? <span className="edit-flag unsaved" title="Edited, not saved yet">Unsaved edit</span> : segment.editedText != null && <span className="edit-flag" title="This segment was edited">Edited</span>}
      </div>
      <textarea ref={field} aria-label={`Transcript at ${timestamp(segment.start)}`} value={value} rows={1} disabled={saving} onFocus={() => onSelect(segment.id)} onChange={event => onText(segment.id, event.target.value)} />
      <span className="segment-end">{preciseTimestamp(segment.end)}</span>
    </div>
  </article>;
});

export function InspectorSection({ title, aside, className, children }: { title: string; aside?: ReactNode; className?: string; children: ReactNode }) {
  return <details className={`inspector-section${className ? ` ${className}` : ''}`} open>
    <summary><IconChevron size={14} className="chevron" /><span>{title}</span>{aside != null && <span className="summary-aside">{aside}</span>}</summary>
    <div className="inspector-content">{children}</div>
  </details>;
}

type EditorProps = {
  job: Job; transcript: Transcript; heading: ReactNode; notices?: ReactNode; inspectorExtras?: ReactNode;
  onSaved: (value: Transcript) => void; onDirtyChange: (dirty: boolean) => void;
};

export default function TranscriptEditor({ job, transcript, heading, notices, inspectorExtras, onSaved, onDirtyChange }: EditorProps) {
  const [view, setView] = useState<'transcript' | 'suggestions'>('transcript');
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary>({ corrections: 0, listening: 0, status: '', stale: false });
  const initialSource = useRef(new URLSearchParams(window.location.hash.slice(1)).get('segment'));
  const [revealedSuggestion, setRevealedSuggestion] = useState<string | null>(null);
  const [texts, setTexts] = useState<Record<string, string | null>>({});
  const [names, setNames] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false); const [feedback, setFeedback] = useState(''); const [saveError, setSaveError] = useState('');
  const [time, setTime] = useState(0); const [duration, setDuration] = useState(0);
  const [ready, setReady] = useState(false); const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1); const [playbackError, setPlaybackError] = useState('');
  const [follow, setFollow] = useState(true); const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState(''); const [matchIndex, setMatchIndex] = useState(0);
  const [exportSource, setExportSource] = useState('current'); const [exportLayout, setExportLayout] = useState('grouped');
  const audio = useRef<HTMLAudioElement>(null); const segmentList = useRef<HTMLDivElement>(null);
  const segments = transcript.segments;
  const sourceById = useMemo(() => new Map(segments.map(segment => [segment.id, segment])), [segments]);
  const blocks = useMemo(() => {
    const saved = transcript.grouping?.blocks;
    // Legacy and test clients may still return only the original v1 source segments.
    if (saved && saved.flatMap(block => block.segmentIds).join('\0') === segments.map(segment => segment.id).join('\0')) return saved;
    return segments.map(segment => ({ ...segment, segmentIds: [segment.id], text: segment.editedText ?? segment.text }));
  }, [segments, transcript.grouping]);
  // Only source partitions (including their React keys) change the rows' DOM placement.
  const sourcePartitions = JSON.stringify(blocks.map(block => [block.id, block.segmentIds]));
  const activeSegment = useMemo(() => segments.find(segment => time >= segment.start && time < segment.end), [segments, time]);
  const dirty = Object.keys(texts).length > 0 || Object.keys(names).length > 0;
  const totalDuration = duration || transcript.duration || job.duration || segments.reduce((end, segment) => Math.max(end, segment.end), 0);
  const fallbackName = job.options.diarization ? 'Speaker unavailable' : 'Text only';
  const speakerName = useCallback((id: string | null) => id ? names[id] ?? transcript.speakers.find(speaker => speaker.id === id)?.displayName ?? id : fallbackName, [names, transcript.speakers, fallbackName]);
  const colors = useMemo(() => new Map(transcript.speakers.map((speaker, index) => [speaker.id, speakerColors[index % speakerColors.length]])), [transcript.speakers]);
  const colorOf = useCallback((id: string | null) => (id && colors.get(id)) || unknownColor, [colors]);
  const valueOf = (segment: Segment) => texts[segment.id] ?? segment.editedText ?? segment.text;

  const stats = useMemo(() => {
    const result = new Map<string | null, { turns: number; seconds: number; first: Segment }>();
    for (const segment of segments) {
      const entry = result.get(segment.speakerId) ?? { turns: 0, seconds: 0, first: segment };
      entry.turns += 1; entry.seconds += Math.max(0, segment.end - segment.start);
      result.set(segment.speakerId, entry);
    }
    return result;
  }, [segments]);
  const talkTotal = useMemo(() => [...stats.values()].reduce((sum, entry) => sum + entry.seconds, 0), [stats]);
  const tracks = useMemo<TimelineTrack[]>(() => [
    ...transcript.speakers.map(speaker => ({ key: speaker.id, speakerId: speaker.id, name: speakerName(speaker.id), color: colorOf(speaker.id) })),
    ...(stats.has(null) || segments.length === 0 ? [{ key: 'unknown', speakerId: null, name: fallbackName, color: unknownColor }] : []),
  ], [transcript.speakers, speakerName, colorOf, stats, segments.length, fallbackName]);

  const needle = query.trim().toLocaleLowerCase();
  const matches = useMemo(() => needle ? segments.filter(segment => (texts[segment.id] ?? segment.editedText ?? segment.text).toLocaleLowerCase().includes(needle)).map(segment => segment.id) : [], [needle, segments, texts]);
  const matchSet = useMemo(() => new Set(matches), [matches]);
  const currentMatch = matches.length ? matches[Math.min(matchIndex, matches.length - 1)] : null;
  const inspected = segments.find(segment => segment.id === selectedId) ?? activeSegment ?? null;

  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', handler); return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);
  useEffect(() => {
    if (!feedback) return;
    const timer = setTimeout(() => setFeedback(''), 6000); return () => clearTimeout(timer);
  }, [feedback]);
  useEffect(() => {
    // Without field-sizing support, re-measure every textarea when the transcript column changes width.
    const container = segmentList.current; if (fieldSizing || !container) return;
    let width = container.clientWidth;
    const observer = new ResizeObserver(() => {
      if (container.clientWidth === width) return;
      width = container.clientWidth; container.querySelectorAll('textarea').forEach(fitHeight);
    });
    observer.observe(container); return () => observer.disconnect();
  }, []);

  const reveal = useCallback((id: string, smooth = true) => {
    const container = segmentList.current;
    const element = container?.querySelector<HTMLElement>(`[data-segment="${CSS.escape(id)}"]`);
    if (!container || !element) return;
    const sources = element.closest('details');
    if (sources) sources.open = true;
    const top = container.scrollTop + element.getBoundingClientRect().top - container.getBoundingClientRect().top - container.clientHeight * .3;
    container.scrollTo({ top, behavior: smooth ? 'smooth' : 'instant' });
  }, []);
  useEffect(() => {
    // Follow the audio inside the transcript column unless the user is working inside it.
    const container = segmentList.current;
    if (!follow || !activeSegment || !container || container.contains(document.activeElement)) return;
    reveal(activeSegment.id, playing);
    // `playing` only picks the scroll style; it must not re-trigger scrolling by itself.
  }, [activeSegment?.id, follow, reveal, sourcePartitions]);
  useEffect(() => {
    setMatchIndex(0);
    if (matches[0]) reveal(matches[0]);
    // Jump to the first match only when the search text changes, not on every edit.
  }, [needle]);
  useEffect(() => {
    // A saved regroup can remount the current result inside collapsed sources.
    // Keep its index and let search take priority over audio when both need revealing.
    if (currentMatch) reveal(currentMatch);
    // Deliberately depend on structure, not matches/currentMatch: drafts must not jump.
  }, [sourcePartitions, reveal]);

  const save = useCallback(async () => {
    setSaving(true); setSaveError(''); setFeedback('');
    try {
      const saved = await api.save(job.id, transcript.revision, texts, names);
      onSaved(saved); setTexts({}); setNames({}); onDirtyChange(false); setFeedback('Changes saved. All exports use this saved version.');
    } catch (error) { setSaveError(messageOf(error)); } finally { setSaving(false); }
  }, [job.id, transcript.revision, texts, names, onSaved, onDirtyChange]);
  const seek = useCallback((value: number) => {
    if (!audio.current || !ready) return;
    const next = Math.min(duration, Math.max(0, value));
    audio.current.currentTime = next; setTime(next);
  }, [ready, duration]);
  const play = useCallback(async () => {
    if (!audio.current || !ready) return;
    setPlaybackError('');
    try { await audio.current.play(); }
    catch { setPlaybackError('Audio could not start. Try playing the recording again.'); }
  }, [ready]);
  // Read the element itself: React state lags behind until the media `play` event arrives.
  const togglePlayback = useCallback(() => { if (audio.current?.paused === false) audio.current.pause(); else void play(); }, [play]);
  const onText = useCallback((id: string, value: string) => { setTexts(current => ({ ...current, [id]: value })); setFeedback(''); }, []);
  const onSelect = useCallback((id: string) => setSelectedId(id), []);
  const pick = useCallback((id: string) => {
    const segment = segments.find(item => item.id === id); if (!segment) return;
    setSelectedId(id); seek(segment.start); reveal(id);
  }, [segments, seek, reveal]);
  const locateSuggestion = useCallback((id: string, listen: boolean) => {
    const source = segments.find(segment => segment.id === id);
    if (!source) return;
    setSelectedId(id); seek(source.start);
    if (listen) { void play(); }
    else { setFollow(false); setQuery(''); setMatchIndex(0); setView('transcript'); setRevealedSuggestion(id); }
  }, [segments, seek, play]);
  useEffect(() => {
    if (view === 'transcript' && revealedSuggestion) reveal(revealedSuggestion, false);
  }, [view, revealedSuggestion, reveal, sourcePartitions]);
  useEffect(() => {
    if (!ready || !initialSource.current) return;
    const id = initialSource.current;
    initialSource.current = null;
    if (!segments.some(segment => segment.id === id)) return;
    locateSuggestion(id, false);
  }, [ready, segments, locateSuggestion]);
  function changeRate(value: number) {
    if (audio.current) audio.current.playbackRate = value;
    setRate(value);
  }
  function metadata() {
    const value = audio.current?.duration;
    if (value && Number.isFinite(value)) { setDuration(value); setReady(true); setPlaybackError(''); }
  }
  function stepMatch(delta: number) {
    if (!matches.length) return;
    const next = (Math.min(matchIndex, matches.length - 1) + delta + matches.length) % matches.length;
    setMatchIndex(next); setSelectedId(matches[next]); reveal(matches[next]);
  }
  function searchKey(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') { event.preventDefault(); stepMatch(event.shiftKey ? -1 : 1); }
    if (event.key === 'Escape') setQuery('');
  }

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === 's') {
        event.preventDefault(); if (dirty && !saving) void save(); return;
      }
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || ownsKeyboard(event.target)) return;
      if (event.key === ' ') { event.preventDefault(); togglePlayback(); }
      else if (event.key === 'ArrowLeft') { event.preventDefault(); seek(time - 5); }
      else if (event.key === 'ArrowRight') { event.preventDefault(); seek(time + 5); }
    }
    window.addEventListener('keydown', shortcut); return () => window.removeEventListener('keydown', shortcut);
  }, [dirty, saving, save, togglePlayback, seek, time]);

  async function discard() {
    if (!window.confirm('Discard unsaved transcript changes and load the latest saved revision?')) return;
    setSaving(true); setSaveError('');
    try { const latest = await api.transcript(job.id); onSaved(latest); setTexts({}); setNames({}); onDirtyChange(false); }
    catch (error) { setSaveError(messageOf(error)); }
    finally { setSaving(false); }
  }
  async function splitBefore(beforeSegmentId: string) {
    setSaving(true); setSaveError('');
    try { onSaved(await api.splitGrouping(job.id, transcript.revision, beforeSegmentId)); }
    catch (error) { setSaveError(messageOf(error)); }
    finally { setSaving(false); }
  }
  function sourceRow(segment: Segment, index: number) {
    return <SegmentRow key={segment.id} segment={segment} value={valueOf(segment)} name={speakerName(segment.speakerId)} color={colorOf(segment.speakerId)}
      continued={index > 0 && segments[index - 1].speakerId === segment.speakerId} draft={segment.id in texts}
      playing={segment.id === activeSegment?.id} selected={segment.id === selectedId} match={segment.id === currentMatch} dimmed={Boolean(needle) && !matchSet.has(segment.id)}
      ready={ready} saving={saving} onText={onText} onSeek={seek} onSelect={onSelect} />;
  }
  const modifier = isMac ? '⌘' : 'Ctrl';
  const progress = duration ? Math.min(100, time / duration * 100) : 0;
  const inspectedStats = inspected ? { words: valueOf(inspected).trim().split(/\s+/).filter(Boolean).length, length: inspected.end - inspected.start } : null;

  return <div className="studio">
    <header className="studio-header">
      <div className="studio-title">{heading}</div>
      <div className="studio-actions">
        {dirty ? <span className="save-state unsaved" title="Save before exporting or opening another recording."><i aria-hidden="true" />Unsaved changes</span> : <span className="save-state"><IconCheck size={14} />{transcript.revision > 0 ? `Saved · revision ${transcript.revision}` : 'Original transcript'}</span>}
        {dirty && <button type="button" className="button secondary" disabled={saving} onClick={discard}>Discard changes</button>}
        <button type="button" className="button primary" disabled={!dirty || saving} onClick={save} title={`Save (${modifier}+S)`}>{saving ? 'Saving…' : 'Save changes'}</button>
      </div>
    </header>

    <div className="studio-notices">
      {notices}
      {saveError && <p role="alert" className="notice error">{saveError} Your edits are still shown; the saved transcript has not changed.</p>}
      {playbackError && <p role="alert" className="notice error">{playbackError}</p>}
    </div>

    <section className="transcript-pane" aria-label="Transcript editor">
      <div className="transcript-toolbar">
        <div className="transcript-view-tabs" role="tablist" aria-label="Transcript views"><button type="button" role="tab" aria-selected={view === 'transcript'} onClick={() => setView('transcript')}>Transcript <span>{segments.length}</span></button><button type="button" role="tab" aria-selected={view === 'suggestions'} onClick={() => setView('suggestions')}>AI suggestions{reviewSummary.corrections + reviewSummary.listening > 0 && <span className="suggestions-badge">{reviewSummary.corrections + reviewSummary.listening}</span>}{['running', 'queued', 'cancelling'].includes(reviewSummary.status) && <span className="review-running-dot" aria-label="Proofreading in progress" />}</button></div>
        <div className="transcript-tools" hidden={view !== 'transcript'}>
          <div className={`search-field${needle ? ' active' : ''}`}>
            <IconSearch size={15} />
            <input type="search" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={searchKey} placeholder="Find in transcript" aria-label="Find in transcript" />
            {needle && <span className="match-count" aria-live="polite">{matches.length ? `${Math.min(matchIndex, matches.length - 1) + 1}/${matches.length}` : 'No matches'}</span>}
            {matches.length > 1 && <><button type="button" className="icon-button small" onClick={() => stepMatch(-1)} aria-label="Previous match"><IconChevron size={14} style={{ transform: 'rotate(180deg)' }} /></button><button type="button" className="icon-button small" onClick={() => stepMatch(1)} aria-label="Next match"><IconChevron size={14} /></button></>}
          </div>
          <label className="switch"><input type="checkbox" checked={follow} onChange={event => setFollow(event.target.checked)} /><span>Follow audio</span></label>
        </div>
      </div>
      {view === 'transcript' && reviewSummary.corrections + reviewSummary.listening > 0 && <div className="review-callout"><div><strong>AI review is ready</strong><span>{reviewSummary.corrections} {reviewSummary.corrections === 1 ? 'correction' : 'corrections'} · {reviewSummary.listening} to listen to</span></div><button type="button" className="button primary" onClick={() => setView('suggestions')}>Review suggestions</button></div>}
      <ProofreadingTools transcript={transcript} dirty={dirty} saving={saving} visible={view === 'suggestions'} onBusy={setSaving} onSaved={onSaved} onSummary={setReviewSummary} onLocate={locateSuggestion} />
      <div className="segments" hidden={view !== 'transcript'} ref={segmentList} role="region" aria-label="Transcript segments" tabIndex={0}>
        {segments.length === 0 ? <p className="empty">No speech was detected in this recording.</p> : blocks.map(block => {
          const sources = block.segmentIds.map(id => sourceById.get(id)!);
          if (sources.length === 1) return sourceRow(sources[0], segments.indexOf(sources[0]));
          const isPlaying = sources.some(segment => segment.id === activeSegment?.id);
          return <article key={block.id} data-block={block.id} className={`transcript-block${isPlaying ? ' playing' : ''}`} style={colorStyle(colorOf(block.speakerId))}>
            <header><strong>{speakerName(block.speakerId)}</strong><button type="button" className="timestamp" disabled={!ready} onClick={() => seek(block.start)} aria-label={`Seek block to ${timestamp(block.start)}`}>{preciseTimestamp(block.start)}–{preciseTimestamp(block.end)}</button></header>
            <p className="block-text">{sources.map(segment => valueOf(segment).trim()).filter(Boolean).join(' ')}</p>
            <details className="block-sources"><summary>Source segments ({sources.length}) · edit or split</summary>{sources.map((segment, index) => <div key={segment.id}>
              {index > 0 && <button type="button" className="text-button split-boundary" disabled={dirty || saving} onClick={() => splitBefore(segment.id)} aria-label={`Split before ${segment.id}`}>Split before {preciseTimestamp(segment.start)}</button>}
              {sourceRow(segment, segments.indexOf(segment))}
            </div>)}</details>
          </article>;
        })}
      </div>
    </section>

    <div className="player-dock" role="group" aria-label="Audio player">
      <div className="transport">
        <div className="transport-buttons">
          <button type="button" className="icon-button skip" disabled={!ready} onClick={() => seek(time - 5)} aria-label="Back 5 seconds" title="Back 5 seconds (←)"><IconBack size={18} /><span aria-hidden="true">5</span></button>
          <button type="button" className="play-button" disabled={!ready} onClick={togglePlayback} aria-label={playing ? 'Pause' : 'Play'} title="Play or pause (Space)">{playing ? <IconPause size={18} /> : <IconPlay size={18} />}</button>
          <button type="button" className="icon-button skip" disabled={!ready} onClick={() => seek(time + 5)} aria-label="Forward 5 seconds" title="Forward 5 seconds (→)"><IconForward size={18} /><span aria-hidden="true">5</span></button>
        </div>
        <div className="playback-clock"><strong>{preciseTimestamp(time)}</strong><span>/ {timestamp(totalDuration)}</span></div>
        <input className="scrubber" type="range" min={0} max={duration || 0} step={0.1} value={Math.min(time, duration)} disabled={!ready} style={{ '--progress': `${progress}%` } as CSSProperties} onChange={event => seek(Number(event.target.value))} aria-label="Audio position" aria-valuetext={`${timestamp(time)} of ${timestamp(duration)}`} />
        <div className="now-speaking" style={colorStyle(colorOf(activeSegment?.speakerId ?? null))} title="Now speaking"><Avatar name={activeSegment ? speakerName(activeSegment.speakerId) : '?'} size="sm" /><span>{activeSegment ? speakerName(activeSegment.speakerId) : ready ? 'No speech at this position' : 'Loading audio…'}</span></div>
        <label className="playback-speed"><span className="visually-hidden">Playback speed</span><select aria-label="Playback speed" value={rate} onChange={event => changeRate(Number(event.target.value))}>{[0.5, 0.75, 1, 1.25, 1.5, 2].map(value => <option value={value} key={value}>{value}×</option>)}</select></label>
      </div>
      <Timeline tracks={tracks} segments={segments} duration={totalDuration} time={time} playing={playing} ready={ready} follow={follow} activeId={activeSegment?.id ?? null} selectedId={selectedId} audio={audio} onSeek={seek} onPick={pick} />
      <p className="shortcut-hint"><kbd>Space</kbd> play · <kbd>←</kbd><kbd>→</kbd> 5 s · <kbd>{modifier}</kbd><kbd>S</kbd> save · click a block to jump</p>
    </div>

    <aside className="inspector" aria-label="Recording details">
      <InspectorSection title="Transcript tools">
        <TranscriptTools transcript={transcript} dirty={dirty} saving={saving} onBusy={setSaving} onSaved={onSaved} />
      </InspectorSection>
      <InspectorSection title="Recording">
        <dl className="properties">
          <div><dt>File</dt><dd title={job.name}>{job.name}</dd></div>
          <div><dt>Language</dt><dd>{languageName(transcript.language)}</dd></div>
          <div><dt>Duration</dt><dd>{timestamp(totalDuration)}</dd></div>
          <div><dt>Model</dt><dd>{job.options.profile === 'quality' ? 'Quality' : 'Fast'}</dd></div>
          <div><dt>Revision</dt><dd>{transcript.revision}</dd></div>
        </dl>
      </InspectorSection>

      <InspectorSection title="Speakers" aside={transcript.speakers.length || undefined}>
        {transcript.speakers.length > 0 ? <>
          <p className="inspector-hint">Names apply throughout this recording.</p>
          <div className="speaker-names">{transcript.speakers.map(speaker => {
            const entry = stats.get(speaker.id); const share = talkTotal ? Math.round((entry?.seconds ?? 0) / talkTotal * 100) : 0;
            return <div className="speaker-card" key={speaker.id} style={colorStyle(colorOf(speaker.id))}>
              <Avatar name={speakerName(speaker.id)} />
              <div className="speaker-card-body">
                <input value={names[speaker.id] ?? speaker.displayName} maxLength={120} disabled={saving} onChange={event => { setNames({ ...names, [speaker.id]: event.target.value }); setFeedback(''); }} aria-label={`Display name for ${speaker.id}`} />
                <div className="speaker-stats"><span>{entry?.turns ?? 0} turns · {timestamp(entry?.seconds ?? 0)}</span><span>{share}%</span></div>
                <div className="share-bar" aria-hidden="true"><span style={{ width: `${share}%` }} /></div>
              </div>
              {entry && <button type="button" className="icon-button" disabled={!ready} onClick={() => { seek(entry.first.start); void play(); }} aria-label={`Hear ${speakerName(speaker.id)}`} title={`Listen from ${timestamp(entry.first.start)}`}><IconPlay size={13} /></button>}
            </div>;
          })}</div>
        </> : <p className="speaker-empty">{job.options.diarization ? 'Speaker labels are unavailable for this recording.' : 'Speaker identification was turned off for this recording.'}</p>}
      </InspectorSection>

      <InspectorSection title={selectedId && inspected?.id === selectedId ? 'Selected segment' : 'Current segment'}>
        {inspected && inspectedStats ? <>
          <div className="segment-card" style={colorStyle(colorOf(inspected.speakerId))}><Avatar name={speakerName(inspected.speakerId)} size="sm" /><span>{speakerName(inspected.speakerId)}</span></div>
          <dl className="properties">
            <div><dt>Start</dt><dd className="mono">{preciseTimestamp(inspected.start)}</dd></div>
            <div><dt>End</dt><dd className="mono">{preciseTimestamp(inspected.end)}</dd></div>
            <div><dt>Length</dt><dd className="mono">{inspectedStats.length.toFixed(1)} s</dd></div>
            <div><dt>Words</dt><dd>{inspectedStats.words}</dd></div>
          </dl>
          <button type="button" className="button secondary full" disabled={!ready} onClick={() => { seek(inspected.start); void play(); }}><IconPlay size={13} />Play segment</button>
        </> : <p className="inspector-hint">Click a segment or a timeline block to inspect it.</p>}
      </InspectorSection>

      <InspectorSection title="Export">
        <label>Export source<select aria-label="Export source" value={exportSource} onChange={event => setExportSource(event.target.value)}><option value="current">Current saved</option><option value="original">Original ASR</option></select></label>
        <label>Export layout<select aria-label="Export layout" value={exportLayout} onChange={event => setExportLayout(event.target.value)}><option value="grouped">Grouped (JSON v2)</option><option value="segmented">Source segments (JSON v1)</option></select></label>
        <div className="export-buttons">{['txt', 'srt', 'vtt', 'json'].map(format => <a className="button secondary" key={format} href={api.export(job.id, format, exportSource, exportLayout)} download><IconDownload size={13} />{format.toUpperCase()}</a>)}</div>
        <p className="inspector-hint">{dirty ? 'Exports include saved edits only.' : 'Exports use the saved transcript.'} SRT/VTT always keep source cue timings. Original ASR JSON is v1.</p>
      </InspectorSection>
      {inspectorExtras}
    </aside>

    <audio ref={audio} hidden preload="metadata" src={api.media(job.id)} onLoadedMetadata={metadata} onDurationChange={metadata} onTimeUpdate={() => setTime(audio.current?.currentTime || 0)} onSeeked={() => setTime(audio.current?.currentTime || 0)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onRateChange={() => setRate(audio.current?.playbackRate || 1)} onError={() => { setReady(false); setPlaying(false); setPlaybackError('The recording audio could not be loaded. Reload the page to try again. Your transcript remains available.'); }}>Your browser does not support audio playback.</audio>
    {feedback && <div className="toast" role="status"><IconCheck size={15} />{feedback}</div>}
  </div>;
}
