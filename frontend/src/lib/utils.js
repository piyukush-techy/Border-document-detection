import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function dataUrlToBlob(dataUrl) {
  const [header, base64] = dataUrl.split(",");
  const mime = header.match(/data:(.*?);base64/)[1];
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

export function hexChars(n) {
  const chars = "0123456789abcdef";
  let out = "";
  for (let i = 0; i < n; i++) out += chars[Math.floor(Math.random() * 16)];
  return out;
}

export function truncateHash(h) {
  if (!h) return "—";
  return `${h.slice(0, 10)}…${h.slice(-8)}`;
}

export function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

export function verdictFromScore(score) {
  if (score >= 75) return "GENUINE";
  if (score >= 45) return "SUSPICIOUS";
  return "FAKE";
}

export function formatTimestamp(timestamp) {
  if (!timestamp) return "—";
  return new Date(timestamp).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: 'UTC'
  }) + " UTC";
}