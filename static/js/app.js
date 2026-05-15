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
    return await resp.json();
  } catch (e) {
    toast('Network error: ' + e.message, 'error');
    return { ok: false, error: e.message };
  }
}

// Confirm dialog
function confirmDialog(msg) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title">确认</span>
        </div>
        <p style="margin-bottom:16px">${msg}</p>
        <div style="text-align:right">
          <button class="btn" id="confirm-no">取消</button>
          <button class="btn btn-danger" id="confirm-yes" style="margin-left:8px">确定</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#confirm-no').onclick = () => { overlay.remove(); resolve(false); };
    overlay.querySelector('#confirm-yes').onclick = () => { overlay.remove(); resolve(true); };
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
