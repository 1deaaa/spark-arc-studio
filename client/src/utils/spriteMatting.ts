export type SpriteMattingMode = 'chroma_key' | string;

export type SpriteMattingOptions = {
  mode?: SpriteMattingMode;
  chromaKey?: string;
  threshold?: number;
  feather?: number;
};

export type SpriteMattingProvider = (
  source: Blob,
  options: SpriteMattingOptions,
) => Promise<Blob>;

const providers = new Map<string, SpriteMattingProvider>();

function parseHexColor(value: string): [number, number, number] {
  const normalized = /^#[0-9a-f]{6}$/i.test(value) ? value.slice(1) : '00ff00';
  return [
    Number.parseInt(normalized.slice(0, 2), 16),
    Number.parseInt(normalized.slice(2, 4), 16),
    Number.parseInt(normalized.slice(4, 6), 16),
  ];
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
  const pixels = frame.data;
  const [keyR, keyG, keyB] = parseHexColor(options.chromaKey || '#00FF00');
  const threshold = Math.max(8, Math.min(180, options.threshold ?? 54));
  const feather = Math.max(4, Math.min(120, options.feather ?? 42));
  const candidateLimit = threshold + feather;
  const visited = new Uint8Array(width * height);
  const queue = new Uint32Array(width * height);
  let head = 0;
  let tail = 0;

  const colorDistance = (pixelIndex: number) => {
    const offset = pixelIndex * 4;
    const dr = pixels[offset] - keyR;
    const dg = pixels[offset + 1] - keyG;
    const db = pixels[offset + 2] - keyB;
    return Math.sqrt(dr * dr + dg * dg + db * db);
  };
  const enqueue = (pixelIndex: number) => {
    if (visited[pixelIndex] || colorDistance(pixelIndex) > candidateLimit) return;
    visited[pixelIndex] = 1;
    queue[tail++] = pixelIndex;
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
    const pixelIndex = queue[head++];
    const x = pixelIndex % width;
    const y = Math.floor(pixelIndex / width);
    if (x > 0) enqueue(pixelIndex - 1);
    if (x + 1 < width) enqueue(pixelIndex + 1);
    if (y > 0) enqueue(pixelIndex - width);
    if (y + 1 < height) enqueue(pixelIndex + width);
  }

  for (let pixelIndex = 0; pixelIndex < visited.length; pixelIndex += 1) {
    if (!visited[pixelIndex]) continue;
    const offset = pixelIndex * 4;
    const distance = colorDistance(pixelIndex);
    const factor = distance <= threshold ? 0 : (distance - threshold) / feather;
    pixels[offset + 3] = Math.round(pixels[offset + 3] * Math.max(0, Math.min(1, factor)));
    if (factor > 0 && factor < 1 && keyG > keyR && keyG > keyB) {
      const neutralGreen = Math.max(pixels[offset], pixels[offset + 2]);
      pixels[offset + 1] = Math.round(pixels[offset + 1] * factor + neutralGreen * (1 - factor));
    }
  }

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
