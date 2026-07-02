import { defineStore } from 'pinia';
import { fetchCharacters } from '@/services/api';
import type { StoryCharacter } from '@/services/aiContracts';

type CharacterStoreState = {
  list: StoryCharacter[];
  map: Record<number, string>;
  loadedForProject: string | null;
  loading: boolean;
};

export const useCharacterStore = defineStore('characters', {
  state: (): CharacterStoreState => ({
    list: [], // [{id:number, name:string}]
    map: {},  // { [id:number]: name }
    loadedForProject: null,
    loading: false,
  }),
  actions: {
    async load(projectName: string | null, options: { force?: boolean } = {}) {
      if (!projectName) {
        this.list = [];
        this.map = {};
        this.loadedForProject = null;
        return;
      }
      // 避免重复加载
      if (!options.force && this.loadedForProject === projectName && this.list.length) return;
      this.loading = true;
      try {
        const items = await fetchCharacters(projectName, false, true);
        this.list = Array.isArray(items) ? items : [];
        const m: Record<number, string> = {};
        for (const it of this.list) {
          if (it && typeof it.id !== 'undefined') m[Number(it.id)] = it.name ?? String(it.id);
        }
        this.map = m;
        this.loadedForProject = projectName;
      } finally {
        this.loading = false;
      }
    },
    async reload(projectName: string | null) {
      await this.load(projectName, { force: true });
    },
  },
});
