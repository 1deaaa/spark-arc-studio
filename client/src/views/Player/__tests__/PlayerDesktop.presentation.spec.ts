import { flushPromises, mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
  routerReplace: vi.fn(),
  route: {
    params: { shareId: 'version-1' },
    path: '/play/v/version-1',
    query: { scene: '1', dia: '2' } as Record<string, string>,
  },
}));

vi.mock('@/services/apiClient', () => ({
  fetchWithAuth: mocks.fetchWithAuth,
}));

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ replace: mocks.routerReplace }),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

import PlayerDesktop from '../PlayerDesktop.vue';

const playerData = {
  format: 'script',
  stories: [{
    chapter: 1,
    scene_name: '测试场景',
    dlg: [
      { chr: '旁白', speaker: '旁白', txt: '开场旁白' },
      { chr: 1, speaker: '鹿野', txt: '鹿野的对白' },
      { chr: 0, speaker: '程遥', txt: '程遥的对白', presentation: { sprite: 'sprite_explicit' } },
      { chr: '旁白', speaker: '旁白', txt: '收束旁白' },
    ],
  }],
  characters: { '0': '程遥', '1': '鹿野' },
  presentation: {
    assetBaseUrl: '/api/play/v/version-1/presentation/assets',
    manifest: {
      assets: {
        sprite_kano: {
          id: 'sprite_kano',
          type: 'character_sprite',
          characterId: '1',
          expression: 'default',
          path: 'assets/presentation/sprites/kano.png',
          createdAt: '2026-08-31T00:00:00Z',
        },
        sprite_cheng: {
          id: 'sprite_cheng',
          type: 'character_sprite',
          characterId: '0',
          expression: 'default',
          path: 'assets/presentation/sprites/cheng.png',
          createdAt: '2026-08-31T00:00:00Z',
        },
        sprite_explicit: {
          id: 'sprite_explicit',
          type: 'character_sprite',
          characterId: '0',
          expression: 'smile',
          path: 'assets/presentation/sprites/explicit.png',
          createdAt: '2026-09-01T00:00:00Z',
        },
      },
    },
  },
};

async function mountPlayer(dia: string) {
  mocks.route.query = { scene: '1', dia };
  mocks.fetchWithAuth.mockResolvedValue({
    ok: true,
    json: vi.fn().mockResolvedValue(playerData),
  });
  const wrapper = mount(PlayerDesktop, {
    global: {
      stubs: {
        PlayerAmbient: true,
        ZhOnlyTag: true,
        BookNavButton: true,
      },
    },
  });
  await flushPromises();
  await nextTick();
  return wrapper;
}

describe('播放器角色立绘绑定', () => {
  beforeEach(() => {
    mocks.fetchWithAuth.mockReset();
    mocks.routerReplace.mockReset();
    localStorage.clear();
  });

  it('对白没有 sprite cue 时按当前角色自动显示默认立绘', async () => {
    const wrapper = await mountPlayer('2');

    expect(wrapper.find('.character-sprite img').attributes('src')).toBe(
      '/api/play/v/version-1/presentation/assets/assets/presentation/sprites/kano.png',
    );
    expect(wrapper.find('.character-sprite img').attributes('alt')).toBe('鹿野');
    wrapper.unmount();
  });

  it('显式 sprite cue 覆盖自动绑定，旁白节点隐藏立绘', async () => {
    const explicitWrapper = await mountPlayer('3');
    expect(explicitWrapper.find('.character-sprite img').attributes('src')).toBe(
      '/api/play/v/version-1/presentation/assets/assets/presentation/sprites/explicit.png',
    );
    explicitWrapper.unmount();

    const narratorWrapper = await mountPlayer('1');
    expect(narratorWrapper.find('.character-sprite img').exists()).toBe(false);
    narratorWrapper.unmount();
  });
});
