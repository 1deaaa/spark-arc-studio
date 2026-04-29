export type ApiId = number | string;

export type JsonObject = Record<string, unknown>;

export type StoryFormat = 'arc' | 'novel';

export type StoryFileTreeNode = {
  name: string;
  type: 'folder' | 'story';
  path: string;
  children?: StoryFileTreeNode[];
  sceneCount?: number;
  format?: StoryFormat;
  filename?: string;
  meta?: JsonObject | null;
  sortKey?: string | number;
};

export type StoryFileContentResponse = {
  content: string;
  format: StoryFormat;
  path: string;
};

export type StoryMutationResult = {
  success: boolean;
  message?: string;
  error?: string;
  detail?: string;
  id?: ApiId;
  filename?: string | string[];
  existing?: string[];
  result?: JsonObject;
};

export type StoryCharacter = {
  id: number;
  name: string;
  desc: string;
};

export type StoryCharacterDetail = StoryCharacter & {
  content: string;
};

export type InspirationTags = {
  styles: string[];
  genres: string[];
  tones: string[];
  worldviews: string[];
  lengthHint: string[];
};

export type InspirationStatus = 'read' | 'unread';

export type InspirationOrigin = 'ui' | 'mcp' | 'legacy';

export type InspirationEntry = {
  id: string;
  timestamp: string;
  origin?: InspirationOrigin;
  source?: string;
  content?: string;
  tags?: InspirationTags;
  status?: InspirationStatus;
  [key: string]: unknown;
};

export type InspirationListResponse = {
  inspirations: InspirationEntry[];
  unreadCount: number;
};

export type OutlineHistoryEntry = {
  id?: number;
  markup?: string;
  outline?: OutlineData;
  [key: string]: unknown;
};

export type AiModelItem = {
  model_id: ApiId;
  model_name: string;
  display_name: string;
  extra_body?: JsonObject | null;
  temperature?: number | null;
  max_context_tokens?: number | null;
  max_output_tokens?: number | null;
  sys_credit_input_price_per_million?: number | null;
  sys_credit_output_price_per_million?: number | null;
};

export type AiEmbeddingItem = {
  model_id: ApiId;
  model_name: string;
  display_name: string;
  extra_body?: JsonObject | null;
  temperature?: number | null;
};

export type AiPlatform = {
  platform_id: ApiId;
  name: string;
  base_url: string;
  api_key_set: boolean;
  api_key_status?: string;
  api_key_message?: string;
  sys_key_set?: boolean;
  sys_key_status?: string;
  sys_key_message?: string;
  sys_credit_balance?: number | null;
  is_sys: boolean;
  user_key_override?: boolean;
  user_key_saved?: boolean;
  user_key_status?: string;
  user_key_message?: string;
  disabled?: boolean;
  models?: AiModelItem[];
  embeddings?: AiEmbeddingItem[];
};

export type AiFlattenedModelItem = {
  platform_id: ApiId;
  platform_name: string;
  platform_is_sys: boolean;
  platform_disabled?: boolean;
  base_url: string;
  api_key_set: boolean;
  api_key_status?: string;
  api_key_message?: string;
  sys_key_set?: boolean;
  sys_key_status?: string;
  sys_key_message?: string;
  sys_credit_balance?: number | null;
  user_key_override?: boolean;
  user_key_saved?: boolean;
  user_key_status?: string;
  user_key_message?: string;
  model_id: ApiId;
  model_name: string;
  display_name: string;
  extra_body?: JsonObject | null;
  temperature?: number | null;
  max_context_tokens?: number | null;
  max_output_tokens?: number | null;
};

export type AiUsageSelection = {
  usage_key: string;
  usage_label: string;
  platform: string;
  platform_id: ApiId;
  platform_is_sys: boolean;
  base_url: string;
  model_display_name: string;
  model_id: ApiId;
  model_name: string;
  api_key_set: boolean;
  needs_rebind: boolean;
  missing_key?: boolean;
  error?: string;
};

export type AiUserSelectionResponse = {
  current: AiUsageSelection;
  usage_selections: AiUsageSelection[];
};

export type EmbeddingSelectionCurrent = {
  platform_id: ApiId;
  platform_name: string;
  base_url: string;
  model_id: ApiId;
  model_name: string;
  display_name: string;
  api_key_set: boolean;
};

export type EmbeddingSelectionResponse = {
  current: EmbeddingSelectionCurrent | null;
};

export type EmbeddingStatusResponse = {
  has_embeddings: boolean;
  has_selection: boolean;
  current: EmbeddingSelectionCurrent | null;
  recommended: {
    platform_id: ApiId;
    model_id: ApiId;
    display_name: string;
  } | null;
};

export type ApiMutationResult = {
  success: boolean;
  id?: ApiId;
  message?: string;
  error?: string;
  detail?: string;
};

export type RemoteModelInfo = {
  id: string;
  max_context_tokens?: number | null;
  max_output_tokens?: number | null;
};

export type ModelListResponse = {
  models: RemoteModelInfo[];
};

export type TestModelResponse = {
  response: unknown;
  dims?: number;
};

export type SpeedTestEvent =
  | { type: 'first_token'; ftl: number }
  | { type: 'update'; speed: number }
  | { type: 'final'; speed: number; ftl: number }
  | { error: string };

export type BeatSheetBeat = {
  beat_id: number;
  beat_type: string;
  narrative_action: string;
  emotional_goal: string;
  reader_experience: string;
  tension_level: string;
};

export type BeatSheetData = {
  global_emotional_arc: string;
  beats: BeatSheetBeat[];
};

export type OutlineScene = {
  id: string;
  name: string;
  title: string;
  type: 'scene';
  description: string;
  mood: string;
  tension: 'Low' | 'Medium' | 'High';
  characters: string[];
  mapped_beats: number[];
};

export type OutlineChapter = {
  id: string;
  name: string;
  title: string;
  type: 'chapter';
  chapter: number;
  description: string;
  children: OutlineScene[];
};

export type OutlineData = {
  title: string;
  summary?: string;
  mainTheme?: string;
  nodes: OutlineChapter[];
  totalChapters?: number;
  estimatedScenes?: number;
  updatedAt?: string | null;
  [key: string]: unknown;
};

export type StyleAnalyzeEvent = {
  step?: string;
  message?: string;
  current?: number;
  total?: number;
  style_profile?: JsonObject;
  raw?: unknown;
  [key: string]: unknown;
};
