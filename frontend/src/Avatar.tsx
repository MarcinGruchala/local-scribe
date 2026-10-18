import type { CSSProperties } from 'react';

/** "Speaker 2" → "2", "Anna Nowak" → "A". */
export function initialOf(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const last = words[words.length - 1] ?? '';
  if (words.length > 1 && /^\d+$/.test(last)) return last.slice(0, 2);
  return (words[0]?.[0] ?? '?').toUpperCase();
}

/*
 * A gradient orb per speaker. The initial is rendered through CSS (`content: attr(data-initial)`),
 * so it never becomes part of the surrounding text that screen readers and tests read.
 */
export default function Avatar({ name, color, size = 'md' }: { name: string; color?: string; size?: 'sm' | 'md' | 'lg' }) {
  const style = color ? { '--speaker-color': color } as CSSProperties : undefined;
  return <span className={`avatar ${size}`} data-initial={initialOf(name)} style={style} aria-hidden="true" />;
}
