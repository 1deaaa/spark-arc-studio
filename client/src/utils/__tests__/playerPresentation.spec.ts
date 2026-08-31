import { describe, expect, it } from 'vitest';
import {
  resolveDialogueCharacterId,
  resolveDefaultCharacterSprite,
  selectDefaultCharacterSprite,
} from '../playerPresentation';

describe('播放器角色立绘解析', () => {
  it('支持使用数字角色 ID 或角色名解析对白角色', () => {
    const charMap = { 0: '程遥', 1: '鹿野' };

    expect(resolveDialogueCharacterId({ chr: 1 }, charMap)).toBe('1');
    expect(resolveDialogueCharacterId({ chr: '鹿野', speaker: '鹿野' }, charMap)).toBe('1');
    expect(resolveDialogueCharacterId({ chr: '旁白', speaker: '旁白' }, charMap)).toBe('');
  });

  it('优先选择最新 default 立绘，不让表情变体抢占默认位', () => {
    const assets = {
      oldDefault: {
        id: 'oldDefault', type: 'character_sprite', characterId: '1', expression: 'default',
        createdAt: '2026-08-01T00:00:00Z', path: 'old.png',
      },
      newerExpression: {
        id: 'newerExpression', type: 'character_sprite', characterId: '1', expression: 'smile',
        createdAt: '2026-09-01T00:00:00Z', path: 'smile.png',
      },
      newDefault: {
        id: 'newDefault', type: 'character_sprite', characterId: '1', expression: 'default',
        createdAt: '2026-08-31T00:00:00Z', path: 'new.png',
      },
    };

    expect(selectDefaultCharacterSprite(assets, '1')?.id).toBe('newDefault');
    expect(resolveDefaultCharacterSprite({ chr: 1 }, {}, assets)?.id).toBe('newDefault');
  });

  it('角色未知或没有对应资源时返回空结果', () => {
    const assets = {
      sprite: {
        id: 'sprite', type: 'character_sprite', characterId: '1', expression: 'default',
        createdAt: '2026-09-01T00:00:00Z', path: 'sprite.png',
      },
    };

    expect(resolveDefaultCharacterSprite({ chr: '旁白' }, { 1: '鹿野' }, assets)).toBeNull();
    expect(resolveDefaultCharacterSprite({ chr: '未知角色' }, { 1: '鹿野' }, assets)).toBeNull();
  });
});
