import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { i18n } from '@/i18n';
import { useAIPlatformManager } from '../useAIPlatformManager';

const { fetchWithAuth, getUserInfo } = vi.hoisted(() => ({
    fetchWithAuth: vi.fn(),
    getUserInfo: vi.fn(),
}));

vi.mock('@/services/api', () => ({ fetchWithAuth }));
vi.mock('@/services/authService', () => ({ getUserInfo }));
vi.mock('naive-ui', () => ({
    useMessage: () => ({ error: vi.fn(), success: vi.fn(), warning: vi.fn() }),
    useDialog: () => ({ warning: vi.fn() }),
}));

describe('AI 平台个人密钥回退', () => {
    afterEach(() => {
        fetchWithAuth.mockReset();
        getUserInfo.mockReset();
    });

    it('普通用户将系统平台 API Key 留空保存时清除个人覆盖', async () => {
        fetchWithAuth.mockImplementation(async (url: string) => {
            if (url === '/api/ai/platforms-with-models') {
                return { ok: true, json: async () => [] };
            }
            if (url === '/api/ai/system-config') {
                return {
                    ok: true,
                    json: async () => ({
                        llm_auto_key: true,
                        use_sys_llm_config: false,
                        billing_enabled: false,
                    }),
                };
            }
            return { ok: true, json: async () => ({ success: true }) };
        });
        getUserInfo.mockResolvedValue({ is_admin: false });

        let manager: ReturnType<typeof useAIPlatformManager>;
        const wrapper = mount(defineComponent({
            setup() {
                manager = useAIPlatformManager();
                return () => null;
            },
        }), {
            global: { plugins: [i18n] },
        });

        manager!.editingPlatform.value = {
            id: 17,
            name: '系统平台',
            baseUrl: 'https://api.example.test/v1',
            rechargeUrl: '',
            is_sys: true,
            user_key_saved: true,
            user_key_override: true,
        };
        manager!.editingApiKey.value = '';

        await manager!.handleUpdatePlatform();

        expect(fetchWithAuth).toHaveBeenCalledWith('/api/ai/platform-config', {
            method: 'POST',
            body: JSON.stringify({ platform_id: 17, api_key: null }),
            headers: { 'Content-Type': 'application/json' },
        });

        wrapper.unmount();
    });
});
