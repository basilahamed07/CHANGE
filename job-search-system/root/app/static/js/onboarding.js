// === Onboarding Wizard ===

// M15b: the onboarding flag is PER USER — otherwise, on a shared browser,
// user #1 finishing setup would hide the resume prompt from every later user.
function onboardingKey() {
    const u = (typeof auth !== 'undefined' && auth.state && auth.state.user)
        ? auth.state.user.username : '';
    return `careerpulse_onboarded${u ? ':' + u : ''}`;
}

function isOnboardingDone() {
    return localStorage.getItem(onboardingKey()) === 'true';
}

function markOnboardingDone() {
    localStorage.setItem(onboardingKey(), 'true');
}

async function checkSetupCompleteness() {
    try {
        const [profile, resumesData, aiSettings] = await Promise.all([
            api.request('GET', '/api/profile'),
            api.request('GET', '/api/resumes'),
            api.getAISettings(),
        ]);
        const steps = {
            profile: !!(profile.full_name && profile.email),
            resume: (resumesData.resumes || []).length > 0,
            ai: !!(aiSettings.provider && (aiSettings.api_key || aiSettings.provider === 'ollama')),
        };
        const done = Object.values(steps).filter(Boolean).length;
        const total = Object.keys(steps).length;
        return { steps, done, total, complete: done === total };
    } catch {
        return { steps: {}, done: 0, total: 3, complete: false };
    }
}

async function updateSetupIndicator() {
    const existing = document.getElementById('setup-indicator');
    if (existing) existing.remove();

    const status = await checkSetupCompleteness();
    if (status.complete) {
        markOnboardingDone();
        return;
    }

    const settingsLink = document.querySelector('.nav-link[data-route="settings"]');
    if (settingsLink) {
        const indicator = document.createElement('span');
        indicator.id = 'setup-indicator';
        indicator.className = 'setup-indicator';
        indicator.textContent = `${status.done}/${status.total}`;
        indicator.title = 'Setup incomplete — click Settings to finish';
        settingsLink.style.position = 'relative';
        settingsLink.appendChild(indicator);
    }
}

