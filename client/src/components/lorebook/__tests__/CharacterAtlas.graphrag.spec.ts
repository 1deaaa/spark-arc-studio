import { mount } from '@vue/test-utils';
import { createI18n } from 'vue-i18n';
import { nextTick } from 'vue';
import { beforeEach, describe, expect, it } from 'vitest';
import { NInput } from 'naive-ui';

import CharacterAtlas from '../CharacterAtlas.vue';
import type { GraphRAGCharacterGraph } from '@/services/graphragService';
import type { CharacterRelation } from '@/services/storyService';

const messages = {
  views: {
    common: { save: '保存' },
    characters: {
      searchPlaceholder: '搜索', groupByFaction: '按阵营分组', allFactions: '全部阵营',
      ungrouped: '未分组', noFaction: '未设置阵营', roleUnknown: '身份待补充',
      noProfile: '暂无设定', unnamedCharacter: '未命名', memberCount: '{count} 人', openProfileHint: '打开档案',
      graphStatus: {
        loading: '读取中', unavailable: '不可用', disabled: '未启用', building: '构建中', error: '异常',
        stale: '待更新', notBuilt: '未构建', ready: '已就绪',
      },
      graphBuilding: '构建中', graphBuildingProgress: '{done}/{total}', refreshGraph: '刷新', enableGraph: '启用',
      graphRelation: '角色关系', graphRelationLegend: 'GraphRAG 角色关系',
      manualRelationLegend: '人工关系',
      graphRelationEvidence: '{relation}，证据 {count} 条',
      zoomOut: '缩小', zoomIn: '放大', fitView: '适配', addCharacter: '添加角色',
      connectRelation: '连接关系', connectRelationHint: '手动连接两个角色',
      relationChooseTarget: '选择目标角色', relationChooseSource: '选择起始角色',
      relationFrom: '起始角色', relationTo: '目标角色', relationName: '关系', relationNamePlaceholder: '填写关系',
      relationNote: '备注', relationNotePlaceholder: '填写备注', deleteRelationConfirm: '确认删除关系',
      emptyTitle: '暂无角色', emptyDescription: '暂无', nameLabel: '名称', namePlaceholder: '名称',
      profileLabel: '档案', profilePlaceholder: '档案', deleteConfirm: '确认删除 {name}', sprite: '立绘', create: '创建',
    },
  },
  common: { delete: '删除', cancel: '取消' },
};

const characters = [
  { id: 1, name: '沈棠', desc: '', content: '阵营：档案局\n身份：管理员\n她信任林烬。' },
  { id: 2, name: '林烬', desc: '', content: '阵营：调查组\n身份：调查员' },
];

function mountAtlas(graph: GraphRAGCharacterGraph | null, manualRelations: CharacterRelation[] = [], projectName = 'test-project') {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } });
  return mount(CharacterAtlas, {
    props: { characters, graph, manualRelations, projectName },
    global: { plugins: [i18n], stubs: { teleport: true } },
  });
}

beforeEach(() => localStorage.clear());

