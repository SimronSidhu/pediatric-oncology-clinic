import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function clock(openHour: number, t: number): string {
  const minutes = Math.max(0, Math.floor(openHour * 60 + t));
  const hh = Math.floor(minutes / 60) % 24;
  const mm = minutes % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

export function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}
