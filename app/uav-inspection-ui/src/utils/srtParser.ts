export interface TelemetryFrame {
  frameCnt: number
  time: number
  endTime: number
  datetime: string
  latitude: number
  longitude: number
  relAlt: number
  absAlt: number
  gbYaw: number
  gbPitch: number
  gbRoll: number
  iso: number
  shutter: string
  fnum: number
  focalLen: number
}

function toSeconds(timestamp: string): number {
  const match = timestamp.match(/(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/)
  if (!match) return 0
  const [, hh, mm, ss, ms] = match
  return Number(hh) * 3600 + Number(mm) * 60 + Number(ss) + Number(ms) / 1000
}

function extractNumber(source: string, key: string): number {
  const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const patterns = [
    new RegExp(`\\[${escaped}:\\s*([-\\d.]+)\\]`, 'i'),
    new RegExp(`${escaped}:\\s*([-\\d.]+)`, 'i'),
  ]

  for (const pattern of patterns) {
    const match = source.match(pattern)
    if (match) return Number(match[1])
  }
  return 0
}

function extractText(source: string, key: string): string {
  const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const patterns = [
    new RegExp(`\\[${escaped}:\\s*([^\\]]+)\\]`, 'i'),
    new RegExp(`${escaped}:\\s*([^\\s\\]]+)`, 'i'),
  ]

  for (const pattern of patterns) {
    const match = source.match(pattern)
    if (match) return match[1].trim()
  }
  return ''
}

export function parseSrt(content: string): TelemetryFrame[] {
  const normalized = content.replace(/\r\n/g, '\n').trim()
  if (!normalized) return []

  const blocks = normalized.split(/\n{2,}/)
  const frames: TelemetryFrame[] = []

  for (const block of blocks) {
    const lines = block
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)

    if (lines.length < 3) continue

    const timeLine = lines.find((line) => line.includes('-->'))
    if (!timeLine) continue

    const [startRaw = '', endRaw = ''] = timeLine.split('-->').map((part) => part.trim())
    const startTime = toSeconds(startRaw)
    const endTime = toSeconds(endRaw)
    const payload = lines.slice(lines.indexOf(timeLine) + 1).join(' ')

    const datetimeMatch = payload.match(/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})/)

    frames.push({
      frameCnt: extractNumber(payload, 'FrameCnt'),
      time: startTime,
      endTime,
      datetime: datetimeMatch ? datetimeMatch[1] : '',
      latitude: extractNumber(payload, 'latitude'),
      longitude: extractNumber(payload, 'longitude'),
      relAlt: extractNumber(payload, 'rel_alt'),
      absAlt: extractNumber(payload, 'abs_alt'),
      gbYaw: extractNumber(payload, 'gb_yaw'),
      gbPitch: extractNumber(payload, 'gb_pitch'),
      gbRoll: extractNumber(payload, 'gb_roll'),
      iso: extractNumber(payload, 'iso'),
      shutter: extractText(payload, 'shutter'),
      fnum: extractNumber(payload, 'fnum'),
      focalLen: extractNumber(payload, 'focal_len'),
    })
  }

  return frames.filter((frame) => Number.isFinite(frame.time)).sort((a, b) => a.time - b.time)
}

export function findTelemetry(frames: TelemetryFrame[], timeSec: number): TelemetryFrame | null {
  if (frames.length === 0) return null
  let lo = 0
  let hi = frames.length - 1

  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (frames[mid].time <= timeSec) lo = mid
    else hi = mid - 1
  }

  return frames[lo] ?? null
}
