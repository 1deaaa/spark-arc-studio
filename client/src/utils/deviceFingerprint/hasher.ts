import FingerprintJS from '@fingerprintjs/fingerprintjs'

type Components = Record<string, { value?: unknown; error?: unknown }>

const DEEP_HARDWARE_KEYS = [
  'deepWebglPixelHash',
  'deepWebglParams',
  'deepCpuMathExtended',
  'deepAudioHash',
]

const HARDWARE_KEYS = [
  ...DEEP_HARDWARE_KEYS,
  'hardwareConcurrency',
  'deviceMemory',
  'screenResolution',
  'screenFrame',
  'colorDepth',
  'timezone',
  'platform',
  'osCpu',
  'colorGamut',
  'monochrome',
  'contrast',
  'hdr',
  'math',
  'architecture',
  'dateTimeLocale',
]

const BROWSER_EXTRA_KEYS = [
  'webGlBasics',
  'canvas',
  'audio',
  'fonts',
  'fontPreferences',
  'plugins',
  'touchSupport',
]

function pickComponents(all: Components, keys: string[]): Components {
  const result: Components = {}
  for (const key of keys) {
    const comp = all[key]
    if (comp && 'value' in comp) {
      result[key] = comp
    }
  }
  return result
}

export function computeHardwareId(components: Components): string {
  const deep = pickComponents(components, DEEP_HARDWARE_KEYS)
  return FingerprintJS.hashComponents(deep as Parameters<typeof FingerprintJS.hashComponents>[0])
}

export function computeDeviceId(components: Components): string {
  const stable = pickComponents(components, HARDWARE_KEYS)
  return FingerprintJS.hashComponents(stable as Parameters<typeof FingerprintJS.hashComponents>[0])
}

export function computeBrowserId(components: Components): string {
  const all = pickComponents(components, [...HARDWARE_KEYS, ...BROWSER_EXTRA_KEYS])
  return FingerprintJS.hashComponents(all as Parameters<typeof FingerprintJS.hashComponents>[0])
}

export function extractSignals(components: Components): Record<string, unknown> {
  const signals: Record<string, unknown> = {}
  for (const key of HARDWARE_KEYS) {
    const comp = components[key]
    signals[key] = comp && 'value' in comp ? comp.value : null
  }
  return signals
}

export function computeConfidence(components: Components): number {
  let score = 0.5

  const webgl = components.webGlBasics
  if (webgl && 'value' in webgl && webgl.value) {
    score += 0.1
  }

  const deepWebgl = components.deepWebglPixelHash
  if (deepWebgl && 'value' in deepWebgl && deepWebgl.value) {
    score += 0.1
  }

  const mem = components.deviceMemory
  if (mem && 'value' in mem && mem.value != null) {
    score += 0.05
  }

  const cpu = components.hardwareConcurrency
  if (cpu && 'value' in cpu && typeof cpu.value === 'number' && cpu.value > 0) {
    score += 0.1
  }

  const screen = components.screenResolution
  if (screen && 'value' in screen && Array.isArray(screen.value) && screen.value.length === 2) {
    score += 0.1
  }

  const tz = components.timezone
  if (tz && 'value' in tz && tz.value) {
    score += 0.05
  }

  return Math.min(score, 1.0)
}
