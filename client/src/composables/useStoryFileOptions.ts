import { computed, type Ref } from 'vue';
import { useFileStore } from '../components/stores/fileStore';
import type { StoryFileTreeNode } from '../services/aiContracts';

/**
 * 剧本文件下拉选项（移动端创作页 / 蓝图页共用）
 *
 * 统一文件选择的分组逻辑，避免在多个页面重复实现：
 * - flatOptions：扁平的剧本文件列表（无分组）
 * - groupedOptions：按文件夹（章节）分组的 n-select 选项；无分组时回退为扁平列表
 *
 * @param rootGroupLabel 根目录文件的分组标题（各页面文案不同，由调用方传入）
 */
export function useStoryFileOptions(rootGroupLabel: Ref<string> | (() => string)) {
    const fileStore = useFileStore();

    type SelectOption = { label: string; value: string };
    type SelectGroup = { type: string; label: string; key: string; children: SelectOption[] };

    const resolveRootLabel = () =>
        typeof rootGroupLabel === 'function' ? rootGroupLabel() : rootGroupLabel.value;

    // 扁平剧本文件列表
    const flatOptions = computed<SelectOption[]>(() => {
        const flat: SelectOption[] = [];
        function walk(list: StoryFileTreeNode[] = []) {
            list.forEach(item => {
                if (item.type === 'story') {
                    flat.push({ label: item.name || item.path, value: item.path });
                } else if (Array.isArray(item.children)) {
                    walk(item.children);
                }
            });
        }
        walk(fileStore.fileTree || []);
        return flat;
    });

    // 按文件夹（章节）分组的选项
    const groupedOptions = computed<(SelectGroup | SelectOption)[]>(() => {
        const tree = fileStore.fileTree || [];
        const groups: SelectGroup[] = [];

        function walkFolder(list: StoryFileTreeNode[]) {
            list.forEach(item => {
                if (item.type === 'folder' && Array.isArray(item.children)) {
                    const folderLabel = item.name || resolveRootLabel();
                    const children: SelectOption[] = [];
                    item.children.forEach(child => {
                        if (child.type === 'story') {
                            children.push({ label: child.name || child.path, value: child.path });
                        }
                    });
                    if (children.length > 0) {
                        groups.push({ type: 'group', label: folderLabel, key: `folder:${folderLabel}`, children });
                    }
                    walkFolder(item.children);
                } else if (item.type === 'story') {
                    const root = groups.find(g => g.key === 'root');
                    if (!root) {
                        groups.push({
                            type: 'group',
                            label: resolveRootLabel(),
                            key: 'root',
                            children: [{ label: item.name || item.path, value: item.path }],
                        });
                    } else {
                        root.children.push({ label: item.name || item.path, value: item.path });
                    }
                }
            });
        }

        walkFolder(tree);
        return groups.length > 0 ? groups : flatOptions.value;
    });

    return { flatOptions, groupedOptions };
}
