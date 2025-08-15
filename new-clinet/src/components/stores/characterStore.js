import { defineStore } from 'pinia';
import { fetchCharacters } from '@/services/api';

export const useCharacterStore = defineStore('characters', {
  state: () => ({
    list: [], // [{id:number, name:string}]
    map: {},  // { [id:number]: name }
    loadedForProject: null,
    loading: false,
  }),
  actions: {
    async load(projectName) {
      if (!projectName) {
        this.list = [];
        this.map = {};
        this.loadedForProject = null;
        return;
      }
      // 避免重复加载
      if (this.loadedForProject === projectName && this.list.length) return;
      this.loading = true;
      try {
        const items = await fetchCharacters(projectName);
        this.list = Array.isArray(items) ? items : [];
        const m = {};
        for (const it of this.list) {
          if (it && typeof it.id !== 'undefined') m[Number(it.id)] = it.name ?? String(it.id);
        }
        this.map = m;
        this.loadedForProject = projectName;
      } finally {
        this.loading = false;
      }
    },
  },
});
