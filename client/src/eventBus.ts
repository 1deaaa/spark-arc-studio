import mitt from 'mitt';

// 统一应用内事件：
// 'save-request' | 'saved' | 'scene-selected' | 'ai-append-text'
export type CancelLoadingPayload = {
	scope?: string;
	target?: string;
	reason?: string;
};

export type GlobalLoadingPayload = {
	show: boolean;
	scope?: string;
	target?: string;
	text?: string;
	canCancel?: boolean;
	progress?: string;
	statsEnabled?: boolean;
	secondaryText?: string;
	secondaryVisible?: boolean;
	secondaryMode?: 'output' | 'elapsed' | 'tool_elapsed' | string;
	statsChars?: number;
	statsSpeed?: number;
	statsLabel?: string;
} & Record<string, unknown>;

type AppEventMap = {
	'cancel-loading': CancelLoadingPayload;
	'global-loading': GlobalLoadingPayload;
	[key: string]: unknown;
};

export const bus = mitt<AppEventMap>();

export default bus;
