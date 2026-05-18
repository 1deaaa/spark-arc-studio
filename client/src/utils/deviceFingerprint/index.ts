import FingerprintJS from '@fingerprintjs/fingerprintjs'
import { computeDeviceId, computeBrowserId, computeHardwareId, computeConfidence, extractSignals } from './hasher'
import { collectDeepSignals } from './deepSignals'
import type { DeviceIdResult } from './types'

export type { DeviceIdResult } from './types'

let fpPromise: ReturnType<typeof FingerprintJS.load> | null = null

export function preloadDeviceId(): void {
  if (!fpPromise) fpPromise = FingerprintJS.load()
}

export async function getDeviceId(): Promise<DeviceIdResult> {
  if (!fpPromise) fpPromise = FingerprintJS.load()
  const fp = await fpPromise
  const result = await fp.get()

  const deep = await collectDeepSignals()

  const components: Record<string, { value?: unknown; error?: unknown }> = {
    ...result.components,
  }

  if (deep.webglPixelHash) {
    components.deepWebglPixelHash = { value: deep.webglPixelHash }
  }
  if (deep.webglParams) {
    components.deepWebglParams = { value: deep.webglParams }
  }
  if (deep.cpuMathExtended) {
    components.deepCpuMathExtended = { value: deep.cpuMathExtended }
  }
  if (deep.audioHash != null) {
    components.deepAudioHash = { value: deep.audioHash }
  }

  const hardwareId = computeHardwareId(components)
  const deviceId = computeDeviceId(components)
  const browserId = computeBrowserId(components)
  const signals = extractSignals(components)
  const confidence = computeConfidence(components)

  return {
    deviceId,
    browserId,
    hardwareId,
    signals,
    confidence,
    noiseDetected: deep.noiseDetected,
    timestamp: Date.now(),
  }
}
