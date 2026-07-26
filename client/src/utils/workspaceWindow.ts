const WORKSPACE_WINDOW_PARAM = 'spark_workspace_window';

function parseAbsoluteUrl(input: string): URL | null {
  try {
    return new URL(input);
  } catch {
    return null;
  }
}

export function markWorkspaceWindow(targetUrl: string): string {
  const url = parseAbsoluteUrl(targetUrl);
  if (!url) return targetUrl;
  url.searchParams.set(WORKSPACE_WINDOW_PARAM, '1');
  return url.toString();
}

export function hasWorkspaceWindowMarker(
  inputUrl = typeof window !== 'undefined' ? window.location.href : '',
): boolean {
  const url = parseAbsoluteUrl(inputUrl);
  return url?.searchParams.get(WORKSPACE_WINDOW_PARAM) === '1';
}

export function preserveWorkspaceWindow(targetUrl: string, sourceUrl: string): string {
  return hasWorkspaceWindowMarker(sourceUrl) ? markWorkspaceWindow(targetUrl) : targetUrl;
}
