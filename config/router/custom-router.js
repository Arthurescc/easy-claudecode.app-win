const IMAGE_PATTERNS = [
  /\bimage\b/i,
  /\bscreenshot\b/i,
  /\bocr\b/i,
  /\bvision\b/i,
  /\bui\b/i,
  /\bfigma\b/i,
  /截图/,
  /图片/,
  /视觉/,
  /界面/
];

const REVIEW_PATTERNS = [
  /\breview\b/i,
  /\baudit\b/i,
  /\bverify\b/i,
  /\binspect\b/i,
  /\bcheck\b/i,
  /\bdiff\b/i,
  /\bregression\b/i,
  /代码审查/,
  /代码核验/,
  /核验/,
  /审查/,
  /复盘/,
  /检查/
];

const DOCUMENT_PATTERNS = [
  /\bpdf\b/i,
  /\bdocx\b/i,
  /\bpptx\b/i,
  /\bxlsx\b/i,
  /\bspreadsheet\b/i,
  /文档/,
  /表格/,
  /幻灯片/,
  /报告/
];

const CODING_PATTERNS = [
  /\bdebug\b/i,
  /\bfix\b/i,
  /\bbug\b/i,
  /\bimplement\b/i,
  /\brefactor\b/i,
  /\bmigration\b/i,
  /\barchitecture\b/i,
  /\bdesign\b/i,
  /\btest\b/i,
  /\bself[- ]?heal\b/i,
  /\bself[- ]?repair\b/i,
  /\bself[- ]?evol/i,
  /编程/,
  /写代码/,
  /排障/,
  /修复/,
  /重构/,
  /架构/,
  /调试/,
  /复杂/
];

const EXPLICIT_ROUTES = [
  {
    pattern: /\[route:opus46\]/i,
    target: "aicodelink-opus,claude-opus-4-6-thinking"
  },
  { pattern: /\[route:glm5\]/i, target: "dashscope-codingplan,glm-5" },
  { pattern: /\[route:glm47\]/i, target: "dashscope-codingplan,glm-4.7" },
  {
    pattern: /\[route:qwenmax\]/i,
    target: "dashscope-codingplan,qwen3-max-2026-01-23"
  },
  { pattern: /\[route:kimi\]/i, target: "dashscope-codingplan,kimi-k2.5" },
  {
    pattern: /\[route:qwen35\]/i,
    target: "dashscope-codingplan,qwen3.5-plus"
  },
  {
    pattern: /\[route:qwencoder\]/i,
    target: "dashscope-codingplan,qwen3-coder-plus"
  },
  {
    pattern: /\[route:minimax\]/i,
    target: "dashscope-codingplan,MiniMax-M2.7-highspeed"
  }
];

const ROLE_ROUTE_PATTERNS = [
  {
    target: "dashscope-codingplan,glm-5",
    normalizedNeedles: [
      "你是产品经理",
      "产品经理角色",
      "你是项目经理",
      "项目经理角色",
      "你是系统架构师",
      "系统架构师角色",
      "productmanager",
      "projectmanager",
      "systemarchitect"
    ],
    patterns: [
      /你是产品经理/,
      /产品经理角色/,
      /你是项目经理/,
      /项目经理角色/,
      /你是系统架构师/,
      /系统架构师角色/,
      /product-manager/i,
      /project-manager/i,
      /system-architect/i
    ]
  },
  {
    target: "dashscope-codingplan,MiniMax-M2.7-highspeed",
    normalizedNeedles: [
      "你是前端工程师",
      "前端工程师角色",
      "你是后端工程师",
      "后端工程师角色",
      "frontendengineer",
      "backendengineer"
    ],
    patterns: [
      /你是前端工程师/,
      /前端工程师角色/,
      /你是后端工程师/,
      /后端工程师角色/,
      /frontend-engineer/i,
      /backend-engineer/i
    ]
  },
  {
    target: "dashscope-codingplan,qwen3-max-2026-01-23",
    normalizedNeedles: [
      "你是qa工程师",
      "qa工程师角色",
      "qaengineer",
      "reviewverifier",
      "你是独立核验代理",
      "你是审查代理"
    ],
    patterns: [
      /你是QA工程师/,
      /你是 QA 工程师/,
      /QA 工程师角色/,
      /qa-engineer/i,
      /review-verifier/i,
      /你是独立核验代理/,
      /你是审查代理/
    ]
  },
  {
    target: "dashscope-codingplan,glm-5",
    normalizedNeedles: [
      "completionsupervisor",
      "你是完成度监督代理",
      "你是最终放行代理"
    ],
    patterns: [
      /completion-supervisor/i,
      /你是完成度监督代理/,
      /你是最终放行代理/
    ]
  },
  {
    target: "dashscope-codingplan,kimi-k2.5",
    normalizedNeedles: [
      "你是uiux设计师",
      "uiux设计师角色",
      "uiuxdesigner"
    ],
    patterns: [
      /你是 UI\/UX 设计师/,
      /UI\/UX 设计师角色/,
      /ui-ux-designer/i
    ]
  }
];

