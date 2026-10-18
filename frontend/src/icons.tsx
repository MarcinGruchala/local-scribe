import type { ReactNode, SVGProps } from 'react';

/* Small inline stroke icons. They are bundled with the app so the UI never loads remote assets. */
type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function icon(paths: ReactNode) {
  return function Icon({ size = 16, ...props }: IconProps) {
    return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}>{paths}</svg>;
  };
}

export const IconPlay = icon(<path d="M7 4.8v14.4a1 1 0 0 0 1.5.86l11.6-7.2a1 1 0 0 0 0-1.72L8.5 3.94A1 1 0 0 0 7 4.8Z" fill="currentColor" stroke="none" />);
export const IconPause = icon(<><rect x="6" y="4.5" width="4" height="15" rx="1.2" fill="currentColor" stroke="none" /><rect x="14" y="4.5" width="4" height="15" rx="1.2" fill="currentColor" stroke="none" /></>);
export const IconBack = icon(<><path d="M3 12a9 9 0 1 0 2.64-6.36" /><path d="M3 4v4.5h4.5" /></>);
export const IconForward = icon(<><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 4v4.5h-4.5" /></>);
export const IconUpload = icon(<><path d="M12 15V4" /><path d="m7 9 5-5 5 5" /><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" /></>);
export const IconHistory = icon(<><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l3 2" /></>);
export const IconPlus = icon(<><path d="M12 5v14" /><path d="M5 12h14" /></>);
export const IconDownload = icon(<><path d="M12 4v11" /><path d="m7 10 5 5 5-5" /><path d="M4 19h16" /></>);
export const IconFolder = icon(<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />);
export const IconCopy = icon(<><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h8" /></>);
export const IconTrash = icon(<><path d="M4 7h16" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12" /><path d="M9 7V4h6v3" /></>);
export const IconRetry = icon(<><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></>);
export const IconSearch = icon(<><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>);
export const IconChevron = icon(<path d="m6 9 6 6 6-6" />);
export const IconArrowLeft = icon(<><path d="M19 12H5" /><path d="m11 6-6 6 6 6" /></>);
export const IconArrowRight = icon(<><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>);
export const IconCheck = icon(<path d="m5 12.5 4.5 4.5L19 7.5" />);
export const IconWave = icon(<><path d="M4 10v4" /><path d="M8 6v12" /><path d="M12 3v18" /><path d="M16 7v10" /><path d="M20 10v4" /></>);
export const IconSpeaker = icon(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>);
export const IconZoomIn = icon(<><circle cx="11" cy="11" r="7" /><path d="M11 8v6" /><path d="M8 11h6" /><path d="m20 20-3.5-3.5" /></>);
export const IconZoomOut = icon(<><circle cx="11" cy="11" r="7" /><path d="M8 11h6" /><path d="m20 20-3.5-3.5" /></>);
export const IconLock = icon(<><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>);
export const IconX = icon(<><path d="M6 6l12 12" /><path d="M18 6 6 18" /></>);
export const IconFile = icon(<><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" /><path d="M14 3v5h5" /></>);
export const IconKeyboard = icon(<><rect x="3" y="6" width="18" height="12" rx="2" /><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10" /></>);
