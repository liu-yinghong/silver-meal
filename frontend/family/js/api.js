/* ============================================================
   饭心 · 银龄放心单 — 前端 API 接口层
   严格遵循 API契约.md v0.1.0 规范
   Base URL: http://localhost:8000
   ============================================================ */

const API = (function () {
  'use strict';

  // ===== 基础配置 =====
  // 页面由后端静态服务托管时，BASE_URL 自动取当前来源（localhost/IP 均可）；
  // 直接双击打开 HTML（file://）时回退到契约默认地址。
  const BASE_URL = (function () {
    if (location.protocol === 'http:' || location.protocol === 'https:') {
      return location.origin;
    }
    return 'http://localhost:8000';
  })();

  // Demo 固定参数（从 API契约.md 第一节）
  const DEMO_ELDER_ID = 'elder_001';
  const DEMO_FAMILY_ID = 'family_001';

  // ===== 内部工具函数 =====

  /**
   * 通用请求封装
   * @param {string} path - 接口路径（如 /api/meals/recommend）
   * @param {object} options - fetch 选项
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function request(path, options = {}) {
    const url = BASE_URL + path;

    const defaultHeaders = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    const config = {
      headers: { ...defaultHeaders, ...options.headers },
      ...options,
    };

    // FormData 交给浏览器设置 multipart 边界；其余对象自动序列化为 JSON
    const isFormData = config.body instanceof FormData;
    if (isFormData) {
      delete config.headers['Content-Type'];
    } else if (config.body && typeof config.body === 'object') {
      config.body = JSON.stringify(config.body);
    }

    // 超时保护：避免请求悬挂导致界面无响应
    const timeoutMs = options.timeout || 15000;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, { ...config, signal: controller.signal });

      // 尝试解析 JSON
      let data = null;
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      }

      // 成功响应
      if (response.ok) {
        return { data, error: null };
      }

      // 错误响应 — 提取 X-Error-Code
      const errorCode = response.headers.get('X-Error-Code') || 'UNKNOWN_ERROR';
      const errorMessage = data?.detail || `请求失败 (HTTP ${response.status})`;

      return {
        data: null,
        error: {
          code: errorCode,
          message: errorMessage,
          status: response.status,
        },
      };
    } catch (err) {
      // 网络错误或超时（真实连接失败时触发全局"服务器连接失败"提示）
      if (err && err.name !== 'AbortError' && typeof window !== 'undefined' && window.__onServerError) {
        window.__onServerError();
      }
      return {
        data: null,
        error: {
          code: 'NETWORK_ERROR',
          message: err && err.name === 'AbortError' ? '请求超时，请重试' : '网络连接失败，请检查后端服务是否已启动',
          status: 0,
        },
      };
    } finally {
      clearTimeout(timer);
    }
  }

  // ===== 公开 API 方法 =====

  /**
   * 健康检查 — 检测后端是否启动
   * GET /health
   * @returns {Promise<boolean>}
   */
  async function healthCheck() {
    const { data, error } = await request('/health');
    return !error && data?.status === 'ok';
  }

  /**
   * 餐食推荐 — 老人输入需求，返回推荐餐食
   * POST /api/meals/recommend
   * @param {string} textInput - 用户输入的需求文字
   * @returns {Promise<{data: object|null, error: object|null}>}
   *
   * 成功响应示例：
   * {
   *   meals: [{ id, name, description, price, image_url, dietary_tags, calories, eta_minutes }],
   *   query_summary: "您说：...",
   *   reasons: ["..."],
   *   ai_mode: "remote" | "local"
   * }
   */
  async function recommendMeals(textInput) {
    return request('/api/meals/recommend', {
      method: 'POST',
      body: {
        text_input: textInput,
        family_id: DEMO_FAMILY_ID,
      },
    });
  }

  /**
   * 创建订单
   * POST /api/orders
   * @param {string} mealId - 餐品 ID
   * @returns {Promise<{data: object|null, error: object|null}>}
   *
   * 成功响应示例：
   * { order_id: "ORD-xxx", status: "created", created_at: "...", eta_minutes: 35 }
   */
  async function createOrder(mealId) {
    return request('/api/orders', {
      method: 'POST',
      body: {
        meal_id: mealId,
        elder_id: DEMO_ELDER_ID,
        family_id: DEMO_FAMILY_ID,
      },
    });
  }

  /**
   * 查询订单状态
   * GET /api/orders/{order_id}
   * @param {string} orderId
   * @returns {Promise<{data: object|null, error: object|null}>}
   *
   * 成功响应：
   * { order_id, status, meal_name, meal_price, eta_minutes, updated_at, confirmed, confirmed_at }
   */
  async function getOrderStatus(orderId) {
    return request(`/api/orders/${encodeURIComponent(orderId)}`);
  }

  /**
   * 推进订单状态
   * POST /api/orders/{order_id}/advance
   * @param {string} orderId
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function advanceOrder(orderId) {
    return request(`/api/orders/${encodeURIComponent(orderId)}/advance`, {
      method: 'POST',
    });
  }

  /**
   * 一键送达
   * POST /api/orders/{order_id}/deliver
   * @param {string} orderId
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function deliverOrder(orderId) {
    return request(`/api/orders/${encodeURIComponent(orderId)}/deliver`, {
      method: 'POST',
    });
  }

  /**
   * 取消订单
   * POST /api/orders/{order_id}/cancel
   * @param {string} orderId
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function cancelOrder(orderId) {
    return request(`/api/orders/${encodeURIComponent(orderId)}/cancel`, {
      method: 'POST',
    });
  }

  /**
   * 确认收餐
   * POST /api/orders/confirm
   * @param {string} orderId
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function confirmReceipt(orderId) {
    return request('/api/orders/confirm', {
      method: 'POST',
      body: {
        order_id: orderId,
        action: 'confirm',
      },
    });
  }

  /**
   * 获取家属关联订单列表（用于判断"再来一份"）
   * GET /api/family/{family_id}/orders
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function getFamilyOrders() {
    return request(`/api/family/${encodeURIComponent(DEMO_FAMILY_ID)}/orders`);
  }

  /**
   * 获取家属规则
   * GET /api/family/{family_id}/rules?elder_id=xxx
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function getFamilyRules() {
    return request(
      `/api/family/${encodeURIComponent(DEMO_FAMILY_ID)}/rules?elder_id=${encodeURIComponent(DEMO_ELDER_ID)}`
    );
  }

  /**
   * 获取老人全部留言
   * GET /api/messages/{elder_id}
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function getMessages() {
    return request(`/api/messages/${encodeURIComponent(DEMO_ELDER_ID)}`);
  }

  /**
   * 获取未读留言
   * GET /api/messages/{elder_id}/unread
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function getUnreadMessages() {
    return request(`/api/messages/${encodeURIComponent(DEMO_ELDER_ID)}/unread`);
  }

  /**
   * 标记留言已读
   * POST /api/messages/{message_id}/read
   * @param {string} messageId
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function markMessageRead(messageId) {
    return request(`/api/messages/${encodeURIComponent(messageId)}/read`, {
      method: 'POST',
    });
  }

  /**
   * 发送留言
   * POST /api/messages
   * @param {string} content - 留言内容
   * @param {string} sender - 发送家属称呼（如：女儿）
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function sendMessage(content, sender) {
    return request('/api/messages', {
      method: 'POST',
      body: {
        elder_id: DEMO_ELDER_ID,
        family_id: DEMO_FAMILY_ID,
        sender: sender || '',
        content: content,
      },
    });
  }

  /**
   * 保存家属规则
   * POST /api/family/settings
   * @param {object} rules - 规则对象 { max_price, allowed_dietary, blocked_items, ... }
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function saveFamilySettings(rules) {
    return request('/api/family/settings', {
      method: 'POST',
      body: {
        family_id: DEMO_FAMILY_ID,
        elder_id: DEMO_ELDER_ID,
        rules: rules,
      },
    });
  }

  /**
   * 联系老人（模拟）
   * POST /api/family/contact
   * @param {string} orderId - 订单 ID 或 "latest"
   * @param {string} contactType - "call" 或 "message"
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function contactElder(orderId, contactType) {
    return request('/api/family/contact', {
      method: 'POST',
      body: {
        order_id: orderId || 'latest',
        family_id: DEMO_FAMILY_ID,
        contact_type: contactType || 'call',
      },
    });
  }

  /**
   * 标记超时未确认
   * POST /api/orders/{order_id}/timeout
   * @param {string} orderId
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function timeoutOrder(orderId) {
    return request(`/api/orders/${encodeURIComponent(orderId)}/timeout`, {
      method: 'POST',
    });
  }

  /**
   * 重置演示数据
   * POST /api/demo/reset
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function resetDemo() {
    return request('/api/demo/reset', {
      method: 'POST',
    });
  }

  /**
   * 家属端 AI 分析 — 大模型分析家属规则与推荐餐食的匹配
   * POST /api/analysis
   * @returns {Promise<{data: object|null, error: object|null}>}
   */
  async function getAnalysis() {
    // 大模型分析约需 20~28 秒，放宽超时到 35 秒
    return request('/api/analysis', { method: 'POST', timeout: 35000 });
  }

  // ===== 公开 API =====
  return {
    // 基础
    healthCheck,
    getAnalysis,
    resetDemo,

    // 推荐与订单
    recommendMeals,
    createOrder,
    getOrderStatus,
    advanceOrder,
    deliverOrder,
    cancelOrder,
    confirmReceipt,

    // 家属相关
    getFamilyOrders,
    getFamilyRules,

    // 留言
    getMessages,
    getUnreadMessages,
    markMessageRead,
    sendMessage,

    // 家属规则
    saveFamilySettings,
    contactElder,

    // 订单超时
    timeoutOrder,

    // 常量
    DEMO_ELDER_ID,
    DEMO_FAMILY_ID,
    BASE_URL,
  };
})();
