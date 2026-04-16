/**
 * SparkArc 产品主页 · 九幕文案集中存放
 *
 * 设计原则（硬性）：
 *   1. 每段至少含一个具体动作或物件（如"手写便签"、"地铁 11 分钟"）
 *   2. 每段至少一次情感承载（如"心跳了一下"、"献给所有还在写的人"）
 *   3. 技术特性必须落到"你的什么体验发生了什么变化"
 *   4. 对用户用"你"，不用"用户/创作者/您"
 *   5. 禁用词：赋能、引擎、革命、平权、颠覆、一键、神器、黑科技、最强、极致
 */

export const brand = {
  name: 'SparkArc',
  tagline: '灵感之火 · 世界之弧',
  edition: '灵感工业 / 2025',
  chapterFont: 'Ch.',
};

export const nav = {
  links: [
    { id: 'act-seed', label: '灵感' },
    { id: 'act-ensemble', label: '编剧部' },
    { id: 'act-pipeline', label: '流水线' },
    { id: 'act-protocol', label: '协作秩序' },
    { id: 'act-guard', label: '反 AI' },
    { id: 'act-control', label: '白盒' },
    { id: 'act-stage', label: '生态' },
  ],
  cta: '进入工作台',
};

/* ========== 第 0 幕 · 一点星火 ========== */
export const hero = {
  chapterMark: 'Ch. 00 · Spark',
  titleLines: ['让一粒星火', '成为一整个', '可以被阅读的世界'],
  subtitle: '你不必独自写作——一整支编剧部，已经就位。',
  helper: '多智能体创作流水线 · 从灵感 · 到剧本 · 到游戏资产',
  typingWords: [
    '一整支好莱坞编剧部',
    '一本严谨的世界圣经',
    '一套反 AI 的风格基因',
    '一条可分支的剧情蓝图',
    '一位 24 小时的审稿编辑',
    '一枚即插即用的游戏资产',
  ],
  ctaPrimary: { label: '开始写下第一句', to: '/login' },
  ctaSecondary: { label: '先看完这部短片', to: '#act-seed' },
  bindingEye: '装订眼 · 仅做装饰',
};

/* ========== 第 1 幕 · 一个灵感的重量 ========== */
export const seed = {
  chapterMark: 'Ch. 01 · Seed',
  title: '灵感总在不该工作的时候出现',
  subtitle: '我们不指望你当场写下它，只要把它捡起来。',
  noteLines: [
    '地铁隧道里，一个陌生人的背影。',
    '一句歌词，突然和五年前的自己对上。',
    '做梦梦见的一座城，天亮忘了一半。',
    '和 AI 瞎聊，说到某个转折，心跳了一下。',
  ],
  mailboxLabel: '灵感信箱',
  sources: [
    { label: '地铁', detail: '手机端 · 一句话' },
    { label: '歌词', detail: '剪贴板 · 一段文字' },
    { label: '梦', detail: '半睡半醒 · 几个关键词' },
    { label: 'CherryStudio / RikkaHub', detail: 'MCP 客户端 · 聊出来的一个转折' },
  ],
  explainer: [
    '把一句话发到 SparkArc 灵感信箱——',
    '从手机、从 CherryStudio、从你常用的任意 MCP 客户端。',
    '它会被打上风格、基调、视点三个标签，',
    '安静躺在你下一次打开工作台时的案头。',
  ],
};

