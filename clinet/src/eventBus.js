import mitt from 'mitt';

// 统一应用内事件：
// 'save-request' | 'saved' | 'scene-selected' | 'ai-append-text'
export const bus = mitt();

export default bus;
