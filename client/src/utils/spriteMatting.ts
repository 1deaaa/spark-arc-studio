export type SpriteMattingMode = 'chroma_key' | string;

export type SpriteMattingOptions = {
  mode?: SpriteMattingMode;
  chromaKey?: string;
  threshold?: number;
  feather?: number;
};

export type SpriteMattingPixelFrame = {
  data: Uint8ClampedArray;
  width: number;
  height: number;
};

export type SpriteMattingProvider = (
  source: Blob,
  options: SpriteMattingOptions,
) => Promise<Blob>;

type Rgb = [number, number, number];

const providers = new Map<string, SpriteMattingProvider>();

function parseHexColor(value: string): Rgb {
  const normalized = /^#[0-9a-f]{6}$/i.test(value) ? value.slice(1) : '00ff00';
  return [
    Number.parseInt(normalized.slice(0, 2), 16),
    Number.parseInt(normalized.slice(2, 4), 16),
    Number.parseInt(normalized.slice(4, 6), 16),
  ];
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.max(min, Math.min(max, value));
}

function pixelOffset(index: number): number {
  return index * 4;
}

function greenExcess(data: Uint8ClampedArray, offset: number): number {
  return Math.max(0, data[offset + 1] - Math.max(data[offset], data[offset + 2]));
}

function colorDistance(data: Uint8ClampedArray, offset: number, key: Rgb): number {
  const dr = data[offset] - key[0];
  const dg = data[offset + 1] - key[1];
  const db = data[offset + 2] - key[2];
  return Math.sqrt(dr * dr + dg * dg + db * db);
}

function floodFillBackground(
  candidate: Uint8Array,
  width: number,
  height: number,
): Uint8Array {
  const visited = new Uint8Array(candidate.length);
  const queue = new Uint32Array(candidate.length);
  let head = 0;
  let tail = 0;

  const enqueue = (index: number) => {
    if (!candidate[index] || visited[index]) return;
    visited[index] = 1;
    queue[tail++] = index;
  };

  for (let x = 0; x < width; x += 1) {
    enqueue(x);
    enqueue((height - 1) * width + x);
  }
  for (let y = 0; y < height; y += 1) {
    enqueue(y * width);
    enqueue(y * width + width - 1);
  }

  while (head < tail) {
    const index = queue[head++];
    const x = index % width;
    const y = Math.floor(index / width);
    if (x > 0) enqueue(index - 1);
    if (x + 1 < width) enqueue(index + 1);
    if (y > 0) enqueue(index - width);
    if (y + 1 < height) enqueue(index + width);
  }

  return visited;
}

function findEnclosedGreenBackground(
  candidate: Uint8Array,
  data: Uint8ClampedArray,
  width: number,
  height: number,
  minGreenDominance: number,
): Uint8Array {
  const visited = new Uint8Array(candidate.length);
  const enclosed = new Uint8Array(candidate.length);
  const queue = new Uint32Array(candidate.length);
  const componentThreshold = Math.max(48, minGreenDominance * 5);

  for (let start = 0; start < candidate.length; start += 1) {
    if (!candidate[start] || visited[start]) continue;

    let head = 0;
    let tail = 0;
    let opaqueCount = 0;
    let greenExcessSum = 0;
    let greenSum = 0;
    let nonGreenSum = 0;
    let strongGreenCount = 0;
    let brightGreenCount = 0;
    let touchesEdge = false;
    queue[tail++] = start;
    visited[start] = 1;

    while (head < tail) {
      const index = queue[head++];
      const x = index % width;
      const y = Math.floor(index / width);
      if (x === 0 || x === width - 1 || y === 0 || y === height - 1) touchesEdge = true;

      const offset = pixelOffset(index);
      if (data[offset + 3] > 0) {
        const excess = greenExcess(data, offset);
        const green = data[offset + 1];
        opaqueCount += 1;
        greenExcessSum += excess;
        greenSum += green;
        nonGreenSum += Math.max(data[offset], data[offset + 2]);
        if (excess >= Math.max(60, minGreenDominance * 6)) strongGreenCount += 1;
        if (green >= 150 && excess >= Math.max(48, minGreenDominance * 5)) brightGreenCount += 1;
      }

      if (x > 0) {
        const neighbor = index - 1;
        if (candidate[neighbor] && !visited[neighbor]) {
          visited[neighbor] = 1;
          queue[tail++] = neighbor;
        }
      }
      if (x + 1 < width) {
        const neighbor = index + 1;
        if (candidate[neighbor] && !visited[neighbor]) {
          visited[neighbor] = 1;
          queue[tail++] = neighbor;
        }
      }
      if (y > 0) {
        const neighbor = index - width;
        if (candidate[neighbor] && !visited[neighbor]) {
          visited[neighbor] = 1;
          queue[tail++] = neighbor;
        }
      }
      if (y + 1 < height) {
        const neighbor = index + width;
        if (candidate[neighbor] && !visited[neighbor]) {
          visited[neighbor] = 1;
          queue[tail++] = neighbor;
        }
      }
    }

    if (touchesEdge || opaqueCount < 8) continue;
    const averageGreenExcess = greenExcessSum / opaqueCount;
    const averageGreen = greenSum / opaqueCount;
    const averageNonGreen = nonGreenSum / opaqueCount;
    const strongGreenRatio = strongGreenCount / opaqueCount;
    const brightGreenRatio = brightGreenCount / opaqueCount;
    const backgroundLike = averageGreenExcess >= Math.max(54, componentThreshold)
      && strongGreenRatio >= 0.4
      && brightGreenRatio >= 0.25
      && averageNonGreen / Math.max(1, averageGreen) <= 0.72;
    if (!backgroundLike) continue;

    for (let index = 0; index < tail; index += 1) {
      enclosed[queue[index]] = 1;
    }
  }

  return enclosed;
}

