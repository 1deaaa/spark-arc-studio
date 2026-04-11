import { config } from '@vue/test-utils';

type GlobalWithOptionalDomException = typeof globalThis & {
  DOMException?: typeof DOMException;
};

try {
  localStorage.setItem('spark_locale', 'zh-CN');
} catch {
  // jsdom normally provides localStorage; keep tests resilient in leaner DOM shims.
}

if (!globalThis.requestAnimationFrame) {
  globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
}

if (!globalThis.cancelAnimationFrame) {
  globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
}

if (!globalThis.DOMException) {
  const testGlobal = globalThis as GlobalWithOptionalDomException;
  testGlobal.DOMException = class DOMException extends Error {
    constructor(message = '', name = 'Error') {
      super(message);
      this.name = name;
    }
  } as unknown as typeof DOMException;
}

config.global.stubs = {
  transition: false,
};
