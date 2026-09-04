export type ModuleThemeKey =
  | 'telecom'
  | 'power'
  | 'roof'
  | 'wall'
  | 'pest'
  | 'pruning'
  | 'height'
  | 'area'
  | 'roseDigital'
  | 'roseYield'
  | 'roseFlow'

export interface ModuleTheme {
  accent: string
  badge: string
  card: string
  gradient: string
  hover: string
  icon: string
  ring: string
  soft: string
  text: string
}

export const moduleThemes: Record<ModuleThemeKey, ModuleTheme> = {
  telecom: {
    accent: 'bg-blue-600',
    badge: 'border-blue-200 bg-blue-50 text-blue-700',
    card: 'bg-blue-50/75 border-blue-200/80 shadow-blue-500/10',
    gradient: 'from-blue-500 to-indigo-500',
    hover: 'hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700',
    icon: 'text-blue-600',
    ring: 'ring-blue-200',
    soft: 'bg-blue-50',
    text: 'text-blue-700',
  },
  power: {
    accent: 'bg-amber-500',
    badge: 'border-amber-200 bg-amber-50 text-amber-700',
    card: 'bg-amber-50/75 border-amber-200/80 shadow-amber-500/10',
    gradient: 'from-amber-400 to-orange-400',
    hover: 'hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700',
    icon: 'text-amber-600',
    ring: 'ring-amber-200',
    soft: 'bg-amber-50',
    text: 'text-amber-700',
  },
  roof: {
    accent: 'bg-cyan-500',
    badge: 'border-cyan-200 bg-cyan-50 text-cyan-700',
    card: 'bg-cyan-50/75 border-cyan-200/80 shadow-cyan-500/10',
    gradient: 'from-cyan-400 to-sky-400',
    hover: 'hover:border-cyan-300 hover:bg-cyan-50 hover:text-cyan-700',
    icon: 'text-cyan-600',
    ring: 'ring-cyan-200',
    soft: 'bg-cyan-50',
    text: 'text-cyan-700',
  },
  wall: {
    accent: 'bg-teal-500',
    badge: 'border-teal-200 bg-teal-50 text-teal-700',
    card: 'bg-teal-50/75 border-teal-200/80 shadow-teal-500/10',
    gradient: 'from-teal-500 to-emerald-500',
    hover: 'hover:border-teal-300 hover:bg-teal-50 hover:text-teal-700',
    icon: 'text-teal-600',
    ring: 'ring-teal-200',
    soft: 'bg-teal-50',
    text: 'text-teal-700',
  },
  pest: {
    accent: 'bg-rose-500',
    badge: 'border-rose-200 bg-rose-50 text-rose-700',
    card: 'bg-rose-50/75 border-rose-200/80 shadow-rose-500/10',
    gradient: 'from-rose-500 to-red-500',
    hover: 'hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700',
    icon: 'text-rose-600',
    ring: 'ring-rose-200',
    soft: 'bg-rose-50',
    text: 'text-rose-700',
  },
  pruning: {
    accent: 'bg-emerald-500',
    badge: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    card: 'bg-emerald-50/75 border-emerald-200/80 shadow-emerald-500/10',
    gradient: 'from-emerald-500 to-green-400',
    hover: 'hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700',
    icon: 'text-emerald-600',
    ring: 'ring-emerald-200',
    soft: 'bg-emerald-50',
    text: 'text-emerald-700',
  },
  height: {
    accent: 'bg-violet-500',
    badge: 'border-violet-200 bg-violet-50 text-violet-700',
    card: 'bg-violet-50/75 border-violet-200/80 shadow-violet-500/10',
    gradient: 'from-violet-500 to-purple-500',
    hover: 'hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700',
    icon: 'text-violet-600',
    ring: 'ring-violet-200',
    soft: 'bg-violet-50',
    text: 'text-violet-700',
  },
  area: {
    accent: 'bg-lime-500',
    badge: 'border-lime-200 bg-lime-50 text-lime-700',
    card: 'bg-lime-50/75 border-lime-200/80 shadow-lime-500/10',
    gradient: 'from-lime-500 to-green-500',
    hover: 'hover:border-lime-300 hover:bg-lime-50 hover:text-lime-700',
    icon: 'text-lime-600',
    ring: 'ring-lime-200',
    soft: 'bg-lime-50',
    text: 'text-lime-700',
  },
  roseDigital: {
    accent: 'bg-fuchsia-500',
    badge: 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700',
    card: 'bg-fuchsia-50/75 border-fuchsia-200/80 shadow-fuchsia-500/10',
    gradient: 'from-fuchsia-500 to-pink-500',
    hover: 'hover:border-fuchsia-300 hover:bg-fuchsia-50 hover:text-fuchsia-700',
    icon: 'text-fuchsia-600',
    ring: 'ring-fuchsia-200',
    soft: 'bg-fuchsia-50',
    text: 'text-fuchsia-700',
  },
  roseYield: {
    accent: 'bg-pink-500',
    badge: 'border-pink-200 bg-pink-50 text-pink-700',
    card: 'bg-pink-50/75 border-pink-200/80 shadow-pink-500/10',
    gradient: 'from-pink-500 to-rose-500',
    hover: 'hover:border-pink-300 hover:bg-pink-50 hover:text-pink-700',
    icon: 'text-pink-600',
    ring: 'ring-pink-200',
    soft: 'bg-pink-50',
    text: 'text-pink-700',
  },
  roseFlow: {
    accent: 'bg-sky-500',
    badge: 'border-sky-200 bg-sky-50 text-sky-700',
    card: 'bg-sky-50/75 border-sky-200/80 shadow-sky-500/10',
    gradient: 'from-sky-500 to-cyan-500',
    hover: 'hover:border-sky-300 hover:bg-sky-50 hover:text-sky-700',
    icon: 'text-sky-600',
    ring: 'ring-sky-200',
    soft: 'bg-sky-50',
    text: 'text-sky-700',
  },
}