function isNearForeground(
  candidate: Uint8Array,
  index: number,
  width: number,
  height: number,
): boolean {
  const x = index % width;
  const y = Math.floor(index / width);
  for (let dy = -1; dy <= 1; dy += 1) {
    for (let dx = -1; dx <= 1; dx += 1) {
      if (!dx && !dy) continue;
      const nx = x + dx;
      const ny = y + dy;
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
      if (!candidate[ny * width + nx]) return true;
    }
  }
  return false;
}

function isNearBackground(
  backgroundMask: Uint8Array,
  index: number,
  width: number,
  height: number,
  radius: number,
): boolean {
  const x = index % width;
  const y = Math.floor(index / width);
  for (let dy = -radius; dy <= radius; dy += 1) {
    for (let dx = -radius; dx <= radius; dx += 1) {
      if (!dx && !dy) continue;
      const nx = x + dx;
      const ny = y + dy;
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
      if (backgroundMask[ny * width + nx]) return true;
    }
  }
  return false;
}

function estimateBorderBackground(
  data: Uint8ClampedArray,
  backgroundMask: Uint8Array,
  width: number,
  height: number,
  key: Rgb,
  minGreenDominance: number,
): Rgb {
  let red = 0;
  let green = 0;
  let blue = 0;
  let count = 0;
  const add = (index: number) => {
    if (!backgroundMask[index]) return;
    const offset = pixelOffset(index);
    if (data[offset + 3] === 0 || greenExcess(data, offset) < minGreenDominance * 0.5) return;
    red += data[offset];
    green += data[offset + 1];
    blue += data[offset + 2];
    count += 1;
  };

  for (let x = 0; x < width; x += 1) {
    add(x);
    add((height - 1) * width + x);
  }
  for (let y = 1; y + 1 < height; y += 1) {
    add(y * width);
    add(y * width + width - 1);
  }

  if (!count) return key;
  return [red / count, green / count, blue / count];
}

function estimateLocalBackground(
  data: Uint8ClampedArray,
  backgroundMask: Uint8Array,
  index: number,
  width: number,
  height: number,
  fallback: Rgb,
): Rgb {
  const x = index % width;
  const y = Math.floor(index / width);
  const radius = 4;
  let strongestExcess = -1;

  for (let dy = -radius; dy <= radius; dy += 1) {
    for (let dx = -radius; dx <= radius; dx += 1) {
      if (!dx && !dy) continue;
      const nx = x + dx;
      const ny = y + dy;
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
      const neighbor = ny * width + nx;
      const offset = pixelOffset(neighbor);
      if (!backgroundMask[neighbor] || data[offset + 3] === 0) continue;
      strongestExcess = Math.max(strongestExcess, greenExcess(data, offset));
    }
  }

  if (strongestExcess < 0) return fallback;

  let red = 0;
  let green = 0;
  let blue = 0;
  let count = 0;
  const minimumExcess = strongestExcess * 0.78;
  for (let dy = -radius; dy <= radius; dy += 1) {
    for (let dx = -radius; dx <= radius; dx += 1) {
      if (!dx && !dy) continue;
      const nx = x + dx;
      const ny = y + dy;
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
      const neighbor = ny * width + nx;
      const offset = pixelOffset(neighbor);
      if (!backgroundMask[neighbor] || data[offset + 3] === 0) continue;
      if (greenExcess(data, offset) < minimumExcess) continue;
      red += data[offset];
      green += data[offset + 1];
      blue += data[offset + 2];
      count += 1;
    }
  }

  return count ? [red / count, green / count, blue / count] : fallback;
}

