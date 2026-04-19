import { computed, ref } from 'vue';
import {
  FALLBACK_IMPORT_CAPABILITIES,
  getImportCapabilities,
  type ImportCapabilitiesResponse,
  type ImportUsage,
} from '@/services/fileImportService';

export function useDocumentImport(options: {
  usage: ImportUsage;
  onSelectFile: (file: File) => void | Promise<void>;
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

  async function selectFile(file: File | null) {
    if (!file) return;
    if (!isSupportedFile(file)) {
      emitInvalid(`仅支持 ${supportedFormatsLabel.value} 文件`);
      return;
    }
    await options.onSelectFile(file);
  }

  async function handleFileChange(event: Event) {
    const target = event.target as HTMLInputElement | null;
    const file = target?.files?.[0] || null;
    await selectFile(file);
    if (target) target.value = '';
  }

  async function handleDrop(event: DragEvent) {
    isDragOver.value = false;
    const file = event.dataTransfer?.files?.[0] || null;
    await selectFile(file);
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
  };
}
