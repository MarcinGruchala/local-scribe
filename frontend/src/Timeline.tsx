import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, PointerEvent as ReactPointerEvent, RefObject } from 'react';
import { preciseTimestamp, timestamp } from './api';
import type { Segment } from './api';
import Avatar from './Avatar';
import { IconZoomIn, IconZoomOut } from './icons';

export type TimelineTrack = { key: string; speakerId: string | null; name: string; color: string };

const zoomLevels = [1, 2, 4, 8, 16, 32, 64];
const tickSteps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];
const percent = (value: number) => `${Math.min(100, Math.max(0, value * 100))}%`;

/*
 * Segment blocks are memoized separately from the playhead: playback updates the playhead
 * several times per second, while blocks only change when the active or selected segment does.
 */
const TrackBlocks = memo(function TrackBlocks({ tracks, segments, duration, activeId, selectedId }: { tracks: TimelineTrack[]; segments: Segment[]; duration: number; activeId: string | null; selectedId: string | null }) {
  const byTrack = useMemo(() => {
    const groups = new Map<string | null, Segment[]>();
    for (const segment of segments) {
      const group = groups.get(segment.speakerId);
      if (group) group.push(segment); else groups.set(segment.speakerId, [segment]);
    }
    return groups;
  }, [segments]);
  return <>{tracks.map(track => <div className="timeline-track" key={track.key} style={{ '--speaker-color': track.color } as CSSProperties}>
    {duration > 0 && (byTrack.get(track.speakerId) ?? []).map(segment => <span
      key={segment.id}
      data-segment={segment.id}
      className={`timeline-block${segment.id === activeId ? ' active' : ''}${segment.id === selectedId ? ' selected' : ''}`}
      style={{ left: percent(segment.start / duration), width: percent((segment.end - segment.start) / duration) }}
    />)}
  </div>)}</>;
});

type TimelineProps = {
  tracks: TimelineTrack[]; segments: Segment[]; duration: number; time: number; playing: boolean; ready: boolean; follow: boolean;
  activeId: string | null; selectedId: string | null; audio: RefObject<HTMLAudioElement | null>;
  onSeek: (time: number) => void; onPick: (segmentId: string) => void;
};

export default function Timeline({ tracks, segments, duration, time, playing, ready, follow, activeId, selectedId, audio, onSeek, onPick }: TimelineProps) {
  const [zoom, setZoom] = useState(0); const [viewport, setViewport] = useState(0);
  const scroller = useRef<HTMLDivElement>(null); const canvas = useRef<HTMLDivElement>(null);
  const playhead = useRef<HTMLDivElement>(null); const playheadLabel = useRef<HTMLSpanElement>(null);
  const drag = useRef<{ pointer: number; x: number; moved: boolean; segment: string | null } | null>(null);
  const factor = zoomLevels[zoom];
  const pixelsPerSecond = duration > 0 ? viewport * factor / duration : 0;
  const step = tickSteps.find(value => value * pixelsPerSecond >= 76) ?? 3600;
  const ticks = pixelsPerSecond > 0 ? Array.from({ length: Math.floor(duration / step) + 1 }, (_, index) => index * step) : [];

  useLayoutEffect(() => {
    const element = scroller.current; if (!element) return;
    const observer = new ResizeObserver(() => setViewport(element.clientWidth));
    observer.observe(element); setViewport(element.clientWidth);
    return () => observer.disconnect();
  }, []);

  // The playhead is moved directly in the DOM so it can glide at display frame rate without re-rendering React.
  const place = useCallback((seconds: number, keepVisible: boolean) => {
    if (!playhead.current || duration <= 0) return;
    const ratio = Math.min(1, Math.max(0, seconds / duration));
    playhead.current.style.left = percent(ratio);
    if (playheadLabel.current) playheadLabel.current.textContent = preciseTimestamp(seconds);
    const element = scroller.current;
    if (keepVisible && element && factor > 1) {
      const x = ratio * element.scrollWidth;
      if (x < element.scrollLeft + 16 || x > element.scrollLeft + element.clientWidth - 32) element.scrollLeft = x - element.clientWidth * .25;
    }
  }, [duration, factor]);
  useLayoutEffect(() => { place(time, follow); }, [time, place, follow, viewport]);
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = () => { place(audio.current?.currentTime ?? 0, follow); frame = requestAnimationFrame(tick); };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, place, follow, audio]);
  useLayoutEffect(() => {
    // Keep the playhead in view when the zoom level changes.
    const element = scroller.current; if (!element || duration <= 0) return;
    element.scrollLeft = Math.min(1, (audio.current?.currentTime ?? 0) / duration) * element.scrollWidth - element.clientWidth / 2;
  }, [factor, duration, audio]);

  function timeAt(clientX: number) {
    const rect = canvas.current!.getBoundingClientRect();
    return Math.min(duration, Math.max(0, (clientX - rect.left) / rect.width * duration));
  }
  function pointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (!ready || duration <= 0 || event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const block = (event.target as HTMLElement).closest<HTMLElement>('[data-segment]');
    drag.current = { pointer: event.pointerId, x: event.clientX, moved: false, segment: block?.dataset.segment ?? null };
    if (!block) onSeek(timeAt(event.clientX));
  }
  function pointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const current = drag.current;
    if (!current || current.pointer !== event.pointerId) return;
    if (!current.moved && Math.abs(event.clientX - current.x) < 3) return;
    current.moved = true; onSeek(timeAt(event.clientX));
  }
  function pointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    const current = drag.current; drag.current = null;
    if (current && current.pointer === event.pointerId && !current.moved && current.segment) onPick(current.segment);
  }

  return <section className="timeline" aria-label="Speaker timeline">
    <div className="timeline-labels">
      <div className="timeline-labels-head">
        <span>Speakers</span>
        <div className="zoom-controls">
          <button type="button" className="icon-button small" onClick={() => setZoom(value => Math.max(0, value - 1))} disabled={zoom === 0} aria-label="Zoom out timeline" title="Zoom out"><IconZoomOut size={14} /></button>
          <span aria-live="polite">{factor}×</span>
          <button type="button" className="icon-button small" onClick={() => setZoom(value => Math.min(zoomLevels.length - 1, value + 1))} disabled={zoom === zoomLevels.length - 1 || duration <= 0} aria-label="Zoom in timeline" title="Zoom in"><IconZoomIn size={14} /></button>
        </div>
      </div>
      {tracks.map(track => <div className="timeline-label" key={track.key} title={track.name}><Avatar name={track.name} color={track.color} size="sm" /><span>{track.name}</span></div>)}
    </div>
    <div className="timeline-scroll" ref={scroller}>
      <div className={`timeline-canvas${ready ? '' : ' disabled'}`} ref={canvas} style={{ width: factor === 1 ? '100%' : `${Math.round(viewport * factor)}px` }} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={() => { drag.current = null; }} aria-hidden="true">
        <div className="timeline-ruler">{ticks.map(value => <span className="tick" key={value} style={{ left: percent(value / duration) }}><span>{timestamp(value)}</span></span>)}</div>
        <TrackBlocks tracks={tracks} segments={segments} duration={duration} activeId={activeId} selectedId={selectedId} />
        <div className="playhead" ref={playhead}><span ref={playheadLabel}>00:00.0</span></div>
      </div>
    </div>
  </section>;
}
