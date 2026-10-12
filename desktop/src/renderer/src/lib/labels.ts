// Human-readable names for the backend's identifiers (stages, steps, object types, recipes).
export const STAGE_LABELS: Record<string, string> = {
  linear: '线性处理',
  stretch: '拉伸',
  stars: '去星',
  starless: '无星图增强',
  stars_color: '星点色彩',
  combine: '合成成品'
}

export const STEP_LABELS: Record<string, string> = {
  locate_object: '定位目标',
  find_background: '寻找背景区域',
  gradient_correction: '梯度校正 (GC)',
  dbe_auto: '自动 DBE',
  abe: 'ABE',
  color_calibration: '色彩校准 (SPCC/BNCC)',
  spcc: 'SPCC',
  bncc: 'BNCC',
  preview: '预览图',
  bxt: 'BlurXTerminator',
  nxt: 'NoiseXTerminator',
  sxt: 'StarXTerminator',
  stretch: '拉伸',
  ht: '直方图变换',
  lhe: '局部直方图均衡 (LHE)',
  curves: '曲线',
  saturation: '饱和度',
  usm: 'USM 锐化',
  scnr: 'SCNR',
  hdr: 'HDR 压缩',
  pixelmath: 'PixelMath',
  split_stars: '分离星点',
  recombine: '星点合并',
  crop: '裁切'
}

export const TYPE_LABELS: Record<string, string> = {
  emission_nebula: '发射星云',
  reflection_nebula: '反射星云',
  planetary_nebula: '行星状星云',
  supernova_remnant: '超新星遗迹',
  dark_nebula: '暗星云',
  galaxy: '星系',
  comet: '彗星',
  unknown: '未知类型'
}

export const RECIPE_LABELS: Record<string, string> = {
  osc_broadband_nebula: '宽带星云',
  osc_galaxy: '星系',
  osc_multiband_nebula: '多波段星云',
  comet: '彗星'
}

export const JOB_STATE_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '运行中',
  done: '完成',
  failed: '失败',
  cancelled: '已取消'
}

export const label = (map: Record<string, string>, key: string | null | undefined): string =>
  key ? (map[key] ?? key) : '—'

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m < 60 ? `${m} 分 ${s} 秒` : `${Math.floor(m / 60)} 小时 ${m % 60} 分`
}

export function basename(path: string): string {
  return path.split(/[\\/]/).pop() ?? path
}
