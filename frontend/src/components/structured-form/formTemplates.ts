import type { StructuredFormData } from '../../types/structuredForm';

export type FormTemplate = {
  id: string;
  label: string;
  description: string;
  data: StructuredFormData;
};

export const FORM_TEMPLATES: FormTemplate[] = [
  {
    id: 'friend-circle-copywriter',
    label: '朋友圈文案助手',
    description: 'C 端 AI 文案生成工具，适合演示完整表单结构',
    data: {
      product_name: '朋友圈文案助手',
      product_goal: '帮助运营人员快速生成高质量朋友圈文案，降低内容创作门槛。',
      target_users: '微商\n销售\n自媒体从业者\n小企业主',
      platform: '网页应用（Web App）',
      mvp_features: [
        { name: '场景分类选择', description: '提供 7 个预设场景标签供用户单选', user_value: '降低用户思考成本，快速确定文案方向' },
        { name: '场景自由描述', description: '允许用户补充具体场景描述，最多 200 字', user_value: '支持个性化生成，提高结果准确性' },
        { name: '风格与字数选择', description: '提供 6 个预设风格与 4 档字数区间', user_value: '控制输出文案调性与长度' },
        { name: '一次生成 3 条文案', description: '基于当前条件返回 3 条不同文案', user_value: '提供更多可选结果' },
        { name: '一键复制', description: '每条文案提供复制按钮并显示成功提示', user_value: '缩短从生成到发布的路径' },
        { name: '换一批', description: '保留原条件重新生成 3 条文案', user_value: '快速获取替代结果' },
      ],
      v2_features: '历史记录\n收藏功能\n文案模板库\n批量生成',
      ui_pages: [
        { name: '输入页', modules: '场景分类,场景描述,风格选择,字数范围,参考示例,生成按钮', notes: '主输入视图' },
        { name: '结果页', modules: '结果卡片,复制按钮,换一批按钮,修改条件按钮', notes: '展示生成结果' },
      ],
      interaction_notes: '采用单页应用形式，通过输入页和结果页两个视图切换完成主流程\n返回修改条件时保留原输入内容',
      design_theme: '科技感暗色',
      responsive: '需要',
      auth: '不需要登录',
      database: '不需要数据库',
      frontend: 'React + TypeScript',
      backend: 'Serverless Function',
      deployment: 'Vercel + Serverless Function',
      llm_usage: '调用大语言模型 API，一次生成 3 条朋友圈文案。',
      security_requirements: 'API Key 仅存储在服务端环境变量中\n前端做输入长度限制与基础 XSS 防护',
      performance_requirements: '页面首次加载时间不超过 2 秒\nAI 文案生成响应时间不超过 10 秒',
      usability_requirements: '表单校验需提供实时反馈\n生成失败时保留用户已填写内容',
      in_scope: '单页 Web 应用\n输入页与结果页视图切换\n生成 3 条文案与复制换一批',
      out_of_scope: '用户登录注册\n历史记录与收藏\n后台管理\n原生 App',
    },
  },
  {
    id: 'internal-approval',
    label: '内部审批流',
    description: 'B 端企业内部审批与待办管理',
    data: {
      product_name: '内部审批流',
      product_goal: '让员工在统一平台发起、审批和跟踪各类内部申请，减少邮件与口头沟通成本。',
      target_users: '普通员工\n部门负责人\nHR 与行政\n财务人员',
      platform: '网页应用（Web App）',
      mvp_features: [
        { name: '发起申请', description: '支持请假、报销、采购等模板化申请表单', user_value: '统一入口，减少填表困惑' },
        { name: '审批流转', description: '按组织架构自动路由给直属上级与相关审批人', user_value: '流程透明，减少催办' },
        { name: '待办中心', description: '审批人可查看待办、已办与抄送列表', user_value: '集中处理，不遗漏任务' },
        { name: '状态跟踪', description: '发起人可实时查看当前节点与历史意见', user_value: '进度可查，降低焦虑' },
        { name: '消息通知', description: '关键节点通过站内信或邮件提醒', user_value: '及时触达相关人' },
      ],
      v2_features: '移动端审批\n批量审批\n流程设计器\n与 OA 集成',
      ui_pages: [
        { name: '工作台', modules: '待办列表,我发起的,抄送我的,快捷发起', notes: '登录后首页' },
        { name: '申请详情', modules: '表单内容,审批时间线,附件,操作按钮', notes: '查看与审批' },
        { name: '发起申请', modules: '模板选择,动态表单,提交', notes: '新建流程' },
      ],
      interaction_notes: '审批人可在列表页快速通过/驳回，也可进入详情填写意见\n驳回需填写理由',
      design_theme: '简洁企业蓝',
      responsive: '需要',
      auth: '需要登录',
      database: '需要数据库',
      frontend: 'React + TypeScript',
      backend: 'Python FastAPI',
      deployment: '内网 Kubernetes 或私有云',
      llm_usage: '本期不使用 LLM',
      security_requirements: '按角色控制数据可见范围\n操作日志审计\n敏感字段脱敏展示',
      performance_requirements: '列表页加载不超过 2 秒\n支持 500 并发在线用户',
      usability_requirements: '审批操作不超过 3 次点击\n表单支持草稿保存',
      in_scope: '三种申请模板\n审批流转与待办\n站内通知',
      out_of_scope: '自定义流程设计\n移动端 App\n与财务系统自动对账',
    },
  },
  {
    id: 'content-community',
    label: '内容社区',
    description: 'C 端 UGC 社区：发帖、互动与信息流',
    data: {
      product_name: '内容社区',
      product_goal: '为兴趣用户提供轻量社区，支持发帖、评论与发现优质内容。',
      target_users: '18-35 岁兴趣爱好者\n内容创作者\n社区运营',
      platform: '网页应用（Web App）',
      mvp_features: [
        { name: '用户注册登录', description: '邮箱或手机号注册，支持基础个人资料', user_value: '建立用户身份与关系链' },
        { name: '发帖', description: '支持图文帖子，标题+正文+最多 9 张图', user_value: '核心 UGC 能力' },
        { name: '信息流', description: '按时间倒序展示关注与推荐内容', user_value: '持续消费内容' },
        { name: '评论与点赞', description: '帖子下评论、回复与点赞', user_value: '促进互动' },
        { name: '话题标签', description: '发帖可选话题，按话题聚合浏览', user_value: '帮助发现同好' },
      ],
      v2_features: '私信\n收藏\n内容审核后台\n推荐算法',
      ui_pages: [
        { name: '首页信息流', modules: '帖子卡片,话题入口,发布按钮', notes: '主浏览页' },
        { name: '帖子详情', modules: '正文,图片,评论列表,互动按钮', notes: '阅读与互动' },
        { name: '发布页', modules: '标题,正文,图片上传,话题选择', notes: '创建内容' },
      ],
      interaction_notes: '双击点赞动画反馈\n评论支持楼中楼一层回复',
      design_theme: '明亮轻快',
      responsive: '需要',
      auth: '需要登录',
      database: '需要数据库',
      frontend: 'React + TypeScript',
      backend: 'Node.js 或 Python API',
      deployment: '云服务器 + 对象存储',
      llm_usage: '本期不使用 LLM，可选敏感词过滤服务',
      security_requirements: '图片上传类型与大小限制\n基础 XSS 防护\n举报入口',
      performance_requirements: '首屏信息流 1.5 秒内可交互\n图片懒加载',
      usability_requirements: '发布流程不超过 4 步\n未登录可浏览不可互动',
      in_scope: '注册登录\n发帖评论点赞\n话题浏览',
      out_of_scope: '直播\n电商带货\n复杂推荐算法',
    },
  },
  {
    id: 'ai-copilot',
    label: 'AI 助手 / Copilot',
    description: '对话式 AI 工具，强调上下文与多轮协作',
    data: {
      product_name: '团队 AI Copilot',
      product_goal: '在浏览器侧边栏提供对话式 AI 助手，帮助用户写文档、总结与执行任务建议。',
      target_users: '产品经理\n研发工程师\n运营人员',
      platform: '网页应用（Web App）',
      mvp_features: [
        { name: '多轮对话', description: '保持上下文的多轮问答与续聊', user_value: '连续协作而非单次问答' },
        { name: '文档上下文', description: '用户可粘贴或上传文本作为对话背景', user_value: '回答更贴合当前工作' },
        { name: '快捷指令', description: '预设「总结」「润色」「列提纲」等一键 prompt', user_value: '降低提示词门槛' },
        { name: '会话历史', description: '按会话保存历史，可回看与继续', user_value: '工作成果可追溯' },
        { name: '流式输出', description: '回答逐字展示，可随时停止生成', user_value: '减少等待焦虑' },
      ],
      v2_features: '团队共享会话\n插件调用外部 API\n自定义 Agent',
      ui_pages: [
        { name: '对话主界面', modules: '消息列表,输入框,快捷指令,停止按钮', notes: '核心交互' },
        { name: '会话列表', modules: '新建会话,历史会话,搜索', notes: '侧边栏' },
        { name: '设置', modules: '模型选择,API Key 说明,用量提示', notes: '配置页' },
      ],
      interaction_notes: 'Enter 发送，Shift+Enter 换行\n支持 Markdown 渲染回复',
      design_theme: '深色 IDE 风格',
      responsive: '需要',
      auth: '需要登录',
      database: '需要数据库',
      frontend: 'React + TypeScript',
      backend: 'Python FastAPI + LangChain',
      deployment: 'Docker 部署，LLM 通过 API 调用',
      llm_usage: '核心能力依赖大语言模型 API；需记录 token 用量与超时重试。',
      security_requirements: '用户数据隔离\n不上传内容用于模型训练（声明）\nAPI Key 服务端保管',
      performance_requirements: '首 token 延迟不超过 3 秒\n长回答支持流式',
      usability_requirements: '失败时可一键重试\n输入框支持粘贴大段文本',
      in_scope: '多轮对话与流式输出\n会话历史\n快捷指令',
      out_of_scope: '代码执行沙箱\n多 Agent 编排\n企业 SSO',
    },
  },
];

export const DEFAULT_TEMPLATE_ID = 'friend-circle-copywriter';

export function getTemplateById(id: string): FormTemplate | undefined {
  return FORM_TEMPLATES.find((t) => t.id === id);
}
