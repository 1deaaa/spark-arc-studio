// 全局变量
let scriptData = [];  // 完整的脚本数据
let currentScene = null;  // 当前选中的场景
let currentNode = null;  // 当前选中的节点
let nodeParent = null;  // 当前节点的父节点 (用于选项的子对话)
let undoStack = [];  // 撤销栈
let redoStack = [];  // 重做栈

// DOM 元素
const sceneListEl = document.getElementById('scene-list');
const dialogueTreeEl = document.getElementById('dialogue-tree');
const nodeEditorEl = document.getElementById('node-editor');

const sceneEditorEl = document.getElementById('scene-editor');
const dialogueEditorEl = document.getElementById('dialogue-editor');
const optionEditorEl = document.getElementById('option-editor');

const dialogueNextEl = document.getElementById('dialogue-next');

// 常用DOM元素获取工具函数
function getElement(id) {
    return document.getElementById(id);
}