describe('角色画布 GraphRAG 融合', () => {
  it('添加角色命令位于缩放工具之前，避开右侧全局浮动按钮', () => {
    const wrapper = mountAtlas(null);
    const firstAction = wrapper.find('.atlas-actions button');

    expect(firstAction.text()).toContain('添加角色');
  });

  it('默认不启用阵营分组，并仍然显示全部角色', async () => {
    const wrapper = mountAtlas(null);

    expect(wrapper.findAll('.faction-zone')).toHaveLength(0);
    expect(wrapper.findAll('.character-node')).toHaveLength(2);

    await wrapper.find('.n-checkbox').trigger('click');

    expect(wrapper.findAll('.faction-zone')).toHaveLength(2);
    expect(wrapper.findAll('.character-node')).toHaveLength(2);
  });

  it('可在创建后立即定位并选中新角色', async () => {
    const wrapper = mountAtlas(null);
    await wrapper.setProps({
      characters: [
        ...characters,
        { id: 3, name: '周遥', desc: '', content: '' },
      ],
    });

    await (wrapper.vm as unknown as { revealCharacter: (id: number, openProfile: boolean) => Promise<void> })
      .revealCharacter(3, true);

    const selected = wrapper.find('.character-node.selected');
    expect(selected.exists()).toBe(true);
    expect(selected.text()).toContain('周遥');
  });

  it('创建角色时一次提交名称与完整档案', async () => {
    const wrapper = mountAtlas(null);
    const addButton = wrapper.findAll('button').find(button => button.text().includes('添加角色'));
    expect(addButton).toBeDefined();
    await addButton!.trigger('click');

    const fields = wrapper.find('.profile-form').findAllComponents(NInput);
    expect(fields).toHaveLength(2);
    await fields[0].find('input').setValue('周遥');
    await fields[1].find('textarea').setValue('身份：记者\n动机：查明旧案真相');

    const createButton = wrapper.findAll('.profile-footer button')
      .find(button => button.text().includes('创建'));
    expect(createButton).toBeDefined();
    await createButton!.trigger('click');

    expect(wrapper.emitted('create')?.[0]?.[0]).toEqual({
      name: '周遥',
      content: '身份：记者\n动机：查明旧案真相',
    });
  });

  it('按画布容器尺寸自动缩放并居中', async () => {
    const wrapper = mountAtlas(null);
    const viewport = wrapper.find('.atlas-viewport').element as HTMLElement;
    Object.defineProperty(viewport, 'clientWidth', { configurable: true, value: 400 });
    Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 200 });

    await (wrapper.vm as unknown as { fitViewport: () => Promise<void> }).fitViewport();

    expect(wrapper.find('.zoom-value').text()).toBe('53%');
  });

  it('图谱就绪时使用真实关系', () => {
    const graph: GraphRAGCharacterGraph = {
      projectName: 'demo', enabled: true, graphReady: true, needsRebuild: false,
      buildState: {
        status: 'ready', stage: 'ready', error: '', started_at: '', finished_at: '',
        progress: { total_chunks: 1, done_chunks: 1, triplets_collected: 1, source_docs: 1, nodes: 2, edges: 1 },
      },
      metadata: { built_at: '', source_docs: 1, chunks: 1, triplets: 1, nodes: 2, edges: 1 },
      nodes: [],
      edges: [{
        id: '1:2', source: '1', target: '2', relation: '共同调查旧案', evidenceCount: 2,
        sources: ['第一章'], evidenceSamples: ['并肩调查'],
      }],
    };

    const wrapper = mountAtlas(graph);

    expect(wrapper.findAll('.relation-edge')).toHaveLength(1);
    expect(wrapper.find('.relation-edge text').text()).toBe('共同调查旧案');
    expect(wrapper.find('.atlas-legend').text()).toContain('GraphRAG 角色关系');
  });

  it('图谱不可用时默认不自动绘制档案提名关系', () => {
    const wrapper = mountAtlas(null);

    expect(wrapper.findAll('.relation-edge')).toHaveLength(0);
    expect(wrapper.find('.atlas-legend').text()).not.toContain('档案提名');
    expect(wrapper.find('.atlas-legend').text()).not.toContain('GraphRAG 角色关系');
  });

  it('关系线连接同排节点相向的最近边缘', () => {
    const wrapper = mountAtlas(null, [{
      id: 'manual-1', source: '1', target: '2', relation: '盟友', note: '',
    }]);

    const path = wrapper.find('.relation-edge.manual .relation-stroke').attributes('d');
    expect(path).toMatch(/^M 310 88 Q /);
    expect(path).toMatch(/ 370 88$/);
  });

  it('单击人工关系的宽点击区后选中连线并打开快捷编辑', async () => {
    const wrapper = mountAtlas(null, [{
      id: 'manual-1', source: '1', target: '2', relation: '盟友', note: '共同调查旧案',
    }]);

    const hitArea = wrapper.find('.relation-edge.manual .relation-hit');
    expect(hitArea.exists()).toBe(true);
    await hitArea.trigger('click');

    expect(wrapper.find('.relation-edge.manual').classes()).toContain('selected');
    expect(wrapper.find('.relation-modal').exists()).toBe(true);
  });

  it('拖动角色后保存位置，并在重新进入项目时恢复', async () => {
    const wrapper = mountAtlas(null);
    const node = wrapper.find('.character-node');
    const dispatchPointer = async (type: string, clientX: number, clientY: number) => {
      const event = new MouseEvent(type, { bubbles: true, button: 0, clientX, clientY });
      Object.defineProperty(event, 'pointerId', { value: 1 });
      node.element.dispatchEvent(event);
      await nextTick();
    };

    await dispatchPointer('pointerdown', 100, 100);
    await dispatchPointer('pointermove', 220, 150);
    await dispatchPointer('pointerup', 220, 150);

    expect(node.attributes('style')).toContain('left: 156px');
    expect(node.attributes('style')).toContain('top: 86px');
    expect(localStorage.getItem('spark_character_atlas_positions_v1:test-project')).toContain('"x":156');

    const restored = mountAtlas(null);
    expect(restored.find('.character-node').attributes('style')).toContain('left: 156px');
    expect(restored.find('.character-node').attributes('style')).toContain('top: 86px');
  });
});
