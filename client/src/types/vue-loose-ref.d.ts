import 'vue';
import type { Ref } from 'vue';

declare module 'vue' {
  function ref(value: null): Ref<any>;
  function ref(value: undefined): Ref<any>;
  function ref(value: []): Ref<any[]>;
  function ref(value: Record<string, never>): Ref<Record<string, any>>;
}
