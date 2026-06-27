import { computed, type Ref } from 'vue';
import { useFileStore } from '../components/stores/fileStore';
import type { StoryFileTreeNode } from '../services/aiContracts';

type SortPart = string | number | null | undefined;
type SelectOption = { label: string; value: string };
type SelectGroup = { type: 'group'; label: string; key: string; children: SelectOption[] };

const naturalCollator = new Intl.Collator('zh-Hans-CN', {
    numeric: true,
    sensitivity: 'base',
});

const chineseDigits: Record<string, number> = {
    零: 0,
    〇: 0,
    一: 1,
    二: 2,
    两: 2,
    三: 3,
    四: 4,
    五: 5,
    六: 6,
    七: 7,
    八: 8,
    九: 9,
};

function parseChineseNumber(value: string): number | null {
    const text = String(value || '').trim();
    if (!text) return null;
    if (/^\d+$/.test(text)) return Number(text);
    if (!/^[零〇一二两三四五六七八九十]+$/.test(text)) return null;

    if (text === '十') return 10;
    const tenIndex = text.indexOf('十');
    if (tenIndex >= 0) {
        const before = text.slice(0, tenIndex);
        const after = text.slice(tenIndex + 1);
        const tens = before ? chineseDigits[before] : 1;
        const ones = after ? chineseDigits[after] : 0;
        if (typeof tens === 'number' && typeof ones === 'number') {
            return tens * 10 + ones;
        }
        return null;
    }

    return chineseDigits[text] ?? null;
}

function extractLeadingOrder(label: string): number {
    const text = String(label || '').trim();
    const numericPrefix = text.match(/^(?:第\s*)?(\d+)(?:\s*[章节卷部篇回集]|\s*[-_.·、\s])/i);
    if (numericPrefix) return Number(numericPrefix[1]);

    const chinesePrefix = text.match(/^(?:第\s*)?([零〇一二两三四五六七八九十]+)(?:\s*[章节卷部篇回集]|\s*[·•、\s])/);
    if (chinesePrefix) {
        const parsed = parseChineseNumber(chinesePrefix[1]);
        if (parsed != null) return parsed;
    }

    return 999999;
}

function normalizeSortKey(item: StoryFileTreeNode): SortPart[] {
    if (Array.isArray(item.sortKey)) return item.sortKey;
    if (item.sortKey != null) return [item.sortKey];
    const label = item.path || item.name || '';
    return [extractLeadingOrder(label), label];
}

function compareSortParts(left: SortPart, right: SortPart): number {
    const leftNumber = typeof left === 'number' ? left : Number.NaN;
    const rightNumber = typeof right === 'number' ? right : Number.NaN;
    if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
        return leftNumber - rightNumber;
    }
    return naturalCollator.compare(String(left ?? ''), String(right ?? ''));
}

function compareStoryNodes(left: StoryFileTreeNode, right: StoryFileTreeNode): number {
    const typeOrder = (node: StoryFileTreeNode) => (node.type === 'folder' ? 0 : 1);
    const typeDiff = typeOrder(left) - typeOrder(right);
    if (typeDiff !== 0) return typeDiff;

    if (left.type === 'folder' && right.type === 'folder') {
        const orderDiff = extractLeadingOrder(left.name) - extractLeadingOrder(right.name);
        if (orderDiff !== 0) return orderDiff;
        return naturalCollator.compare(left.name || left.path || '', right.name || right.path || '');
    }

    const leftKey = normalizeSortKey(left);
    const rightKey = normalizeSortKey(right);
    const length = Math.max(leftKey.length, rightKey.length);
    for (let index = 0; index < length; index += 1) {
        const diff = compareSortParts(leftKey[index], rightKey[index]);
        if (diff !== 0) return diff;
    }
    return naturalCollator.compare(left.path || left.name || '', right.path || right.name || '');
}

function sortedStoryNodes(list: StoryFileTreeNode[] = []): StoryFileTreeNode[] {
    return [...list].sort(compareStoryNodes);
}

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

    const resolveRootLabel = () =>
        typeof rootGroupLabel === 'function' ? rootGroupLabel() : rootGroupLabel.value;

    const toOption = (item: StoryFileTreeNode): SelectOption => ({
        label: item.name || item.path,
        value: item.path,
    });

    // 扁平剧本文件列表
    const flatOptions = computed<SelectOption[]>(() => {
        const flat: SelectOption[] = [];
        function walk(list: StoryFileTreeNode[] = []) {
            sortedStoryNodes(list).forEach(item => {
                if (item.type === 'story') {
                    flat.push(toOption(item));
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
        const rootChildren: SelectOption[] = [];

        function walkFolder(list: StoryFileTreeNode[], isRootLevel = true) {
            sortedStoryNodes(list).forEach(item => {
                if (item.type === 'folder' && Array.isArray(item.children)) {
                    const folderLabel = item.name || resolveRootLabel();
                    const children = sortedStoryNodes(item.children)
                        .filter(child => child.type === 'story')
                        .map(toOption);
                    if (children.length > 0) {
                        groups.push({
                            type: 'group',
                            label: folderLabel,
                            key: `folder:${item.path || folderLabel}`,
                            children,
                        });
                    }
                    walkFolder(item.children, false);
                } else if (isRootLevel && item.type === 'story') {
                    rootChildren.push(toOption(item));
                }
            });
        }

        walkFolder(tree);
        if (rootChildren.length > 0) {
            groups.push({
                type: 'group',
                label: resolveRootLabel(),
                key: 'root',
                children: rootChildren,
            });
        }
        return groups.length > 0 ? groups : flatOptions.value;
    });

    return { flatOptions, groupedOptions };
}
