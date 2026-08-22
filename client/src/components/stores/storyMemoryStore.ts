import { defineStore } from 'pinia';
import { fetchStoryMemoryState, type StoryMemoryOverview } from '@/services/api';

/**
 * 项目级 StoryMemory 总览状态。
 *
 * 写作界面标题栏角标与故事记忆面板共享同一份数据，避免重复请求；
 * 切换项目由 projectStore.setCurrentProject 级联 reset。
 */
export const useStoryMemoryStore = defineStore('storyMemory', {
  state: () => ({
    overview: null as StoryMemoryOverview | null,
    loading: false,
    error: '',
    loadedForProject: null as string | null,
    lastFetchedAt: 0,
  }),
  getters: {
    /** 待关注信号数：矛盾风险 + 开放修订工单，用于标题栏角标。 */
    attentionCount(state): number {
      const counts = state.overview?.counts;
      if (!counts) return 0;
      return (counts.conflict_risks || 0) + (counts.quality_tickets_open || 0);
    },
  },
  actions: {
    /**
     * 拉取当前项目的记忆总览；同项目已加载且非强制时跳过。
     * 失败时保留旧数据并记录错误，面板可展示"数据可能过期"提示。
     */
    async fetch(projectName: string, options: { force?: boolean } = {}) {
      const target = (projectName || '').trim();
      if (!target || this.loading) return;
      if (!options.force && this.loadedForProject === target && this.overview) return;

      this.loading = true;
      this.error = '';
      try {
        const overview = await fetchStoryMemoryState(target);
        this.overview = overview;
        this.loadedForProject = target;
        this.lastFetchedAt = Date.now();
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
      } finally {
        this.loading = false;
      }
    },
    reset() {
      this.overview = null;
      this.loading = false;
      this.error = '';
      this.loadedForProject = null;
      this.lastFetchedAt = 0;
    },
  },
});
