import { defineStore } from 'pinia';
import { fetchActionBindings, fetchRegistries, saveActionBindings, saveRegistries } from '@/services/api';

export type ActionBindingArgs = Record<string, unknown>;

export type ActionBindingItem = {
  id: string | number;
  act_name: string;
  func_name: string;
  act_type?: string | null;
  act_description?: string | null;
  act_args?: ActionBindingArgs;
  act_args_str?: string;
};

export type RegistryItem = {
  id: string | number;
  name: string;
  value: unknown[];
  value_str?: string;
};

type ActionBindingStoreState = {
  actionBindings: ActionBindingItem[];
  registries: RegistryItem[];
  loadedForProject: string | null;
  loading: boolean;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function normalizeActionBinding(item: unknown, index: number): ActionBindingItem {
  const raw = asRecord(item);
  const actName = String(raw.act_name ?? '').trim();
  const funcName = String(raw.func_name ?? '').trim();
  const actArgs = asRecord(raw.act_args);
  return {
    id: raw.id != null ? String(raw.id) : `${actName || 'act'}-${index}`,
    act_name: actName,
    func_name: funcName,
    act_type: raw.act_type == null ? null : String(raw.act_type),
    act_description: raw.act_description == null ? null : String(raw.act_description),
    act_args: actArgs,
    act_args_str: JSON.stringify(actArgs, null, 2),
  };
}

function normalizeRegistry(item: unknown, index: number): RegistryItem {
  const raw = asRecord(item);
  const value = Array.isArray(raw.value)
    ? raw.value
    : raw.value == null
      ? []
      : [raw.value];
  return {
    id: raw.id != null ? String(raw.id) : `${String(raw.name ?? 'registry')}-${index}`,
    name: String(raw.name ?? '').trim(),
    value,
    value_str: JSON.stringify(value, null, 2),
  };
}

export const useActionBindingStore = defineStore('action-bindings', {
  state: (): ActionBindingStoreState => ({
    actionBindings: [],
    registries: [],
    loadedForProject: null,
    loading: false,
  }),
  getters: {
    actionBindingMap(state): Record<string, ActionBindingItem> {
      const map: Record<string, ActionBindingItem> = {};
      state.actionBindings.forEach((item) => {
        const key = String(item.act_name || '').trim();
        if (key) map[key] = item;
      });
      return map;
    },
    registryTokens(state): string[] {
      return state.registries
        .map((item) => String(item.name || '').trim())
        .filter(Boolean)
        .map((name) => `{${name}}`);
    },
  },
  actions: {
    async load(projectName: string | null, force = false) {
      if (!projectName) {
        this.actionBindings = [];
        this.registries = [];
        this.loadedForProject = null;
        return;
      }

      if (!force && this.loadedForProject === projectName && (this.actionBindings.length || this.registries.length)) {
        return;
      }

      this.loading = true;
      try {
        const [actData, regData] = await Promise.all([
          fetchActionBindings(projectName),
          fetchRegistries(projectName),
        ]);
        this.actionBindings = Array.isArray(actData)
          ? actData.map((item, index) => normalizeActionBinding(item, index))
          : [];
        this.registries = Array.isArray(regData)
          ? regData.map((item, index) => normalizeRegistry(item, index))
          : [];
        this.loadedForProject = projectName;
      } finally {
        this.loading = false;
      }
    },

    async saveActionBindingsForProject(projectName: string | null) {
      if (!projectName) return;
      const payload = this.actionBindings.map((act) => ({
        id: act.id,
        act_name: String(act.act_name || '').trim(),
        func_name: String(act.func_name || '').trim(),
        act_type: act.act_type ?? null,
        act_description: act.act_description ?? null,
        act_args: asRecord(act.act_args),
      }));
      await saveActionBindings(projectName, payload);
      this.loadedForProject = projectName;
    },

    async saveRegistriesForProject(projectName: string | null) {
      if (!projectName) return;
      const payload = this.registries.map((reg) => ({
        id: reg.id,
        name: String(reg.name || '').trim(),
        value: Array.isArray(reg.value) ? reg.value : [],
      }));
      await saveRegistries(projectName, payload);
      this.loadedForProject = projectName;
    },
  },
});
