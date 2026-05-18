export interface DeepSignalResult {
  webglPixelHash: string | null
  webglParams: Record<string, number> | null
  audioHash: number | null
  cpuMathExtended: Record<string, number> | null
  noiseDetected: boolean
}

function fnv1aHash(data: Uint8Array): string {
  let hash = 0x811c9dc5
  for (let i = 0; i < data.length; i++) {
    hash ^= data[i]
    hash = Math.imul(hash, 0x01000193)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

function hashFloat32(data: Float32Array): number {
  let h = 0
  const view = new DataView(new ArrayBuffer(4))
  for (let i = 0; i < data.length; i++) {
    view.setFloat32(0, data[i])
    h = ((h << 5) - h + view.getInt32(0)) | 0
  }
  return h
}

const VERT_SRC = 'attribute vec2 a;attribute vec3 b;varying vec3 c;void main(){gl_Position=vec4(a,0,1);c=b;}'
const FRAG_SRC = 'precision mediump float;varying vec3 c;void main(){gl_FragColor=vec4(c,1);}'

function compileShader(gl: WebGLRenderingContext, type: number, src: string): WebGLShader | null {
  const s = gl.createShader(type)
  if (!s) return null
  gl.shaderSource(s, src)
  gl.compileShader(s)
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    gl.deleteShader(s)
    return null
  }
  return s
}

function renderTriangle(gl: WebGLRenderingContext): Uint8Array | null {
  const vs = compileShader(gl, gl.VERTEX_SHADER, VERT_SRC)
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, FRAG_SRC)
  if (!vs || !fs) return null

  const prog = gl.createProgram()
  if (!prog) return null
  gl.attachShader(prog, vs)
  gl.attachShader(prog, fs)
  gl.linkProgram(prog)
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return null
  gl.useProgram(prog)

  const verts = new Float32Array([
    -0.5, -0.5, 1, 0, 0,
     0.5, -0.5, 0, 1, 0,
     0.0,  0.5, 0, 0, 1,
  ])

  const buf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, buf)
  gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STATIC_DRAW)

  const posLoc = gl.getAttribLocation(prog, 'a')
  const colLoc = gl.getAttribLocation(prog, 'b')
  gl.enableVertexAttribArray(posLoc)
  gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 20, 0)
  gl.enableVertexAttribArray(colLoc)
  gl.vertexAttribPointer(colLoc, 3, gl.FLOAT, false, 20, 8)

  gl.viewport(0, 0, 64, 64)
  gl.clearColor(0.2, 0.3, 0.4, 1.0)
  gl.clear(gl.COLOR_BUFFER_BIT)
  gl.drawArrays(gl.TRIANGLES, 0, 3)

  const pixels = new Uint8Array(64 * 64 * 4)
  gl.readPixels(0, 0, 64, 64, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
  return pixels
}

