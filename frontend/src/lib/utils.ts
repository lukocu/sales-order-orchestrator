import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

// Joins class names and lets the last conflicting Tailwind utility win (shadcn convention).
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
