# SparkArc 法律与运营声明目录

本目录用于存放 SparkArc 仓库级的中文法律与运营声明，目标是同时服务于以下场景：

- 为仓库维护者提供可公开引用的法律与运营说明
- 为官方实例提供可直接展示或复用的站内文档
- 为第三方部署者提供最小合规参考与责任边界说明
- 为主体识别、内容治理、侵权处理与证据管理提供统一入口

重要说明：

- 本目录内容仅作为项目文档与风控参考，不构成正式法律意见。
- 第三方部署者在对公众提供服务前，应结合自身主体、部署地、用户地区、所接入模型与具体业务形态自行补充、修改并承担责任。
- 若本目录文件与第三方实例自定条款冲突，以该第三方实例自行公示并实际执行的文件为准；但该第三方实例不得据此冒充 SparkArc 官方实例。

阅读顺序：

1. `OfficialInstancePolicy.zh-CN.md`
2. `ThirdPartyOperatorNotice.zh-CN.md`
3. `TermsOfService.zh-CN.md`
4. `PrivacyPolicy.zh-CN.md`
5. `ContentPolicy.zh-CN.md`
6. `EvidenceAndIPCompliance.zh-CN.md`

文件用途说明：

- `TermsOfService.zh-CN.md`
  当前实例对注册用户的服务条款、使用规则与免责声明。
- `PrivacyPolicy.zh-CN.md`
  当前实例对个人信息处理、日志留存、模型转发与用户权利的说明。
- `OfficialInstancePolicy.zh-CN.md`
  用于区分官方实例与第三方实例，降低主体混淆风险。
- `ThirdPartyOperatorNotice.zh-CN.md`
  用于明确第三方站长独立运营、独立负责的边界。
- `ContentPolicy.zh-CN.md`
  用于明确禁止内容、投诉举报、侵权通知、下架与封禁规则。
- `EvidenceAndIPCompliance.zh-CN.md`
  用于说明贡献者版权、来源证明、电子证据固定与知识产权争议处理建议。

维护说明：

- 对外提供服务的实例，应在登录页、页脚、帮助页或设置页显著位置链接本目录中的核心文件。
- `server/core/routes_tos.py` 应优先读取本目录中的 `TermsOfService.zh-CN.md`，保证仓库与站内展示同源。
- 如后续新增官方域名、商标、软件著作权登记号、投诉邮箱、备案号，应优先更新本目录，再同步到页面。
