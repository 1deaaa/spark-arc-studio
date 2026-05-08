import { computed, ref } from 'vue';
import {
  FALLBACK_IMPORT_CAPABILITIES,
  getImportCapabilities,
  type ImportCapabilitiesResponse,
  type ImportUsage,
} from '@/services/fileImportService';

/**
 * 通用文档导入 composable。
 *
 * 多文件协议：
 * - 优先回调 ``onSelectFiles(files: File[])``（支持多文件场景，如聊天附件）。
 * - 缺失时回落到老的 ``onSelectFile(file: File)``：会逐个 await 调用以保留串行语义。
 * - input 元素若想接受多文件，使用方需自行加 ``:multiple="true"`` 或在模板里设置 ``multiple`` 属性。
 *
 * 多文件中只要有一个不被支持，会触发 ``onInvalidFile`` 一次说明，跳过该文件继续处理其它合法文件。
 */
export function useDocumentImport(options: {
  usage: ImportUsage;
  onSelectFile?: (file: File) => void | Promise<void>;
  onSelectFiles?: (files: File[]) => void | Promise<void>;
  onInvalidFile?: (message: string) => void;
}) {
  const fileInput = ref<HTMLInputElement | null>(null);
  const isDragOver = ref(false);
  const isLoadingCapabilities = ref(false);
  const capabilities = ref<ImportCapabilitiesResponse>(FALLBACK_IMPORT_CAPABILITIES);

  const supportedFormats = computed(() => {
    return capabilities.value.formats[options.usage] || FALLBACK_IMPORT_CAPABILITIES.formats[options.usage] || [];
  });

  const accept = computed(() => {
    return capabilities.value.accept[options.usage] || FALLBACK_IMPORT_CAPABILITIES.accept[options.usage] || '';
  });

  const supportedFormatsLabel = computed(() => supportedFormats.value.join(', '));

  async function loadCapabilities() {
    if (isLoadingCapabilities.value) return;
    isLoadingCapabilities.value = true;
    try {
      capabilities.value = await getImportCapabilities();
    } catch {
      capabilities.value = FALLBACK_IMPORT_CAPABILITIES;
    } finally {
      isLoadingCapabilities.value = false;
    }
  }

  function emitInvalid(message: string) {
    options.onInvalidFile?.(message);
  }

  function isSupportedFile(file: File): boolean {
    const ext = file.name.includes('.') ? `.${file.name.split('.').pop()?.toLowerCase() || ''}` : '';
    return !!ext && supportedFormats.value.includes(ext);
  }

  /** 单文件兼容入口：依然支持老调用方传单文件。 */
  async function selectFile(file: File | null) {
    if (!file) return;
    await selectFiles([file]);
  }

  /** 多文件入口：过滤不支持的文件，剩下的全部交给 onSelectFiles / onSelectFile。 */
  async function selectFiles(files: File[] | null | undefined) {
    if (!files || files.length === 0) return;

    const supported: File[] = [];
    const unsupported: string[] = [];
    for (const file of files) {
      if (!file) continue;
      if (isSupportedFile(file)) {
        supported.push(file);
      } else {
        unsupported.push(file.name);
      }
    }

    if (unsupported.length > 0) {
      // 一次性提示所有被跳过的文件，避免多文件场景下连续弹多条 toast。
      const formatHint = `仅支持 ${supportedFormatsLabel.value} 文件`;
      const message = unsupported.length === 1
        ? `「${unsupported[0]}」${formatHint}`
        : `${unsupported.length} 个文件不被支持（${formatHint}）：${unsupported.map((n) => `「${n}」`).join('、')}`;
      emitInvalid(message);
    }

    if (supported.length === 0) return;

    if (options.onSelectFiles) {
      await options.onSelectFiles(supported);
    } else if (options.onSelectFile) {
      // 老回调签名兜底：串行调用每个文件。
      for (const file of supported) {
        await options.onSelectFile(file);
      }
    }
  }

  async function handleFileChange(event: Event) {
    const target = event.target as HTMLInputElement | null;
    const files = target?.files ? Array.from(target.files) : [];
    await selectFiles(files);
    if (target) target.value = '';
  }

  async function handleDrop(event: DragEvent) {
    isDragOver.value = false;
    const files = event.dataTransfer?.files ? Array.from(event.dataTransfer.files) : [];
    await selectFiles(files);
  }

  function triggerFileInput() {
    fileInput.value?.click();
  }

  return {
    fileInput,
    isDragOver,
    isLoadingCapabilities,
    supportedFormats,
    supportedFormatsLabel,
    accept,
    loadCapabilities,
    handleFileChange,
    handleDrop,
    triggerFileInput,
    selectFile,
    selectFiles,
  };
}