/* ========== 第 2 幕 · 编剧部的六把椅子 ========== */
export const ensemble = {
  chapterMark: 'Ch. 02 · Ensemble',
  title: '你会在这里遇见他们——',
  subtitle: '六个专家，一张圆桌。分工明确，各自有名。',
  agents: [
    {
      key: 'director',
      name: 'Director',
      zh: '导演',
      role: '最先听见你说话的人。',
      work: '读懂你的诉求，切成子任务，派给合适的专家。',
      signature: 'agent_director.py',
      seat: 'center',
    },
    {
      key: 'muse',
      name: 'Muse',
      zh: '灵感',
      role: '替你把那些会飞走的东西钉在纸上。',
      work: '捕捉 Flash Idea，打上风格 / 基调 / 视点标签。',
      signature: 'agent_muse.py',
      seat: 'top',
    },
    {
      key: 'lorebook',
      name: 'Lorebook',
      zh: '世界观',
      role: '记得一切——从大陆风向到酒馆那只猫。',
      work: '构建世界观、地理、物理法则、角色小传。',
      signature: 'agent_lorebook.py',
      seat: 'top-right',
    },
    {
      key: 'showrunner',
      name: 'Showrunner',
      zh: '文案策划',
      role: '给故事一副不会塌的骨架。',
      work: '生成节拍表、树状大纲，控制幕结构。',
      signature: 'agent_showrunner.py',
      seat: 'bottom-right',
    },
    {
      key: 'scriptwriter',
      name: 'Scriptwriter',
      zh: '执笔编剧',
      role: '终于落笔的那只手。',
      work: '将大纲写成 .arc 剧本——场景、动作、对白。',
      signature: 'agent_scriptwriter.py',
      seat: 'bottom-left',
    },
    {
      key: 'critic',
      name: 'Critic',
      zh: '审稿编辑',
      role: '不替你改稿，但会指着句子告诉你哪里假。',
      work: '五维审稿 S/A/B/C/D，带原文证据与 fix_ticket。',
      signature: 'agent_critic.py',
      seat: 'top-left',
    },
  ],
  tripleMode: {
    title: '他们有三种状态',
    lines: [
      '一个人的时候——你手动叫他。',
      '在聊天里——你和他说话。',
      '被导演派去做活儿——他自己照流程跑完。',
    ],
    tail: '我们把它叫做 Agent 三模态，确保每次你看到的，都是对的那个他。',
  },
};

/* ========== 第 3 幕 · 剧本工业流水线 ========== */
export const pipeline = {
  chapterMark: 'Ch. 03 · Pipeline',
  title: '不是一遍生成，是一条流水线',
  subtitle: '好莱坞花了一百年才搭起来的流程，我们一站一站还原给你。',
  stations: [
    {
      idx: '01',
      zh: '种子',
      en: 'Seed',
      hollywood: 'Logline',
      desc: '一句话的核心概念。够短，才经得起所有人反复追问。',
      work: '打上风格、基调、视点标签；给 Muse 起草。',
    },
    {
      idx: '02',
      zh: '世界',
      en: 'World',
      hollywood: 'Story Bible',
      desc: '一本只属于这个故事的字典。从大陆风向到酒馆的猫。',
      work: 'Lorebook 沉淀设定；跨章节一致性自动校验。',
    },
    {
      idx: '03',
      zh: '节拍',
      en: 'Beats',
      hollywood: 'Beat Sheet',
      desc: '故事的心跳。哪里紧，哪里松，哪里翻面。',
      work: 'Showrunner 生成节拍表；你手动调张力曲线。',
    },
    {
      idx: '04',
      zh: '大纲',
      en: 'Outline',
      hollywood: 'Treatment',
      desc: '骨架立好，每个章节知道自己要完成什么。',
      work: '树状大纲；章内事件 · 章间钩子一目了然。',
    },
    {
      idx: '05',
      zh: '剧本',
      en: '.arc',
      hollywood: 'Screenplay',
      desc: '落笔。场景、动作、对白——直接可演、可跑、可读。',
      work: 'Scriptwriter 按大纲落笔；Markdown 流畅 + XML 严谨。',
    },
    {
      idx: '06',
      zh: '审稿',
      en: 'Review',
      hollywood: 'Script Doctor',
      desc: '过关才叫定稿。过不了，就带工单回上一站。',
      work: 'Critic 五维打分 S/A/B/C/D；B 及以下生成 fix_ticket。',
    },
  ],
  workCard: {
    title: '当前工单 · 示例',
    fields: [
      { label: '场景', value: '废弃地铁站 · 凌晨 3:17' },
      { label: '节拍', value: '主角首次见到反派' },
      { label: '情绪张力', value: '0.82 · 紧绷' },
      { label: 'Critic 等级', value: 'B · 对白解释腔略重' },
      { label: 'fix_ticket', value: '#0132 → 回到第 05 站' },
    ],
  },
  tail: {
    title: '每一环都能被看见，也能被打断',
    body:
      '他们做的不是一遍生成。是像一间真的编剧部那样——流水线上的每一环，都有自己的名字、自己的产出、自己的错误码。',
  },
};