function showOnboardingWizard() {
    let currentStep = 0;
    // Resume comes FIRST: a brand-new user must give us a resume before the app
    // can know which roles to search for. The AI step then powers the extraction
    // and the keywords step lets the user confirm what we'll search for.
    const stepData = { resumeUploaded: false, analysis: null };

    const wizard = document.createElement('div');
    wizard.id = 'onboarding-wizard';

    function renderStep() {
        const steps = [renderStep1Resume, renderStep2Ai, renderStep3Keywords, renderStep4Done];
        const dots = [0, 1, 2, 3].map(i =>
            `<div class="onboarding-step-dot ${i === currentStep ? 'active' : (i < currentStep ? 'done' : '')}"></div>`
        ).join('');

        wizard.innerHTML = `
            <div class="modal-overlay">
                <div class="onboarding-modal" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
                    <div class="onboarding-steps">${dots}</div>
                    <div id="onboarding-step-content">${steps[currentStep]()}</div>
                </div>
            </div>
        `;

        if (!wizard.parentNode) document.body.appendChild(wizard);
        attachStepListeners();
    }

    function renderStep1Resume() {
        return `
            <h2 id="onboarding-title" class="onboarding-heading">Welcome to jobagent</h2>
            <p class="onboarding-desc">First, upload your resume. We read it to learn which roles you're looking for, then search for them.</p>
            <div class="onboarding-upload" id="onb-upload-area">
                <div class="onboarding-upload-icon">&#128196;</div>
                <div class="onboarding-upload-text">Drop a file here or click to browse</div>
                <div class="onboarding-upload-hint">PDF, DOCX, or TXT</div>
                <input type="file" id="onb-file" accept=".pdf,.docx,.doc,.txt" style="display:none">
            </div>
            <div id="onb-upload-status"></div>
            <div class="onboarding-actions">
                <button class="btn btn-primary" id="onb-next" disabled>Next</button>
            </div>
        `;
    }

    function renderStep2Ai() {
        return `
            <h2 id="onboarding-title" class="onboarding-heading">Connect AI Provider</h2>
            <p class="onboarding-desc">jobagent uses AI to read your resume, score jobs and tailor applications. Connect a provider to get started.</p>
            <div class="onboarding-form">
                <div class="onboarding-field">
                    <label for="onb-provider">Provider</label>
                    <select id="onb-provider" class="filter-select" style="width:100%">
                        <option value="">Select a provider...</option>
                        <option value="anthropic">Anthropic (Claude)</option>
                        <option value="openai">OpenAI (GPT)</option>
                        <option value="google">Google (Gemini)</option>
                        <option value="openrouter">OpenRouter</option>
                        <option value="deepseek">DeepSeek</option>
                        <option value="ollama">Ollama (Local)</option>
                    </select>
                </div>
                <div class="onboarding-field" id="onb-key-field" style="display:none">
                    <label for="onb-api-key">API Key</label>
                    <input type="password" id="onb-api-key" class="search-input" placeholder="sk-...">
                </div>
                <div class="onboarding-field" id="onb-ollama-field" style="display:none">
                    <label for="onb-ollama-url">Ollama URL</label>
                    <input type="text" id="onb-ollama-url" class="search-input" placeholder="http://localhost:11434" value="http://localhost:11434">
                </div>
                <button class="btn btn-secondary btn-sm" id="onb-test-ai" style="display:none">Test Connection</button>
                <div id="onb-ai-status"></div>
            </div>
            <div class="onboarding-actions">
                <button class="btn btn-secondary" id="onb-back">Back</button>
                <button class="btn btn-primary" id="onb-next">Next</button>
            </div>
        `;
    }

    function renderStep3Keywords() {
        const a = stepData.analysis || {};
        const terms = (a.search_terms || []).join('\n');
        const titles = a.job_titles || [];
        const skills = a.key_skills || [];
        const titleLines = titles.map(t => {
            const title = typeof t === 'object' ? (t.title || '') : t;
            const why = typeof t === 'object' ? (t.why || '') : '';
            return `<li><strong>${escapeHtml(title)}</strong>${why ? ` — ${escapeHtml(why)}` : ''}</li>`;
        }).join('');
        const skillChips = skills.map(s =>
            `<span class="onboarding-keyword-chip">${escapeHtml(String(s))}</span>`).join('');
        return `
            <h2 id="onboarding-title" class="onboarding-heading">Here's what we'll search for</h2>
            <p class="onboarding-desc">Extracted from your resume. Edit the search terms if you want to widen or narrow the search, then continue.</p>
            <div class="onboarding-form">
                <div class="onboarding-field">
                    <label for="onb-terms">Search terms (one per line)</label>
                    <textarea id="onb-terms" class="search-input" rows="6" style="width:100%;font-family:inherit">${escapeHtml(terms)}</textarea>
                </div>
                ${titleLines ? `
                <div class="onboarding-field">
                    <label>Suggested roles</label>
                    <ul class="onboarding-keyword-list">${titleLines}</ul>
                </div>` : ''}
                ${skillChips ? `
                <div class="onboarding-field">
                    <label>Key skills</label>
                    <div class="onboarding-keyword-chips">${skillChips}</div>
                </div>` : ''}
            </div>
            <div class="onboarding-actions">
                <button class="btn btn-secondary" id="onb-back">Back</button>
                <button class="btn btn-primary" id="onb-next">Save &amp; Continue</button>
            </div>
        `;
    }

    function renderStep4Done() {
        return `
            <h2 id="onboarding-title" class="onboarding-heading">You're All Set!</h2>
            <p class="onboarding-desc">jobagent is ready to find and match jobs for you. Start your first scrape to discover opportunities.</p>
            <div class="onboarding-summary">
                <div class="onboarding-summary-item" id="onb-summary"></div>
            </div>
            <div class="onboarding-actions">
                <button class="btn btn-secondary" id="onb-back">Back</button>
                <button class="btn btn-primary" id="onb-scrape">Start Scraping</button>
                <button class="btn btn-ghost" id="onb-later">I'll do this later</button>
            </div>
        `;
    }

    function attachStepListeners() {
        const next = wizard.querySelector('#onb-next');
        const back = wizard.querySelector('#onb-back');
        const scrape = wizard.querySelector('#onb-scrape');
        const later = wizard.querySelector('#onb-later');

        if (back) back.addEventListener('click', () => { currentStep--; renderStep(); });

        // --- step 0: resume (required) ------------------------------------
        if (currentStep === 0) {
            const uploadArea = wizard.querySelector('#onb-upload-area');
            const fileInput = wizard.querySelector('#onb-file');
            const statusEl = wizard.querySelector('#onb-upload-status');

            if (uploadArea && fileInput) {
                uploadArea.addEventListener('click', () => fileInput.click());
                uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('drag-over'); });
                uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag-over'));
                uploadArea.addEventListener('drop', (e) => {
                    e.preventDefault();
                    uploadArea.classList.remove('drag-over');
                    if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
                });
                fileInput.addEventListener('change', () => {
                    if (fileInput.files.length) handleUpload(fileInput.files[0]);
                });
            }

            async function handleUpload(file) {
                if (statusEl) statusEl.innerHTML = '<span class="spinner"></span> Uploading &amp; analyzing...';
                try {
                    const result = await api.uploadResume(file);
                    stepData.resumeUploaded = true;
                    stepData.analysis = result;
                    if (next) next.disabled = false;
                    if (statusEl) {
                        const n = (result.search_terms || []).length;
                        statusEl.innerHTML = `<span style="color:var(--score-green);font-weight:600">Resume uploaded!</span>`
                            + (n ? `<div style="font-size:0.8125rem;color:var(--text-secondary)">We found ${n} search term${n === 1 ? '' : 's'} for you.</div>` : '');
                    }
                } catch (err) {
                    if (statusEl) statusEl.innerHTML = `<span style="color:var(--danger)">${escapeHtml(err.message)}</span>`;
                }
            }

            // A returning user who already has a resume need not re-upload it.
            api.request('GET', '/api/resumes').then(data => {
                if ((data.resumes || []).length > 0) {
                    stepData.resumeUploaded = true;
                    if (next) next.disabled = false;
                    if (statusEl) statusEl.innerHTML = '<span style="color:var(--text-secondary)">You already have a resume on file.</span>';
                }
            }).catch(() => {});

            if (next) next.addEventListener('click', () => {
                if (!stepData.resumeUploaded) return;
                currentStep++; renderStep();
            });
        }

        // --- step 1: AI provider ------------------------------------------
        if (currentStep === 1) {
            const providerSelect = wizard.querySelector('#onb-provider');
            const keyField = wizard.querySelector('#onb-key-field');
            const ollamaField = wizard.querySelector('#onb-ollama-field');
            const testBtn = wizard.querySelector('#onb-test-ai');
            const statusEl = wizard.querySelector('#onb-ai-status');

            if (providerSelect) {
                providerSelect.addEventListener('change', () => {
                    const v = providerSelect.value;
                    if (keyField) keyField.style.display = (v && v !== 'ollama') ? '' : 'none';
                    if (ollamaField) ollamaField.style.display = v === 'ollama' ? '' : 'none';
                    if (testBtn) testBtn.style.display = v ? '' : 'none';
                });
            }

            if (testBtn) {
                testBtn.addEventListener('click', async () => {
                    const provider = providerSelect?.value;
                    const apiKey = wizard.querySelector('#onb-api-key')?.value?.trim();
                    const ollamaUrl = wizard.querySelector('#onb-ollama-url')?.value?.trim();
                    if (!provider) return;
                    testBtn.disabled = true;
                    testBtn.innerHTML = '<span class="spinner"></span> Testing...';
                    try {
                        // Only Ollama uses a base_url; sending one for hosted
                        // providers (e.g. OpenRouter) overrides their API endpoint.
                        const settings = { provider, api_key: apiKey || undefined };
                        if (provider === 'ollama' && ollamaUrl) settings.base_url = ollamaUrl;
                        await api.testAIConnection(settings);
                        if (statusEl) statusEl.innerHTML = '<span style="color:var(--score-green);font-weight:600">Connected!</span>';
                    } catch (err) {
                        if (statusEl) statusEl.innerHTML = `<span style="color:var(--danger)">${escapeHtml(err.message)}</span>`;
                    } finally {
                        testBtn.disabled = false;
                        testBtn.textContent = 'Test Connection';
                    }
                });
            }

            if (next) {
                next.addEventListener('click', async () => {
                    const provider = providerSelect?.value;
                    if (provider) {
                        const apiKey = wizard.querySelector('#onb-api-key')?.value?.trim();
                        const ollamaUrl = wizard.querySelector('#onb-ollama-url')?.value?.trim();
                        try {
                            const payload = { provider, api_key: apiKey || undefined };
                            if (provider === 'ollama' && ollamaUrl) payload.base_url = ollamaUrl;
                            await api.updateAISettings(payload);
                        } catch {}
                    }
                    currentStep++; renderStep();
                });
            }
        }

        // --- step 2: confirm / edit keywords ------------------------------
        if (currentStep === 2) {
            if (!stepData.analysis) {
                // Re-run path: prefill from whatever is already saved.
                api.getSearchConfig().then(cfg => {
                    stepData.analysis = {
                        search_terms: cfg.search_terms || [],
                        job_titles: cfg.job_titles || [],
                        key_skills: cfg.key_skills || [],
                    };
                    renderStep();
                }).catch(() => {});
            }

            if (next) {
                next.addEventListener('click', async () => {
                    const raw = wizard.querySelector('#onb-terms')?.value || '';
                    const terms = raw.split('\n').map(t => t.trim()).filter(Boolean);
                    const a = stepData.analysis || {};
                    try {
                        await api.updateSearchKeywords({
                            search_terms: terms,
                            job_titles: a.job_titles || [],
                            key_skills: a.key_skills || [],
                        });
                    } catch {}
                    currentStep++; renderStep();
                });
            }
        }

        // --- step 3: done --------------------------------------------------
        if (currentStep === 3) {
            const summaryEl = wizard.querySelector('#onb-summary');
            if (summaryEl) {
                checkSetupCompleteness().then(status => {
                    const items = [];
                    items.push(status.steps.profile ? '&#10003; Profile configured' : '&#10007; Profile not set');
                    items.push(status.steps.resume ? '&#10003; Resume uploaded' : '&#10007; No resume yet');
                    items.push(status.steps.ai ? '&#10003; AI provider connected' : '&#10007; AI not configured');
                    summaryEl.innerHTML = items.map(i => `<div class="onboarding-check-item">${i}</div>`).join('');
                });
            }

            if (scrape) {
                scrape.addEventListener('click', async () => {
                    markOnboardingDone();
                    wizard.remove();
                    updateSetupIndicator();
                    handleScrape();
                });
            }

            if (later) {
                later.addEventListener('click', () => {
                    markOnboardingDone();
                    wizard.remove();
                    updateSetupIndicator();
                });
            }
        }

        // Keyboard: Escape skips (but the resume step is still required for search).
        wizard.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.stopPropagation();
                markOnboardingDone();
                wizard.remove();
                updateSetupIndicator();
            }
        });
    }

    renderStep();
}
