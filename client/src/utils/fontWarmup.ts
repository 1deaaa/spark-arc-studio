const DEFAULT_FONT_FAMILY = 'LXGW WenKai Screen';
const DEFAULT_FONT_SIZE = '16px';
const DEFAULT_TIMEOUT_MS = 1200;
// 登录界面预热字符：大小写字母 + 阿拉伯数字 + 密码遮盖符 + 登录页常用中文。
const LOGIN_FONT_SAMPLE = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789•●·登录注册密码用户名记住忘记邮箱确认提交服务器连接进入中文日本語한국어';

const pendingLoads = new Map<string, Promise<boolean>>();
let commonChineseWarmupPromise: Promise<boolean> | null = null;

export type FontWarmupOptions = {
  fontFamily?: string;
  fontSize?: string;
  timeoutMs?: number;
  maxChars?: number;
};

function compactSample(text: string, maxChars: number): string {
  const seen = new Set<string>();
  let result = '';
  for (const char of String(text || '').normalize('NFC')) {
    if (!char.trim()) continue;
    if (seen.has(char)) continue;
    seen.add(char);
    result += char;
    if (result.length >= maxChars) break;
  }
  return result;
}

function splitFontFamilies(stack: string): string[] {
  const result: string[] = [];
  let current = '';
  let quote = '';
  for (const char of stack) {
    if (quote) {
      current += char;
      if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      current += char;
      continue;
    }
    if (char === ',') {
      if (current.trim()) {
        result.push(current.trim());
      }
      current = '';
      continue;
    }
    current += char;
  }
  if (current.trim()) {
    result.push(current.trim());
  }
  return result;
}

