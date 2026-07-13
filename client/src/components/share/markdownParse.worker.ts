import { getMarkdown, parseMarkdownToStructure } from 'markstream-vue';

type ParseRequest = {
  id: number;
  content: string;
};

type ParseResponse = {
  id: number;
  nodes?: unknown[];
  error?: string;
};

const workerScope = globalThis as unknown as {
  onmessage: ((event: MessageEvent<ParseRequest>) => void) | null;
  postMessage: (message: ParseResponse) => void;
};
const markdown = getMarkdown();

workerScope.onmessage = (event) => {
  const id = Number(event.data?.id);
  try {
    const nodes = parseMarkdownToStructure(String(event.data?.content || ''), markdown, {
      final: true,
      streamParse: false,
    });
    workerScope.postMessage({ id, nodes });
  } catch (error) {
    workerScope.postMessage({
      id,
      error: error instanceof Error ? error.message : String(error || 'Markdown 解析失败'),
    });
  }
};