/* ========== 第 4 幕 · 信标 · 号角 · 旗帜 ========== */
export const protocol = {
  chapterMark: 'Ch. 04 · Protocol',
  title: '他们有自己的秩序',
  subtitle: '谁可以听，谁可以说，谁现在在做——都写在明面上。',
  triad: [
    {
      key: 'beacon',
      name: '信标',
      en: 'Beacon',
      question: '他能不能被看见？',
      detail: 'Scriptwriter 进入心流的长章写作，关上信标，其他 Agent 与 UI 都无法打扰他。',
      log: '[Beacon] Scriptwriter 进入心流模式，关闭信标',
    },
    {
      key: 'horn',
      name: '号角',
      en: 'Horn',
      question: '他能不能主动开口？',
      detail: '只有拿到号角的 Agent 能越级呼唤其他 Agent——避免所有人同时开口的广播风暴。',
      log: '[Horn]   Director 吹响号角，将任务分发给 Showrunner',
    },
    {
      key: 'baton',
      name: '旗帜',
      en: 'Baton',
      question: '这条任务现在归谁？',
      detail: 'Director 把任务交给 Lorebook，旗帜就转到 Lorebook 手上；做完再回到 Director。',
      log: '[Baton]  旗帜已由 Director 转交至 Lorebook',
    },
  ],
  tail: '你的 AI 不再是一团模糊的模型黑盒。他们是一个真的有秩序的团队。',
};

/* ========== 第 5 幕 · 反 AI 双保险 ========== */
export const guard = {
  chapterMark: 'Ch. 05 · Guard',
  title: '为什么 SparkArc 写出来的字，不像 AI',
  subtitle: '两道关，一前一后，像编辑部审稿一样较真。',
  styleLoop: {
    title: '风格克隆图灵回测',
    steps: [
      '读完你指定作家的所有作品——按 30k tokens 一块，串行分析。',
      '每一块末尾做剧情概括，传给下一块。读到最后一页，也不会忘记第一章的气味。',
      '交给 ValidatorAgent 替你写一段。',
      '他会自己打脸说"这段还是 AI"，生成负向约束，注入档案。',
      '直到他写的东西，连他自己都认不出是 AI。',
    ],
    tag: 'UnifiedStyleAnalyzer + ValidatorAgent',
    verdict: '图灵回测通过 · 风格档案已固化',
  },
  criticTicket: {
    title: 'Critic 五维审稿单',
    meta: [
      { label: '审稿人', value: 'Critic Agent' },
      { label: '等级', value: 'B' },
      { label: '五维', value: '结构 · 语言 · 对白 · AI 检测 · 人设' },
    ],
    evidence: {
      quote: '"他望着窗外，陷入了沉思。"',
      issue: '解释腔过重，动作空白。',
      suggest: '删掉"陷入了沉思"，换成一个具体动作——指节敲桌、烟灰掉地。',
    },
    ticketId: 'fix_ticket#0132',
    tail: 'S/A 通过；B/C/D 带着工单回到 Scriptwriter 重写。',
  },
  graphRag: {
    title: 'GraphRAG 事实约束',
    body: '跨章节的"这个角色上卷刚死，这章不能复活"这类吃书问题，也会被自动挡在门外。',
  },
};

