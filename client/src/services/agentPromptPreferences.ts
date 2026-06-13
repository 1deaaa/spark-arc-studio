import { fetchWithAuth } from './api';

export type PromptPreferenceState = {
  agent_id: string;
  guardrail: string;
  default_content: string;
  override_content: string;
  effective_content: string;
  enabled: boolean;
  customized: boolean;
  updated_at?: string | null;
};

export async function fetchAgentPromptPreferences(agentId: string): Promise<PromptPreferenceState> {
  const response = await fetchWithAuth(`/api/agents/prompt-preferences/${encodeURIComponent(agentId)}`);
  if (!response.ok) {
    throw new Error('FAILED_TO_LOAD_PROMPT_PREFERENCES');
  }
  return await response.json() as PromptPreferenceState;
}

export async function saveAgentPromptPreference(
  agentId: string,
  content: string,
): Promise<PromptPreferenceState> {
  const response = await fetchWithAuth('/api/agents/prompt-preferences', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      content,
      enabled: true,
    }),
  });
  if (!response.ok) {
    throw new Error('FAILED_TO_SAVE_PROMPT_PREFERENCE');
  }
  return await response.json() as PromptPreferenceState;
}

export async function resetAgentPromptPreference(
  agentId: string,
): Promise<PromptPreferenceState> {
  const response = await fetchWithAuth(
    `/api/agents/prompt-preferences/${encodeURIComponent(agentId)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    throw new Error('FAILED_TO_RESET_PROMPT_PREFERENCE');
  }
  return await response.json() as PromptPreferenceState;
}