function stripFamilyQuotes(family: string): string {
  return family.trim().replace(/^['"]+|['"]+$/g, '');
}

function quoteFontFamily(family: string): string {
  if (/^['"].*['"]$/.test(family)) {
    return family;
  }
  if (/^[a-z0-9-]+$/i.test(family)) {
    return family;
  }
  return `"${family.replace(/"/g, '\\"')}"`;
}

function getFontApi(): FontFaceSet | null {
  if (typeof document === 'undefined') {
    return null;
  }
  if (!('fonts' in document)) {
    return null;
  }
  const fontSet = document.fonts;
  if (!fontSet || typeof fontSet.load !== 'function' || typeof fontSet.check !== 'function') {
    return null;
  }
  return fontSet;
}

function resolvePrimaryFontFamily(explicitFamily?: string): string {
  const preferred = stripFamilyQuotes(String(explicitFamily || '').trim());
  if (preferred) {
    return preferred;
  }
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return DEFAULT_FONT_FAMILY;
  }
  const target = document.body || document.documentElement;
  const computed = window.getComputedStyle(target);
  const fromVar = computed.getPropertyValue('--spark-font').trim();
  const stack = fromVar || computed.fontFamily || DEFAULT_FONT_FAMILY;
  const firstFamily = splitFontFamilies(stack)[0];
  return stripFamilyQuotes(firstFamily || DEFAULT_FONT_FAMILY) || DEFAULT_FONT_FAMILY;
}

function waitWithTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T | null> {
  return new Promise((resolve) => {
    const timerId = window.setTimeout(() => resolve(null), timeoutMs);
    promise
      .then((value) => {
        window.clearTimeout(timerId);
        resolve(value);
      })
      .catch(() => {
        window.clearTimeout(timerId);
        resolve(null);
      });
  });
}

function getLoadTask(fontSet: FontFaceSet, descriptor: string, sample: string): Promise<boolean> {
  const cacheKey = `${descriptor}__${sample}`;
  const existing = pendingLoads.get(cacheKey);
  if (existing) {
    return existing;
  }
  const task = fontSet
    .load(descriptor, sample)
    .then(() => fontSet.check(descriptor, sample))
    .catch(() => false)
    .finally(() => {
      pendingLoads.delete(cacheKey);
    });
  pendingLoads.set(cacheKey, task);
  return task;
}

export async function ensureAppFontReadyForText(text: string, options: FontWarmupOptions = {}): Promise<boolean> {
  const fontSet = getFontApi();
  if (!fontSet) {
    return true;
  }
  const sample = compactSample(text, options.maxChars ?? 120);
  if (!sample) {
    return true;
  }
  const family = resolvePrimaryFontFamily(options.fontFamily);
  const descriptor = `${options.fontSize || DEFAULT_FONT_SIZE} ${quoteFontFamily(family)}`;
  if (fontSet.check(descriptor, sample)) {
    return true;
  }
  const loaded = await waitWithTimeout(getLoadTask(fontSet, descriptor, sample), options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  if (loaded === null) {
    return false;
  }
  return loaded;
}

export function warmupAppFontInBackground(text: string, options: FontWarmupOptions = {}): void {
  if (typeof window === 'undefined') {
    return;
  }
  const sample = compactSample(`${LOGIN_FONT_SAMPLE}${text || ''}`, options.maxChars ?? 180);
  if (!sample) {
    return;
  }
  window.setTimeout(() => {
    void ensureAppFontReadyForText(sample, {
      ...options,
      timeoutMs: options.timeoutMs ?? 2500,
      maxChars: options.maxChars ?? 160,
    });
  }, 0);
}

// ============================================================================
// 常用汉字后台静默预热逻辑
// ============================================================================

const COMMON_CHINESE_CHARS = '阿啊哎哀唉埃挨癌矮艾爱碍安氨俺岸按案暗昂凹熬傲奥澳八巴叭吧拔把坝爸罢霸白百柏摆败拜班般颁斑搬板版办半伴扮瓣邦帮膀傍棒包胞宝饱保堡报抱豹暴爆卑杯悲碑北贝备背倍被辈奔本崩逼鼻比彼笔币必毕闭辟碧蔽壁避臂边编蝙鞭扁便变遍辨辩标表别宾滨冰兵丙柄饼并病拨波玻剥播脖伯驳泊勃博搏膊薄卜补捕不布步部擦猜才材财裁采彩踩菜蔡参餐残蚕惨灿仓苍舱藏操曹槽草册侧测策层叉插查茶察差拆柴缠产阐颤昌长肠尝偿常厂场畅倡唱抄超巢朝潮吵炒车扯彻撤尘臣沉陈闯衬称趁撑成呈承诚城乘惩程橙吃池驰迟持匙尺齿斥赤翅充冲虫崇抽仇绸愁筹酬丑瞅臭出初除厨础储楚处触川穿传船喘串窗床晨创吹垂锤春纯唇醇词瓷慈辞磁雌此次刺从匆葱聪丛凑粗促催脆翠村存寸措错搭达答打大呆代带待袋逮戴丹单担胆旦但诞弹淡蛋氮当挡党荡刀导岛倒蹈到盗道稻得德的灯登等邓凳瞪低堤滴迪敌笛底抵地弟帝递第颠典点电店垫淀殿雕吊钓调掉爹跌叠蝶丁叮盯钉顶订定丢东冬懂动冻洞都斗抖陡豆督毒读独堵赌杜肚度渡端短段断锻堆队对吨敦蹲盾顿多夺朵躲俄鹅额恶饿鳄恩儿而尔耳二发乏伐罚阀法帆番翻凡烦繁反返犯泛饭范贩方坊芳防妨房肪仿访纺放飞非啡菲肥废沸肺费分纷芬坟粉份奋愤粪丰风枫封疯峰锋蜂冯逢缝凤奉佛否夫肤孵弗伏扶服浮符幅福辐蝠抚府辅腐父付妇负附复赴副傅富赋腹覆该改钙盖溉概干甘杆肝赶敢感刚岗纲缸钢港高搞稿告戈哥胳鸽割歌阁革格葛隔个各给根跟更耕工弓公功攻供宫恭巩拱共贡勾沟钩狗构购够估咕姑孤菇古谷股骨鼓固故顾瓜刮挂拐怪关观官冠馆管贯惯灌罐光广归龟规硅轨鬼柜贵桂滚棍郭锅国果裹过哈孩海害含函寒韩罕喊汉汗旱杭航毫豪好号浩耗呵喝合何和河核荷盒贺褐赫鹤黑嘿痕很狠恨哼恒横衡轰哄红宏洪虹鸿侯喉猴吼后厚候乎呼忽狐胡壶湖葫糊蝴虎互户护花华哗滑化划画话桦怀淮坏欢还环缓幻唤换患荒慌皇黄煌晃灰恢挥辉徽回毁悔汇会绘惠慧昏婚浑魂混活火伙或货获祸惑霍击饥圾机肌鸡积基迹绩激及吉级即极急疾集辑籍几己挤脊计记纪忌技际剂季既济继寂寄加夹佳家嘉甲贾钾价驾架假嫁稼尖坚间肩艰兼监减剪检简碱见件建剑健舰渐践鉴键箭江姜将浆僵疆讲奖蒋匠降交郊娇浇骄胶焦礁角脚搅叫轿较教阶皆接揭街节劫杰洁结捷截竭姐解介戒届界借巾今斤金津筋仅紧锦尽劲近进晋浸禁京经茎惊晶睛精鲸井颈景警净径竞竟敬境静镜纠究九久酒旧救就舅居局菊橘举矩句巨拒具俱剧惧据距聚卷倦决绝觉掘嚼军君均菌俊峻卡开凯慨刊堪砍看康抗炕考烤靠科棵颗壳咳可渴克刻客课肯坑空孔恐控口扣枯哭苦库裤酷夸跨块快宽款狂况矿亏葵愧溃昆困扩括阔垃拉啦喇腊蜡辣来莱赖兰拦栏蓝篮览懒烂滥郎狼廊朗浪捞劳牢老乐勒雷蕾泪类累冷愣厘梨离莉犁璃黎礼李里哩理鲤力历厉立丽利励例隶粒俩连帘怜莲联廉脸练炼恋链良凉梁粮两亮辆量辽疗聊僚了料列劣烈猎裂邻林临淋磷灵玲凌铃陵羚零龄领岭令另溜刘流留硫瘤柳六龙笼隆垄拢楼漏露卢芦炉鲁陆录鹿碌路驴旅铝履律虑率绿氯滤卵乱掠略伦轮论罗萝逻螺裸洛络骆落妈麻马玛码蚂骂吗嘛埋买迈麦卖脉蛮满曼慢漫忙芒盲茫猫毛矛茅茂冒贸帽貌么没枚玫眉梅媒煤霉每美妹门闷们萌盟猛蒙孟梦弥迷谜米泌秘密蜜眠绵棉免勉面苗描秒妙庙灭民敏名明鸣命摸模膜摩磨蘑魔抹末沫陌莫漠墨默谋某母亩牡姆拇木目牧墓幕慕穆拿哪内那纳娜钠乃奶奈耐男南难囊恼脑闹呢嫩能尼泥你拟逆年念娘酿鸟尿捏您宁凝牛扭纽农浓弄奴努怒女暖挪诺哦欧偶爬帕怕拍排牌派攀盘判叛盼庞旁胖抛炮跑泡胚陪培赔佩配喷盆朋棚蓬鹏膨捧碰批披皮疲脾匹屁譬片偏篇骗漂飘瓢票拼贫频品平评凭苹屏瓶萍坡泼颇婆迫破剖扑铺葡蒲朴浦普谱七妻栖戚期欺漆齐其奇歧骑棋旗企岂启起气弃汽契砌器恰千迁牵铅谦签前钱潜浅遣欠枪腔强墙抢悄敲乔桥瞧巧切茄且窃亲侵秦琴禽勤青氢轻倾清情晴顷请庆穷丘秋蚯求球区曲驱屈躯趋取娶去趣圈全权泉拳犬劝券缺却雀确鹊裙群然燃染嚷壤让饶扰绕惹热人仁忍认任扔仍日绒荣容溶熔融柔肉如儒乳辱入软锐瑞润若弱撒洒萨塞赛三伞散桑嗓丧扫嫂色森僧杀沙纱刹砂傻啥晒山杉衫珊闪陕扇善伤商赏上尚梢烧稍少绍哨舌蛇舍设社射涉摄申伸身深神审婶肾甚渗慎升生声牲胜绳省圣盛剩尸失师诗施狮湿十什石时识实拾蚀食史使始驶士氏世市示式事侍势视试饰室是适逝释收手守首寿受兽售授瘦书抒叔枢殊疏舒输蔬熟暑署属鼠薯术束述树竖数刷耍衰摔甩帅双霜爽谁水税睡顺瞬说丝司私思斯撕死四寺似饲松耸宋送颂搜艘苏俗诉肃素速宿塑酸蒜算虽随髓岁遂碎穗孙损笋缩所索锁他它她塌塔踏胎台抬太态泰贪摊滩坛谈潭坦叹炭探碳汤唐堂塘糖躺趟涛掏逃桃陶淘萄讨套特疼腾藤梯踢啼提题蹄体替天添田甜填挑条跳贴铁厅听廷亭庭停蜓挺艇通同桐铜童统桶筒痛偷头投透突图徒涂途屠土吐兔团推腿退吞托拖脱驼妥拓唾挖哇蛙娃瓦歪外弯湾丸完玩顽挽晚碗万汪亡王网往忘旺望危威微为围违唯惟维伟伪尾纬委萎卫未位味胃谓喂慰魏温文纹闻蚊吻稳问翁窝我沃卧握乌污屋无吴吾五午伍武舞务物误悟雾夕西吸希析息牺悉惜晰稀溪锡熙嘻膝习席袭媳洗喜戏系细隙虾瞎峡狭辖霞下吓夏厦仙先纤掀鲜闲弦贤咸衔嫌显险县现线限宪陷献腺乡相香厢湘箱详祥翔享响想向巷项象像橡削消萧硝销小晓孝效校笑些歇协胁斜谐携鞋写泄泻卸屑械谢蟹心辛欣新信兴星猩刑行形型醒杏姓幸性凶兄匈胸雄熊休修羞朽秀绣袖嗅须虚需徐许序叙畜绪续蓄宣玄悬旋选穴学雪血寻巡询循训讯迅压呀鸦鸭牙芽崖哑雅亚咽烟淹延严言岩沿炎研盐颜衍掩眼演厌宴艳验焰雁燕央扬羊阳杨洋仰养氧痒样腰邀摇遥咬药要耀爷也冶野业叶页夜液一伊衣医依仪夷宜姨移遗疑乙已以矣蚁椅义亿忆艺议亦异役抑译易疫益谊逸意溢毅翼因阴音吟银引饮蚓隐印应英婴鹰迎盈营蝇赢影映硬哟拥永泳勇涌用优忧幽悠尤犹由邮油游友有又右幼诱于予余鱼娱渔愉愚与宇羽雨语玉吁育郁狱浴预域欲喻寓御裕遇愈誉豫元员园原圆袁援缘源远怨院愿曰约月岳钥悦阅跃越云匀允孕运晕韵蕴杂砸灾栽宰载再在咱暂赞脏葬遭糟早枣藻灶皂造噪燥躁则择泽责贼怎曾增赠渣扎眨炸摘宅窄债沾粘展占战站张章涨掌丈仗帐胀账障招找召兆赵照罩遮折哲者这浙针侦珍真诊枕阵振镇震争征挣睁蒸整正证郑政症之支汁芝枝知织肢脂蜘执直值职植殖止只旨址纸指趾至志制治质致智置中忠终钟肿种仲众重州舟周洲轴宙皱骤朱株珠诸猪蛛竹烛逐主煮嘱住助注贮驻柱祝著筑抓爪专砖转赚庄桩装壮状撞追准捉桌着仔兹姿资滋籽子紫字自宗综棕踪总纵走奏租足族阻组祖钻嘴最罪醉尊遵昨左作坐座做蔼隘庵鞍黯肮拗袄懊扒芭疤捌跋靶掰扳拌绊梆绑榜蚌谤磅镑苞褒雹鲍狈悖惫笨绷泵蹦匕鄙庇毙痹弊璧贬匾辫彪憋鳖瘪彬斌缤濒鬓秉禀菠舶渤跛簸哺怖埠簿睬惭沧糙厕蹭茬岔豺掺搀禅馋蝉铲猖敞钞嘲澈忱辰铛澄逞秤痴弛侈耻宠畴稠锄雏橱矗揣囱疮炊捶椿淳蠢戳绰祠赐醋簇窜篡崔摧悴粹搓撮挫瘩歹怠贷耽档叨捣祷悼蹬嘀涤缔蒂掂滇巅碘佃甸玷惦奠刁叼迭谍碟鼎董栋兜蚪逗痘睹妒镀缎兑墩盹囤钝咄哆踱垛堕舵惰跺讹娥峨蛾扼鄂愕遏噩饵贰筏矾妃匪诽吠吩氛焚忿讽敷芙拂俘袱甫斧俯脯咐缚尬丐柑竿尴秆橄赣冈肛杠羔膏糕镐疙搁蛤庚羹埂耿梗蚣躬汞苟垢沽辜雇寡卦褂乖棺逛闺瑰诡癸跪亥骇酣憨涵悍捍焊憾撼翰夯嚎皓禾烘弘弧唬沪猾徊槐宦涣焕痪凰惶蝗簧恍谎幌卉讳诲贿晦秽荤豁讥叽唧缉畸箕稽棘嫉妓祭鲫冀颊奸歼煎拣俭柬茧捡荐贱涧溅槛缰桨酱椒跤蕉侥狡绞饺矫剿缴窖酵秸睫芥诫藉襟谨荆兢靖窘揪灸玖韭臼疚拘驹鞠桔沮炬锯娟捐鹃绢眷诀倔崛爵钧骏竣咖揩楷勘坎慷糠扛亢拷铐坷苛磕蝌垦恳啃吭抠叩寇窟垮挎筷筐旷框眶盔窥魁馈坤捆廓睐婪澜揽缆榄琅榔唠姥涝烙酪垒磊肋擂棱狸漓篱吏沥俐荔栗砾痢雳镰敛粱谅晾寥嘹撩缭瞭咧琳鳞凛吝赁躏拎伶聆菱浏琉馏榴咙胧聋窿娄搂篓陋庐颅卤虏赂禄吕侣屡缕峦抡仑沦啰锣箩骡蟆馒瞒蔓莽锚卯昧媚魅氓朦檬锰咪靡眯觅缅瞄渺藐蔑皿闽悯冥铭谬馍摹茉寞沐募睦暮捺挠瑙呐馁妮匿溺腻捻撵碾聂孽拧狞柠泞钮脓疟虐懦糯殴鸥呕藕趴啪耙徘湃潘畔乓螃刨袍沛砰烹彭澎篷坯劈霹啤僻翩撇聘乒坪魄仆菩圃瀑曝柒凄祈脐崎鳍乞迄泣掐洽钳乾黔谴嵌歉呛跷锹侨憔俏峭窍翘撬怯钦芹擒寝沁卿蜻擎琼囚岖渠痊瘸冉瓤壬刃纫韧戎茸蓉榕冗揉蹂蠕汝褥蕊闰腮叁搔骚臊涩瑟鲨煞霎筛删煽擅赡裳晌捎勺奢赦呻绅沈笙甥矢屎恃拭柿嗜誓梳淑赎蜀曙恕庶墅漱蟀拴栓涮吮烁硕嗽嘶巳伺祀肆讼诵酥粟溯隋祟隧唆梭嗦琐蹋苔汰瘫痰谭檀毯棠膛倘淌烫滔誊剔屉剃涕惕恬舔迢帖彤瞳捅凸秃颓蜕褪屯豚臀驮鸵椭洼袜豌宛婉惋皖腕枉妄偎薇巍帷苇畏尉猬蔚瘟紊嗡涡蜗呜巫诬芜梧蜈侮捂鹉勿戊昔犀熄蟋徙匣侠暇馅羡镶宵潇箫霄嚣淆肖哮啸蝎邪挟懈芯锌薪馨衅腥汹锈戌墟旭恤酗婿絮轩喧癣炫绚渲靴薛勋熏旬驯汛逊殉丫押涯衙讶焉阎蜒檐砚唁谚堰殃秧鸯漾夭吆妖尧肴姚窑谣舀椰腋壹怡贻胰倚屹邑绎姻茵荫殷寅淫瘾莺樱鹦荧莹萤颖佣庸咏踊酉佑迂淤渝隅逾榆舆屿禹芋冤鸳渊猿苑粤耘陨酝哉赃凿蚤澡憎咋喳轧闸乍诈栅榨斋寨毡瞻斩盏崭辗栈绽彰樟杖昭沼肇辙蔗贞斟疹怔狰筝拯吱侄帜挚秩掷窒滞稚衷粥肘帚咒昼拄瞩蛀铸拽撰妆幢椎锥坠缀赘谆卓拙灼茁浊酌啄琢咨姊揍卒佐佘赊';

/**
 * 页面加载完毕且主线程空闲时，在后台静默预热 3500 常用中文字集
 * 一次性发起加载，利用浏览器和 CDN 的 HTTP/2 并发优势极速完成预热并写入强缓存
 */
export function warmupCommonChineseCharacters(): Promise<boolean> {
  if (typeof window === 'undefined') {
    return Promise.resolve(false);
  }
  if (commonChineseWarmupPromise) {
    return commonChineseWarmupPromise;
  }

  commonChineseWarmupPromise = new Promise((resolve) => {
    const idleCallback = window.requestIdleCallback;

    const triggerWarmup = () => {
      void ensureAppFontReadyForText(COMMON_CHINESE_CHARS, {
        timeoutMs: 5000,
        maxChars: 4000,
      }).then(resolve).catch(() => resolve(false));
    };

    // 保证在浏览器完全空闲（Idle）时触发，支持 requestIdleCallback 时优先使用
    if (typeof idleCallback === 'function') {
      idleCallback(() => triggerWarmup(), { timeout: 8000 });
      return;
    }
    window.setTimeout(() => triggerWarmup(), 2500);
  });

  return commonChineseWarmupPromise;
}