function clearPixel(data: Uint8ClampedArray, offset: number) {
  data[offset] = 0;
  data[offset + 1] = 0;
  data[offset + 2] = 0;
  data[offset + 3] = 0;
}

function writeMattePixel(
  data: Uint8ClampedArray,
  offset: number,
  matteAlpha: number,
  background: Rgb,
  backgroundGreenExcess: number,
) {
  const sourceAlpha = data[offset + 3] / 255;
  const alpha = Math.min(sourceAlpha, clamp(matteAlpha));
  if (alpha <= 0.02) {
    clearPixel(data, offset);
    return;
  }

  let red = data[offset];
  let green = data[offset + 1];
  let blue = data[offset + 2];
  if (alpha > 0.12 && alpha < 0.995) {
    const backgroundWeight = 1 - alpha;
    red = (red - backgroundWeight * background[0]) / alpha;
    green = (green - backgroundWeight * background[1]) / alpha;
    blue = (blue - backgroundWeight * background[2]) / alpha;
  }

  red = clamp(red, 0, 255);
  green = clamp(green, 0, 255);
  blue = clamp(blue, 0, 255);
  const spill = Math.max(0, green - Math.max(red, blue));
  if (spill > 0) {
    const strength = clamp((spill - 2) / Math.max(12, backgroundGreenExcess * 0.24));
    green -= spill * strength;
  }

  data[offset] = Math.round(clamp(red, 0, 255));
  data[offset + 1] = Math.round(clamp(green, 0, 255));
  data[offset + 2] = Math.round(clamp(blue, 0, 255));
  data[offset + 3] = Math.round(alpha * 255);
}

function applyGreenChromaKey(
  frame: SpriteMattingPixelFrame,
  key: Rgb,
  threshold: number,
  feather: number,
) {
  const { data, width, height } = frame;
  const size = width * height;
  const minGreenDominance = Math.max(6, Math.min(24, (key[1] - Math.max(key[0], key[2])) * 0.04));
  const candidateLimit = threshold + feather * 2.5;
  const candidate = new Uint8Array(size);

  for (let index = 0; index < size; index += 1) {
    const offset = pixelOffset(index);
    if (data[offset + 3] === 0) {
      candidate[index] = 1;
      continue;
    }
    const isGreenDominant = data[offset + 1] >= data[offset] && data[offset + 1] >= data[offset + 2];
    const hasGreenChroma = greenExcess(data, offset) >= minGreenDominance;
    candidate[index] = hasGreenChroma || (isGreenDominant && colorDistance(data, offset, key) <= candidateLimit) ? 1 : 0;
  }

  const backgroundMask = floodFillBackground(candidate, width, height);
  const fallbackBackground = estimateBorderBackground(
    data,
    backgroundMask,
    width,
    height,
    key,
    minGreenDominance,
  );
  const fallbackGreenExcess = Math.max(
    12,
    fallbackBackground[1] - Math.max(fallbackBackground[0], fallbackBackground[2]),
  );
  const enclosedBackgroundMask = findEnclosedGreenBackground(
    candidate,
    data,
    width,
    height,
    minGreenDominance,
  );

  for (let index = 0; index < size; index += 1) {
    const offset = pixelOffset(index);
    if (enclosedBackgroundMask[index]) {
      clearPixel(data, offset);
      continue;
    }
    if (backgroundMask[index]) {
      if (!isNearForeground(candidate, index, width, height)) {
        clearPixel(data, offset);
        continue;
      }
      const background = estimateLocalBackground(data, backgroundMask, index, width, height, fallbackBackground);
      const backgroundGreenExcess = Math.max(
        12,
        background[1] - Math.max(background[0], background[2]),
      );
      const alpha = clamp(1 - greenExcess(data, offset) / backgroundGreenExcess);
      writeMattePixel(data, offset, alpha, background, backgroundGreenExcess);
      continue;
    }

    if (data[offset + 3] === 0 || greenExcess(data, offset) < 3) continue;
    if (!isNearBackground(backgroundMask, index, width, height, 2)) continue;
    const background = estimateLocalBackground(data, backgroundMask, index, width, height, fallbackBackground);
    const backgroundGreenExcess = Math.max(
      12,
      background[1] - Math.max(background[0], background[2]),
    );
    const alpha = clamp(1 - greenExcess(data, offset) / backgroundGreenExcess);
    if (greenExcess(data, offset) >= minGreenDominance && alpha < 0.995) {
      writeMattePixel(data, offset, alpha, background, backgroundGreenExcess);
    } else {
      const spill = Math.max(0, data[offset + 1] - Math.max(data[offset], data[offset + 2]));
      const strength = clamp((spill - 2) / Math.max(12, fallbackGreenExcess * 0.24));
      data[offset + 1] = Math.round(data[offset + 1] - spill * strength);
    }
  }
}

