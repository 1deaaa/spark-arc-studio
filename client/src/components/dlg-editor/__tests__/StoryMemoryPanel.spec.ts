import { mount, shallowMount } from '@vue/test-utils';
import { createPinia, setActivePinia, type Pinia } from 'pinia';
import StoryMemoryPanel from '@/components/dlg-editor/StoryMemoryPanel.vue';
import { useStoryMemoryStore } from '@/components/stores/storyMemoryStore';
import type { StoryMemoryOverview } from '@/services/api';
import { i18n } from '@/i18n';

/**
 * 守护对象：
 * - 故事记忆面板正确消费 storyMemoryStore 总览数据（统计、四个 Tab、状态徽章）
 * - 空状态引导与吸收入口存在；加载失败展示可重试的错误提示
 * 本测试禁止：真实网络请求、真实 LLM、依赖具体后端数据
 */

function buildOverview(overrides: Partial<StoryMemoryOverview> = {}): StoryMemoryOverview {
  return {
    updated_at: '2026-08-22T10:00:00+00:00',
    counts: {
      scenes: 12,
      characters: 2,
      relationships: 1,
      threads: 3,
      open_threads: 2,
      resolved_threads: 1,
      fact_claims: 4,
      conflict_risks: 1,
      quality_tickets_open: 1,
      quality_tickets_total: 2,
    },
    recent_scenes: [
      {
        scene_id: 'ch001-sc012',
        chapter_title: '一 · 开端',
        scene_title: '钟楼交易',
        summary: '沈棠把旧钥匙交给林烬。',
        characters: ['沈棠', '林烬'],
        state_delta_source: 'heuristic',
        updated_at: '2026-08-22T10:00:00+00:00',
      },
    ],
    characters: [
      {
        name: '沈棠',
        last_seen_title: '钟楼交易',
        last_seen_scene: 'ch001-sc012',
        status: '交付钥匙后保持警惕',
        goal: '查明档案室真相',
        emotion: '克制',
        knowledge: '知道钥匙的来历',
        recent_summary: '沈棠把旧钥匙交给林烬。',
        updated_at: '2026-08-22T10:00:00+00:00',
      },
    ],
    relationships: [
      {
        characters: ['林烬', '沈棠'],
        relation_hint: '互相试探的合作者',
        why: '交换了线索',
        co_presence_count: 3,
        recent_summary: '钟楼交易中互换线索。',
        updated_at: '2026-08-22T10:00:00+00:00',
      },
    ],
    threads: [
      {
        thread_id: 'thread-a',
        status: 'open',
        description: '档案室的秘密记录尚未揭开。',
        related_characters: ['林烬'],
        scene_title: '钟楼交易',
        last_touched_title: '钟楼交易',
        resolved_title: '',
        updated_at: '2026-08-22T10:00:00+00:00',
      },
      {
        thread_id: 'thread-b',
        status: 'resolved',
        description: '旧钥匙归属已确认。',
        related_characters: ['沈棠'],
        scene_title: '钟楼交易',
        last_touched_title: '',
        resolved_title: '钟楼交易',
        updated_at: '2026-08-21T10:00:00+00:00',
      },
    ],
    fact_claims: [
      {
        claim: '林烬已获得旧钥匙。',
        entities: ['林烬'],
        scene_title: '钟楼交易',
        evidence: '沈棠把旧钥匙交给林烬。',
        updated_at: '2026-08-22T10:00:00+00:00',
      },
    ],
    conflict_risks: [
      {
        risk: '钥匙归属与第三章描述冲突。',
        severity: 'high',
        scene_title: '钟楼交易',
        evidence: '旧钥匙已在钟楼交给林烬。',
        updated_at: '2026-08-22T10:00:00+00:00',
      },
    ],
    quality_tickets: [
      {
        ticket_id: 'quality-1',
        target: '钟楼交易',
        edit_goal: '压缩环境描写',
        must_keep: ['钥匙交接动作'],
        operations: ['删减比喻'],
        scene_name: '钟楼交易',
        overall_grade: 'B',
        updated_at: '2026-08-22T10:00:00+00:00',
      },
    ],
    ...overrides,
  };
}

