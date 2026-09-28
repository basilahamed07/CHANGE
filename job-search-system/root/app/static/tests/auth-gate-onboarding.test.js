import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest';
import { loadScripts } from './setup.js';

// Regression: the onboarding wizard (the one that asks for a resume) used to open
// from DOMContentLoaded BEFORE the auth gate ran. On a fresh browser (empty
// localStorage) an anonymous visitor was therefore told to upload a resume with
// no session — and every call the wizard made 401'd. Login must always come
// first; the 4-step setup belongs to a signed-in user.

beforeAll(() => {
    // jsdom has no matchMedia; the real browser does. Without this the page-load
    // handler aborts inside initTheme() before it can route at all.
    window.matchMedia = window.matchMedia || (() => ({
        matches: false, media: '',
        addEventListener() {}, removeEventListener() {},
        addListener() {}, removeListener() {},
    }));
    // jsdom has no EventSource; the page-load handler starts the notification stream.
    globalThis.EventSource = globalThis.EventSource || class {
        constructor() {} close() {} addEventListener() {}
    };

    // index.html elements the DOMContentLoaded handler wires up.
    document.body.innerHTML = `
        <div id="toast-container"></div>
        <nav class="nav-actions"></nav>
        <div class="nav-links">
            <a class="nav-link" data-route="settings">Settings</a>
        </div>
        <button id="scrape-btn"></button>
        <button id="theme-toggle"></button>
        <button id="notif-btn"></button>
        <button id="nav-hamburger"></button>
        <div id="nav-drawer-overlay"></div>
        <div id="app"></div>
    `;
    loadScripts('utils.js', 'api.js', 'onboarding.js', 'auth.js');

    globalThis.renderFeed = async () => {};
    globalThis.renderJobDetail = async () => {};
    globalThis.renderStats = async () => {};
    globalThis.renderPipeline = async () => {};
    globalThis.renderQueue = async () => {};
    globalThis.renderNetwork = async () => {};
    globalThis.renderSettings = async () => {};
    globalThis.renderCalendar = async () => {};
    globalThis.renderSalaryCalculator = async () => {};

    // Stub triage globals referenced by app.js keyboard shortcuts
    globalThis.enterTriageMode = () => {};
    globalThis.exitTriageMode = () => {};
    globalThis.triageActive = false;
    globalThis.triageJobs = [];
    globalThis.triageIndex = 0;
    globalThis.triageUndoStack = [];

    loadScripts('app.js');
});

beforeEach(() => {
    localStorage.clear();
    window.location.hash = '#/';
    document.getElementById('app').innerHTML = '';
    document.body.querySelectorAll('#onboarding-wizard').forEach(el => el.remove());
    document.getElementById('setup-indicator')?.remove();
    // The once-per-page-load latch lives in app.js; reset it so each scenario
    // below starts from a real page load.
    _setupUiShown = false;
});

/** Minimal fetch double: routes by path, 401s anything not explicitly allowed. */
function stubFetch(routes) {
    globalThis.fetch = vi.fn(async (path) => {
        const handler = routes[path];
        if (!handler) {
            return { ok: false, status: 401, statusText: 'Unauthorized',
                     json: async () => ({ detail: 'Not authenticated' }) };
        }
        return { ok: true, status: 200, json: async () => handler() };
    });
}

/** Fire the browser's page-load event and let the async route handler settle. */
async function loadPage() {
    document.dispatchEvent(new Event('DOMContentLoaded'));
    for (let i = 0; i < 5; i++) await Promise.resolve();
    await new Promise(r => setTimeout(r, 0));
}

describe('auth gate vs onboarding', () => {
    it('an anonymous page load shows LOGIN — never the resume wizard', async () => {
        stubFetch({
            '/api/auth/status': () => ({ needs_bootstrap: false, authenticated: false, user: null }),
        });

        await loadPage();

        expect(document.getElementById('auth-form')).toBeTruthy();
        expect(document.getElementById('onboarding-wizard')).toBeNull();
        // No "n/3 setup" badge before login either — it is per-user data.
        expect(document.getElementById('setup-indicator')).toBeNull();
    });

    it('a brand-new install shows "Create Admin" first, not the wizard', async () => {
        stubFetch({
            '/api/auth/status': () => ({ needs_bootstrap: true, authenticated: false, user: null }),
        });

        await loadPage();

        expect(document.getElementById('auth-form').textContent)
            .toContain('Create Admin Account');
        expect(document.getElementById('onboarding-wizard')).toBeNull();
    });

    it('shows the 4-step setup wizard only AFTER login, once per page load', async () => {
        stubFetch({
            '/api/auth/status': () => ({ needs_bootstrap: false, authenticated: true,
                                         user: { id: 2, username: 'alice', role: 'user' } }),
            '/api/profile': () => ({ full_name: '', email: '' }),
            '/api/resumes': () => ({ resumes: [] }),
            '/api/ai-settings': () => ({}),
        });

        // The login form's submit handler calls handleRoute() once signed in.
        await handleRoute();

        expect(document.getElementById('auth-form')).toBeNull();
        const wizard = document.getElementById('onboarding-wizard');
        expect(wizard).toBeTruthy();
        expect(wizard.querySelectorAll('.onboarding-step-dot').length).toBe(4);
        expect(wizard.textContent).toContain('Welcome to jobagent');
        // The per-user setup badge appears too (0 of 3 steps done).
        expect(document.getElementById('setup-indicator').textContent).toBe('0/3');

        // A route change must not stack a second wizard.
        window.location.hash = '#/settings';
        await handleRoute();
        expect(document.querySelectorAll('#onboarding-wizard').length).toBe(1);
    });

    it('does not reopen setup for a user who already finished it', async () => {
        // The flag is PER USER — finishing as alice must not hide it for bob.
        localStorage.setItem('careerpulse_onboarded:alice', 'true');
        stubFetch({
            '/api/auth/status': () => ({ needs_bootstrap: false, authenticated: true,
                                         user: { id: 2, username: 'alice', role: 'user' } }),
            '/api/profile': () => ({ full_name: 'Alice', email: 'a@b.c' }),
            '/api/resumes': () => ({ resumes: [{ id: 1 }] }),
            '/api/ai-settings': () => ({ provider: 'deepseek', api_key: 'set' }),
        });

        await handleRoute();

        expect(document.getElementById('onboarding-wizard')).toBeNull();
    });
});
