import { fetchWithAuth } from './api';

export type AgentSkillRecord = {
  skill_id: string;
  domain: 'user' | 'global' | string;
  name: string;
  normalized_name: string;
  description: string;
  source_url?: string;
  source_key?: string;
  compatibility_status: 'compatible_text_only' | 'compatible_scripts_ignored' | string;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
  reference_paths?: string[];
};

export type AgentSkillListResponse = {
  success: boolean;
  is_admin: boolean;
  skills: AgentSkillRecord[];
};

export type AgentSkillImportResult = {
  skill_id: string;
  name: string;
  description: string;
  domain: string;
  compatibility_status: string;
  duplicate_of?: string | null;
};

export async function fetchAgentSkills(): Promise<AgentSkillListResponse> {
  const response = await fetchWithAuth('/api/agents/skills');
  if (!response.ok) {
    throw new Error('FAILED_TO_LOAD_AGENT_SKILLS');
  }
  return await response.json() as AgentSkillListResponse;
}

export async function uploadAgentSkill(file: File, publishGlobal = false): Promise<AgentSkillImportResult[]> {
  const form = new FormData();
  form.append('file', file);
  form.append('publish_global', publishGlobal ? 'true' : 'false');
  const response = await fetchWithAuth('/api/agents/skills/upload', {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw new Error('FAILED_TO_UPLOAD_AGENT_SKILL');
  }
  const payload = await response.json();
  return payload.skills || [];
}

export async function importAgentSkillFromUrl(url: string, publishGlobal = false): Promise<AgentSkillImportResult[]> {
  const response = await fetchWithAuth('/api/agents/skills/import-url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, publish_global: publishGlobal }),
  });
  if (!response.ok) {
    throw new Error('FAILED_TO_IMPORT_AGENT_SKILL');
  }
  const payload = await response.json();
  return payload.skills || [];
}

export async function deleteAgentSkill(skillId: string): Promise<boolean> {
  const response = await fetchWithAuth(`/api/agents/skills/${encodeURIComponent(skillId)}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('FAILED_TO_DELETE_AGENT_SKILL');
  }
  const payload = await response.json();
  return Boolean(payload.deleted);
}

