# Next Phase Plan: Tavily Search Discovery

Generated: 2026-10-05

Google Custom Search and Vertex AI Search are removed from active discovery.
The replacement web-search source is:

```text
tavily_search
```

It is implemented in:

```text
app/adapters/tavily_search.py
```

## Why Tavily

Tavily is simpler for this app:

- one API key
- one search endpoint
- domain filtering
- no Google project entitlement issue
- no search-engine `cx`
- no Agent Builder data store setup

The adapter searches trusted career domains, then JobAgent still filters by:

- AI/LLM/RAG job title signals
- hiring/apply/career page hints
- selected country
- valid public URL

## Setup

Create a Tavily account and get an API key.

Set the key before starting the server:

```powershell
$env:JOBAGENT_TAVILY_API_KEY="tvly-your-key-here"
```

Or add this to your local `.env`:

```text
JOBAGENT_TAVILY_API_KEY=tvly-your-key-here
```

Do not add Google search keys for discovery. They are no longer used.

## Domains Used By The Adapter

The current included domains are:

```text
mycareersfuture.gov.sg
jobs.lever.co
boards.greenhouse.io
jobs.ashbyhq.com
groupcareers.singtel.com
ncs.co
smartrecruiters.com
jobs.workable.com
apply.workable.com
myworkdayjobs.com
jobs.jobvite.com
jobs.sap.com
nodeflair.com
germantechjobs.de
jobbank.gc.ca
```

These can be tuned inside:

```text
app/adapters/tavily_search.py
```

## Test Steps

Run focused tests:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests\test_adapters.py::test_tavily_search_adapter_missing_key_is_honest_noop tests\test_adapters.py::test_tavily_search_adapter_normalizes_results tests\test_discovery_upgrade.py tests\test_discovery_expansion.py
```

Start/restart the app, then check:

```text
GET http://localhost:8085/api/discovery/adapters
GET http://localhost:8085/api/discovery/registry
GET http://localhost:8085/api/discovery/health
```

Expected:

```text
tavily_search appears in adapters
tavily_search appears in registry
tavily_search health is ok when the API key is valid
```

Run a small discovery pass:

```text
POST http://localhost:8085/api/discovery/run?passes=3
GET  http://localhost:8085/api/discovery/status
```

Good outcomes:

```text
PASS
NO_RESULTS
CONFIGURATION_REQUIRED
```

`NO_RESULTS` is acceptable if Tavily returned pages but none passed the strict
job filters. `CONFIGURATION_REQUIRED` means the API key is missing.