/* ========== 第 6 幕 · 白盒可控 ========== */
export const control = {
  chapterMark: 'Ch. 06 · White-box',
  title: '每一步都看得见，也改得动',
  subtitle: '三档介入 · 打断 · 重写 · 指定专家',
  modes: [
    {
      key: 'manual',
      label: '全手动',
      desc: '只用结构化编辑器，AI 只做梳理、验证、建议。你是唯一的笔。',
    },
    {
      key: 'semi',
      label: '半自动（推荐）',
      desc: '你给灵感与情感高光，AI 填细节与润色。两个人一起写。',
      recommended: true,
    },
    {
      key: 'auto',
      label: '全自动',
      desc: '只给一个模糊的想法，AI 给你多条候选。你负责挑。',
    },
  ],
  stamps: [
    { key: 'stop', label: '打断', desc: '任何时候点击，当前生成立刻停，已写入部分完整保留。' },
    { key: 'rewrite', label: '重写', desc: '选中一段，指定"用 Critic 的审稿意见 + Scriptwriter 重写"。' },
    { key: 'delegate', label: '指定专家', desc: '不满意 Scriptwriter 的输出？单独把 Muse 或 Showrunner 叫过来二次加工。' },
  ],
  tail: '普通 AI 工具把所有秘密藏在黑盒里，只给你一个"生成完成"。我们相信创作的尊严，在于每一步都看得见，也改得动。',
};

/* ========== 第 7 幕 · 故事登台演出 ========== */
export const stage = {
  chapterMark: 'Ch. 07 · Stage',
  title: '写完之后，故事才开始',
  subtitle: '剧本不是躺在 doc 里的字——是游戏、是分享、是演出。',
  cards: [
    {
      key: 'mobile',
      title: '地铁 5 分钟',
      head: '手机端 · 移动版工作台',
      body: '早高峰的 11 分钟，够你审完昨天 AI 写的三章大纲，在一个转折上打个勾。',
    },
    {
      key: 'mcp',
      title: 'MCP 灵感信箱',
      head: 'CherryStudio / RikkaHub / 任意 MCP 客户端',
      body: '和任意 AI 助手聊到的一个好主意，一句话发进信箱，就是故事的种子。',
    },
    {
      key: 'web',
      title: 'WEB 演出端',
      head: '一键生成分享链接',
      body: '朋友不需要装任何东西，点击链接，就走进你的故事。角色对话、选项分支、音乐与氛围，全都在那里。',
    },
    {
      key: 'unity',
      title: 'Unity SDK',
      head: '剧本即游戏资产',
      body: '把 .arc 文件放进 StreamingAssets，DialogueManager 自动加载。改剧本不再需要重新编译。',
    },
  ],
  platforms: 'Windows · macOS · Linux · Android · iOS · Web · Unity',
  tail: '你创作的容器，比你想象中更安静地无处不在。',
};

/* ========== 第 8 幕 · 写给未来的创作者 ========== */
export const finale = {
  chapterMark: 'Ch. 08 · Finale',
  title: '情感，必须源于你的脉搏。',
  creed: [
    '我们做这个工具，不是为了代替任何人去写。',
    '而是因为——在这个 AI 泛滥的时代，',
    '人类的灵感主权，需要一个更好的工具去守住。',
    '让 AI 臣服于你的创造力，而不是反过来。',
  ],
  ctaPrimary: { label: '写下你的第一句', to: '/login' },
  ctaSecondary: { label: '先在本地跑一遍试试', to: 'https://github.com/' },
  micro: '项目基于 AGPL-3.0 开源 · 由 Mournight 独立开发 · 献给所有还在写的人。',
};

/* ========== Footer ========== */
export const footer = {
  brand: {
    name: 'SparkArc',
    tagline: '灵感之火 · 世界之弧',
  },
  columns: [
    {
      title: '产品',
      links: [
        { label: '核心功能', to: '#act-ensemble' },
        { label: '流水线', to: '#act-pipeline' },
        { label: '下载', to: '/login' },
      ],
    },
    {
      title: '社区',
      links: [
        { label: 'GitHub', to: 'https://github.com/' },
        { label: '文档', to: '#' },
        { label: '进入工作台', to: '/login' },
      ],
    },
  ],
  copyright: '© 2025 SparkArc · All rights reserved.',
  disclaimer:
    '第三方部署实例由其运营者独立负责，与 SparkArc 上游作者不存在代理、联营或共同运营关系。',
};
