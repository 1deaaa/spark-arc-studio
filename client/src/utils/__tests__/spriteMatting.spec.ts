import { applyChromaKeyMatte, type SpriteMattingPixelFrame } from '@/utils/spriteMatting';

function createFrame(width: number, height: number, color: [number, number, number, number]): SpriteMattingPixelFrame {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let index = 0; index < width * height; index += 1) {
    data.set(color, index * 4);
  }
  return { data, width, height };
}

function setPixel(
  frame: SpriteMattingPixelFrame,
  x: number,
  y: number,
  color: [number, number, number, number],
) {
  frame.data.set(color, (y * frame.width + x) * 4);
}

function getPixel(frame: SpriteMattingPixelFrame, x: number, y: number): number[] {
  const offset = (y * frame.width + x) * 4;
  return Array.from(frame.data.slice(offset, offset + 4));
}

describe('立绘绿幕抠图', () => {
  it('能清除亮度变化的连通绿幕并反混合人物边缘', () => {
    const frame = createFrame(9, 9, [40, 244, 25, 255]);
    for (let x = 0; x < frame.width; x += 1) {
      setPixel(frame, x, frame.height - 1, [72, 217, 52, 255]);
    }

    setPixel(frame, 3, 4, [110, 147, 42, 255]);
    setPixel(frame, 4, 4, [180, 50, 50, 255]);
    setPixel(frame, 5, 4, [110, 147, 42, 255]);
    setPixel(frame, 4, 3, [110, 147, 42, 255]);
    setPixel(frame, 4, 5, [110, 147, 42, 255]);

    applyChromaKeyMatte(frame);

    expect(getPixel(frame, 0, 0)).toEqual([0, 0, 0, 0]);
    expect(getPixel(frame, 0, 8)).toEqual([0, 0, 0, 0]);
    expect(getPixel(frame, 4, 4)).toEqual([180, 50, 50, 255]);

    const edge = getPixel(frame, 3, 4);
    expect(edge[3]).toBeGreaterThan(0);
    expect(edge[3]).toBeLessThan(255);
    expect(edge[1]).toBeLessThanOrEqual(Math.max(edge[0], edge[2]) + 2);
  });

  it('会清零原本就透明的绿像素，避免缩放插值重新产生绿边', () => {
    const frame = createFrame(5, 3, [40, 244, 25, 255]);
    setPixel(frame, 0, 1, [0, 255, 0, 0]);
    setPixel(frame, 1, 1, [180, 50, 50, 255]);

    applyChromaKeyMatte(frame);

    expect(getPixel(frame, 0, 1)).toEqual([0, 0, 0, 0]);
    expect(getPixel(frame, 1, 1)).toEqual([180, 50, 50, 255]);
  });

  it('会清除人物轮廓内未与画面边缘连通的绿幕孔洞', () => {
    const frame = createFrame(11, 11, [40, 244, 25, 255]);
    for (let x = 3; x <= 7; x += 1) {
      setPixel(frame, x, 3, [25, 30, 35, 255]);
      setPixel(frame, x, 7, [25, 30, 35, 255]);
    }
    for (let y = 4; y <= 6; y += 1) {
      setPixel(frame, 3, y, [25, 30, 35, 255]);
      setPixel(frame, 7, y, [25, 30, 35, 255]);
    }

    applyChromaKeyMatte(frame);

    expect(getPixel(frame, 5, 5)).toEqual([0, 0, 0, 0]);
    expect(getPixel(frame, 4, 4)).toEqual([0, 0, 0, 0]);
  });

  it('会保留封闭区域内低绿度的前景细节', () => {
    const frame = createFrame(11, 11, [40, 244, 25, 255]);
    for (let x = 3; x <= 7; x += 1) {
      setPixel(frame, x, 3, [25, 30, 35, 255]);
      setPixel(frame, x, 7, [25, 30, 35, 255]);
    }
    for (let y = 4; y <= 6; y += 1) {
      setPixel(frame, 3, y, [25, 30, 35, 255]);
      setPixel(frame, 7, y, [25, 30, 35, 255]);
    }
    for (let y = 4; y <= 6; y += 1) {
      for (let x = 4; x <= 6; x += 1) {
        setPixel(frame, x, y, [70, 125, 70, 255]);
      }
    }

    applyChromaKeyMatte(frame);

    expect(getPixel(frame, 5, 5)).toEqual([70, 125, 70, 255]);
  });
});
