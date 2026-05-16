/* Shared JS utilities */

// Simple toast notification
function toast(msg, type = 'info') {
  const colors = { info: '#1890ff', success: '#52c41a', error: '#ff4d4f', warning: '#faad14' };
  const el = document.createElement('div');
  el.style.cssText = `position:fixed;top:20px;right:20px;padding:12px 24px;border-radius:4px;background:${colors[type]};color:#fff;z-index:9999;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.15);transition:opacity 0.3s;`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3000);
}

// Fetch helper
async function api(url, options = {}) {
  try {
    const resp = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
    if (resp.headers.get('content-type')?.includes('text/event-stream')) {
      return resp;
    }
    const text = await resp.text();
    try {
      const json = JSON.parse(text);
      return json;
    } catch {
      if (!resp.ok) {
        return { ok: false, error: `HTTP ${resp.status}: ${text.slice(0, 200)}` };
      }
      return { ok: false, error: text };
    }
  } catch (e) {
    toast('Network error: ' + e.message, 'error');
    return { ok: false, error: e.message };
  }
}

// Confirm dialog
function confirmDialog(msg) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.45);z-index:9999;display:flex;align-items:center;justify-content:center;';
    const box = document.createElement('div');
    box.style.cssText = 'background:#fff;border-radius:8px;padding:24px;min-width:360px;box-shadow:0 4px 20px rgba(0,0,0,0.15);';
    box.innerHTML = `
      <div style="font-size:16px;font-weight:600;margin-bottom:16px;">确认</div>
      <p style="margin-bottom:16px">${msg}</p>
      <div style="text-align:right;display:flex;gap:8px;justify-content:flex-end;">
        <button class="btn" id="confirm-no">取消</button>
        <button class="btn btn-danger" id="confirm-yes">确定</button>
      </div>`;
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    box.querySelector('#confirm-no').onclick = () => { overlay.remove(); resolve(false); };
    box.querySelector('#confirm-yes').onclick = () => { overlay.remove(); resolve(true); };
    overlay.addEventListener('click', (e) => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
  });
}

// Status badge HTML
function statusBadge(status) {
  const map = { running: 'running', starting: 'starting', stopped: 'stopped', stopped_error: 'error' };
  const cls = map[status] || 'stopped';
  const labels = { running: '运行中', starting: '启动中', stopped: '已停止', stopped_error: '异常停止' };
  return `<span class="badge badge-${cls}">${labels[status] || status}</span>`;
}

// Current page active nav
document.addEventListener('DOMContentLoaded', () => {
  const path = location.pathname;
  document.querySelectorAll('.sidebar nav a').forEach(a => {
    if (path.startsWith(a.href.replace(location.origin, ''))) {
      a.classList.add('active');
    }
  });
});
