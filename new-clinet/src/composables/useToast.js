import { ref } from 'vue';
import Toast from '@/components/Toast.vue';

let toastVm = null;

export function installToast(app) {
  // 在根实例挂一个全局 toast 组件
  const mount = document.createElement('div');
  document.body.appendChild(mount);
  const vnode = app._context?.app?.component ? null : null; // 占位，保持简单实现
}

export function bindToastInstance(vm) {
  toastVm = vm;
}

export function useToast() {
  return {
    info(msg, d) { toastVm?.show?.(msg, 'info', d); },
    success(msg, d) { toastVm?.show?.(msg, 'success', d); },
    error(msg, d) { toastVm?.show?.(msg, 'error', d); },
  };
}
