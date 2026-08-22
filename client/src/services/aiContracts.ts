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
  sortKey?: string | number | Array<string | number | null> | null;
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

// 灵感列表过滤范围：
// - all：全部（默认）
// - project：仅返回已绑定到指定项目的灵感
// - drafts：仅返回未绑定到任何项目的草稿
export type InspirationScope = 'all' | 'project' | 'drafts';

export type InspirationEntry = {
  id: string;
  timestamp: string;
  origin?: InspirationOrigin;
  source?: string;
  content?: string;
  tags?: InspirationTags;
  status?: InspirationStatus;
  /**
   * 已绑定到的项目名列表；空数组 / 缺失 表示草稿。
   * 多对多软关联：一条灵感可同时属于多个项目。
   */
  project_links?: string[];
  [key: string]: unknown;
};

export type InspirationListResponse = {
  inspirations: InspirationEntry[];
  unreadCount: number;
  /** 后端回显的过滤范围，供前端验证一致性 */
  scope?: InspirationScope;
  /** 后端回显的项目名（其他 scope 下可能为 null） */
  project?: string | null;
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
  input_modalities: string[];
  output_modalities: string[];
  image_generation_adapter?: string | null;
  extra_body?: JsonObject | null;
  temperature?: number | null;
  max_context_tokens?: number | null;
  max_output_tokens?: number | null;
  sys_credit_input_price_per_million?: number | null;
  sys_credit_cached_input_price_per_million?: number | null;
  sys_credit_output_price_per_million?: number | null;
  sort_order?: number | null;
};

export type AiEmbeddingItem = {
  model_id: ApiId;
  model_name: string;
  display_name: string;
  input_modalities: string[];
  output_modalities: string[];
  extra_body?: JsonObject | null;
  temperature?: number | null;
};

export type InspirationBindChangedPayload = {
  boundId?: string | null;
  unboundIds?: string[];
  projectName: string;
  entry?: InspirationEntry;
};

export type AiPlatform = {
  platform_id: ApiId;
  /** 平台配置的稳定身份；与可重复的 Base URL 解耦。 */
  platform_key?: string | null;
  name: string;
  base_url: string;
  recharge_url?: string | null;
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
  /** 平台配置的稳定身份；与可重复的 Base URL 解耦。 */
  platform_key?: string | null;
  platform_name: string;
  platform_is_sys: boolean;
  platform_disabled?: boolean;
  base_url: string;
  recharge_url?: string | null;
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
  input_modalities: string[];
  output_modalities: string[];
  image_generation_adapter?: string | null;
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
  input_modalities: string[];
  output_modalities: string[];
  api_key_set: boolean;
};

export type EmbeddingSelectionSource = 'selection' | 'default';

export type EmbeddingSelectionResponse = {
  current: EmbeddingSelectionCurrent | null;
  has_selection?: boolean;
  source?: EmbeddingSelectionSource;
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
  source?: EmbeddingSelectionSource;
};

export type ApiMutationResult = {
  success: boolean;
  id?: ApiId;
  platform_id?: ApiId;
  platform_key?: string | null;
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
  pre_state?: string;
  trigger?: string;
  choice_or_action?: string;
  post_state?: string;
  reveal?: string;
  knowledge_change?: string;
  causal_dependencies?: string[];
  setup_refs?: string[];
  payoff_refs?: string[];
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
  beat_refs?: string[];
  guide?: string;
  key_dialogues?: string[];
  location?: string;
  time?: string;
  pre_state?: string;
  objective?: string;
  conflict?: string;
  turn?: string;
  post_state?: string;
  knowledge_before?: string;
  knowledge_after?: string;
  forbidden_setup?: string;
  causal_dependencies?: string[];
  setup_refs?: string[];
  payoff_refs?: string[];
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
  style_profile?: JsonObject | string;
  raw?: unknown;
  [key: string]: unknown;
};
