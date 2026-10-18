import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { api, timestamp } from './api';
import type { Job, RecordingView, Transcript } from './api';

const speakerColors = ['#376da6', '#8a559b', '#297b66', '#ab672f', '#b14e66', '#616bb0'];
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'The local request failed. Please try again.';

export default function TranscriptEditor({ job, transcript, view, onViewChange, onSaved, onDirtyChange }: { job: Job; transcript: Transcript; view: RecordingView; onViewChange: (view: RecordingView) => void; onSaved: (value: Transcript) => void; onDirtyChange: (dirty: boolean) => void }) {
  const [texts, setTexts] = useState<Record<string, string | null>>({});
  const [names, setNames] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false); const [feedback, setFeedback] = useState(''); const [saveError, setSaveError] = useState('');
  const [time, setTime] = useState(0); const [duration, setDuration] = useState(0);
  const [ready, setReady] = useState(false); const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1); const [playbackError, setPlaybackError] = useState('');
  const [follow, setFollow] = useState(true);
  const audio = useRef<HTMLAudioElement>(null); const segments = useRef<HTMLDivElement>(null);
  const activeSegment = transcript.segments.find(segment => time >= segment.start && time < segment.end);
  const dirty = Object.keys(texts).length > 0 || Object.keys(names).length > 0;
  const reviewing = view === 'review';
  const speakerName = (id: string | null) => id ? names[id] ?? transcript.speakers.find(speaker => speaker.id === id)?.displayName ?? id : job.options.diarization ? 'Speaker unavailable' : 'Text only';
  const speakerStyle = (id: string | null): CSSProperties => ({ '--speaker-color': id ? speakerColors[Math.max(0, transcript.speakers.findIndex(speaker => speaker.id === id)) % speakerColors.length] : '#738195' } as CSSProperties);

  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', handler); return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);
  useEffect(() => {
    const container = segments.current;
    if (!reviewing || !follow || !container || container.contains(document.activeElement)) return;
    const current = container.querySelector<HTMLElement>('.segment.playing');
    if (current) container.scrollTo({ top: container.scrollTop + current.getBoundingClientRect().top - container.getBoundingClientRect().top - 12, behavior: 'instant' });
  }, [activeSegment?.id, reviewing, follow]);

  async function save() {
    setSaving(true); setSaveError(''); setFeedback('');
    try {
      const saved = await api.save(job.id, transcript.revision, texts, names);
      onSaved(saved); setTexts({}); setNames({}); onDirtyChange(false); setFeedback('Changes saved. All exports use this saved version.');
    } catch (error) { setSaveError(messageOf(error)); } finally { setSaving(false); }
  }
  function seek(value: number) {
    if (!audio.current || !ready) return;
    const next = Math.min(duration, Math.max(0, value));
    audio.current.currentTime = next; setTime(next);
  }
  async function play() {
    if (!audio.current || !ready) return;
    setPlaybackError('');
    try { await audio.current.play(); }
    catch { setPlaybackError('Audio could not start. Try playing the recording again.'); }
  }
  function changeRate(value: number) {
    if (audio.current) audio.current.playbackRate = value;
    setRate(value);
  }
  function metadata() {
    const value = audio.current?.duration;
    if (value && Number.isFinite(value)) { setDuration(value); setReady(true); setPlaybackError(''); }
  }

  return <div className={`transcript-editor ${reviewing ? 'review-mode' : ''}`}>
    <nav className="recording-views" aria-label="Recording views">
      <button type="button" aria-pressed={!reviewing} onClick={() => onViewChange('transcript')}>Transcript</button>
      <button type="button" aria-pressed={reviewing} onClick={() => onViewChange('review')}>Listen &amp; review</button>
    </nav>
    {reviewing && <div className="review-intro"><h3>Listen alongside the transcript</h3><p>Jump to a timestamp, check the words, and give each speaker a name.</p></div>}
    <div className="editor-toolbar"><span>{transcript.segments.length} segments · {transcript.language || 'Language unknown'} · revision {transcript.revision}</span><button type="button" className="button primary" disabled={!dirty || saving} onClick={save}>{saving ? 'Saving…' : 'Save changes'}</button></div>
    {dirty && <p className="notice warning">Unsaved edits. Save before exporting or opening another recording.</p>}
    {feedback && <p role="status" className="notice success">{feedback}</p>}
    {saveError && <p role="alert" className="notice error">{saveError} Your edits are still shown; the saved transcript has not changed.</p>}
    <div className="review-layout">
      <div className="listening-panel">
        {reviewing && <div className="review-player" aria-label="Audio player">
          <span className="eyebrow">RECORDING AUDIO</span>
          <div className="playback-clock"><strong>{timestamp(time)}</strong><span>/ {timestamp(duration || transcript.duration || job.duration || 0)}</span></div>
          <label className="seek-label">Position in recording<input type="range" min={0} max={duration || 0} step={0.1} value={Math.min(time, duration)} disabled={!ready} onChange={event => seek(Number(event.target.value))} aria-label="Audio position" aria-valuetext={`${timestamp(time)} of ${timestamp(duration)}`} /></label>
          <div className="playback-buttons">
            <button type="button" className="button secondary" disabled={!ready} onClick={() => seek(time - 5)} aria-label="Back 5 seconds">↶ 5s</button>
            <button type="button" className="button primary" disabled={!ready} onClick={() => playing ? audio.current?.pause() : void play()}>{playing ? 'Pause' : 'Play'}</button>
            <button type="button" className="button secondary" disabled={!ready} onClick={() => seek(time + 5)} aria-label="Forward 5 seconds">5s ↷</button>
          </div>
          <label className="playback-speed">Playback speed<select aria-label="Playback speed" value={rate} onChange={event => changeRate(Number(event.target.value))}>{[0.5, 0.75, 1, 1.25, 1.5, 2].map(value => <option value={value} key={value}>{value}×</option>)}</select></label>
          <div className="now-speaking" style={speakerStyle(activeSegment?.speakerId ?? null)}><span className="speaker-dot" aria-hidden="true" /><span>{activeSegment ? speakerName(activeSegment.speakerId) : ready ? 'No speech at this position' : 'Loading audio…'}</span></div>
        </div>}
        <audio ref={audio} controls={!reviewing} hidden={reviewing} preload="metadata" src={api.media(job.id)} onLoadedMetadata={metadata} onDurationChange={metadata} onTimeUpdate={() => setTime(audio.current?.currentTime || 0)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onRateChange={() => setRate(audio.current?.playbackRate || 1)} onError={() => { setReady(false); setPlaying(false); setPlaybackError('The recording audio could not be loaded. Reload the page to try again. Your transcript remains available.'); }}>Your browser does not support audio playback.</audio>
        {playbackError && <p role="alert" className="notice error">{playbackError}</p>}
        {reviewing && <div className="speakers-heading"><h3>Speakers</h3><p>Names apply throughout this recording. Save changes when you are done.</p></div>}
        <div className="speaker-names">{transcript.speakers.map(speaker => {
          const first = transcript.segments.find(segment => segment.speakerId === speaker.id);
          return <div className="speaker-card" key={speaker.id} style={speakerStyle(speaker.id)}>
            <label><span><i className="speaker-dot" aria-hidden="true" />{speaker.id}</span><input value={names[speaker.id] ?? speaker.displayName} maxLength={120} disabled={saving} onChange={event => { setNames({ ...names, [speaker.id]: event.target.value }); setFeedback(''); }} aria-label={`Display name for ${speaker.id}`} /></label>
            {reviewing && first && <button type="button" className="text-button" disabled={!ready} onClick={() => { seek(first.start); void play(); }} aria-label={`Hear ${speakerName(speaker.id)}`}>Listen from {timestamp(first.start)}</button>}
          </div>;
        })}</div>
        {reviewing && transcript.speakers.length === 0 && <p className="speaker-empty">{job.options.diarization ? 'Speaker labels are unavailable for this recording.' : 'Speaker identification was turned off for this recording.'}</p>}
      </div>
      <div className="transcript-panel">
        {reviewing && <div className="review-transcript-heading"><h3>Transcript</h3><label className="checkbox-label"><input type="checkbox" checked={follow} onChange={event => setFollow(event.target.checked)} />Follow audio</label></div>}
        <div className="segments" ref={segments} role={reviewing ? 'region' : undefined} aria-label={reviewing ? 'Transcript segments' : undefined} tabIndex={reviewing ? 0 : undefined}>{transcript.segments.length === 0 ? <p className="empty">No speech was detected in this recording.</p> : transcript.segments.map(segment => <article className={`segment ${time >= segment.start && time < segment.end ? 'playing' : ''}`} key={segment.id} style={speakerStyle(segment.speakerId)}>
          <div className="segment-meta"><button type="button" className="timestamp" disabled={!ready} onClick={() => seek(segment.start)} aria-label={`Seek to ${timestamp(segment.start)}`}>{timestamp(segment.start)}</button>{reviewing && <span className="segment-end">– {timestamp(segment.end)}</span>}<strong><i className="speaker-dot" aria-hidden="true" />{speakerName(segment.speakerId)}</strong>{segment.overlap && <span className="tag warning-tag">Overlapping speech</span>}</div>
          <textarea aria-label={`Transcript at ${timestamp(segment.start)}`} value={texts[segment.id] ?? segment.editedText ?? segment.text} disabled={saving} rows={Math.max(2, Math.ceil((texts[segment.id] ?? segment.editedText ?? segment.text).length / (reviewing ? 60 : 95)))} onChange={event => { setTexts({ ...texts, [segment.id]: event.target.value }); setFeedback(''); }} />
        </article>)}</div>
      </div>
    </div>
    <div className="export-bar"><strong>Export saved transcript</strong><div>{['txt', 'srt', 'vtt', 'json'].map(format => <a className="button secondary" key={format} href={api.export(job.id, format)} download>{format.toUpperCase()}</a>)}</div>{dirty && <span className="muted">Exports include saved edits only.</span>}</div>
  </div>;
}
