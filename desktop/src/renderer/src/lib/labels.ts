// Human-readable names for the backend's identifiers (stages, steps, object types, recipes).
import { mark, tr } from './i18n'

export const STAGE_LABELS: Record<string, string> = {
  channels: mark('通道对齐与合成'),
  color: mark('色彩校准'),
  lum: mark('亮度通道 (L)'),
  linear: mark('线性处理'),
  stretch: mark('拉伸'),
  stars: mark('去星'),
  starless: mark('无星图增强'),
  stars_color: mark('星点色彩'),
  combine: mark('合成成品')
}

export const STEP_LABELS: Record<string, string> = {
  locate_object: mark('定位目标'),
  find_background: mark('寻找背景区域'),
  gradient_correction: mark('梯度校正 (GC)'),
  dbe_auto: mark('自动 DBE'),
  abe: 'ABE',
  color_calibration: mark('色彩校准 (SPCC/BNCC)'),
  spcc: 'SPCC',
  bncc: 'BNCC',
  preview: mark('预览图'),
  bxt: 'BlurXTerminator',
  nxt: 'NoiseXTerminator',
  sxt: 'StarXTerminator',
  stretch: mark('拉伸'),
  ht: mark('直方图变换'),
  lhe: mark('局部直方图均衡 (LHE)'),
  curves: mark('曲线'),
  saturation: mark('饱和度'),
  usm: mark('USM 锐化'),
  scnr: 'SCNR',
  hdr: mark('HDR 压缩'),
  pixelmath: 'PixelMath',
  split_stars: mark('分离星点'),
  recombine: mark('星点合并'),
  crop: mark('裁切'),
  plate_solve: mark('板解析'),
  align_channels: mark('通道对齐'),
  crop_common: mark('裁到共同区域'),
  combine_rgb: mark('合成彩色 (RGB)'),
  lrgb: mark('LRGB 合成')
}

export const TYPE_LABELS: Record<string, string> = {
  emission_nebula: mark('发射星云'),
  reflection_nebula: mark('反射星云'),
  planetary_nebula: mark('行星状星云'),
  supernova_remnant: mark('超新星遗迹'),
  dark_nebula: mark('暗星云'),
  galaxy: mark('星系'),
  comet: mark('彗星'),
  unknown: mark('未知类型')
}

export const RECIPE_LABELS: Record<string, string> = {
  osc_broadband_nebula: mark('宽带星云'),
  osc_galaxy: mark('星系'),
  osc_multiband_nebula: mark('多波段星云'),
  comet: mark('彗星'),
  mono_lrgb_galaxy: mark('黑白 LRGB 星系'),
  mono_lrgb_nebula: mark('黑白 LRGB 星云')
}

export const JOB_STATE_LABELS: Record<string, string> = {
  queued: mark('排队中'),
  running: mark('运行中'),
  done: mark('完成'),
  failed: mark('失败'),
  cancelled: mark('已取消')
}

export const STORAGE_PART_LABELS: Record<string, { name: string; hint: string }> = {
  frames: { name: mark('原始帧'), hint: mark('光照帧和校准帧，不会删除') },
  masters: { name: mark('叠加结果'), hint: mark('WBPP 的主帧，处理从这里开始') },
  wbpp_frames: { name: mark('WBPP 中间单帧'), hint: mark('校准、去马赛克、配准后的单帧，重新叠加会再生成') },
  checkpoints: { name: mark('处理中间结果'), hint: mark('各阶段的中间图（最终成品除外），重跑时自动补回') },
  results: { name: mark('成品和预览'), hint: mark('成品图、预览、分享图') }
}

/** The name of an identifier in the current language (the maps hold the marked Chinese names). */
export const label = (map: Record<string, string>, key: string | null | undefined): string =>
  key ? (map[key] ? tr(map[key]) : key) : '—'

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  if (seconds < 60) return tr('{s} 秒', { s: Math.round(seconds) })
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m < 60 ? tr('{m} 分 {s} 秒', { m, s }) : tr('{h} 小时 {m} 分', { h: Math.floor(m / 60), m: m % 60 })
}

/** "Running: M8: stage starless · PixInsight" for a job shown next to the thing it works on. */
export function runningText(job: { title: string; progress?: string | null }): string {
  return tr('正在运行：{job}', { job: job.title + (job.progress ? ` · ${job.progress}` : '') })
}

export function basename(path: string): string {
  return path.split(/[\\/]/).pop() ?? path
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024 ** 2) return `${Math.round(bytes / 1024)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(0)} MB`
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`
}

/** '2026May17' -> '2026-05-17' (other folder names unchanged). */
export function nightLabel(night: string): string {
  const m = /^(\d{4})([A-Z][a-z]{2})(\d{2})$/.exec(night)
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  if (!m || !months.includes(m[2])) return night
  return `${m[1]}-${String(months.indexOf(m[2]) + 1).padStart(2, '0')}-${m[3]}`
}
