# Vue I18n 维护说明

## 目标
- 所有用户可见文本统一接入 i18n。
- 任何新功能上线前，必须补齐 `zh-CN` / `en-US` / `ja-JP` / `ko-KR`。

## 目录结构
- `src/i18n/index.ts`: i18n 初始化与全局配置。
- `src/i18n/types.ts`: 语言类型、默认语言、存储键。
- `src/i18n/locales/zh-CN.ts`: 中文词条。
- `src/i18n/locales/en-US.ts`: 英文词条。
- `src/i18n/locales/ja-JP.ts`: 日文词条。
- `src/i18n/locales/ko-KR.ts`: 韩文词条。

## 新增文案流程
1. 先在 `zh-CN.ts` 增加语义化 key。
2. 同步在 `en-US.ts`、`ja-JP.ts` 与 `ko-KR.ts` 填写翻译。
3. 在组件里使用 `t('your.key.path')`，禁止硬编码文本。
4. 运行 `npm run typecheck` 确认类型与模板无误。

## 快速排查硬编码
运行：

```bash
npm run i18n:scan
```

默认仅扫描 Vue 模板中的用户可见文案（排除 locale/test 目录），并输出包含中日韩字符的行号，便于迁移为 i18n key。

如需全量扫描（包含脚本文件）：

```bash
npm run i18n:scan:full
```

## 约束
- 禁止在组件中新增用户可见硬编码文本。
- 允许保留注释中的中文说明，但界面文案必须迁移到 i18n。
