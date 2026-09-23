// M15a — Auth UI: bootstrap (first admin), login, route guard, logout banner.
// The guard lives here because app.js owns routing; this file loads BEFORE app.js.

const auth = {
    state: { needs_bootstrap: false, authenticated: false, user: null },

    async refresh() {
        try {
            this.state = await api.request('GET', '/api/auth/status');
        } catch {
            this.state = { needs_bootstrap: false, authenticated: false, user: null };
        }
        return this.state;
    },

    async bootstrap(username, password) {
        const res = await api.request('POST', '/api/auth/bootstrap', { username, password });
        await this.refresh();
        return res;
    },

    async login(username, password) {
        const res = await api.request('POST', '/api/auth/login', { username, password });
        await this.refresh();
        return res;
    },

    async logout() {
        try { await api.request('POST', '/api/auth/logout'); } catch { /* ignore */ }
        this.state = { needs_bootstrap: false, authenticated: false, user: null };
    },

    isAdmin() {
        return this.state.user && this.state.user.role === 'admin';
    },
};

// === Login / bootstrap screen ===

function renderAuthScreen(app, mode) {
    const isBootstrap = mode === 'bootstrap';
    app.innerHTML = `
        <div class="auth-wrap" style="max-width:420px;margin:8vh auto 0;">
            <div class="card" style="padding:32px;">
                <div style="text-align:center;margin-bottom:24px;">
                    <img src="/static/favicon.svg" alt="" width="48" height="48">
                    <h1 style="margin:12px 0 4px;font-size:1.5rem;">jobagent</h1>
                    <p style="color:var(--text-muted,#888);font-size:.9rem;">
                        ${isBootstrap
                            ? 'Welcome! Create the administrator account to secure your system.'
                            : 'Sign in to continue to your workspace.'}
                    </p>
                </div>
                <form id="auth-form" autocomplete="${isBootstrap ? 'new-password' : 'current-password'}">
                    <div style="margin-bottom:14px;">
                        <label for="auth-username" style="display:block;font-size:.85rem;margin-bottom:4px;">Username</label>
                        <input id="auth-username" class="form-input" style="width:100%;" required
                               maxlength="64" autocomplete="username" autofocus>
                    </div>
                    <div style="margin-bottom:18px;">
                        <label for="auth-password" style="display:block;font-size:.85rem;margin-bottom:4px;">Password</label>
                        <input id="auth-password" class="form-input" style="width:100%;" type="password" required
                               minlength="${isBootstrap ? 8 : 1}" autocomplete="${isBootstrap ? 'new-password' : 'current-password'}">
                        ${isBootstrap ? '<p style="font-size:.78rem;color:var(--text-muted,#888);margin-top:4px;">Minimum 8 characters.</p>' : ''}
                    </div>
                    <button type="submit" class="btn btn-primary" style="width:100%;" id="auth-submit">
                        ${isBootstrap ? 'Create Admin Account' : 'Sign In'}
                    </button>
                    <p id="auth-error" role="alert" style="color:var(--danger,#e5484d);font-size:.85rem;margin-top:12px;display:none;"></p>
                </form>
            </div>
        </div>
    `;

    const form = document.getElementById('auth-form');
    const errEl = document.getElementById('auth-error');
    const submitBtn = document.getElementById('auth-submit');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errEl.style.display = 'none';
        submitBtn.disabled = true;
        submitBtn.textContent = isBootstrap ? 'Creating…' : 'Signing in…';
        try {
            const username = document.getElementById('auth-username').value.trim();
            const password = document.getElementById('auth-password').value;
            if (isBootstrap) {
                await auth.bootstrap(username, password);
                showToast('Admin account created — welcome!', 'success');
            } else {
                await auth.login(username, password);
                showToast(`Welcome back, ${username}!`, 'success');
            }
            await handleRoute();
        } catch (err) {
            errEl.textContent = err.message || 'Something went wrong';
            errEl.style.display = 'block';
            submitBtn.disabled = false;
            submitBtn.textContent = isBootstrap ? 'Create Admin Account' : 'Sign In';
        }
    });
}

// === Guard hook used by handleRoute() in app.js ===
// Returns true when the route may proceed; renders the auth screen instead when not.
async function authGate(app) {
    await auth.refresh();
    if (auth.state.needs_bootstrap) {
        renderAuthScreen(app, 'bootstrap');
        return false;
    }
    if (!auth.state.authenticated) {
        renderAuthScreen(app, 'login');
        return false;
    }
    renderAuthNavExtras();
    return true;
}

// === Nav additions: user chip + logout button ===

function renderAuthNavExtras() {
    const actions = document.querySelector('.nav-actions');
    if (!actions || document.getElementById('logout-btn')) return;
    const chip = document.createElement('span');
    chip.id = 'auth-user-chip';
    chip.className = 'btn btn-ghost btn-sm';
    chip.style.pointerEvents = 'none';
    chip.textContent = auth.state.user ? `${auth.state.user.username} (${auth.state.user.role})` : '';
    chip.title = `Signed in as ${chip.textContent}`;
    const btn = document.createElement('button');
    btn.id = 'logout-btn';
    btn.className = 'btn btn-ghost btn-sm';
    btn.textContent = 'Log out';
    btn.addEventListener('click', async () => {
        await auth.logout();
        showToast('Logged out', 'info');
        navigate('#/');
        await handleRoute();
    });
    actions.appendChild(chip);
    actions.appendChild(btn);
}
