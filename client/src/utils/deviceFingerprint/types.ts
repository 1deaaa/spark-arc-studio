export interface DeviceIdResult {
  deviceId: string
  browserId: string
  hardwareId: string
  signals: Record<string, unknown>
  confidence: number
  noiseDetected: boolean
  timestamp: number
}