function flattenContent(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (!item) return "";
        if (typeof item === "string") return item;
        if (typeof item.text === "string") return item.text;
        if (typeof item.content === "string") return item.content;
        return "";
      })
      .join("\n");
  }
  if (content && typeof content.text === "string") return content.text;
  return "";
}

function keepUserAuthoredText(text) {
  const trimmed = text.trim();
  if (!trimmed) return "";
  if (trimmed.startsWith("<system-reminder>")) {
    return "";
  }
  return trimmed;
}

function stripRouteMarkersFromString(value) {
  return String(value || "")
    .replace(/\[route:[^\]]+\]\s*/ig, "")
    .trim();
}

function stripRouteMarkersFromContent(content) {
  if (typeof content === "string") {
    return stripRouteMarkersFromString(content);
  }
  if (Array.isArray(content)) {
    return content.map((item) => {
      if (!item) return item;
      if (typeof item === "string") {
        return stripRouteMarkersFromString(item);
      }
      const nextItem = { ...item };
      if (typeof nextItem.text === "string") {
        nextItem.text = stripRouteMarkersFromString(nextItem.text);
      }
      if (typeof nextItem.content === "string") {
        nextItem.content = stripRouteMarkersFromString(nextItem.content);
      }
      return nextItem;
    });
  }
  if (content && typeof content === "object") {
    const nextContent = { ...content };
    if (typeof nextContent.text === "string") {
      nextContent.text = stripRouteMarkersFromString(nextContent.text);
    }
    if (typeof nextContent.content === "string") {
      nextContent.content = stripRouteMarkersFromString(nextContent.content);
    }
    return nextContent;
  }
  return content;
}

function stripRouteMarkersFromMessages(messages) {
  if (!Array.isArray(messages)) {
    return;
  }
  for (const message of messages) {
    if (!message || message.role !== "user") {
      continue;
    }
    message.content = stripRouteMarkersFromContent(message.content);
  }
}

function normalizeRoutingText(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[_\-]/g, "")
    .replace(/[\s`~!@#$%^&*()+=[\]{}|\\;:'",.<>/?，。！？、（）【】《》“”‘’：；·]+/g, "");
}

module.exports = async function router(req) {
  const allChunks = (req?.body?.messages || [])
    .flatMap((message) => {
      const content = message?.content;
      if (Array.isArray(content)) {
        return content.map((item) => {
          if (!item) return "";
          if (typeof item === "string") return item;
          if (typeof item.text === "string") return item.text;
          if (typeof item.content === "string") return item.content;
          return "";
        });
      }
      return [flattenContent(content)];
    })
    .filter(Boolean);

  const userChunks = (req?.body?.messages || [])
    .filter((message) => message?.role === "user")
    .flatMap((message) => {
      const content = message?.content;
      if (Array.isArray(content)) {
        return content.map((item) => {
          if (!item) return "";
          if (typeof item === "string") return keepUserAuthoredText(item);
          if (typeof item.text === "string") {
            return keepUserAuthoredText(item.text);
          }
          if (typeof item.content === "string") {
            return keepUserAuthoredText(item.content);
          }
          return "";
        });
      }
      return [keepUserAuthoredText(flattenContent(content))];
    })
    .filter(Boolean);

  const allText = allChunks.join("\n").trim();
  const userText = userChunks.join("\n").trim();
  const roleScopeText = allText.slice(0, 180);
  const normalizedRoleScopeText = normalizeRoutingText(roleScopeText);

  if (!allText && !userText) return null;

  for (const route of EXPLICIT_ROUTES) {
    if (route.pattern.test(userText) || route.pattern.test(allText)) {
      stripRouteMarkersFromMessages(req?.body?.messages);
      return route.target;
    }
  }

  for (const route of ROLE_ROUTE_PATTERNS) {
    const hasRegexMatch = route.patterns.some((pattern) => pattern.test(roleScopeText));
    const hasNormalizedMatch = (route.normalizedNeedles || []).some((needle) =>
      normalizedRoleScopeText.includes(normalizeRoutingText(needle))
    );
    if (hasRegexMatch || hasNormalizedMatch) {
      return route.target;
    }
  }

  if (IMAGE_PATTERNS.some((pattern) => pattern.test(userText))) {
    return "dashscope-codingplan,kimi-k2.5";
  }

  if (REVIEW_PATTERNS.some((pattern) => pattern.test(userText))) {
    return "dashscope-codingplan,qwen3-max-2026-01-23";
  }

  if (CODING_PATTERNS.some((pattern) => pattern.test(userText))) {
    return "dashscope-codingplan,MiniMax-M2.7-highspeed";
  }

  if (DOCUMENT_PATTERNS.some((pattern) => pattern.test(userText))) {
    return "dashscope-codingplan,qwen3-max-2026-01-23";
  }

  return null;
};