function buildEmptyOverview(): StoryMemoryOverview {
  return buildOverview({
    counts: {
      scenes: 0,
      characters: 0,
      relationships: 0,
      threads: 0,
      open_threads: 0,
      resolved_threads: 0,
      fact_claims: 0,
      conflict_risks: 0,
      quality_tickets_open: 0,
      quality_tickets_total: 0,
    },
    recent_scenes: [],
    characters: [],
    relationships: [],
    threads: [],
    fact_claims: [],
    conflict_risks: [],
    quality_tickets: [],
  });
}

/** 创建共享 Pinia 并以给定总览数据播种 store，保证组件内外的 store 是同一实例。 */
function setupStore(overview: StoryMemoryOverview | null, error = ''): Pinia {
  const pinia = createPinia();
  setActivePinia(pinia);
  const store = useStoryMemoryStore();
  store.overview = overview;
  store.error = error;
  store.loading = false;
  return pinia;
}

describe('故事记忆面板', () => {
  it('渲染总览统计与角色状态、关系记录', () => {
    const pinia = setupStore(buildOverview());

    const wrapper = shallowMount(StoryMemoryPanel, {
      global: { plugins: [i18n, pinia] },
    });

    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.title'));
    expect(wrapper.text()).toContain('12');
    expect(wrapper.text()).toContain('沈棠');
    expect(wrapper.text()).toContain('查明档案室真相');
    expect(wrapper.text()).toContain('林烬 ↔ 沈棠');
  });

  it('线索 Tab 区分开放与已回收线索', async () => {
    const pinia = setupStore(buildOverview());

    const wrapper = shallowMount(StoryMemoryPanel, {
      global: { plugins: [i18n, pinia] },
    });
    const tabs = wrapper.findAll('.memory-tab');
    expect(tabs).toHaveLength(4);
    await tabs[1].trigger('click');

    expect(wrapper.text()).toContain('档案室的秘密记录尚未揭开。');
    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.threadOpen'));
    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.sectionResolvedThreads'));
    expect(wrapper.text()).toContain('旧钥匙归属已确认。');
  });

  it('风险与工单 Tab 展示严重度徽章与修订目标', async () => {
    const pinia = setupStore(buildOverview());

    const wrapper = shallowMount(StoryMemoryPanel, {
      global: { plugins: [i18n, pinia] },
    });
    const tabs = wrapper.findAll('.memory-tab');
    await tabs[3].trigger('click');

    expect(wrapper.text()).toContain('钥匙归属与第三章描述冲突。');
    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.riskHigh'));
    expect(wrapper.text()).toContain('压缩环境描写');
    expect(wrapper.find('.memory-card.risk.severity-high').exists()).toBe(true);
  });

  it('无已吸收场景时展示空状态引导与吸收入口', () => {
    const pinia = setupStore(buildEmptyOverview());

    const wrapper = mount(StoryMemoryPanel, {
      global: { plugins: [i18n, pinia] },
    });

    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.emptyTitle'));
    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.emptyDesc'));
    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.absorbCurrentFile'));
  });

  it('首次加载失败时展示错误横幅与重试按钮', () => {
    const pinia = setupStore(null, '网络错误');

    const wrapper = shallowMount(StoryMemoryPanel, {
      global: { plugins: [i18n, pinia] },
    });

    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.loadFailed'));
    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.retry'));
    expect(wrapper.find('.memory-retry-button').exists()).toBe(true);
  });
});

describe('故事记忆面板集成冒烟', () => {
  it('完整挂载不抛错且渲染页脚提示', () => {
    const pinia = setupStore(buildOverview());

    const wrapper = mount(StoryMemoryPanel, {
      global: { plugins: [i18n, pinia] },
    });

    expect(wrapper.text()).toContain(i18n.global.t('components.storyMemoryPanel.footerHint'));
  });
});