function applyDistanceChromaKey(
  frame: SpriteMattingPixelFrame,
  key: Rgb,
  threshold: number,
  feather: number,
) {
  const { data, width, height } = frame;
  const size = width * height;
  const candidateLimit = threshold + feather;
  const candidate = new Uint8Array(size);

  for (let index = 0; index < size; index += 1) {
    const offset = pixelOffset(index);
    candidate[index] = data[offset + 3] === 0 || colorDistance(data, offset, key) <= candidateLimit ? 1 : 0;
  }

  const backgroundMask = floodFillBackground(candidate, width, height);
  for (let index = 0; index < size; index += 1) {
    if (!backgroundMask[index]) continue;
    const offset = pixelOffset(index);
    if (data[offset + 3] === 0) {
      clearPixel(data, offset);
      continue;
    }
    const distance = colorDistance(data, offset, key);
    const alpha = clamp((distance - threshold) / Math.max(1, feather));
    if (alpha <= 0.02) {
      clearPixel(data, offset);
      continue;
    }
    data[offset + 3] = Math.round(data[offset + 3] * alpha);
  }
}

export function applyChromaKeyMatte(
  frame: SpriteMattingPixelFrame,
  options: Pick<SpriteMattingOptions, 'chromaKey' | 'threshold' | 'feather'> = {},
) {
  if (!frame.width || !frame.height || frame.data.length < frame.width * frame.height * 4) {
    throw new Error('立绘图片尺寸无效');
  }
  const key = parseHexColor(options.chromaKey || '#00FF00');
  const threshold = Math.max(8, Math.min(180, options.threshold ?? 54));
  const feather = Math.max(4, Math.min(120, options.feather ?? 42));
  if (key[1] >= key[0] && key[1] >= key[2]) {
    applyGreenChromaKey(frame, key, threshold, feather);
  } else {
    applyDistanceChromaKey(frame, key, threshold, feather);
  }
}

async function decodeImage(source: Blob): Promise<ImageBitmap | HTMLImageElement> {
  if (typeof createImageBitmap === 'function') return await createImageBitmap(source);
  const url = URL.createObjectURL(source);
  try {
    return await new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('无法读取立绘图片'));
      image.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function chromaKeyProvider(source: Blob, options: SpriteMattingOptions): Promise<Blob> {
  const image = await decodeImage(source);
  const width = image.width;
  const height = image.height;
  if (!width || !height) throw new Error('立绘图片尺寸无效');

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('浏览器不支持图片抠图画布');
  context.drawImage(image, 0, 0);
  if ('close' in image && typeof image.close === 'function') image.close();

  const frame = context.getImageData(0, 0, width, height);
  applyChromaKeyMatte(frame, options);
  context.putImageData(frame, 0, 0);
  return await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('透明立绘导出失败')), 'image/png');
  });
}

providers.set('chroma_key', chromaKeyProvider);

export function registerSpriteMattingProvider(name: string, provider: SpriteMattingProvider) {
  const key = String(name || '').trim();
  if (!key) throw new Error('抠图 provider 名称不能为空');
  providers.set(key, provider);
}

export async function matteSprite(source: Blob, options: SpriteMattingOptions = {}): Promise<Blob> {
  const mode = options.mode || 'chroma_key';
  const provider = providers.get(mode);
  if (!provider) throw new Error(`未注册的立绘抠图 provider: ${mode}`);
  return await provider(source, options);
}
