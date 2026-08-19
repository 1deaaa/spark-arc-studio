/**
 * 故事文件树的稳定节点类型。它们与后端 API 的 folder/story 字段保持一致。
 * 这里的 story 不是用户可见的“故事”称谓，而是正文文件的历史兼容类型名。
 */
export type StoryNodeType = 'folder' | 'story';

/** 项目的创作模式。 */
export type StoryWorkspaceMode = 'script' | 'novel';

/** 用户可见术语在 i18n 中的变体。 */
export type StoryTerminologyVariant =
  | 'label'
  | 'create'
  | 'delete'
  | 'promptTitle'
  | 'promptMessage';

/**
 * 结构页的展示区域和术语路径。路径统一由本 helper 生成，避免页面各自维护剧本/小说分支。
 */
export type StoryStructureSurface = 'desktop' | 'mobile';

/**
 * 返回节点在当前创作模式下的历史兼容角色。
 *
 * 注意：返回值中的 chapter/scene/volume 只服务旧代码/API，不能当作用户界面的正式称谓。
 * 剧本实际显示为“剧幕/场景”，小说实际显示为“分卷/章节”；旧角色名若继续扩散会造成语义混乱。
 * 这里保留旧值是向后兼容，维护新界面时必须通过 i18n 术语 key 显示正式称谓。
 */
export function resolveStoryNodeRole(
  mode: string | null | undefined,
  type: StoryNodeType,
): 'chapter' | 'scene' | 'volume' {
  const normalizedMode: StoryWorkspaceMode = mode === 'novel' ? 'novel' : 'script';
  if (normalizedMode === 'novel') {
    return type === 'folder' ? 'volume' : 'chapter';
  }
  // “chapter” 是剧本文件夹的历史内部角色名，不等于用户可见的“剧幕”。
  return type === 'folder' ? 'chapter' : 'scene';
}

/** 返回节点术语对应的 i18n key，避免各组件各自维护模式分支。 */
export function storyTerminologyKey(
  mode: string | null | undefined,
  type: StoryNodeType,
  variant: StoryTerminologyVariant = 'label',
): string {
  const normalizedMode: StoryWorkspaceMode = mode === 'novel' ? 'novel' : 'script';
  const keys: Record<StoryWorkspaceMode, Record<StoryNodeType, Record<StoryTerminologyVariant, string>>> = {
    script: {
      folder: {
        label: 'newAct', create: 'newAct', delete: 'deleteAct',
        promptTitle: 'newAct', promptMessage: 'promptMessageActFolder',
      },
      story: {
        label: 'newSceneScript', create: 'newSceneScript', delete: 'deleteScene',
        promptTitle: 'promptTitleStoryScript', promptMessage: 'promptMessageStoryScript',
      },
    },
    novel: {
      folder: {
        label: 'newVolume', create: 'newVolume', delete: 'deleteVolume',
        promptTitle: 'promptTitleFolder', promptMessage: 'promptMessageFolder',
      },
      story: {
        label: 'newSceneNovel', create: 'newSceneNovel', delete: 'deleteChapter',
        promptTitle: 'promptTitleStoryNovel', promptMessage: 'promptMessageStoryNovel',
      },
    },
  };
  return `components.fileExplorer.${keys[normalizedMode][type][variant]}`;
}

/** 返回结构页当前模式下的展示术语，内部请求字段仍保持旧命名以兼容后端。 */
export function storyStructureTerminologyKey(
  mode: string | null | undefined,
  surface: StoryStructureSurface,
  variant: string,
): string {
  const normalizedMode: StoryWorkspaceMode = mode === 'novel' ? 'novel' : 'script';
  return `views.structure.${surface}.${normalizedMode}.${variant}`;
}
