let fullFontCssPromise: Promise<unknown> | null = null;

export function ensureFullAppFontCss(): Promise<unknown> {
  if (!fullFontCssPromise) {
    fullFontCssPromise = import('cn-fontsource-lxgw-wen-kai-screen/font.css').then((module) => {
      if (typeof document !== 'undefined') {
        document.body.classList.add('app-font-ready');
      }
      return module;
    });
  }
  return fullFontCssPromise;
}