function collectWebGLDeep(): {
  hash: string
  params: Record<string, number>
  noiseDetected: boolean
} | null {
  try {
    const canvas = document.createElement('canvas')
    canvas.width = 64
    canvas.height = 64
    const gl = canvas.getContext('webgl', {
      preserveDrawingBuffer: true,
      premultipliedAlpha: false,
    })
    if (!gl) return null

    try {
      const p: Record<string, number> = {}

      const precisions: Array<[string, number, number]> = [
        ['vhf', gl.VERTEX_SHADER, gl.HIGH_FLOAT],
        ['vmf', gl.VERTEX_SHADER, gl.MEDIUM_FLOAT],
        ['vlf', gl.VERTEX_SHADER, gl.LOW_FLOAT],
        ['fhf', gl.FRAGMENT_SHADER, gl.HIGH_FLOAT],
        ['fmf', gl.FRAGMENT_SHADER, gl.MEDIUM_FLOAT],
        ['flf', gl.FRAGMENT_SHADER, gl.LOW_FLOAT],
      ]

      for (const [n, st, pt] of precisions) {
        const f = gl.getShaderPrecisionFormat(st, pt)
        if (f) {
          p[n + 'r'] = f.rangeMin
          p[n + 'R'] = f.rangeMax
          p[n + 'p'] = f.precision
        }
      }

      p['mts'] = gl.getParameter(gl.MAX_TEXTURE_SIZE) as number
      p['mrbs'] = gl.getParameter(gl.MAX_RENDERBUFFER_SIZE) as number
      p['mcTS'] = gl.getParameter(gl.MAX_CUBE_MAP_TEXTURE_SIZE) as number
      p['mtiu'] = gl.getParameter(gl.MAX_TEXTURE_IMAGE_UNITS) as number
      p['mvtiu'] = gl.getParameter(gl.MAX_VERTEX_TEXTURE_IMAGE_UNITS) as number
      p['mctiu'] = gl.getParameter(gl.MAX_COMBINED_TEXTURE_IMAGE_UNITS) as number
      p['mva'] = gl.getParameter(gl.MAX_VERTEX_ATTRIBS) as number
      p['mvv'] = gl.getParameter(gl.MAX_VARYING_VECTORS) as number
      p['mvuv'] = gl.getParameter(gl.MAX_VERTEX_UNIFORM_VECTORS) as number
      p['mfuv'] = gl.getParameter(gl.MAX_FRAGMENT_UNIFORM_VECTORS) as number

      const vpd = gl.getParameter(gl.MAX_VIEWPORT_DIMS) as Int32Array | null
      if (vpd) {
        p['vpd0'] = vpd[0]
        p['vpd1'] = vpd[1]
      }

      const alwr = gl.getParameter(gl.ALIASED_LINE_WIDTH_RANGE) as Float32Array | null
      if (alwr) {
        p['alwr0'] = alwr[0]
        p['alwr1'] = alwr[1]
      }

      const apsr = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE) as Float32Array | null
      if (apsr) {
        p['apsr0'] = apsr[0]
        p['apsr1'] = apsr[1]
      }

      const pixels1 = renderTriangle(gl)
      const pixels2 = renderTriangle(gl)

      if (!pixels1 || !pixels2) return null

      const hash1 = fnv1aHash(pixels1)
      const hash2 = fnv1aHash(pixels2)

      return { hash: hash1, params: p, noiseDetected: hash1 !== hash2 }
    } finally {
      const ext = gl.getExtension('WEBGL_lose_context')
      if (ext) ext.loseContext()
    }
  } catch {
    return null
  }
}

async function collectAudioHash(): Promise<number | null> {
  try {
    const ctx = new OfflineAudioContext(1, 44100, 44100)
    const osc = ctx.createOscillator()
    osc.type = 'triangle'
    osc.frequency.value = 440
    osc.connect(ctx.destination)
    osc.start(0)
    const buffer = await ctx.startRendering()
    return hashFloat32(buffer.getChannelData(0))
  } catch {
    return null
  }
}

function collectCPUMathExtended(): Record<string, number> {
  const r: Record<string, number> = {}
  r['tan'] = Math.tan(Math.PI / 4)
  r['sin'] = Math.sin(Math.PI / 6)
  r['cos'] = Math.cos(Math.PI / 3)
  r['log'] = Math.log(2)
  r['exp'] = Math.exp(1)
  r['sqrt'] = Math.sqrt(2)
  r['pow'] = Math.pow(2, 0.5)
  r['cbrt'] = Math.cbrt(3)
  r['hypot'] = Math.hypot(3, 4)
  r['atan2'] = Math.atan2(1, 1)
  r['fround'] = Math.fround(1.337)
  return r
}

export async function collectDeepSignals(): Promise<DeepSignalResult> {
  const webgl = collectWebGLDeep()
  const audio = await collectAudioHash()
  const cpuMath = collectCPUMathExtended()

  return {
    webglPixelHash: webgl?.hash ?? null,
    webglParams: webgl?.params ?? null,
    audioHash: audio,
    cpuMathExtended: cpuMath,
    noiseDetected: webgl?.noiseDetected ?? false,
  }
}
