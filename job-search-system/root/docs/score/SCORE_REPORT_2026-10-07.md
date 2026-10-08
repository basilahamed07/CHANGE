# Score Report

Generated: `2026-10-07T12:48:45.905729+00:00`

## Coverage

| Measure | Count |
|---|---|
| Jobs seen | 1245 |
| ELIGIBLE | 240 |
| INELIGIBLE / REVIEW | 1005 |
| Has any score | 240 |
| AI-scored | 240 |
| Hybrid-scored (free) | 0 |
| Unscored | 1005 |

Which engine decided each score: **AI 240** · **hybrid 0** · unscored 1005.

## Integrity checks

**Overall: ATTENTION NEEDED**

| Check | Result | Count |
|---|---|---|
| `eligibility_containment` | PASS | 0 |
| `eligible_coverage` | PASS | 0 |
| `hybrid_coverage` | FAIL | 240 |
| `no_fabricated_zeros` | PASS | 0 |
| `role_match_cap` | PASS | 0 |

### What each check means

- **`eligibility_containment`** — No INELIGIBLE / REVIEW_REQUIRED / dismissed job carries a score (the Stage-3 SCORE-gate contract).
- **`eligible_coverage`** — Every ELIGIBLE job has a score of some kind (hybrid or AI).
- **`hybrid_coverage`** — Every ELIGIBLE job has a hybrid (free) score. Before 2026-10-07 this was 0 across the board because the free pass was fed the AI query.
  - Offenders (240): 354, 378, 562, 657, 291, 361, 266, 591, 751, 379, 433, 286, 287, 295, 315, 698, 359, 296, 421, 496, 417, 437, 260, 595, 610, 646, 985, 1178, 358, 881, 276, 336, 590, 267, 316, 405, 460, 517, 582, 624, 644, 310, 327, 413, 880, 733, 258, 285, 326, 444
- **`no_fabricated_zeros`** — No AI score of exactly 0 — the D1 artifact class, where a job the model never returned was padded with a fabricated zero.
- **`role_match_cap`** — No AI score above the cap while role_match is explicitly false (D3b).

## Per-job scores

| Job | Title | Company | Effective | Decided by | AI | Hybrid | Eligibility | role_match |
|---|---|---|---|---|---|---|---|---|
| 354 | Senior Software Engineer - Generative AI Innovat | Dexian DISYS | 86 | ai | 86 | — | ELIGIBLE | True |
| 378 | LLM Application Engineer, Artificial Intelligenc | Next Step Systems | 86 | ai | 86 | — | ELIGIBLE | True |
| 562 | AI Agent Developer | Corpay | 85 | ai | 85 | — | ELIGIBLE | True |
| 657 | Agentic AI Engineer - Officer | Citi | 85 | ai | 85 | — | ELIGIBLE | True |
| 291 | AI Engineer 5 (GenAI Platform Services, Agentic  | Capital One | 84 | ai | 84 | — | ELIGIBLE | True |
| 361 | Software Developer â Generative AI & Python Mo | ChaTeck Incorporated | 84 | ai | 84 | — | ELIGIBLE | True |
| 266 | AI Engineer | Purplejack Technologies  | 83 | ai | 83 | — | ELIGIBLE | True |
| 591 | Java/Python Engineer (Agentic AI) | Learn Beyond Consulting  | 82 | ai | 82 | — | ELIGIBLE | True |
| 751 | Gen AI/ML Engineer - Entry Level | NET2ASPIRE LLC | 82 | ai | 82 | — | ELIGIBLE | True |
| 379 | Backend Engineer, LLM Applications - Newton, MA | Motion Recruitment Partn | 78 | ai | 78 | — | ELIGIBLE | True |
| 433 | Senior AI Engineer with RAG and Agentic architec | EPAM Systems | 78 | ai | 78 | — | ELIGIBLE | True |
| 286 | AI Engineer 5 (GenAI Platform, Agentic Infrastru | Capital One | 76 | ai | 76 | — | ELIGIBLE | True |
| 287 | AI Engineer 5 (Gen AI Platform Services) | Capital One | 76 | ai | 76 | — | ELIGIBLE | True |
| 295 | Senior AI Engineer | EPAM Systems | 76 | ai | 76 | — | ELIGIBLE | True |
| 315 | Senior AI Engineer/ AI Agents Development | EPAM Systems | 75 | ai | 75 | — | ELIGIBLE | True |
| 698 | AI Engineer | System One | 75 | ai | 75 | — | ELIGIBLE | True |
| 359 | Generative AI | Aivra Health LLC | 74 | ai | 74 | — | ELIGIBLE | True |
| 296 | AI Engineer 5 (Gen AI Platform Services - Agenti | Capital One | 72 | ai | 72 | — | ELIGIBLE | True |
| 421 | AI Engineer 5 (AI Foundations, LLM Core and Agen | Capital One | 72 | ai | 72 | — | ELIGIBLE | True |
| 496 | AI/ML Engineer | Boston Technology Corpor | 72 | ai | 72 | — | ELIGIBLE | True |
| 417 | AI Software Engineer (Python, LangChain, LLMs) | ACA Group | 70 | ai | 70 | — | ELIGIBLE | True |
| 437 | AI/ML Engineer (Gen AI, LLM, RAG) | Karwell Technologies Inc | 70 | ai | 70 | — | ELIGIBLE | True |
| 260 | Sr. Forward-Deployed AI Engineer, Snowflake | Spar Information Systems | 68 | ai | 68 | — | ELIGIBLE | True |
| 595 | Java/Python Engineer (Agentic AI)_ W2 | Learn Beyond Consulting  | 68 | ai | 68 | — | ELIGIBLE | True |
| 610 | Senior Python Agentic AI Developer | AgreeYa Solutions | 68 | ai | 68 | — | ELIGIBLE | True |
| 646 | Agentic AI Engineer | Shiv Software Experts LL | 68 | ai | 68 | — | ELIGIBLE | True |
| 985 | AI Engineer – Forward Deployed Engineering (AI F | databricks | 68 | ai | 68 | — | ELIGIBLE | True |
| 1178 | Strategist, Agent Development - Travel, Transpor | sierra | 68 | ai | 68 | — | ELIGIBLE | True |
| 358 | Generative AI Solution Developer | Randstad Digital | 67 | ai | 67 | — | ELIGIBLE | True |
| 881 | Senior AI Engineer | gitlab | 67 | ai | 67 | — | ELIGIBLE | True |
| 276 | AI Engineer 4 | Capital One | 66 | ai | 66 | — | ELIGIBLE | True |
| 336 | Senior Generative AI Engineer | Citi | 66 | ai | 66 | — | ELIGIBLE | True |
| 590 | Junior AI Engineer with Python | Stanley David and Associ | 66 | ai | 66 | — | ELIGIBLE | True |
| 267 | AI Engineer | MassMutual | 65 | ai | 65 | — | ELIGIBLE | True |
| 316 | Generative AI Engineer | Healthcare Triangle Inc | 65 | ai | 65 | — | ELIGIBLE | True |
| 405 | AI/ML Engineer (Gen AI, LLM, RAG) | LetitBeX AI Tech Solutio | 65 | ai | 65 | — | ELIGIBLE | True |
| 460 | Machine Learning Engineer | Stellar IT Solutions | 65 | ai | 65 | — | ELIGIBLE | True |
| 517 | Python AI developer | Mitchell Martin, Inc. | 65 | ai | 65 | — | ELIGIBLE | True |
| 582 | Senior AI / GenAI Solutions Engineer (Python, La | Innova Solutions, Inc | 65 | ai | 65 | — | ELIGIBLE | True |
| 624 | Agentic AI Engineer | Oscar Technology | 65 | ai | 65 | — | ELIGIBLE | True |
| 644 | Agentic AI Engineer - W2 Contract | HPTech Inc. | 65 | ai | 65 | — | ELIGIBLE | True |
| 310 | Lead AI Engineer (10-12 onsite a month) | Calance | 64 | ai | 64 | — | ELIGIBLE | True |
| 327 | Generative AI Engineer - Kansas  City, KS, Denve | TechniPros, LLC | 64 | ai | 64 | — | ELIGIBLE | True |
| 413 | AI Engineer 4 (AI Foundations, LLM Customization | Capital One | 64 | ai | 64 | — | ELIGIBLE | True |
| 880 | Forward Deployed Engineer, AI and Agentic SDLC | gitlab | 64 | ai | 64 | — | ELIGIBLE | True |
| 733 | AI Engineer - Sunnyvale, CA (W2)  ,L2 and GC | BridgeNexus Technologies | 63 | ai | 63 | — | ELIGIBLE | True |
| 258 | AI Engineer | Randstad Digital | 62 | ai | 62 | — | ELIGIBLE | True |
| 285 | Senior GEN AI Engineer | Judge Group, Inc. | 62 | ai | 62 | — | ELIGIBLE | True |
| 326 | Senior Generative AI & Agentic AI Engineer | Apex Systems | 62 | ai | 62 | — | ELIGIBLE | True |
| 444 | RAG Architect / GenAI Solutions Architect | Valcan IT Inc | 62 | ai | 62 | — | ELIGIBLE | True |
| 627 | Senior Agentic AI Engineer | Apex Systems | 62 | ai | 62 | — | ELIGIBLE | True |
| 270 | Principal Agentic AI Engineer | QUANTUM TECHNOLOGIES LLC | 60 | ai | 60 | — | ELIGIBLE | True |
| 509 | Artificial Intelligence/Machine Learning Enginee | Booz Allen Hamilton | 60 | ai | 60 | — | ELIGIBLE | True |
| 634 | Agentic AI Engineer | Sharp Decisions | 60 | ai | 60 | — | ELIGIBLE | True |
| 643 | Agentic AI Engineer | Innova Solutions, Inc | 60 | ai | 60 | — | ELIGIBLE | True |
| 718 | Lead Applied AI Engineer | Innova Solutions, Inc | 60 | ai | 60 | — | ELIGIBLE | True |
| 282 | AI Engineer 5 (AI Foundations) | Capital One | 58 | ai | 58 | — | ELIGIBLE | True |
| 320 | Lead Generative AI / Agentic AI Engineer | PTR Global | 58 | ai | 58 | — | ELIGIBLE | True |
| 331 | Sr Software Engineer /Generative AI Engineer | RightTalents | 58 | ai | 58 | — | ELIGIBLE | True |
| 345 | Generative AI Integration Engineer | Atlantis IT Consulting G | 58 | ai | 58 | — | ELIGIBLE | True |
| 487 | Machine Learning Engineer | Robert Half | 58 | ai | 58 | — | ELIGIBLE | True |
| 546 | .NET Developer with AI & AWS | Nam Info Inc | 58 | ai | 58 | — | ELIGIBLE | True |
| 642 | GenAI/Agentic AI Engineer | Global Soft Systems | 58 | ai | 58 | — | ELIGIBLE | True |
| 708 | Sr AI Engineer-Alpharetta, GA, USA-Hybrid | StoneGate-Technologies L | 58 | ai | 58 | — | ELIGIBLE | True |
| 808 | Senior Machine Learning Engineer | Thorn | 58 | ai | 58 | — | ELIGIBLE | True |
| 906 |  Principal, Agentic Engineering Platform | elastic | 58 | ai | 58 | — | ELIGIBLE | True |
| 961 | Enterprise Application AI Engineer | gusto | 58 | ai | 58 | — | ELIGIBLE | True |
| 1044 | Senior R&D Software Engineer, Fivetran AI | fivetran | 58 | ai | 58 | — | ELIGIBLE | True |
| 425 | AI Engineer 5 (AI Foundations: LLM Customization | Capital One | 56 | ai | 56 | — | ELIGIBLE | True |
| 636 | Agentic AI Engineer -  Madison, WI, Columbus, OH | TechniPros, LLC | 56 | ai | 56 | — | ELIGIBLE | True |
| 262 | Lead Full Stack AI Engineer | Strategic Staffing Solut | 55 | ai | 55 | — | ELIGIBLE | True |
| 269 | Senior AI Engineer/ Lead AI Engineer(Local to GA | Trigint Solutions | 55 | ai | 55 | — | ELIGIBLE | True |
| 294 | AI Engineer 5 (LLM Gateway, FM Hosting) | Capital One | 55 | ai | 55 | — | ELIGIBLE | True |
| 317 | Lead Generative AI Engineer | Apex Systems | 55 | ai | 55 | — | ELIGIBLE | True |
| 511 | AI and ML Engineer and Data Scientist | Booz Allen Hamilton | 55 | ai | 55 | — | ELIGIBLE | True |
| 599 | Sr. AI/ML Engineer - Reading PA, Onsite. Must at | Keylent | 55 | ai | 55 | — | ELIGIBLE | True |
| 712 | Senior AI/ML Engineer | Techsara Solutions | 55 | ai | 55 | — | ELIGIBLE | True |
| 726 | Sr. AI/ML Engineer - Fort Worth, TX (Hybrid) | Saksoft | 55 | ai | 55 | — | ELIGIBLE | True |
| 797 | Staff Software Engineer, AI & Recommendations Pl | hims & hers | 55 | ai | 55 | — | ELIGIBLE | True |
| 1048 | Sr. Principal AI Systems Architect | fivetran | 55 | ai | 55 | — | ELIGIBLE | True |
| 274 | AI Engineer 5 | Capital One | 54 | ai | 54 | — | ELIGIBLE | True |
| 272 | Senior AI Engineer - Contract to Hire | Infolob Global, Inc. | 52 | ai | 52 | — | ELIGIBLE | True |
| 857 | Software Engineer, AI Agents | cloudflare | 52 | ai | 52 | — | ELIGIBLE | True |
| 887 | Senior Machine Learning Engineer, Assistance Eng | airbnb | 52 | ai | 52 | — | ELIGIBLE | True |
| 462 | Senior-level Machine Learning Engineer / Data Sc | BCforward | 50 | ai | 50 | — | ELIGIBLE | True |
| 468 | Principal Machine Learning Engineer | Compunnel Inc. | 50 | ai | 50 | — | ELIGIBLE | True |
| 645 | Agentic AI Engineer | Reveille Technologies | 50 | ai | 50 | — | ELIGIBLE | True |
| 275 | Staff AI Engineer | Capital One | 48 | ai | 48 | — | ELIGIBLE | True |
| 293 | AI Engineer 5 (FM Hosting, LLM Inference) | Capital One | 48 | ai | 48 | — | ELIGIBLE | True |
| 446 | Cloud /AI Architect with RAG and Agentic AI with | Infinity Tech Group Inc | 48 | ai | 48 | — | ELIGIBLE | True |
| 469 | Mid AI/ML Engineer | Booz Allen Hamilton | 48 | ai | 48 | — | ELIGIBLE | True |
| 508 | Machine Learning Engineer 4 (Manager, IC) | Capital One | 48 | ai | 48 | — | ELIGIBLE | True |
| 560 | W2 Local Need :: Technical Architect Lead II (Ap | SVARA SOFTWARE SOLUTIONS | 48 | ai | 48 | — | ELIGIBLE | False |
| 946 | Senior Machine Learning Engineer, AI Insights | coreweave | 48 | ai | 48 | — | ELIGIBLE | True |
| 1089 | Applied AI Engineer, Digital Natives | openai | 48 | ai | 48 | — | ELIGIBLE | True |
| 869 | Senior Product Manager - Bits Agent Builder | datadog | 46 | ai | 46 | — | ELIGIBLE | False |
| 265 | Staff AI Engineer | Compest Solutions Inc | 45 | ai | 45 | — | ELIGIBLE | True |
| 308 | Back End Node.js AI Engineer | Randstad Digital | 45 | ai | 45 | — | ELIGIBLE | False |
| 330 | Generative AI Engineer | Albano Systems Inc | 45 | ai | 45 | — | ELIGIBLE | True |
| 447 | Placement Role - Cloud /AI Architect with RAG an | Infinity Tech Group Inc | 45 | ai | 45 | — | ELIGIBLE | True |
| 466 | AI/ML Engineer | RapidIT, Inc | 45 | ai | 45 | — | ELIGIBLE | True |
| 492 | Machine Learning Engineer 4 - Intelligent Founda | Capital One | 45 | ai | 45 | — | ELIGIBLE | True |
| 549 | AI Software Developer | BESTPEGASUS LLC | 45 | ai | 45 | — | ELIGIBLE | True |
| 620 | Artificial Intelligence/Machine Learning Enginee | Akina, Inc. | 45 | ai | 45 | — | ELIGIBLE | True |
| 766 | AI/ML Data Scientist | System One | 45 | ai | 45 | — | ELIGIBLE | False |
| 872 | Senior Staff GenAI Engineer - Application Perfor | datadog | 45 | ai | 45 | — | ELIGIBLE | True |
| 884 | Sr AI Architect - Conversational AI | twilio | 45 | ai | 45 | — | ELIGIBLE | True |
| 894 | Senior Staff Machine Learning Engineer, Data & E | airbnb | 45 | ai | 45 | — | ELIGIBLE | True |
| 930 | Backend Engineer (Multiple Positions) | launchdarkly | 45 | ai | 45 | — | ELIGIBLE | False |
| 949 | Senior Software and AI Engineer | coreweave | 45 | ai | 45 | — | ELIGIBLE | True |
| 966 | Staff Software Engineer, Core AI Platforms | gusto | 45 | ai | 45 | — | ELIGIBLE | True |
| 871 | Senior Product Solutions Architect - AI Agent | datadog | 44 | ai | 44 | — | ELIGIBLE | False |
| 1002 | Specialist Solutions Architect - AI/ML | databricks | 44 | ai | 44 | — | ELIGIBLE | False |
| 303 | Principal AI Engineer | Judge Group, Inc. | 43 | ai | 43 | — | ELIGIBLE | True |
| 290 | AI Engineer 5 (AI Foundations, VLM Customization | Capital One | 42 | ai | 42 | — | ELIGIBLE | True |
| 631 | Senior Java Agentic AI Engineer (Only W2 & F2F i | COOLSOFT | 42 | ai | 42 | — | ELIGIBLE | True |
| 791 | Staff Software Engineer, AI | YipitData | 42 | ai | 42 | — | ELIGIBLE | False |
| 855 | Senior Systems Engineer, AI Gateway | cloudflare | 42 | ai | 42 | — | ELIGIBLE | False |
| 889 | Senior Machine Learning Engineer, Query Intellig | airbnb | 42 | ai | 42 | — | ELIGIBLE | True |
| 895 | Senior Staff Machine Learning Engineer, Growth P | airbnb | 42 | ai | 42 | — | ELIGIBLE | True |
| 959 | AI Operations Program Manager, Benefits | gusto | 42 | ai | 42 | — | ELIGIBLE | False |
| 964 | Software Engineer, ML Platform | gusto | 42 | ai | 42 | — | ELIGIBLE | True |
| 486 | Artificial Intelligence and Machine Learning Eng | Booz Allen Hamilton | 40 | ai | 40 | — | ELIGIBLE | True |
| 613 | AI Developer with Java Python | Career Soft Solutions In | 40 | ai | 40 | — | ELIGIBLE | False |
| 654 | Agentic AI Engineer | Zelis | 40 | ai | 40 | — | ELIGIBLE | False |
| 702 | Sr Backend Engineer (AWS Serverless & AI Platfor | Trigint Solutions | 40 | ai | 40 | — | ELIGIBLE | False |
| 760 | Machine Learning Engineer, Search Quality | Glean | 40 | ai | 40 | — | ELIGIBLE | False |
| 873 | Staff Applied Scientist - Agentic Interfaces | datadog | 40 | ai | 40 | — | ELIGIBLE | False |
| 875 | Staff Software Engineer - ML Observability | datadog | 40 | ai | 40 | — | ELIGIBLE | True |
| 882 | Senior Backend Engineer, Platform Enablement | gitlab | 40 | ai | 40 | — | ELIGIBLE | False |
| 952 | Senior Systems Engineer, Enterprise AI Platforms | coreweave | 40 | ai | 40 | — | ELIGIBLE | False |
| 984 | Technical Program Manager, AI Tooling | figma | 40 | ai | 40 | — | ELIGIBLE | False |
| 284 | Sr. Manager, AI Engineer (IFX) | Capital One | 38 | ai | 38 | — | ELIGIBLE | False |
| 311 | AI Engineer - Security, Remote - 70475 | PRIMUS Global Services I | 38 | ai | 38 | — | ELIGIBLE | False |
| 441 | Senior AI Engineer (Agentic AI, MCP, RAG)-W2-Ons | Tektree Systems Inc. | 38 | ai | 38 | — | ELIGIBLE | False |
| 456 | Big Data/Machine Learning Engineer | Randstad Digital | 38 | ai | 38 | — | ELIGIBLE | False |
| 457 | Data/Machine Learning Engineer II | The Coca-Cola Company | 38 | ai | 38 | — | ELIGIBLE | False |
| 470 | Senior AI/ML Engineer | Booz Allen Hamilton | 38 | ai | 38 | — | ELIGIBLE | True |
| 490 | Machine Learning Engineer 5 (Senior Manager, IC) | Capital One | 38 | ai | 38 | — | ELIGIBLE | True |
| 524 | Web Application Developer-Agentic AI (Onsite) | GSK Solutions Inc. | 38 | ai | 38 | — | ELIGIBLE | False |
| 570 | Ai Python Engineer Contract | Vega Consulting Solution | 38 | ai | 38 | — | ELIGIBLE | True |
| 589 | AI Scrum Master with Python - 100% remote | System One | 38 | ai | 38 | — | ELIGIBLE | False |
| 608 | Artificial Intelligence/Machine Learning Enginee | Akina, Inc. | 38 | ai | 38 | — | ELIGIBLE | True |
| 616 | Lead Software Engineer - Java / Python / AWS / A | JPMorgan Chase & Co. | 38 | ai | 38 | — | ELIGIBLE | False |
| 678 | AI Architect & Backend Development Lead | VDart, Inc. | 38 | ai | 38 | — | ELIGIBLE | False |
| 795 | Backend Engineer - Music | Spotify | 38 | ai | 38 | — | ELIGIBLE | False |
| 896 | Senior Staff Machine Learning Engineer, Post Tra | airbnb | 38 | ai | 38 | — | ELIGIBLE | True |
| 901 | Staff Machine Learning Engineer, Traffic Intelli | airbnb | 38 | ai | 38 | — | ELIGIBLE | True |
| 911 | Senior Software Engineer - Security Integrations | elastic | 38 | ai | 38 | — | ELIGIBLE | False |
| 922 | Backend Engineer, Control Plane | tailscale | 38 | ai | 38 | — | ELIGIBLE | False |
| 932 | Senior Applied AI Specialist | launchdarkly | 38 | ai | 38 | — | ELIGIBLE | False |
| 257 | AI Engineer- | mProgen | 35 | ai | 35 | — | ELIGIBLE | False |
| 261 | AI Engineer- Irving, TX | mProgen | 35 | ai | 35 | — | ELIGIBLE | False |
| 372 | AI Solution Architect (SAP AI/Generative AI) | ComTec Information Syste | 35 | ai | 35 | — | ELIGIBLE | False |
| 450 | Manager, SAP Business Technology Platform AI Eng | Johnson & Johnson | 35 | ai | 35 | — | ELIGIBLE | False |
| 471 | Staff Machine Learning Engineer | Capital One | 35 | ai | 35 | — | ELIGIBLE | True |
| 493 | Applied Machine Learning Engineer & Computer Vis | Motion Recruitment Partn | 35 | ai | 35 | — | ELIGIBLE | True |
| 615 | Python/React/Full Stack Engineer (AI & Data Plat | NTT DATA, Inc. | 35 | ai | 35 | — | ELIGIBLE | False |
| 648 | Senior Front-End Agentic AI Engineer | LTS | 35 | ai | 35 | — | ELIGIBLE | False |
| 676 | W2 Position - Node.js AI Backend Engineer - CA | Octans Group LLC | 35 | ai | 35 | — | ELIGIBLE | False |
| 680 | Senior Backend Engineer (AWS Serverless & AI Pla | Cyberobotix | 35 | ai | 35 | — | ELIGIBLE | False |
| 730 | Senior Data Scientist | ACI Group, Inc. | 35 | ai | 35 | — | ELIGIBLE | False |
| 864 | Product Manager II, AI & Data Security | datadog | 35 | ai | 35 | — | ELIGIBLE | False |
| 879 | Engineering Manager, Agent Foundations: Agent Ex | gitlab | 35 | ai | 35 | — | ELIGIBLE | False |
| 898 | Staff Backend Engineer - Ads Platform | airbnb | 35 | ai | 35 | — | ELIGIBLE | False |
| 907 | Principal AI Ecosystem Architect - OpenAI/Anthro | elastic | 35 | ai | 35 | — | ELIGIBLE | False |
| 1042 | Principal Software Engineer, AI Tooling & Adopti | fivetran | 35 | ai | 35 | — | ELIGIBLE | False |
| 789 | Principal Data Scientist - Consumer | Gopuff | 34 | ai | 34 | — | ELIGIBLE | False |
| 847 | Senior Customer Engineer-  (AI & Start-Ups). Los | cloudflare | 34 | ai | 34 | — | ELIGIBLE | False |
| 868 | Senior Platform Product Manager - AI SDLC Truste | datadog | 34 | ai | 34 | — | ELIGIBLE | False |
| 263 | NodeJS AI Engineer | Randstad Digital | 32 | ai | 32 | — | ELIGIBLE | False |
| 439 | AI Engineer â Agentic AI / RAG / MCP | Galaxy i Technologies, I | 32 | ai | 32 | — | ELIGIBLE | False |
| 587 | Python AI Full Stack | Capgemini America, Inc. | 32 | ai | 32 | — | ELIGIBLE | False |
| 731 | Senior AI Engineer(Java) | QUANTUM TECHNOLOGIES LLC | 32 | ai | 32 | — | ELIGIBLE | False |
| 787 | Senior Data Scientist | Peerspace | 32 | ai | 32 | — | ELIGIBLE | False |
| 905 | GenAI Security - Principal Security Research Eng | elastic | 32 | ai | 32 | — | ELIGIBLE | False |
| 965 | Staff Software Engineer, AI Voice and Content | gusto | 32 | ai | 32 | — | ELIGIBLE | False |
| 792 | Senior Data Scientist | Customer.io | 31 | ai | 31 | — | ELIGIBLE | False |
| 259 | Network Automation & AI Engineer | Hexaware Technologies, I | 30 | ai | 30 | — | ELIGIBLE | False |
| 377 | AI/LLM Application Engineer | Randstad Digital | 30 | ai | 30 | — | ELIGIBLE | False |
| 510 | Machine Learning Engineer | ConnectedX, Inc. | 30 | ai | 30 | — | ELIGIBLE | False |
| 521 | AI Security Engineer / Application Security Engi | Compest Solutions Inc | 30 | ai | 30 | — | ELIGIBLE | False |
| 578 | Sr. AI/Python Engineer | Citi | 30 | ai | 30 | — | ELIGIBLE | False |
| 696 | Java Backend Developer with AI/DLC | Purview Services | 30 | ai | 30 | — | ELIGIBLE | False |
| 786 | Director, AI-Enabled Fraud Prevention & Investig | Clover Health | 30 | ai | 30 | — | ELIGIBLE | False |
| 793 | Senior Data Engineer II, AI Native | Life360 | 30 | ai | 30 | — | ELIGIBLE | False |
| 877 | AI Transformation Owner, CRO | gitlab | 30 | ai | 30 | — | ELIGIBLE | False |
| 885 | Principal Machine Learning Engineer- LLM Fine-tu | airbnb | 30 | ai | 30 | — | ELIGIBLE | True |
| 902 |  Staff Platform Manager, AI Personalization | airbnb | 30 | ai | 30 | — | ELIGIBLE | False |
| 960 | Data Scientist, Risk  | gusto | 30 | ai | 30 | — | ELIGIBLE | False |
| 1137 | Data Scientist, B2B Generalist | openai | 30 | ai | 30 | — | ELIGIBLE | False |
| 429 | Senior Java Backend Engineer  AI(RAG, Ontology)  | AgreeYa Solutions | 28 | ai | 28 | — | ELIGIBLE | False |
| 861 | Manager I, Applied Science - Frontier Agentic Mo | datadog | 28 | ai | 28 | — | ELIGIBLE | False |
| 909 | Principal Product Manager II, AI/Vectors  | elastic | 28 | ai | 28 | — | ELIGIBLE | False |
| 940 | Senior Product Manager (AI CICD) | chainguard | 28 | ai | 28 | — | ELIGIBLE | False |
| 958 | AI/IT Controls Engineer, Enterprise Applications | gusto | 28 | ai | 28 | — | ELIGIBLE | False |
| 963 | Principal Product Manager, AI Assistant | gusto | 28 | ai | 28 | — | ELIGIBLE | False |
| 982 | Strategic Finance, AI Innovation | figma | 28 | ai | 28 | — | ELIGIBLE | False |
| 455 | Principal Machine Learning Engineer | PaloAlto Networks | 25 | ai | 25 | — | ELIGIBLE | False |
| 481 | Senior Manager, Machine Learning Engineer | Capital One | 25 | ai | 25 | — | ELIGIBLE | False |
| 575 | Senior Python AI Engineer (Hands-On), VP | Citi | 25 | ai | 25 | — | ELIGIBLE | False |
| 798 | Staff Product Manager, Physical AI | Homebound | 25 | ai | 25 | — | ELIGIBLE | False |
| 893 | Senior Staff Data Scientist, Guest & Host Market | airbnb | 25 | ai | 25 | — | ELIGIBLE | False |
| 899 | Staff Data Scientist, Guest & Host | airbnb | 25 | ai | 25 | — | ELIGIBLE | False |
| 1147 | Technical Program Manager, Global Programs — App | openai | 25 | ai | 25 | — | ELIGIBLE | False |
| 876 | Web Content Engineering & AI Visibility Lead | datadog | 24 | ai | 24 | — | ELIGIBLE | False |
| 859 | AI Research Scientist - Datadog AI Research (DAI | datadog | 22 | ai | 22 | — | ELIGIBLE | False |
| 862 | Manager II, Engineering - Database Monitoring (A | datadog | 22 | ai | 22 | — | ELIGIBLE | False |
| 886 | Senior Data Scientist - Payments (Inference) | airbnb | 22 | ai | 22 | — | ELIGIBLE | False |
| 962 | Manager - Developer Productivity, AI Tools | gusto | 22 | ai | 22 | — | ELIGIBLE | False |
| 1027 | Staff Product Designer, Agentic Coding | databricks | 22 | ai | 22 | — | ELIGIBLE | False |
| 572 | Java AWS Angular Python AI Software Engineer | Avancer Corporation | 20 | ai | 20 | — | ELIGIBLE | False |
| 693 | Senior Software Engineer, Backend - Financial AI | Rippling | 20 | ai | 20 | — | ELIGIBLE | False |
| 768 | Data & AI-ML Solution Architect | Ekfrazo Technologies LLC | 20 | ai | 20 | — | ELIGIBLE | False |
| 785 | Software Engineer New Grad, Machine Learning Pla | Quora | 20 | ai | 20 | — | ELIGIBLE | False |
| 800 | Senior Manager of AI Practice, Claude Corps | CodePath | 20 | ai | 20 | — | ELIGIBLE | False |
| 915 | Tech Lead, Agent Framework - Observability | elastic | 20 | ai | 20 | — | ELIGIBLE | False |
| 790 | Senior Pricing Data Scientist | Fivetran | 18 | ai | 18 | — | ELIGIBLE | False |
| 806 | Tamil Translator | Sigma AI | Sigma | 18 | ai | 18 | — | ELIGIBLE | False |
| 860 | Distinguished Architect, AI | datadog | 18 | ai | 18 | — | ELIGIBLE | False |
| 1009 | Sr. Manager, Engineering - AI/BI | databricks | 18 | ai | 18 | — | ELIGIBLE | False |
| 655 | Senior Agentic AI Engineer | Verizon | 15 | ai | 15 | — | ELIGIBLE | False |
| 659 | Agentic AI Engineer (AVP) | Citi | 15 | ai | 15 | — | ELIGIBLE | False |
| 666 | Senior Agentic AI Engineer (VP) | Citi | 15 | ai | 15 | — | ELIGIBLE | False |
| 724 | Gate-level IR/EM CAD/NLP Engineer | Apple, Inc. | 15 | ai | 15 | — | ELIGIBLE | False |
| 866 | Program Manager, AI and Developer Community Cont | datadog | 15 | ai | 15 | — | ELIGIBLE | False |
| 878 | Director of Product Management, Agentic Software | gitlab | 15 | ai | 15 | — | ELIGIBLE | False |
| 883 | Strategic Account Executive, AI - San Francisco  | gitlab | 15 | ai | 15 | — | ELIGIBLE | False |
| 903 | Staff UX Writer, AI | airbnb | 15 | ai | 15 | — | ELIGIBLE | False |
| 947 | Senior Manager, Physical AI Communications | coreweave | 15 | ai | 15 | — | ELIGIBLE | False |
| 1214 | Strategic Finance, AI & Business Partnership | notion | 15 | ai | 15 | — | ELIGIBLE | False |
| 807 | Principal Business Consultant, Buildings & Data  | Autodesk | 12 | ai | 12 | — | ELIGIBLE | False |
| 863 | Manager, Strategic Sourcing, AI Infrastructure & | datadog | 12 | ai | 12 | — | ELIGIBLE | False |
| 865 | Product Strategy and Corporate Development Lead, | datadog | 12 | ai | 12 | — | ELIGIBLE | False |
| 867 | Senior Corporate Development Lead, AI | datadog | 12 | ai | 12 | — | ELIGIBLE | False |
| 892 | Senior Manager, Technical Program Management (Se | airbnb | 12 | ai | 12 | — | ELIGIBLE | False |
| 910 | RVP - AI Natives | elastic | 12 | ai | 12 | — | ELIGIBLE | False |
| 912 | Strategic Account Executive - AI Natives - West | elastic | 12 | ai | 12 | — | ELIGIBLE | False |
| 929 | Expert Backend Engineer | wizinc | 10 | ai | 10 | — | ELIGIBLE | False |
| 1148 | Integrated Marketing Manager, AI Impact | openai | 10 | ai | 10 | — | ELIGIBLE | False |
| 1 | PrairieLearn (Remote US) — Full-Stack Software E | PrairieLearn (Remote US) | — | unscored | — | — | REVIEW_REQUIRED | — |
| 2 | Staff Machine Learning Engineer | Estee Lauder Companies | — | unscored | — | — | REVIEW_REQUIRED | — |
| 3 | AI Scientist (Staff, Senior) | Tempus AI | — | unscored | — | — | REVIEW_REQUIRED | — |
| 4 | Senior AI Engineer | ML6 | — | unscored | — | — | INELIGIBLE | — |
| 5 | (Founding) AI Systems Engineer | Charly | — | unscored | — | — | INELIGIBLE | — |
| 6 | Multiple Engineering, AI/ML Data Science, Revenu | Spade | — | unscored | — | — | REVIEW_REQUIRED | — |
| 7 | Machine Learning Engineer (Python, ML) | Hestus | — | unscored | — | — | INELIGIBLE | — |
| 8 | Founding Engineer (Security / AI / Distributed S | Founding Engineer (Secur | — | unscored | — | — | REVIEW_REQUIRED | — |
| 9 | Principal Product Manager, AI Products | Komodo Health | — | unscored | — | — | INELIGIBLE | — |
| 10 | Data Scientist, Classification and Scoring | Lokker.com | — | unscored | — | — | REVIEW_REQUIRED | — |
| 11 | Engineering Manager, Applied AI | JUPUS | — | unscored | — | — | REVIEW_REQUIRED | — |
| 12 | Head of AI Sales / AI Go To Market | Toolhouse AI | — | unscored | — | — | REVIEW_REQUIRED | — |
| 13 | Software Engineers (SRE, ML, backend, full-stack | Radar Labs | — | unscored | — | — | REVIEW_REQUIRED | — |
| 14 | Senior AI Engineer | Lemon.io | — | unscored | — | — | INELIGIBLE | — |
| 15 | Senior Data Scientist | Lemon.io | — | unscored | — | — | INELIGIBLE | — |
| 16 | Applied AI Engineer (New or Recent Grad) | iManage | — | unscored | — | — | INELIGIBLE | — |
| 17 | AI/ML Engineer, Senior | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 18 | AI/ML Engineer, Mid | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 19 | Senior Machine Learning Engineer | EvenUp | — | unscored | — | — | INELIGIBLE | — |
| 20 | Senior Machine Learning Engineer, Trust | Airbnb | — | unscored | — | — | INELIGIBLE | — |
| 21 | Senior machine learning engineer | Atlassian | — | unscored | — | — | INELIGIBLE | — |
| 22 | Machine Learning Engineer Graduate (E-Commerce R | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 23 | Software Engineer, Early Career (AI) | Notion | — | unscored | — | — | INELIGIBLE | — |
| 24 | Machine Learning Engineer | Plenful | — | unscored | — | — | INELIGIBLE | — |
| 25 | Machine Learning Engineer | ServiceNow | — | unscored | — | — | INELIGIBLE | — |
| 26 | Senior machine learning engineer | Atlassian | — | unscored | — | — | INELIGIBLE | — |
| 27 | Machine Learning Engineer | Crowe | — | unscored | — | — | INELIGIBLE | — |
| 28 | Machine Learning Engineer | Crowe | — | unscored | — | — | INELIGIBLE | — |
| 29 | Machine Learning Engineer | Wanderboat AI | — | unscored | — | — | INELIGIBLE | — |
| 30 | Staff Machine Learning Engineer, Financial Conne | Stripe | — | unscored | — | — | INELIGIBLE | — |
| 31 | Staff Machine Learning Engineer | Databricks | — | unscored | — | — | INELIGIBLE | — |
| 32 | AI Engineer 3 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 33 | AI Engineer II | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 34 | AI Engineer Senior | Hybrid | Allianz Life | — | unscored | — | — | INELIGIBLE | — |
| 35 | AI Engineer II | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 36 | Senior Engineer - Machine Learning | Qualcomm | — | unscored | — | — | INELIGIBLE | — |
| 37 | Staff Machine Learning Engineer, Financial Conne | Stripe | — | unscored | — | — | INELIGIBLE | — |
| 38 | AI/ML Engineer - Multiple levels (Cleared) | Noblis | — | unscored | — | — | INELIGIBLE | — |
| 39 | AI Engineer | CYVL | — | unscored | — | — | INELIGIBLE | — |
| 40 | AI Engineer 3 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 41 | Machine Learning Engineer Graduate (E-Commerce R | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 42 | Sr AI/ML Engineer | Cognizant | — | unscored | — | — | INELIGIBLE | — |
| 43 | Staff Machine Learning Engineer, AI | Sentry | — | unscored | — | — | INELIGIBLE | — |
| 44 | AI Engineer | Avathon | — | unscored | — | — | INELIGIBLE | — |
| 45 | Senior Machine Learning Engineer | GEICO | — | unscored | — | — | INELIGIBLE | — |
| 46 | Machine Learning Engineer | Qualcomm | — | unscored | — | — | INELIGIBLE | — |
| 47 | Senior Machine Learning Engineer - Content and C | Yelp | — | unscored | — | — | INELIGIBLE | — |
| 48 | Senior AI / Machine Learning Engineer — Fraud De | Adobe | — | unscored | — | — | INELIGIBLE | — |
| 49 | Senior AI/ML Engineer | CACI International Inc | — | unscored | — | — | INELIGIBLE | — |
| 50 | Senior ML Engineer | ServiceNow | — | unscored | — | — | INELIGIBLE | — |
| 51 | SR. Machine Learning Engineer, Enterprise AI Sys | The Home Depot | — | unscored | — | — | INELIGIBLE | — |
| 52 | Senior ML Engineer, Computer Vision - Applied AI | Uber | — | unscored | — | — | INELIGIBLE | — |
| 53 | Senior AI Engineer | Avathon | — | unscored | — | — | INELIGIBLE | — |
| 54 | Software Engineer AI/ML - TS/SCI | Parsons Corporation | — | unscored | — | — | INELIGIBLE | — |
| 55 | AI/ML Engineer | Cognizant | — | unscored | — | — | INELIGIBLE | — |
| 56 | AI/LLM Engineer | Gap International | — | unscored | — | — | INELIGIBLE | — |
| 57 | Agentic AI Engineer — Healthcare AI | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 58 | Agentic AI Engineer — Healthcare AI | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 59 | Lead GenAI Engineer (LLM) | State Farm | — | unscored | — | — | INELIGIBLE | — |
| 60 | Sr. AI/ML Engineer- Remote or Eden Prairie, MN | Optum | — | unscored | — | — | INELIGIBLE | — |
| 61 | Lead GenAI Engineer (LLM) | State Farm | — | unscored | — | — | INELIGIBLE | — |
| 62 | Generative AI/LLM Engineer | Public Storage | — | unscored | — | — | INELIGIBLE | — |
| 63 | Lead AI Engineer | ZS | — | unscored | — | — | INELIGIBLE | — |
| 64 | Senior AI Engineer | Capgemini Engineering | — | unscored | — | — | INELIGIBLE | — |
| 65 | Experienced AI Engineer - Generative AI/Machine  | RLI Insurance Company | — | unscored | — | — | INELIGIBLE | — |
| 66 | AI Agent Engineer | Harrison Clarke | — | unscored | — | — | INELIGIBLE | — |
| 67 | GenAI Engineer | Tata Consultancy Service | — | unscored | — | — | INELIGIBLE | — |
| 68 | AI Platform Engineer | Verizon | — | unscored | — | — | INELIGIBLE | — |
| 69 | Applied AI Engineer | Hasbro | — | unscored | — | — | INELIGIBLE | — |
| 70 | AVP, Principal AI Engineer | LPL Financial | — | unscored | — | — | INELIGIBLE | — |
| 71 | Senior AI Engineer | Mastercard | — | unscored | — | — | INELIGIBLE | — |
| 72 | Principal AI Developer, oCTO Industry AI | SAP | — | unscored | — | — | INELIGIBLE | — |
| 73 | Software Engineer AI | Boehringer Ingelheim | — | unscored | — | — | INELIGIBLE | — |
| 74 | Generative AI Applications Engineer (Agents & RA | Accenture Federal Servic | — | unscored | — | — | INELIGIBLE | — |
| 75 | Experienced AI Engineer - Generative AI/Machine  | RLI Insurance Company | — | unscored | — | — | INELIGIBLE | — |
| 76 | Senior AI Engineer | CACI International Inc | — | unscored | — | — | INELIGIBLE | — |
| 77 | Lead AI/ML Engineer - Schaumburg, IL or Eden Pra | Optum | — | unscored | — | — | INELIGIBLE | — |
| 78 | AI Engineer Lead | Capital Group | — | unscored | — | — | INELIGIBLE | — |
| 79 | Cleared GenAI Engineer | Accenture Federal Servic | — | unscored | — | — | INELIGIBLE | — |
| 80 | Principal, AI Engineer | Venture Global LNG | — | unscored | — | — | INELIGIBLE | — |
| 81 | Machine Learning Engineer | Crowe | — | unscored | — | — | INELIGIBLE | — |
| 82 | Principal AI Engineer | Wells Fargo | — | unscored | — | — | INELIGIBLE | — |
| 83 | AVP, Principal AI Engineer | LPL Financial | — | unscored | — | — | INELIGIBLE | — |
| 84 | Machine Learning Engineer | Crowe | — | unscored | — | — | INELIGIBLE | — |
| 85 | AI Engineer Lead | Capital Group | — | unscored | — | — | INELIGIBLE | — |
| 86 | AI Platform Engineer (PC Agentic Applications) - | Lenovo | — | unscored | — | — | INELIGIBLE | — |
| 87 | Generative AI Lead Engineer | Cognizant | — | unscored | — | — | INELIGIBLE | — |
| 88 | AI Platform Engineer | Verizon | — | unscored | — | — | INELIGIBLE | — |
| 89 | AI Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 90 | Applied AI Engineer, Codex Core Agent | OpenAI | — | unscored | — | — | INELIGIBLE | — |
| 91 | Senior AI Engineer | PURE Insurance | — | unscored | — | — | INELIGIBLE | — |
| 92 | AI Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 93 | Applied AI Engineer | MaintainX | — | unscored | — | — | INELIGIBLE | — |
| 94 | Principal AI/ML Engineer - TS/SCI w/ Poly | Parsons Corporation | — | unscored | — | — | INELIGIBLE | — |
| 95 | Agentic AI Engineer — Healthcare AI | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 96 | Applied AI Engineer | MaintainX | — | unscored | — | — | INELIGIBLE | — |
| 97 | AI Eng Lead | Blend | — | unscored | — | — | INELIGIBLE | — |
| 98 | Lead AI Engineer | PowerSchool | — | unscored | — | — | INELIGIBLE | — |
| 99 | Senior LLM Engineer | Molex | — | unscored | — | — | INELIGIBLE | — |
| 100 | Senior LLM Engineer | Molex | — | unscored | — | — | INELIGIBLE | — |
| 101 | Lead AI Engineer | Homeland Talent Solution | — | unscored | — | — | INELIGIBLE | — |
| 102 | Lead Applied AI Engineer | Lincoln Financial | — | unscored | — | — | INELIGIBLE | — |
| 103 | Agentic AI Engineer - Anthropic/Claude | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 104 | Principal Engineer - AI Engineering | GE Vernova | — | unscored | — | — | INELIGIBLE | — |
| 105 | Developer, Applied AI, Penguin Random House (Ope | Penguin Random House | — | unscored | — | — | INELIGIBLE | — |
| 106 | Engineer, Applied AI | National Debt Relief, LL | — | unscored | — | — | INELIGIBLE | — |
| 107 | Agentic AI Engineer/AI Prompt Engineer | Infosys | — | unscored | — | — | INELIGIBLE | — |
| 108 | Agentic AI Engineer - Anthropic/Claude | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 109 | Staff Engineer - AI Engineering | GE Vernova | — | unscored | — | — | INELIGIBLE | — |
| 110 | AI Eng Lead/Manager | Blend | — | unscored | — | — | INELIGIBLE | — |
| 111 | AI & Decision Engineer | Johns Hopkins Applied Ph | — | unscored | — | — | INELIGIBLE | — |
| 112 | AI Engineer Lead | Capital Group | — | unscored | — | — | INELIGIBLE | — |
| 113 | AI & Machine Learning Engineering Consultant - S | EY | — | unscored | — | — | INELIGIBLE | — |
| 114 | Lead GenAI Engineer (LLM) | State Farm | — | unscored | — | — | INELIGIBLE | — |
| 115 | AI Engineer, Agentic Systems | FuelCell Energy | — | unscored | — | — | INELIGIBLE | — |
| 116 | Applied AI / LLM Solutions Engineer | Tachyon Technologies | — | unscored | — | — | INELIGIBLE | — |
| 117 | Founding ML Engineer – Search & Agents | Greylock Partners | — | unscored | — | — | INELIGIBLE | — |
| 118 | Quantitative Trading & Research - Applied Resear | JPMorganChase | — | unscored | — | — | INELIGIBLE | — |
| 119 | ML Engineer, Retrieval & Grounded Generation | DEFCON AI | — | unscored | — | — | INELIGIBLE | — |
| 120 | Principal AI/ML Engineer, Semantic Data | Major League Soccer | — | unscored | — | — | INELIGIBLE | — |
| 121 | AI Engineer | Haystack | — | unscored | — | — | INELIGIBLE | — |
| 122 | Agentic AI Developer III | Realpage | — | unscored | — | — | INELIGIBLE | — |
| 123 | Machine Learning Engineer, Growth Platform | Stripe | — | unscored | — | — | INELIGIBLE | — |
| 124 | Machine Learning Engineer | Evlo AI | — | unscored | — | — | INELIGIBLE | — |
| 125 | Senior Machine Learning Engineer | Atlassian | — | unscored | — | — | INELIGIBLE | — |
| 126 | Machine Learning Engineer 4 (IC) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 127 | Machine Learning Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 128 | Machine Learning Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 129 | Senior Machine Learning Engineer, Trust | Airbnb | — | unscored | — | — | INELIGIBLE | — |
| 130 | Machine Learning Engineer 4 (IC) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 131 | Machine Learning Engineer, Fulfillment | Lyft | — | unscored | — | — | INELIGIBLE | — |
| 132 | Senior Machine Learning Engineer | Atlassian | — | unscored | — | — | INELIGIBLE | — |
| 133 | Principal Machine Learning Engineer | Thrive Market | — | unscored | — | — | INELIGIBLE | — |
| 134 | Senior Machine Learning Engineer, Recommendation | Etsy | — | unscored | — | — | INELIGIBLE | — |
| 135 | Machine Learning Engineer, Level 5 | Snap Inc. | — | unscored | — | — | INELIGIBLE | — |
| 136 | Senior Machine Learning Engineer  I // II | Signifyd | — | unscored | — | — | INELIGIBLE | — |
| 137 | Machine Learning Engineer, Level 4 | Snap Inc. | — | unscored | — | — | INELIGIBLE | — |
| 138 | Senior Machine Learning Engineer | Agero, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 139 | Machine Learning Engineer | Lyft | — | unscored | — | — | INELIGIBLE | — |
| 140 | Machine Learning Engineer | Clay | — | unscored | — | — | INELIGIBLE | — |
| 141 | Staff Machine Learning Engineer, Home Surfaces | Spotify | — | unscored | — | — | INELIGIBLE | — |
| 142 | Senior Machine Learning Engineer | GEICO | — | unscored | — | — | INELIGIBLE | — |
| 143 | AI Engineer II | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 144 | Machine Learning Engineer II | CLEAR | — | unscored | — | — | INELIGIBLE | — |
| 145 | Senior Machine Learning Engineer IV | Trilliant Health | — | unscored | — | — | INELIGIBLE | — |
| 146 | Senior Machine Learning Engineer, Personalizatio | Spotify | — | unscored | — | — | INELIGIBLE | — |
| 147 | Machine Learning Engineer - Fraud Risk | Rain | — | unscored | — | — | INELIGIBLE | — |
| 148 | Machine Learning Engineer II (Applied Research & | PathAI | — | unscored | — | — | INELIGIBLE | — |
| 149 | Machine Learning Engineer | Adobe | — | unscored | — | — | INELIGIBLE | — |
| 150 | Senior Machine Learning Engineer | adMarketplace | — | unscored | — | — | INELIGIBLE | — |
| 151 | Machine Learning Engineer III (Applied Research  | PathAI | — | unscored | — | — | INELIGIBLE | — |
| 152 | Applied AI/ML Engineer | Confido | — | unscored | — | — | INELIGIBLE | — |
| 153 | Sr. AI/ML Engineer - Remote | Optum | — | unscored | — | — | INELIGIBLE | — |
| 154 | Machine Learning Engineer | UST | — | unscored | — | — | INELIGIBLE | — |
| 155 | Software Engineer, Machine Learning (All Levels  | DoorDash | — | unscored | — | — | INELIGIBLE | — |
| 156 | AI Developer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 157 | Senior AI Full stack Software Engineer | McKesson | — | unscored | — | — | INELIGIBLE | — |
| 158 | Senior Software Engineer, AI Platform | Ridgeline | — | unscored | — | — | INELIGIBLE | — |
| 159 | Mid Level AI Engineer | Capco | — | unscored | — | — | INELIGIBLE | — |
| 160 | AI/ML Engineer (sign-on bonus eligible) | Vantor | — | unscored | — | — | INELIGIBLE | — |
| 161 | AI/ML Engineer | Peraton Labs | — | unscored | — | — | INELIGIBLE | — |
| 162 | Senior AI Full stack Software Engineer | McKesson | — | unscored | — | — | INELIGIBLE | — |
| 163 | Senior Software Engineer, AI/ML GenAI, Google Wo | Google | — | unscored | — | — | INELIGIBLE | — |
| 164 | Software Engineer - AI – CoCounsel Forward Deplo | Thomson Reuters | — | unscored | — | — | INELIGIBLE | — |
| 165 | AI Developer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 166 | Software Engineer III, AI/ML GenAI, Google Cloud | Google | — | unscored | — | — | INELIGIBLE | — |
| 167 | AI Software Developer (Mid-level) - TS/SCI with  | General Dynamics Informa | — | unscored | — | — | INELIGIBLE | — |
| 168 | AI Developer | Western & Southern Finan | — | unscored | — | — | INELIGIBLE | — |
| 169 | Senior Software Engineer, Machine Learning (LLM  | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 170 | Software Engineeer, AI | Fitch Ratings | — | unscored | — | — | INELIGIBLE | — |
| 171 | Software Engineer (.NET & AI) | Caterpillar Inc. | — | unscored | — | — | INELIGIBLE | — |
| 172 | Sr. AI Engineer, Special Programs | SpaceX | — | unscored | — | — | INELIGIBLE | — |
| 173 | Software Engineer 2 (AI/GenAI) | U.S. Bank | — | unscored | — | — | INELIGIBLE | — |
| 174 | Applied AI Engineer | Abby Care | — | unscored | — | — | INELIGIBLE | — |
| 175 | AI Software Engineer II | Relativity Space | — | unscored | — | — | INELIGIBLE | — |
| 176 | Senior Software Engineer (AI Agents) | Traba | — | unscored | — | — | INELIGIBLE | — |
| 177 | Gen AI Engineer | Tata Consultancy Service | — | unscored | — | — | INELIGIBLE | — |
| 178 | Senior Software Engineer - LLM and Agentic AI Ap | Skyrocket Ventures | — | unscored | — | — | INELIGIBLE | — |
| 179 | Member of Technical Staff, Applied AI | Finch | — | unscored | — | — | INELIGIBLE | — |
| 180 | AI Associate Engineer for Sales Assistant Platfo | JPMorganChase | — | unscored | — | — | INELIGIBLE | — |
| 181 | Machine Learning Engineer | EarnIn | — | unscored | — | — | INELIGIBLE | — |
| 182 | Application Software Engineer, Applied AI | SpaceX | — | unscored | — | — | INELIGIBLE | — |
| 183 | Senior Software Engineer (AI Agents) | Traba | — | unscored | — | — | INELIGIBLE | — |
| 184 | Applied AI Engineer, Physical AI platform | Dexmate | — | unscored | — | — | INELIGIBLE | — |
| 185 | Member of Technical Staff, AI Agents | Socratix AI | — | unscored | — | — | INELIGIBLE | — |
| 186 | SAP-BTP AI Developer - Lead Software Engineer | JPMorganChase | — | unscored | — | — | INELIGIBLE | — |
| 187 | AI Engineer II | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 188 | AI/ML Engineer | Vanguard | — | unscored | — | — | INELIGIBLE | — |
| 189 | AI/ML Engineer | NODA AI | — | unscored | — | — | INELIGIBLE | — |
| 190 | Senior Applied AI/ML Engineer | Pivotal Health | — | unscored | — | — | INELIGIBLE | — |
| 191 | Senior Applied AI/ML Engineer | Pivotal Health | — | unscored | — | — | INELIGIBLE | — |
| 192 | Staff+ Software Engineer, Account Abuse (Machine | Anthropic | — | unscored | — | — | INELIGIBLE | — |
| 193 | Senior AI Engineer - Subject Matter Expert | Sky Solutions | — | unscored | — | — | INELIGIBLE | — |
| 194 | Sr AI/ML Engineer Remote Nationwide or Office-Ba | Optum | — | unscored | — | — | INELIGIBLE | — |
| 195 | AI Engineer | CYVL | — | unscored | — | — | INELIGIBLE | — |
| 196 | Staff+ Software Engineer, Account Abuse (Machine | Anthropic | — | unscored | — | — | INELIGIBLE | — |
| 197 | Senior AI/ML Engineer | Pedestal Health | — | unscored | — | — | INELIGIBLE | — |
| 198 | Software Engineer - Applied AI/ML | Parsons Corporation | — | unscored | — | — | INELIGIBLE | — |
| 199 | AI Engineer | VOLO Health | — | unscored | — | — | INELIGIBLE | — |
| 200 | AI & Machine Learning Engineering Consultant - S | EY | — | unscored | — | — | INELIGIBLE | — |
| 201 | Sr. AI/ML Engineer - OptumHealth - Remote | Optum | — | unscored | — | — | INELIGIBLE | — |
| 202 | AI & Machine Learning Engineering Consultant - S | EY | — | unscored | — | — | INELIGIBLE | — |
| 203 | Machine Learning Engineer 4 (Python, AWS, SQL, G | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 204 | Applied AI Engineer - National Security (TS/SCI) | TRM Labs | — | unscored | — | — | INELIGIBLE | — |
| 205 | Machine Learning Engineer, Growth Platform | Stripe | — | unscored | — | — | INELIGIBLE | — |
| 206 | AI/ML Engineer, Software Development - Noke | Janus International | — | unscored | — | — | INELIGIBLE | — |
| 207 | Agentic AI Engineer — Healthcare AI | Deloitte | — | unscored | — | — | INELIGIBLE | — |
| 208 | Senior Software Engineer, Agentic AI | Curai Health | — | unscored | — | — | INELIGIBLE | — |
| 209 | Senior Engineer - Applied AI | GEICO | — | unscored | — | — | INELIGIBLE | — |
| 210 | AI Engineer (Healthcare) | San Francisco | $220k | Harrison Clarke | — | unscored | — | — | INELIGIBLE | — |
| 211 | Principal Engineer - Partner with Customers AI S | HARMAN International | — | unscored | — | — | INELIGIBLE | — |
| 212 | Senior Gen AI Software Engineer | Fitch Group, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 213 | Principal Engineer, AI | Anaplan | — | unscored | — | — | INELIGIBLE | — |
| 214 | Senior Engineer - Applied AI | GEICO | — | unscored | — | — | INELIGIBLE | — |
| 215 | Principal Engineer, AI | Anaplan | — | unscored | — | — | INELIGIBLE | — |
| 216 | Senior AI Agentic Engineer | Truist | — | unscored | — | — | INELIGIBLE | — |
| 217 | Senior Software Engineer, Backend - Platform (Co | Coinbase | — | unscored | — | — | INELIGIBLE | — |
| 218 | Senior Software Engineer, Backend - Platform (Co | Coinbase | — | unscored | — | — | INELIGIBLE | — |
| 219 | Senior Python Engineer, AI | eBay | — | unscored | — | — | INELIGIBLE | — |
| 220 | Software Engineer - AI Agent Platforms | Workato | — | unscored | — | — | INELIGIBLE | — |
| 221 | Software Engineer III (AI/ML) | Guidewire Software | — | unscored | — | — | INELIGIBLE | — |
| 222 | Senior AI Engineer | Teradata | — | unscored | — | — | INELIGIBLE | — |
| 223 | Senior Python Engineer, AI | eBay | — | unscored | — | — | INELIGIBLE | — |
| 224 | Staff Software Engineer – AI | Thomson Reuters | — | unscored | — | — | INELIGIBLE | — |
| 225 | Software Engineer II, AI Agents | Storable | — | unscored | — | — | INELIGIBLE | — |
| 226 | Staff Software Engineer – AI | Thomson Reuters | — | unscored | — | — | INELIGIBLE | — |
| 227 | Staff Software Engineer (AI Agents) | People In AI | — | unscored | — | — | INELIGIBLE | — |
| 228 | Backend Engineer, AI | Rain | — | unscored | — | — | INELIGIBLE | — |
| 229 | Senior Software Engineer — Infra Agent Systems | Together AI | — | unscored | — | — | INELIGIBLE | — |
| 230 | Senior AI Engineer | Teradata | — | unscored | — | — | INELIGIBLE | — |
| 231 | Software Engineer, AI Document Generation | EvenUp | — | unscored | — | — | INELIGIBLE | — |
| 232 | AI Backend Engineer, Artificial Intelligence (AI | TalentHop | — | unscored | — | — | INELIGIBLE | — |
| 233 | senior engineer, AI (Nashville, TN) | Starbucks | — | unscored | — | — | INELIGIBLE | — |
| 234 | Senior AI Engineer | Further | — | unscored | — | — | INELIGIBLE | — |
| 235 | Backend Engineer, LLM Applications - Newton, MA | Motion Recruitment | — | unscored | — | — | INELIGIBLE | — |
| 236 | AI Software Engineer | AVEVA | — | unscored | — | — | INELIGIBLE | — |
| 237 | Senior Backend Engineer  (AI Platform) | AZX | — | unscored | — | — | INELIGIBLE | — |
| 238 | Senior Software Engineer, AI Agent Platform | GEICO | — | unscored | — | — | INELIGIBLE | — |
| 239 | Forward Deployed AI Engineer, Backend - West Pal | Draftwise | — | unscored | — | — | INELIGIBLE | — |
| 240 | AI Systems Developer III | Kforce Inc | — | unscored | — | — | INELIGIBLE | — |
| 241 | Senior AI Engineer, Enterprise | Snowflake | — | unscored | — | — | INELIGIBLE | — |
| 242 | Backend Engineer, AI Engineering: Duo Chat | GitLab | — | unscored | — | — | INELIGIBLE | — |
| 243 | Senior Backend Agentic AI Engineer | Henderson Scott | — | unscored | — | — | INELIGIBLE | — |
| 244 | AI Engineer | Sony Interactive Enterta | — | unscored | — | — | INELIGIBLE | — |
| 245 | Senior Software Engineer, AI Agent Platform | GEICO | — | unscored | — | — | INELIGIBLE | — |
| 246 | AI Engineer | People In AI | — | unscored | — | — | INELIGIBLE | — |
| 247 | AI/ML Engineer | Tata Consultancy Service | — | unscored | — | — | INELIGIBLE | — |
| 248 | Machine Learning Scientist - Natural Language Pr | JPMorganChase | — | unscored | — | — | INELIGIBLE | — |
| 249 | Principal Machine Learning Engineer | Palo Alto Networks | — | unscored | — | — | INELIGIBLE | — |
| 250 | Data Scientist | Elsevier | — | unscored | — | — | INELIGIBLE | — |
| 251 | Gen Al / Agentic Al Engineer | Synechron | — | unscored | — | — | INELIGIBLE | — |
| 252 | Lead AI Engineer | Granite Telecommunicatio | — | unscored | — | — | INELIGIBLE | — |
| 253 | AI Engineer | Netrolynx AI | — | unscored | — | — | INELIGIBLE | — |
| 254 | Applied AI Engineer | MaintainX | — | unscored | — | — | INELIGIBLE | — |
| 255 | Applied AI/ML Lead | JPMorganChase | — | unscored | — | — | INELIGIBLE | — |
| 256 | Sr Data Scientist | Elsevier | — | unscored | — | — | INELIGIBLE | — |
| 264 | NodeJS AI Engineer | Randstad Digital | — | unscored | — | — | INELIGIBLE | — |
| 268 | AI Engineer | MassMutual | — | unscored | — | — | INELIGIBLE | — |
| 271 | Lead Full Stack AI Engineer | Strategic Staffing Solut | — | unscored | — | — | INELIGIBLE | — |
| 273 | AI Engineer 3 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 277 | Sr. Staff AI Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 278 | Sr. Staff AI Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 279 | AI Engineer 5 (MLXT) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 280 | AI Engineer 5 (MLX) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 281 | AI Engineer 4 (MLX) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 283 | AI Engineer 4 (AI Foundations) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 288 | AI Engineer 5 (Gen AI Platform Services) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 289 | AI Engineer 4 (Gen AI Platform Services) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 292 | AI Engineer 4 (AI Foundations, VLM Customization | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 297 | AI Engineer 3 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 298 | AI Engineer 5 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 299 | Staff AI Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 300 | AI Engineer 4 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 301 | Applied AI Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 302 | Associate Principal AI Engineer | Techsara Solutions | — | unscored | — | — | INELIGIBLE | — |
| 304 | Sr. Staff AI Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 305 | AI Engineer 5 (MLXT) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 306 | AI Engineer 5 (MLX) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 307 | AI Engineer 4 (MLX) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 309 | Federal AI Engineer | M9 Solutions | — | unscored | — | — | INELIGIBLE | — |
| 312 | AI Engineer 5 (AI Foundations) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 313 | AI Engineer 3 (AI Foundations) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 314 | AI Engineer 4 (AI Foundations) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 318 | Generative AI Engineer | Apex Systems | — | unscored | — | — | INELIGIBLE | — |
| 319 | Sr AWS Cloud Generative AI Engineer | LTM | — | unscored | — | — | INELIGIBLE | — |
| 321 | Lead Generative AI / Agentic AI Engineer | PTR Global | — | unscored | — | — | INELIGIBLE | — |
| 322 | Lead Generative AI / Agentic AI Engineer | PTR Global | — | unscored | — | — | INELIGIBLE | — |
| 323 | Generative AI Engineer | Apex Systems | — | unscored | — | — | INELIGIBLE | — |
| 324 | Lead Generative AI / Agentic AI Engineer | PTR Global | — | unscored | — | — | INELIGIBLE | — |
| 325 | Generative Ai Engineer - Minneapolis, Mn | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 328 | Generative AI Engineer | Apex Systems | — | unscored | — | — | INELIGIBLE | — |
| 329 | Generative AI Engineer | Judge Group, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 332 | Generative AI Engineer | Whiztek Corp | — | unscored | — | — | INELIGIBLE | — |
| 333 | Generative AI Software Developer/Engineer | Infoweb Systems, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 334 | AI / ML & Generative AI Engineer | INSPYR Solutions | — | unscored | — | — | INELIGIBLE | — |
| 335 | Senior Generative AI Engineer (7-10+ yearsâ ex | Promantus, Inc | — | unscored | — | — | INELIGIBLE | — |
| 337 | Generative AI Engineer | Equifax | — | unscored | — | — | INELIGIBLE | — |
| 338 | Senior Generative AI Engineer - Vice President | Citi | — | unscored | — | — | INELIGIBLE | — |
| 339 | Senior Generative AI Engineer | Citi | — | unscored | — | — | INELIGIBLE | — |
| 340 | Generative AI Engineer / QA Engineer | Equifax | — | unscored | — | — | INELIGIBLE | — |
| 341 | Lead AI Engineer - Agentic & Generative AI | Bravo Technical Resource | — | unscored | — | — | INELIGIBLE | — |
| 342 | Generative AI Software Engineer - Cedar Rapids,  | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 343 | Generative Ai Software Engineer - Cedar Rapids,  | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 344 | Lead AI Engineer - Generative AI & Agentic Syste | State Street Corporation | — | unscored | — | — | INELIGIBLE | — |
| 346 | Senior AI Engineer (Generative AI & Intelligent  | Arkhya Tech | — | unscored | — | — | INELIGIBLE | — |
| 347 | Senior AWS Generative AI Solution Engineer | Leidos | — | unscored | — | — | INELIGIBLE | — |
| 348 | Senior Generative AI Python Engineer | EPAM Systems | — | unscored | — | — | INELIGIBLE | — |
| 349 | Generative AI/LLM Engineer | Public Storage, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 350 | Generative AI, Backend Engineer | Morgan Stanley | — | unscored | — | — | INELIGIBLE | — |
| 351 | Lead Software Engineer  AI / Agentic AI Engineer | Lumen Solutions Group In | — | unscored | — | — | INELIGIBLE | — |
| 352 | Senior/Principal Local LLM & Generative AI Platf | Parallel Wireless | — | unscored | — | — | INELIGIBLE | — |
| 353 | Generative AI Developer | System One | — | unscored | — | — | INELIGIBLE | — |
| 355 | AI / ML Engineer - Hourly Contract | Stevens | — | unscored | — | — | INELIGIBLE | — |
| 356 | Senior Software Engineer   Generative AI Innovat | BCforward | — | unscored | — | — | INELIGIBLE | — |
| 357 | RPA Technical Architect â (UiPath, AWS & Gener | Thunderhawk Technology P | — | unscored | — | — | INELIGIBLE | — |
| 360 | Generative AI Developer | Apex Systems | — | unscored | — | — | INELIGIBLE | — |
| 362 | Software engineer, generative AI | Writer | — | unscored | — | — | INELIGIBLE | — |
| 363 | Senior Generative AI Developer | Citi | — | unscored | — | — | INELIGIBLE | — |
| 364 | Lead Generative AI Developer | Citi | — | unscored | — | — | INELIGIBLE | — |
| 365 | Lead Generative AI Developer | Citi | — | unscored | — | — | INELIGIBLE | — |
| 366 | Generative AI Full Stack Developer | Hexaware Technologies, I | — | unscored | — | — | INELIGIBLE | — |
| 367 | Senior Software Engineer - Generative AI Innovat | Apex Systems | — | unscored | — | — | INELIGIBLE | — |
| 368 | Senior Backend Engineer - Generative AI Platform | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 369 | VP - Distinguished Engineer of Generative AI Eng | Slate Auto | — | unscored | — | — | INELIGIBLE | — |
| 370 | Software engineer 1 - AI/ML Engineer (Generative | U.S. Bank | — | unscored | — | — | INELIGIBLE | — |
| 371 | Full Stack Developer with Generative AI | Hexaware Technologies, I | — | unscored | — | — | INELIGIBLE | — |
| 373 | Senior Generative AI (GenAI) Architect with Goog | TekShapers | — | unscored | — | — | INELIGIBLE | — |
| 374 | AI Architect/AI Engineer - Generative & Agentic  | Cencora | — | unscored | — | — | INELIGIBLE | — |
| 375 | Software Development Engineer, Generative AI, An | Annapurna Labs (U.S.) In | — | unscored | — | — | INELIGIBLE | — |
| 376 | Army VANTAGE LLM Engineer | Noblis | — | unscored | — | — | INELIGIBLE | — |
| 380 | LLM Application Engineer | Software Guidance & Assi | — | unscored | — | — | INELIGIBLE | — |
| 381 | LLM Engineer | The Brixton Group | — | unscored | — | — | INELIGIBLE | — |
| 382 | AI Founding Engineer (LLM and Shipping Agents) | Avacend, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 383 | Senior AI/LLM Engineer | Infinite Solutions Inc. | — | unscored | — | — | INELIGIBLE | — |
| 384 | Senior AI/LLM Engineer | Censys | — | unscored | — | — | INELIGIBLE | — |
| 385 | AI Security & LLM Engineer | AnaVation LLC | — | unscored | — | — | INELIGIBLE | — |
| 386 | AI / Machine Learning / Large Language Model Eng | Orion Consortium | — | unscored | — | — | INELIGIBLE | — |
| 387 | Senior Research Engineer, LLM Training & Post-Tr | Lightning AI | — | unscored | — | — | INELIGIBLE | — |
| 388 | Senior LLM Ops Engineer | CINC Systems | — | unscored | — | — | INELIGIBLE | — |
| 389 | LLM Ops Engineer | Litera | — | unscored | — | — | INELIGIBLE | — |
| 390 | LLM Post-Training Engineer Graduate (Research &  | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 391 | LLM Post-training Engineer Graduate (Research &  | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 392 | Principal AI/ML Engineer (Large Language Model) | CACI International, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 393 | Senior AI / ML Engineer (LLMs) | EvolutionIQ | — | unscored | — | — | INELIGIBLE | — |
| 394 | Machine Learning Software Engineer (LLM & Agenti | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 395 | Applied AI / LLM Solutions Engineer | Tachyon Technologies | — | unscored | — | — | INELIGIBLE | — |
| 396 | Software Engineer (LLM) | Visionist | — | unscored | — | — | INELIGIBLE | — |
| 397 | Principal Software Engineer - LLM Optimization | JPMorgan Chase & Co. | — | unscored | — | — | INELIGIBLE | — |
| 398 | Senior and/or Principal Software Engineer- LLM S | Microsoft Corporation | — | unscored | — | — | INELIGIBLE | — |
| 399 | Principal SW Engineer - LLM Serving (Cloud AI) | J VERS LLC | — | unscored | — | — | INELIGIBLE | — |
| 400 | Staff Machine Learning Engineer - LLM Quantizati | XPENG | — | unscored | — | — | INELIGIBLE | — |
| 401 | Senior Machine Learning Engineer - LLM Quantizat | XPENG | — | unscored | — | — | INELIGIBLE | — |
| 402 | AIML - Senior Machine Learning Research Engineer | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 403 | Senior/Staff System Research Engineer - LLM Infe | Snowflake Inc. | — | unscored | — | — | INELIGIBLE | — |
| 404 | Senior Backend Java Engineer with AI / LLM | Randstad Digital | — | unscored | — | — | INELIGIBLE | — |
| 406 | Machine Learning Engineer - AI Evaluation & LLM  | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 407 | Senior Machine Learning Engineer - Boston - Rag/ | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 408 | AI Infrastructure Engineer - Recommendation & LL | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 409 | AI Engineer - Python/Kotlin/LLMs - Waltham | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 410 | AI Engineer 4 (LLM Gateway, FM Hosting) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 411 | AI Engineer 5 (LLM Gateway, FM Hosting) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 412 | AI Engineer 5 (FM Hosting, LLM Inference) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 414 | AI Engineer 4 (AI Foundations, LLM Customization | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 415 | AI Infra Engineer Graduate (Recommendation & LLM | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 416 | AI Infra Engineer Graduate (Recommendation & LLM | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 418 | Senior Software Engineer, Machine Learning (LLM  | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 419 | AI Engineer 4 (AI Foundations, LLM Core and Agen | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 420 | AI Engineer 4 (AI Foundations, LLM Core and Agen | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 422 | AI Engineer 5 ((AI Foundations, LLM Core and Age | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 423 | AI Engineer 5 ((AI Foundations, LLM Core and Age | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 424 | AI Engineer 5 (AI Foundations, LLM Core and Agen | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 426 | AI Engineer 5 (AI Foundations: LLM Customization | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 427 | AI Engineer 4 (AI Foundations: LLM Customization | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 428 | Senior Machine Learning Engineer/ RAG | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 430 | Azure GenAI Engineer â RAG | Tek Labs Inc | — | unscored | — | — | INELIGIBLE | — |
| 431 | AI Data Integration Engineer - RAG Platform | Computer Task Group, Inc | — | unscored | — | — | INELIGIBLE | — |
| 432 | AI Architect & RAG Data Science Engineer | Modern Technology Soluti | — | unscored | — | — | INELIGIBLE | — |
| 434 | Software Engineer, Search and RAG Applications | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 435 | Senior Machine Learning Engineer - Providence -  | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 436 | Senior Machine Learning Engineer - Worcester - L | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 438 | Senior Machine Learning Engineer - Nashua, Nh -  | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 440 | Senior Machine Learning Engineer - Charlotte, Nc | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 442 | Google Cloud Platform Data Engineer - AI & RAG S | Infomatics Corp | — | unscored | — | — | INELIGIBLE | — |
| 443 | AI Engineer--Remote--W2 Role | CogniSoft Technologies | — | unscored | — | — | INELIGIBLE | — |
| 445 | AI Product Manager - RAG & AI Agents (W2 Only) | Miracle Software Systems | — | unscored | — | — | INELIGIBLE | — |
| 448 | RAG Engineer | MCI | — | unscored | — | — | INELIGIBLE | — |
| 449 | Senior RAG Engineer | MCI | — | unscored | — | — | INELIGIBLE | — |
| 451 | Software Engineer - AI (Level determined by expe | Synack | — | unscored | — | — | INELIGIBLE | — |
| 452 | Google Cloud Platform AI Architect / Diamond Lay | Keylent | — | unscored | — | — | INELIGIBLE | — |
| 453 | Database Engineer - RAG Platform Developer | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 454 | Generative AI Applications Engineer (Agents & RA | Accenture LLP | — | unscored | — | — | INELIGIBLE | — |
| 458 | Senior Data/Machine Learning Engineer | The Coca-Cola Company | — | unscored | — | — | INELIGIBLE | — |
| 459 | Sr Big Data/Machine Learning Engineer | Randstad Digital | — | unscored | — | — | INELIGIBLE | — |
| 461 | Machine Learning Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 463 | Principal Machine Learning Engineer (Prisma AIRS | PaloAlto Networks | — | unscored | — | — | INELIGIBLE | — |
| 464 | Senior/Staff ML Engineer, ML Acceleration and Pe | Rivian | — | unscored | — | — | INELIGIBLE | — |
| 465 | Staff ML Engineer, Perception Scene Understandin | Rivian | — | unscored | — | — | INELIGIBLE | — |
| 467 | Machine Learning Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 472 | Staff Machine Learning Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 473 | Machine Learning Engineer 5 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 474 | Machine Learning Engineer 5 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 475 | Machine Learning Engineer 4 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 476 | Machine Learning Engineer 4 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 477 | Machine Learning Engineer 4 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 478 | Machine Learning Engineer 5 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 479 | Senior Staff Machine Learning Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 480 | Senior Staff Machine Learning Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 482 | Machine Learning Engineer 4 (IC) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 483 | Sr. Lead Machine Learning Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 484 | Machine Learning Engineer 5 (IC) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 485 | Machine Learning Engineer 5 (IC) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 488 | Senior Data/Machine Learning Engineer | The Coca-Cola Company | — | unscored | — | — | INELIGIBLE | — |
| 489 | Machine Learning Engineer II | The Coca-Cola Company | — | unscored | — | — | INELIGIBLE | — |
| 491 | Machine Learning Engineer 5 (Senior Manager, IC) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 494 | Machine Learning Engineer 5 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 495 | Machine Learning Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 497 | Machine Learning Engineer 4 | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 498 | Machine Learning Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 499 | Machine Learning Engineer 4 (Python, AWS, SQL, G | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 500 | Machine Learning Engineer 4 (Python, AWS, SQL, G | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 501 | Machine Learning Engineer 4 (Python, AWS, SQL, G | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 502 | Staff ML Engineer, Perception: Auto-labeling | Rivian | — | unscored | — | — | INELIGIBLE | — |
| 503 | Senior Manager, Machine Learning Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 504 | Machine Learning Engineer 4 (IC) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 505 | Machine Learning Engineer 5 (IC) | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 506 | AI and ML Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 507 | Sr. Staff ML Engineer, Model Pre-training, Auton | Rivian | — | unscored | — | — | INELIGIBLE | — |
| 512 | Data Solutions AI Application Developer II - Wor | CareSource | — | unscored | — | — | INELIGIBLE | — |
| 513 | Web Application Developer Agentic AI with Strong | Vinsari LLC | — | unscored | — | — | INELIGIBLE | — |
| 514 | Web Application Developer â Agentic AI | Highbrow | — | unscored | — | — | INELIGIBLE | — |
| 515 | Full Stack Engineer (AI-Enabled Application Engi | NTT DATA Americas, Inc | — | unscored | — | — | INELIGIBLE | — |
| 516 | Web Application Developer Agentic AI | CIS Technologies Inc. | — | unscored | — | — | INELIGIBLE | — |
| 518 | Agentic AI Developer | Dexian DISYS | — | unscored | — | — | INELIGIBLE | — |
| 519 | AI Application Security Engineer | NXP Semiconductors N.V. | — | unscored | — | — | INELIGIBLE | — |
| 520 | Agentic AI Developer | Apolis | — | unscored | — | — | INELIGIBLE | — |
| 522 | Sr. Application Developer (AI) - Milwaukee, WI | | Software Guidance & Assi | — | unscored | — | — | INELIGIBLE | — |
| 523 | AI Application Engineer | Software Guidance & Assi | — | unscored | — | — | INELIGIBLE | — |
| 525 | AI Application Engineer | Generac Power Systems In | — | unscored | — | — | INELIGIBLE | — |
| 526 | Senior AI Application Engineer | Veterans EZ Info, Inc | — | unscored | — | — | INELIGIBLE | — |
| 527 | AI Application Engineer | BigBear.ai | — | unscored | — | — | INELIGIBLE | — |
| 528 | Oracle AI Application Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 529 | Sr. AI Application Engineer (remote) | Software Guidance & Assi | — | unscored | — | — | INELIGIBLE | — |
| 530 | Mid-Level AI Engineer - Application Security & A | HAYS | — | unscored | — | — | INELIGIBLE | — |
| 531 | Senior AI Application Engineer (.NET) | Nasdaq | — | unscored | — | — | INELIGIBLE | — |
| 532 | Senior AI Application Development Engineer | Qualcomm Technologies | — | unscored | — | — | INELIGIBLE | — |
| 533 | Director, AI Application Engineering | Marriott International | — | unscored | — | — | INELIGIBLE | — |
| 534 | Principal AI Application Operations Engineer | GE Vernova | — | unscored | — | — | INELIGIBLE | — |
| 535 | Senior AI Application Engineer (.NET) | Nasdaq | — | unscored | — | — | INELIGIBLE | — |
| 536 | AI Engineer: DevOps & Application Support | GE Appliances | — | unscored | — | — | INELIGIBLE | — |
| 537 | AI Developer | Brooksource | — | unscored | — | — | INELIGIBLE | — |
| 538 | Lead Full Stack Software Engineer (New Applicati | Jobot | — | unscored | — | — | INELIGIBLE | — |
| 539 | Lead Full Stack Software Engineer (New Applicati | Jobot | — | unscored | — | — | INELIGIBLE | — |
| 540 | Lead Full Stack Software Engineer (New Applicati | Jobot | — | unscored | — | — | INELIGIBLE | — |
| 541 | Lead Software Engineer - AI Application | JPMorgan Chase & Co. | — | unscored | — | — | INELIGIBLE | — |
| 542 | Junior AI Engineer - Application Security & AI S | HAYS | — | unscored | — | — | INELIGIBLE | — |
| 543 | Lead AI Application Security Engineer | GXO Logistics | — | unscored | — | — | INELIGIBLE | — |
| 544 | GenAI Application Developer | MetaRPO | — | unscored | — | — | INELIGIBLE | — |
| 545 | AI Software Engineer, App Intelligence | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 547 | Senior AI Software Engineer, App Intelligence | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 548 | Applications Developer II AI (REMOTE) | Cordis | — | unscored | — | — | INELIGIBLE | — |
| 550 | Senior Software Engineer/Developer AI (HUD) | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 551 | Lead Application Security - DevSecOps & AI-Drive | East West Bank | — | unscored | — | — | INELIGIBLE | — |
| 552 | .NET  AI Developer | cyberThink, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 553 | Application Software Engineer, Applied AI | SpaceX | — | unscored | — | — | INELIGIBLE | — |
| 554 | Application Software Engineer, Applied AI | SpaceX | — | unscored | — | — | INELIGIBLE | — |
| 555 | Application Software Engineer, Applied AI | SpaceX | — | unscored | — | — | INELIGIBLE | — |
| 556 | Application Software Engineer, Applied AI | SpaceX | — | unscored | — | — | INELIGIBLE | — |
| 557 | Application Software Engineer, Applied AI | SpaceX | — | unscored | — | — | INELIGIBLE | — |
| 558 | Application Software Engineer, Applied AI | SpaceX | — | unscored | — | — | INELIGIBLE | — |
| 559 | Application Software Engineer, Applied AI | SpaceX | — | unscored | — | — | INELIGIBLE | — |
| 561 | Principal Engineer - Application Security (AI se | Target Corporation | — | unscored | — | — | INELIGIBLE | — |
| 563 | Principal Application & AI Security Engineer | Det Norske Veritas | — | unscored | — | — | INELIGIBLE | — |
| 564 | International Graduate Program - System Applicat | Infineon Technologies | — | unscored | — | — | INELIGIBLE | — |
| 565 | Full Stack Engineer (AI-Enabled Application Engi | NTT DATA, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 566 | AI Application Security Architect | ACV | — | unscored | — | — | INELIGIBLE | — |
| 567 | Agentic AI, Cloud Transformation & Application M | UnivEdge Consulting LLC | — | unscored | — | — | INELIGIBLE | — |
| 568 | Principal Application Architect - Adobe Experien | Novo Nordisk Inc | — | unscored | — | — | INELIGIBLE | — |
| 569 | Need Python AI Engineer -Fulltime -Irving ,TX (I | Newt Global | — | unscored | — | — | INELIGIBLE | — |
| 571 | Senior Python AI Engineer - Only W2 | Info Dinamica Inc | — | unscored | — | — | INELIGIBLE | — |
| 573 | Lead Python AI Engineer, Agentic Systems | Citi | — | unscored | — | — | INELIGIBLE | — |
| 574 | Senior Python-AI Engineer Agentic Systems | Citi | — | unscored | — | — | INELIGIBLE | — |
| 576 | Senior AI Python Solutions Engineer | select minds | — | unscored | — | — | INELIGIBLE | — |
| 577 | AI/Python Engineer with Azure | Trinite Consulting Group | — | unscored | — | — | INELIGIBLE | — |
| 579 | Sr. AI/Python Engineer | Citi | — | unscored | — | — | INELIGIBLE | — |
| 580 | Senior Full Stack Python Engineer - AI Applicati | Consumer Reports | — | unscored | — | — | INELIGIBLE | — |
| 581 | Python QA Automation Engineer (AI Experience req | AgreeYa Solutions | — | unscored | — | — | INELIGIBLE | — |
| 583 | Python/React/Full Stack Engineer (AI & Data Plat | NTT DATA Americas, Inc | — | unscored | — | — | INELIGIBLE | — |
| 584 | Backend Software Engineer - Python & Pipeline Or | Bayside Solutions | — | unscored | — | — | INELIGIBLE | — |
| 585 | Senior Python AI Developer | Prudent Technologies and | — | unscored | — | — | INELIGIBLE | — |
| 586 | Python/Gen AI Developer | Mitchell Martin, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 588 | AI Developer with Python | MphasiS Corporation USA | — | unscored | — | — | INELIGIBLE | — |
| 592 | Python AI Full Stack | Capgemini America, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 593 | Python AI Full Stack | Capgemini America, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 594 | Remote - Senior Python Engineer with AI | Resource Informatics Gro | — | unscored | — | — | INELIGIBLE | — |
| 596 | Lead Data Engineer (AWS, Snowflake, Python, AI/L | Finoit Inc. | — | unscored | — | — | INELIGIBLE | — |
| 597 | Database Engineer with Python for AI | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 598 | Senior AI Engineer/ Node.js, Python, Typescript | EPAM Systems | — | unscored | — | — | INELIGIBLE | — |
| 600 | AI Engineer- Python and Databricks- remote | Calance | — | unscored | — | — | INELIGIBLE | — |
| 601 | Jr. Python AI/ML Developer | Ultimo Software Solution | — | unscored | — | — | INELIGIBLE | — |
| 602 | Senior Software Engineer / React / Python / AI I | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 603 | Senior AI/ML Engineer (Python) | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 604 | Senior AI / ML Engineer (Python) | ITTConnect | — | unscored | — | — | INELIGIBLE | — |
| 605 | Software Engineer 3 - (Python, AI, LLM) | Akina, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 606 | Sr Lead Software Engineer - Java, Python, AI/ML | JPMorgan Chase & Co. | — | unscored | — | — | INELIGIBLE | — |
| 607 | Senior Software Engineer (Python / AI Insurance  | EvolutionIQ | — | unscored | — | — | INELIGIBLE | — |
| 609 | Lead Software Engineer - Java, Python, AI/LLM | JPMorgan Chase & Co. | — | unscored | — | — | INELIGIBLE | — |
| 611 | Lead Software Engineer- Python AI | JPMorgan Chase & Co. | — | unscored | — | — | INELIGIBLE | — |
| 612 | Software Engineer 3 - (Python, AI, NLP) | Akina, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 614 | Software Engineer 3 - (Python, AI/ML, Kafka) | Akina, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 617 | Senior Software Engineer 3 - (AI, Python, Kubern | Akina, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 618 | Lead Software Engineer - Agentic AI, Java/Python | JPMorgan Chase & Co. | — | unscored | — | — | INELIGIBLE | — |
| 619 | Back End Software Engineer Python/SDLC/Ai - Walt | Motion Recruitment Partn | — | unscored | — | — | INELIGIBLE | — |
| 621 | Senior Software Engineer (Python/React & Healthc | Jobot | — | unscored | — | — | INELIGIBLE | — |
| 622 | Associate Data Engineer (Python / AI Insurance S | EvolutionIQ | — | unscored | — | — | INELIGIBLE | — |
| 623 | Lead Software Engineer - Python, Full Stack / AI | JPMorgan Chase & Co. | — | unscored | — | — | INELIGIBLE | — |
| 625 | Agentic AI Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 626 | Agentic AI Engineer & Technical Manager | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 628 | Agentic AI Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 629 | Agentic AI Engineer | Oscar Technology | — | unscored | — | — | INELIGIBLE | — |
| 630 | Lead Enterprise Agentic AI Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 632 | Enterprise Agentic AI Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 633 | Agentic AI Engineer - Software Engineer | Capgemini America, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 635 | Agentic AI Engineer (6+ years) | Nityo Infotech Corporati | — | unscored | — | — | INELIGIBLE | — |
| 637 | Agentic AI Engineer - Nashville, TN, Kansas  Cit | TechniPros, LLC | — | unscored | — | — | INELIGIBLE | — |
| 638 | Lead / Principal Agentic AI Engineer | Constel Global | — | unscored | — | — | INELIGIBLE | — |
| 639 | Senior Software Engineer - Agentic AI Engineer | Capgemini America, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 640 | Agentic AI Engineer | Booz Allen Hamilton | — | unscored | — | — | INELIGIBLE | — |
| 641 | Sr. Agentic AI Engineer (Agent SDK & Developer E | Coforge | — | unscored | — | — | INELIGIBLE | — |
| 647 | Agentic AI Engineer (Agent SDK & Developer Enabl | TekShapers | — | unscored | — | — | INELIGIBLE | — |
| 649 | Agentic AI Engineer | Smart  Synergies | — | unscored | — | — | INELIGIBLE | — |
| 650 | Agentic AI Engineer | International Solutions  | — | unscored | — | — | INELIGIBLE | — |
| 651 | Sr Agentic AI Engineer | Tixy Services LLC | — | unscored | — | — | INELIGIBLE | — |
| 652 | GenAI and Agentic AI Engineer | Envision LLC. | — | unscored | — | — | INELIGIBLE | — |
| 653 | AI prompt Engineer | TECHAGI SOLUTIONS LLC | — | unscored | — | — | INELIGIBLE | — |
| 656 | Agentic AI Engineer Lead | Carrier Corporation | — | unscored | — | — | INELIGIBLE | — |
| 658 | Agentic AI Engineer, Expert | Pacific Gas & Electric | — | unscored | — | — | INELIGIBLE | — |
| 660 | Agentic AI Engineer | VAE Inc | — | unscored | — | — | INELIGIBLE | — |
| 661 | Senior Analyst, Agentic AI Engineer | Dell Technologies | — | unscored | — | — | INELIGIBLE | — |
| 662 | Lead Agentic AI Engineer | Citi | — | unscored | — | — | INELIGIBLE | — |
| 663 | Agentic AI Engineer (AVP) | Citi | — | unscored | — | — | INELIGIBLE | — |
| 664 | Lead Agentic AI Engineer | Royal Bank of Canada | — | unscored | — | — | INELIGIBLE | — |
| 665 | Predictive & Agentic AI Engineer | Bright MLS | — | unscored | — | — | INELIGIBLE | — |
| 667 | Agentic AI Engineer - Global Infrastructure | American Express | — | unscored | — | — | INELIGIBLE | — |
| 668 | Senior Agentic AI Engineer (VP) | Citi | — | unscored | — | — | INELIGIBLE | — |
| 669 | Lead Agentic AI Engineer - Vice President | Citi | — | unscored | — | — | INELIGIBLE | — |
| 670 | Agentic AI Engineer | Elastic | — | unscored | — | — | INELIGIBLE | — |
| 671 | Lead Agentic AI Engineer | EchoStar Corporation | — | unscored | — | — | INELIGIBLE | — |
| 672 | Agentic AI Engineer (T02) | Vectrus Corporate | — | unscored | — | — | INELIGIBLE | — |
| 673 | Senior Agentic AI Engineer | EchoStar Corporation | — | unscored | — | — | INELIGIBLE | — |
| 674 | Senior Agentic AI Engineer II - Global Infrastru | American Express | — | unscored | — | — | INELIGIBLE | — |
| 675 | Agentic AI Engineer | NTT DATA, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 677 | AI Backend Engineer, Artificial Intelligence (AI | Next Step Systems | — | unscored | — | — | INELIGIBLE | — |
| 679 | Senior AI Platform Backend Engineer | Strategic Staffing Solut | — | unscored | — | — | INELIGIBLE | — |
| 681 | Backend AI Developer | Advanced Tech Placement | — | unscored | — | — | INELIGIBLE | — |
| 682 | AI Engineer | Aditi Consulting | — | unscored | — | — | INELIGIBLE | — |
| 683 | Backend & AI/ML Engineer | NTT DATA, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 684 | Backend & AI Platform Engineer | Danaher Corporation | — | unscored | — | — | INELIGIBLE | — |
| 685 | Senior Backend Software Engineer, AI Observabili | LangChain, Inc | — | unscored | — | — | INELIGIBLE | — |
| 686 | AI Backend Engineer, Artificial Intelligence (AI | Parallel Partners | — | unscored | — | — | INELIGIBLE | — |
| 687 | AI Engineer, Back End | OSI Engineering, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 688 | Backend Engineer (Agentic AI) | ITBMS Inc. | — | unscored | — | — | INELIGIBLE | — |
| 689 | Backend Engineer _ AI Gateway- Bilingual (Korean | WOONGJIN, INC | — | unscored | — | — | INELIGIBLE | — |
| 690 | Senior Engineer, Backend & AI Systems | Software Guidance & Assi | — | unscored | — | — | INELIGIBLE | — |
| 691 | Senior Back End Engineer, Hazel AI | Altruist | — | unscored | — | — | INELIGIBLE | — |
| 692 | Senior Backend Engineer, Vector AI | Unity Microelectronics I | — | unscored | — | — | INELIGIBLE | — |
| 694 | Senior Software Engineer, Backend Full Stack - F | Rippling | — | unscored | — | — | INELIGIBLE | — |
| 695 | Senior Backend Engineer II, AI Native, Vertical  | Life360 | — | unscored | — | — | INELIGIBLE | — |
| 697 | Principal Engineer, Applied AI (Fullstack/Backen | Hims and Hers Health, In | — | unscored | — | — | INELIGIBLE | — |
| 699 | Software Engineer, Backend (Agentic AI) | Sift Science, Inc | — | unscored | — | — | INELIGIBLE | — |
| 700 | Software Engineer, Backend (Agentic AI) | Sift Science, Inc | — | unscored | — | — | INELIGIBLE | — |
| 701 | Backend Software Engineer Graduate (Emerging Pro | TikTok | — | unscored | — | — | INELIGIBLE | — |
| 703 | Java Backend Developer with SQL and Strong AI | NetStrive Consulting | — | unscored | — | — | INELIGIBLE | — |
| 704 | Agentforce AI & Cloud Backend Engineering - Atla | Digital Technology Solut | — | unscored | — | — | INELIGIBLE | — |
| 705 | AI Engineer | Randstad Digital | — | unscored | — | — | INELIGIBLE | — |
| 706 | Senior Software Engineer, Backend (Agentic AI) | Sift Science, Inc | — | unscored | — | — | INELIGIBLE | — |
| 707 | Senior Software Engineer, Backend (Agentic AI) | Sift Science, Inc | — | unscored | — | — | INELIGIBLE | — |
| 709 | AI/ML Engineer | Randstad Digital | — | unscored | — | — | INELIGIBLE | — |
| 710 | Web Frontend Engineer, Artificial Intelligence ( | Next Step Systems | — | unscored | — | — | INELIGIBLE | — |
| 711 | AI Engineer | 9th Way Insignia | — | unscored | — | — | INELIGIBLE | — |
| 713 | Backend Engineer | Procom | — | unscored | — | — | INELIGIBLE | — |
| 714 | AI Engineer | Innova Solutions, Inc | — | unscored | — | — | INELIGIBLE | — |
| 715 | Senior Backend Engineer (SF) | NxT Level | — | unscored | — | — | INELIGIBLE | — |
| 716 | Engineer, Backend Integration & AI Transformatio | LifePoint Health | — | unscored | — | — | INELIGIBLE | — |
| 717 | Senior AI/ML Security Engineer | SilverSearch, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 719 | Principal Software Engineer (AI Software Integra | PaloAlto Networks | — | unscored | — | — | INELIGIBLE | — |
| 720 | Sr Staff Software Engineer (AI SW Integration -  | PaloAlto Networks | — | unscored | — | — | INELIGIBLE | — |
| 721 | Senior Software Engineer, AI (New York) | Fitch Group | — | unscored | — | — | INELIGIBLE | — |
| 722 | Senior Gen AI Software Engineer | Fitch Group | — | unscored | — | — | INELIGIBLE | — |
| 723 | Backend Software Engineer - Camera & Photos Tool | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 725 | Machine Learning Research Engineer, NLP, Input E | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 727 | Senior AI/ML Engineer | Techsara Solutions | — | unscored | — | — | INELIGIBLE | — |
| 728 | NLP Engineer - Clearance Required | BTI360 | — | unscored | — | — | INELIGIBLE | — |
| 729 | Senior Software Developer (NLP) | Parsons Services Company | — | unscored | — | — | INELIGIBLE | — |
| 732 | AI/ Automation Engineer | Eclaro | — | unscored | — | — | INELIGIBLE | — |
| 734 | AI/ML Engineer | Intraedge | — | unscored | — | — | INELIGIBLE | — |
| 735 | AI Data Scientist | System One | — | unscored | — | — | INELIGIBLE | — |
| 736 | Senior Machine Learning Engineer, Natural Langua | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 737 | Agentic AI Architect | Purple Hires | — | unscored | — | — | INELIGIBLE | — |
| 738 | AI Testing Engineer - Remote | Techaffinity Consulting | — | unscored | — | — | INELIGIBLE | — |
| 739 | AI/ML - Machine Learning Engineer, Text Language | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 740 | Machine Learning Engineer, Ranking & Retrieval | ClickUp | — | unscored | — | — | INELIGIBLE | — |
| 741 | Machine Learning Engineer, Local Search & Market | NewsBreak | — | unscored | — | — | INELIGIBLE | — |
| 742 | AI-MLFull Stack Engineer | Government Systems Techn | — | unscored | — | — | INELIGIBLE | — |
| 743 | Senior Machine Learning Engineer | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 744 | Staff Machine Learning Engineer I, Search Retrie | Etsy, Inc | — | unscored | — | — | INELIGIBLE | — |
| 745 | Staff Machine Learning Engineer - Search | Warner Bros. Discovery | — | unscored | — | — | INELIGIBLE | — |
| 746 | Machine Learning Engineer | DPP Tech, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 747 | Machine Learning Engineer | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 748 | Lead AI Engineer | EPAM Systems | — | unscored | — | — | INELIGIBLE | — |
| 749 | Senior Data Scientist | Fiekon | — | unscored | — | — | INELIGIBLE | — |
| 750 | Data Scientist (Remote) | Koniag, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 752 | Data Scientist (NLP and GenAI Specialist) | Morgan Stanley | — | unscored | — | — | INELIGIBLE | — |
| 753 | AI engineer | Writer | — | unscored | — | — | INELIGIBLE | — |
| 754 | Senior Machine Learning Engineer | Adobe Systems | — | unscored | — | — | INELIGIBLE | — |
| 755 | Senior Machine Learning Engineer | EvenUp Inc | — | unscored | — | — | INELIGIBLE | — |
| 756 | Senior Machine Learning Engineer | HP Development Company,  | — | unscored | — | — | INELIGIBLE | — |
| 757 | Machine Learning Engineer | Pivotal Solutions | — | unscored | — | — | INELIGIBLE | — |
| 758 | Sr. Machine Learning Engineer - Hybrid schedule  | Calance | — | unscored | — | — | INELIGIBLE | — |
| 759 | AI Engineer | CACI International, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 761 | AI Engineer | Apex Systems | — | unscored | — | — | INELIGIBLE | — |
| 762 | Machine Learning Engineer II | S&P Consultants | — | unscored | — | — | INELIGIBLE | — |
| 763 | Machine Learning Engineer, Natural Language Unde | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 764 | Staff/Senior Machine Learning Engineer, Search & | Apple, Inc. | — | unscored | — | — | INELIGIBLE | — |
| 765 | Senior AI/ML Engineer | Ignite IT | — | unscored | — | — | INELIGIBLE | — |
| 767 | Data Scientist - Senior Job#822 | Allen Integrated Solutio | — | unscored | — | — | INELIGIBLE | — |
| 769 | Applied AI & Backend Engineer (m/w/d) | odacova UG (haftungsbesc | — | unscored | — | — | INELIGIBLE | — |
| 770 | Senior Software Engineer (Typescript), AI Client | gitlab | — | unscored | — | — | REVIEW_REQUIRED | — |
| 771 | Intermediate-Senior Backend Engineer (Ruby), Pla | gitlab | — | unscored | — | — | REVIEW_REQUIRED | — |
| 772 | Backend Engineer (Ruby), AI Engineering: Agent F | gitlab | — | unscored | — | — | REVIEW_REQUIRED | — |
| 773 | Senior Software Engineer AI & Automation (d/m/w) | Listan Gmbh | — | unscored | — | — | INELIGIBLE | — |
| 774 | AI Solutions Engineer | Cascination Ag | — | unscored | — | — | INELIGIBLE | — |
| 775 | AI Systems Engineer | Sonarsource | — | unscored | — | — | INELIGIBLE | — |
| 776 | AI-Native Static Ad Designer | Uplane | — | unscored | — | — | REVIEW_REQUIRED | — |
| 777 | AI-Native Landing Page Designer | Uplane | — | unscored | — | — | REVIEW_REQUIRED | — |
| 778 | AI-Native Video Producer | Uplane | — | unscored | — | — | REVIEW_REQUIRED | — |
| 779 | Senior AI Engineer / Technical Consultant | Artefact | — | unscored | — | — | INELIGIBLE | — |
| 780 | Senior AI Engineer / Technical Consultant | Artefactlinkedin | — | unscored | — | — | INELIGIBLE | — |
| 781 | GenAI/ML Engineer | capco | — | unscored | — | — | REVIEW_REQUIRED | — |
| 782 | Head of Development AI Agent Platform (m/w/d) | Strategy & Transformatio | — | unscored | — | — | INELIGIBLE | — |
| 783 | KI-Spezialist (m/w/d) -  Geförderte Weiterbildun | Mentify Learn GmbH | — | unscored | — | — | INELIGIBLE | — |
| 784 | AI Solutions Engineer (m/w/d) | Tmh | — | unscored | — | — | INELIGIBLE | — |
| 788 | AI Data Scientist | Airtm | — | unscored | — | — | INELIGIBLE | — |
| 794 | Senior Backend Engineer II, AI Native, Vertical  | Life360 | — | unscored | — | — | INELIGIBLE | — |
| 796 | AI Augmented Software Engineer [gn] Data Intelli | Actian | — | unscored | — | — | INELIGIBLE | — |
| 799 | AI Science Writer, Nebius Academy (Contract) | Nebius | — | unscored | — | — | INELIGIBLE | — |
| 801 | AI agent engineer | Sticker Mule | — | unscored | — | — | INELIGIBLE | — |
| 802 | AI Trainer Image QA Evaluator | iMerit Technology | — | unscored | — | — | INELIGIBLE | — |
| 803 | AI Response Analyst | iMerit Technology | — | unscored | — | — | INELIGIBLE | — |
| 804 | AI Engineer Data APIs | Benzinga | — | unscored | — | — | INELIGIBLE | — |
| 805 | Senior Backend Engineer Build AI Agents | Salesforge | — | unscored | — | — | INELIGIBLE | — |
| 809 | Software Engineer (Applied AI/ML) | Oklo | — | unscored | — | — | INELIGIBLE | — |
| 810 | Applied AI Engineer | PermitFlow | — | unscored | — | — | REVIEW_REQUIRED | — |
| 811 | Staff+ Software Engineer, AI | Aleph | — | unscored | — | — | REVIEW_REQUIRED | — |
| 812 | Senior Backend Engineer | Monte Carlo | — | unscored | — | — | REVIEW_REQUIRED | — |
| 813 | Applied AI Engineer | Monte Carlo | — | unscored | — | — | REVIEW_REQUIRED | — |
| 814 | Backend Engineer | Speak | — | unscored | — | — | REVIEW_REQUIRED | — |
| 815 | AI Product Engineer | Speak | — | unscored | — | — | REVIEW_REQUIRED | — |
| 816 | Backend Engineer | Elaborate | — | unscored | — | — | REVIEW_REQUIRED | — |
| 817 | Golang Backend Engineer | Dayout | — | unscored | — | — | REVIEW_REQUIRED | — |
| 818 | Senior Backend Engineer | Dinari | — | unscored | — | — | INELIGIBLE | — |
| 819 | Backend Engineer | Made Card | — | unscored | — | — | REVIEW_REQUIRED | — |
| 820 | Staff Backend Engineer | Made Card | — | unscored | — | — | REVIEW_REQUIRED | — |
| 821 | Sr. Backend Engineer | dv01 | — | unscored | — | — | REVIEW_REQUIRED | — |
| 822 | Senior Backend Engineer | Eight Sleep | — | unscored | — | — | REVIEW_REQUIRED | — |
| 823 | Staff Backend Engineer | Carbon Direct | — | unscored | — | — | REVIEW_REQUIRED | — |
| 824 | Senior Backend Engineer | Triplemint | — | unscored | — | — | REVIEW_REQUIRED | — |
| 825 | Senior Backend Engineer | Honor | — | unscored | — | — | REVIEW_REQUIRED | — |
| 826 | Staff Engineer, Applied AI | Honor | — | unscored | — | — | REVIEW_REQUIRED | — |
| 827 | Rust Backend Engineer | Svix (YC W21) | — | unscored | — | — | REVIEW_REQUIRED | — |
| 828 | Staff Backend Engineer | Astra | — | unscored | — | — | REVIEW_REQUIRED | — |
| 829 | Senior Backend Engineer | Astra | — | unscored | — | — | REVIEW_REQUIRED | — |
| 830 | Senior Backend Engineer | Instrumentl | — | unscored | — | — | REVIEW_REQUIRED | — |
| 831 | BACKEND ENGINEER - SPRING BOOT | REcollab | — | unscored | — | — | INELIGIBLE | — |
| 832 | Senior Backend Engineer | Barometer | — | unscored | — | — | REVIEW_REQUIRED | — |
| 833 | Sr. Backend Engineer (Python) | True Path Leads | — | unscored | — | — | REVIEW_REQUIRED | — |
| 834 | Automation Support Engineer (AI ML Support) (Exp | Emplay | — | unscored | — | — | INELIGIBLE | — |
| 835 | Senior Machine Learning Engineer | Viaduct | — | unscored | — | — | REVIEW_REQUIRED | — |
| 836 | AI Data Engineer | pst.ag | — | unscored | — | — | INELIGIBLE | — |
| 837 | Principal Engineer – Hermes Agent SME | pst.ag | — | unscored | — | — | INELIGIBLE | — |
| 838 | AI Engineer - Methods | pst.ag | — | unscored | — | — | INELIGIBLE | — |
| 839 | Senior GenAI / AgenticAI Engineer (immediate Joi | EazyML | — | unscored | — | — | INELIGIBLE | — |
| 840 | AI Security Engineer | DoseSpot | — | unscored | — | — | REVIEW_REQUIRED | — |
| 841 | AI Security Research & Red Team Engineer | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 842 | Director, Enterprise Sales (AI & Digital Natives | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 843 | Director, Growth Sales (AI & Digital Natives)  | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 844 | Engineering Manager, Agentic Internet & Data Ins | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 845 | Head of GTM, AI Inference | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 846 | Principal Data Scientist, Detection | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 848 | Senior Customer Engineer, Enterprise AI  - Bay A | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 849 | Senior Data Scientist | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 850 | Senior Machine Learning Engineer | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 851 | Senior Machine Learning Engineer | cloudflare | — | unscored | — | — | — | — |
| 852 | Senior Manager, Solutions Architecture, AI & Dev | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 853 | Senior Named Account Executive (AI & Digital Nat | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 854 | Senior Oracle Security and AI Engineer | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 856 | Senior Systems Engineer, Workers AI | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 858 | Solutions Architect, AI/Cloudflare Developer Pla | cloudflare | — | unscored | — | — | INELIGIBLE | — |
| 870 | Senior Product Manager - Data Agent | datadog | — | unscored | — | — | INELIGIBLE | — |
| 874 | Staff GenAI Engineer - Application Performance M | datadog | — | unscored | — | — | INELIGIBLE | — |
| 888 |  Senior Machine Learning Engineer, Payments | airbnb | — | unscored | — | — | INELIGIBLE | — |
| 890 | Senior Machine Learning Engineer, Trust | airbnb | — | unscored | — | — | INELIGIBLE | — |
| 891 | Senior Machine Learning Engineer, Trust | airbnb | — | unscored | — | — | INELIGIBLE | — |
| 897 | Senior Staff Machine Learning Engineer, Trust | airbnb | — | unscored | — | — | INELIGIBLE | — |
| 900 | Staff Machine Learning Engineer, Assistance Engi | airbnb | — | unscored | — | — | INELIGIBLE | — |
| 904 | Agentic AI Engineer | elastic | — | unscored | — | — | INELIGIBLE | — |
| 908 | Principal AI Ecosystem Architect - OpenAI/Anthro | elastic | — | unscored | — | — | INELIGIBLE | — |
| 913 | Strategic Account Executive - AI Natives - West | elastic | — | unscored | — | — | INELIGIBLE | — |
| 914 | Strategic Account Executive - AI Natives - West | elastic | — | unscored | — | — | INELIGIBLE | — |
| 916 | Staff AI Engineer | US | Remote | grafanalabs | — | unscored | — | — | INELIGIBLE | — |
| 917 | Staff Backend Engineer - Analytics | US | Remote | grafanalabs | — | unscored | — | — | INELIGIBLE | — |
| 918 | Staff Backend Engineer - Grafana App Platform |  | grafanalabs | — | unscored | — | — | INELIGIBLE | — |
| 919 | Staff Backend Engineer - Grafana Enterprise | US | grafanalabs | — | unscored | — | — | INELIGIBLE | — |
| 920 | Staff Backend Engineer - Mimir Query, Databases  | grafanalabs | — | unscored | — | — | INELIGIBLE | — |
| 921 | Staff Product Marketing Manager, AI Operations & | cockroachlabs | — | unscored | — | — | INELIGIBLE | — |
| 923 | DevRel Engineer, Agentic Infrastructure | vercel | — | unscored | — | — | INELIGIBLE | — |
| 924 | Software Engineer, Agent | vercel | — | unscored | — | — | INELIGIBLE | — |
| 925 | Software Engineer, Agentic Infrastructure | vercel | — | unscored | — | — | INELIGIBLE | — |
| 926 | Software Engineer, AI Gateway | vercel | — | unscored | — | — | INELIGIBLE | — |
| 927 | Software Engineer, AI SDK | vercel | — | unscored | — | — | INELIGIBLE | — |
| 928 | Software Engineer, Internal Agent  | vercel | — | unscored | — | — | INELIGIBLE | — |
| 931 |  Backend Engineer, Observability | launchdarkly | — | unscored | — | — | INELIGIBLE | — |
| 933 | Senior Backend Engineer, Billing | launchdarkly | — | unscored | — | — | INELIGIBLE | — |
| 934 | Senior Backend Engineer, Experimentation | launchdarkly | — | unscored | — | — | INELIGIBLE | — |
| 935 | Senior Backend Engineer, Flag Delivery | launchdarkly | — | unscored | — | — | INELIGIBLE | — |
| 936 | Senior Backend Engineer, Identity & Access Manag | launchdarkly | — | unscored | — | — | INELIGIBLE | — |
| 937 | Senior Backend Engineer (Multiple Positions) | launchdarkly | — | unscored | — | — | INELIGIBLE | — |
| 938 | Senior Developer Advocate, AI | launchdarkly | — | unscored | — | — | INELIGIBLE | — |
| 939 | Staff Backend Engineer, Guardian | launchdarkly | — | unscored | — | — | INELIGIBLE | — |
| 941 | AI Engineer | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 942 | Business Development Manager- Physical AI  | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 943 | Director of Product Marketing, Agentic AI | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 944 | Senior Applied ML Engineer | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 945 | Senior Forward Deployed Engineer, AI Agents | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 948 | Senior Product Marketing Manager, AI Training In | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 950 | Senior Software Engineer - AI Infrastructure Per | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 951 | Senior Software Engineer II (IC4) – AI Workload  | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 953 | Software Engineer, Inference AI/ML | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 954 | Solution Specialist, AI Runtime Services | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 955 | Staff Machine Learning Engineer, AI Insights | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 956 | Staff Software Engineer- AI Workload Orchestrati | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 957 | VP, Product AI/ ML | coreweave | — | unscored | — | — | INELIGIBLE | — |
| 967 | AI Applied Scientist | figma | — | unscored | — | — | INELIGIBLE | — |
| 968 | Data Scientist, Core Data -  PhD (2026) | figma | — | unscored | — | — | INELIGIBLE | — |
| 969 | Data Scientist, Finance | figma | — | unscored | — | — | INELIGIBLE | — |
| 970 | Director, Product Design - AI & Context | figma | — | unscored | — | — | INELIGIBLE | — |
| 971 | Director, Research - AI Evals | figma | — | unscored | — | — | INELIGIBLE | — |
| 972 | IT Engineer, Internal AI Infrastructure | figma | — | unscored | — | — | INELIGIBLE | — |
| 973 | Manager, Software Engineering - AI Observability | figma | — | unscored | — | — | INELIGIBLE | — |
| 974 | Manager, Software Engineering - DevEx AI Tools | figma | — | unscored | — | — | INELIGIBLE | — |
| 975 | Product Designer, AI Models | figma | — | unscored | — | — | INELIGIBLE | — |
| 976 | Product Designer, Design, Dev, & AI Tools | figma | — | unscored | — | — | INELIGIBLE | — |
| 977 | Product Manager, AI Growth | figma | — | unscored | — | — | INELIGIBLE | — |
| 978 | Researcher, Figma Agentic Experiences | figma | — | unscored | — | — | INELIGIBLE | — |
| 979 | Software Engineer - AI Platforms | figma | — | unscored | — | — | INELIGIBLE | — |
| 980 | Software Engineer - AI Product | figma | — | unscored | — | — | INELIGIBLE | — |
| 981 | Software Engineer - Machine Learning | figma | — | unscored | — | — | INELIGIBLE | — |
| 983 | Support Engineer, AI Infrastructure & Tooling | figma | — | unscored | — | — | INELIGIBLE | — |
| 986 | AI Engineer – Forward Deployed Engineering (AI F | databricks | — | unscored | — | — | INELIGIBLE | — |
| 987 | AI Transformation Leader | databricks | — | unscored | — | — | INELIGIBLE | — |
| 988 | Applied AI Engineer | databricks | — | unscored | — | — | INELIGIBLE | — |
| 989 | Director, Agent & AI Search | databricks | — | unscored | — | — | INELIGIBLE | — |
| 990 | Director, Marketing Strategy and AI Transformati | databricks | — | unscored | — | — | INELIGIBLE | — |
| 991 | Director, Product Marketing, AI  | databricks | — | unscored | — | — | INELIGIBLE | — |
| 992 | Partner Engineer: Partner Intelligence, AI & App | databricks | — | unscored | — | — | INELIGIBLE | — |
| 993 | Principal AI Research Scientist, Research Direct | databricks | — | unscored | — | — | INELIGIBLE | — |
| 994 | Senior Applied ML Engineer - ML4Sys  | databricks | — | unscored | — | — | INELIGIBLE | — |
| 995 | Senior Customer Enablement AI Programs Manager | databricks | — | unscored | — | — | INELIGIBLE | — |
| 996 | Senior Data Scientist  | databricks | — | unscored | — | — | INELIGIBLE | — |
| 997 | Senior Go-To-Market (GTM) Analytics Engineer (AI | databricks | — | unscored | — | — | INELIGIBLE | — |
| 998 | Senior Software Engineer, AI Native Web Platform | databricks | — | unscored | — | — | INELIGIBLE | — |
| 999 | Senior Software Engineer, AI Runtime | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1000 | Senior Software Engineer (Backend) - AI/ML Envir | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1001 | Senior Staff Applied AI Engineer - Context Retri | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1003 | Sr. Developer Advocate, AI and Machine Learning | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1004 | Sr. Developer Advocate, AI and Machine Learning | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1005 | Sr. Engineering Manager - Agentic Service Platfo | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1006 | Sr. Engineering Manager, AI Runtime | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1007 | Sr. Manager, AI Forward Deployed Engineering (AI | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1008 | Sr. Manager – Data & AI Support Engineering | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1010 | Sr. Product Designer, AI/BI | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1011 | Sr. Product Manager, Databricks AI | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1012 | Sr. Product Manager, Databricks AI | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1013 | Sr. Product Marketing Manager, Lakewatch & Agent | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1014 | Sr Software Engineer, Agentic Applications | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1015 | Sr. Staff Fullstack Engineer, Agentic Applicatio | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1016 | Sr. Technology Partner Director - AI Code-Gen &  | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1017 | Staff Backend Software Engineer- (AI Platform) | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1018 | Staff Backline Engineer – ML/AI | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1019 | Staff Data Scientist  | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1020 | Staff Data Scientist - Infrastructure | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1021 |  Staff Data Scientist - Trust and Safety | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1022 | Staff Fullstack Engineer, Agentic Applications | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1023 | Staff Fullstack Engineer, Agentic Applications | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1024 | Staff Machine Learning Engineer  | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1025 | Staff Machine Learning Engineer, CustomerLake (M | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1026 | Staff Partner Engineer, AI Partnerships | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1028 | Staff Product Designer, AI Products  | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1029 | Staff Product Manager, Agentic AI Applications | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1030 | Staff Security Software Engineer, Agentic Securi | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1031 | Staff Software Engineer, Agentic Applications | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1032 | Staff Software Engineer, Agent Quality | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1033 | Staff Software Engineer, AI Native Web Platform | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1034 | Staff Software Engineer, AI Native Web Platform | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1035 | Staff Software Engineer - AI Research Infrastruc | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1036 | Staff Software Engineer - AI Research Infrastruc | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1037 | Staff Software Engineer, AI Runtime | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1038 | Staff Software Engineer, AI Search | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1039 | Staff Software Engineer, Fullstack - AI Product  | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1040 | Staff Software Engineer - GenAI inference | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1041 | Staff Software Engineer - GenAI Performance and  | databricks | — | unscored | — | — | INELIGIBLE | — |
| 1043 | Senior Pricing Data Scientist | fivetran | — | unscored | — | — | INELIGIBLE | — |
| 1045 | Senior R&D Software Engineer, Fivetran AI | fivetran | — | unscored | — | — | INELIGIBLE | — |
| 1046 | Senior R&D Software Engineer, Fivetran AI | fivetran | — | unscored | — | — | INELIGIBLE | — |
| 1047 | Senior R&D Software Engineer, Fivetran AI | fivetran | — | unscored | — | — | INELIGIBLE | — |
| 1049 | Staff R&D Software Engineer, Fivetran AI | fivetran | — | unscored | — | — | INELIGIBLE | — |
| 1050 | Staff R&D Software Engineer, Fivetran AI | fivetran | — | unscored | — | — | INELIGIBLE | — |
| 1051 | Staff R&D Software Engineer, Fivetran AI | fivetran | — | unscored | — | — | INELIGIBLE | — |
| 1052 | Staff R&D Software Engineer, Fivetran AI | fivetran | — | unscored | — | — | INELIGIBLE | — |
| 1053 | Senior Staff Machine Learning Platform Engineer | Faire | — | unscored | — | — | REVIEW_REQUIRED | — |
| 1054 | Backend Engineer, IAM | Reddit | — | unscored | — | — | REVIEW_REQUIRED | — |
| 1055 | Senior Data Scientist | Lemon.io | — | unscored | — | — | INELIGIBLE | — |
| 1056 | Training: ML Framework Engineer | openai | — | unscored | — | — | INELIGIBLE | — |
| 1057 | Software Engineer, Agent Infrastructure | openai | — | unscored | — | — | INELIGIBLE | — |
| 1058 | Applied AI Architect | openai | — | unscored | — | — | INELIGIBLE | — |
| 1059 | Data Scientist, Product | openai | — | unscored | — | — | INELIGIBLE | — |
| 1060 | Software Engineer, Backend (Cooperative AI) | openai | — | unscored | — | — | INELIGIBLE | — |
| 1061 | Software Engineer, AI Safety | openai | — | unscored | — | — | INELIGIBLE | — |
| 1062 | Applied AI Engineer, Startups | openai | — | unscored | — | — | INELIGIBLE | — |
| 1063 | Machine Learning Data Scientist, Forecasting | openai | — | unscored | — | — | INELIGIBLE | — |
| 1064 | Applied AI Engineer, Cyber, Government | openai | — | unscored | — | — | INELIGIBLE | — |
| 1065 | AI Support Engineer - San Francisco | openai | — | unscored | — | — | INELIGIBLE | — |
| 1066 | Security Engineer, Agent Security | openai | — | unscored | — | — | INELIGIBLE | — |
| 1067 | Data Scientist, Infrastructure | openai | — | unscored | — | — | INELIGIBLE | — |
| 1068 | Partner Applied AI Engineer | openai | — | unscored | — | — | INELIGIBLE | — |
| 1069 | Manager, Applied AI Engineering (Digital Natives | openai | — | unscored | — | — | INELIGIBLE | — |
| 1070 | Datacenter Networking Technician, AI Compute Dep | openai | — | unscored | — | — | INELIGIBLE | — |
| 1071 | Data Scientist, Codex | openai | — | unscored | — | — | INELIGIBLE | — |
| 1072 | Data Scientist, Platform and B2B Products | openai | — | unscored | — | — | INELIGIBLE | — |
| 1073 | Data Scientist, Financial Engineering | openai | — | unscored | — | — | INELIGIBLE | — |
| 1074 | Data Scientist, Business | openai | — | unscored | — | — | INELIGIBLE | — |
| 1075 | Applied AI Engineer, Codex | openai | — | unscored | — | — | INELIGIBLE | — |
| 1076 | Software Engineer, Cooperative AI | openai | — | unscored | — | — | INELIGIBLE | — |
| 1077 | Supply Chain Operations Program Manager, AI Infr | openai | — | unscored | — | — | INELIGIBLE | — |
| 1078 | AI Support Engineer - San Francisco (Weekend Shi | openai | — | unscored | — | — | INELIGIBLE | — |
| 1079 | Data Scientist, B2B Demand Generation, Growth &  | openai | — | unscored | — | — | INELIGIBLE | — |
| 1080 | Backend Engineer, Consumer Devices | openai | — | unscored | — | — | INELIGIBLE | — |
| 1081 | Machine Learning Engineer, Monetization AI/ML | openai | — | unscored | — | — | INELIGIBLE | — |
| 1082 | Applied AI Architect | openai | — | unscored | — | — | INELIGIBLE | — |
| 1083 | Applied AI Architect, Digital Natives (Strategic | openai | — | unscored | — | — | INELIGIBLE | — |
| 1084 | Applied AI Architect, Digital Natives | openai | — | unscored | — | — | INELIGIBLE | — |
| 1085 | Applied AI Architect, Enterprise | openai | — | unscored | — | — | INELIGIBLE | — |
| 1086 | Applied AI Architect, Retail | openai | — | unscored | — | — | INELIGIBLE | — |
| 1087 | Applied AI Architect, Healthcare & Life Sciences | openai | — | unscored | — | — | INELIGIBLE | — |
| 1088 | Data Scientist, Preparedness | openai | — | unscored | — | — | INELIGIBLE | — |
| 1090 | Applied AI Engineer, Codex Core Agent | openai | — | unscored | — | — | INELIGIBLE | — |
| 1091 | Manager, Applied AI Architect | openai | — | unscored | — | — | INELIGIBLE | — |
| 1092 | Applied AI Engineer, Digital Natives | openai | — | unscored | — | — | INELIGIBLE | — |
| 1093 | Software Engineer, Kernel Performance & AI Tooli | openai | — | unscored | — | — | INELIGIBLE | — |
| 1094 | Machine Learning Engineer, API Multicloud | openai | — | unscored | — | — | INELIGIBLE | — |
| 1095 | Full Stack Software Engineer, Agent Enablement | openai | — | unscored | — | — | INELIGIBLE | — |
| 1096 | Data Scientist, Core Experimentation | openai | — | unscored | — | — | INELIGIBLE | — |
| 1097 | Supply Chain Program Manager (SCPM) - AI Infrast | openai | — | unscored | — | — | INELIGIBLE | — |
| 1098 | Data Scientist, Safety | openai | — | unscored | — | — | INELIGIBLE | — |
| 1099 | AI Systems Engineer, Codex Agents | openai | — | unscored | — | — | INELIGIBLE | — |
| 1100 | Manager, Applied AI Engineering (Startups) | openai | — | unscored | — | — | INELIGIBLE | — |
| 1101 | Software Engineer,  ML Systems & Training Archit | openai | — | unscored | — | — | INELIGIBLE | — |
| 1102 | Agent Post-Training, API & Power Users | openai | — | unscored | — | — | INELIGIBLE | — |
| 1103 | Agent Post-Training, Artifacts Research | openai | — | unscored | — | — | INELIGIBLE | — |
| 1104 | Agent Post-Training, Computer Use Research | openai | — | unscored | — | — | INELIGIBLE | — |
| 1105 | Software Engineer, Monetization ML Infrastructur | openai | — | unscored | — | — | INELIGIBLE | — |
| 1106 | Agent Post-Training, Connectors Research | openai | — | unscored | — | — | INELIGIBLE | — |
| 1107 | Agent Post-Training, Context Research | openai | — | unscored | — | — | INELIGIBLE | — |
| 1108 | Agent Post-Training, Frontier Evals and Environm | openai | — | unscored | — | — | INELIGIBLE | — |
| 1109 | Agent Post-Training Research | openai | — | unscored | — | — | INELIGIBLE | — |
| 1110 | People Research Data Scientist, AI Fairness & Bi | openai | — | unscored | — | — | INELIGIBLE | — |
| 1111 | Agent Post-Training, Personality | openai | — | unscored | — | — | INELIGIBLE | — |
| 1112 | Applied AI Engineer, Cyber | openai | — | unscored | — | — | INELIGIBLE | — |
| 1113 | Manager, Applied AI Engineering  (Enterprise) | openai | — | unscored | — | — | INELIGIBLE | — |
| 1114 | Network Operations Engineer, AI Networking | openai | — | unscored | — | — | INELIGIBLE | — |
| 1115 | Applied AI Engineer, Enterprise | openai | — | unscored | — | — | INELIGIBLE | — |
| 1116 | Technical Program Manager, Cloud AI Partnerships | openai | — | unscored | — | — | INELIGIBLE | — |
| 1117 | Applied AI Engineer, Plugins | openai | — | unscored | — | — | INELIGIBLE | — |
| 1118 | Data Scientist, Inference Capacity Optimization | openai | — | unscored | — | — | INELIGIBLE | — |
| 1119 | AI Support Engineer, Biosciences - San Francisco | openai | — | unscored | — | — | INELIGIBLE | — |
| 1120 | Applied AI Engineer, Agent Enablement | openai | — | unscored | — | — | INELIGIBLE | — |
| 1121 | Software Engineer, AI accelerator Runtime | openai | — | unscored | — | — | INELIGIBLE | — |
| 1122 | Applied AI Software Engineer, GTM Growth Enginee | openai | — | unscored | — | — | INELIGIBLE | — |
| 1123 | Data Scientist, Ads Demand | openai | — | unscored | — | — | INELIGIBLE | — |
| 1124 | Data Scientist, SMB Ads Growth | openai | — | unscored | — | — | INELIGIBLE | — |
| 1125 | Research Engineer / Research Scientist / AI Syst | openai | — | unscored | — | — | INELIGIBLE | — |
| 1126 | Data Scientist, Cybersecurity | openai | — | unscored | — | — | INELIGIBLE | — |
| 1127 | AI Support Engineer - Toronto | openai | — | unscored | — | — | INELIGIBLE | — |
| 1128 | AI Support Engineer, Government - San Francisco, | openai | — | unscored | — | — | INELIGIBLE | — |
| 1129 | Senior Counsel, AI Product (Enterprise/API) | openai | — | unscored | — | — | INELIGIBLE | — |
| 1130 | AI Support Engineer, Government - Washington, D. | openai | — | unscored | — | — | INELIGIBLE | — |
| 1131 | Technical Program Manager, AI Accelerator Softwa | openai | — | unscored | — | — | INELIGIBLE | — |
| 1132 | Technical Program Manager, AI Safety & Safeguard | openai | — | unscored | — | — | INELIGIBLE | — |
| 1133 | Machine Learning Engineer, Multimodal Perception | openai | — | unscored | — | — | INELIGIBLE | — |
| 1134 | Data Scientist, Real Estate & Workplace | openai | — | unscored | — | — | INELIGIBLE | — |
| 1135 | Model Policy Manager, Agentic Safety | openai | — | unscored | — | — | INELIGIBLE | — |
| 1136 | Manager, Applied AI Engineering (Codex) | openai | — | unscored | — | — | INELIGIBLE | — |
| 1138 | Applied AI Architect, Government | openai | — | unscored | — | — | INELIGIBLE | — |
| 1139 | Researcher, Agent Safety, Training and Evaluatio | openai | — | unscored | — | — | INELIGIBLE | — |
| 1140 | Researcher, Agent Safety, Oversight and System M | openai | — | unscored | — | — | INELIGIBLE | — |
| 1141 | Applied AI Engineer, Government | openai | — | unscored | — | — | INELIGIBLE | — |
| 1142 | Agent Standards Architect, Global Affairs | openai | — | unscored | — | — | INELIGIBLE | — |
| 1143 | Machine Learning Engineer, Core Experimentation | openai | — | unscored | — | — | INELIGIBLE | — |
| 1144 | Research Engineer, AI for Chip Design | openai | — | unscored | — | — | INELIGIBLE | — |
| 1145 | Software Engineer, AI for Chip Design | openai | — | unscored | — | — | INELIGIBLE | — |
| 1146 | AI Infrastructure Engineer, pAGI | openai | — | unscored | — | — | INELIGIBLE | — |
| 1149 | AI Support Engineer - Toronto (Weekend Shift) | openai | — | unscored | — | — | INELIGIBLE | — |
| 1150 | Staff Software Engineer, AI Platform | harvey | — | unscored | — | — | INELIGIBLE | — |
| 1151 | Data Scientist, Marketing | harvey | — | unscored | — | — | INELIGIBLE | — |
| 1152 | Senior Software Engineer, AI Platform | harvey | — | unscored | — | — | INELIGIBLE | — |
| 1153 | Data Scientist, Product | harvey | — | unscored | — | — | INELIGIBLE | — |
| 1154 | Senior Software Engineer, AI Platform | harvey | — | unscored | — | — | INELIGIBLE | — |
| 1155 | Staff Software Engineer, AI Platform | harvey | — | unscored | — | — | INELIGIBLE | — |
| 1156 | Product Manager, Agent Development | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1157 | Software Engineer, Agent | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1158 | Software Engineer, Agent Runtime | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1159 | Strategist, Agent Development | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1160 | Engineering Manager, Agent | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1161 | Product Manager, Agent Development - Financial S | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1162 | Agent Experience Designer, Voice (Multilingual) | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1163 | Software Engineer, Agent - Healthcare | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1164 | GTM Operations, Agent Development | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1165 | Product Manager, Agent Development - Healthcare | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1166 | Software Engineer, Agent Builder | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1167 | Product Manager, Agent Development (Brazilian Po | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1168 | Software Engineer, Agent (Brazilian Portuguese s | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1169 | Product Manager, Agent Development (Spanish spea | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1170 | Software Engineer, Agent (New Grad 2027) | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1171 | Product Manager, Agent Development - Public Sect | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1172 | Software Engineer, Agent (Spanish speaking) | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1173 | Strategist, Agent Development (Spanish speaking) | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1174 | Strategist, Agent Development (Brazilian Portugu | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1175 | Strategist, Agent Development - Flagship Deploym | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1176 | Strategist, Agent Development - Retail | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1177 | Software Engineer, Agent - Financial Services | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1179 | Software Engineer, Agent - Public Sector | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1180 | Software Engineer, Agent - Retail | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1181 | Strategist, Agent Development - Financial Servic | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1182 | Software Engineer, Agent - Travel & Hospitality | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1183 | Strategist, Agent Development - Healthcare | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1184 | Strategist, Agent Development - Public Sector | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1185 | Software Engineer, Agent - Insurance | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1186 | Strategist, Agent Development - Tech, Media & Te | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1187 | Software Engineer, Agent - Tech, Media & Telecom | sierra | — | unscored | — | — | INELIGIBLE | — |
| 1188 | Applied AI Engineer | ramp | — | unscored | — | — | INELIGIBLE | — |
| 1189 | Data Scientist | ramp | — | unscored | — | — | INELIGIBLE | — |
| 1190 | Backend Engineer, Ops Engineering | ramp | — | unscored | — | — | INELIGIBLE | — |
| 1191 | AI Solutions Engineer | ramp | — | unscored | — | — | INELIGIBLE | — |
| 1192 | Machine Learning Engineer | ramp | — | unscored | — | — | INELIGIBLE | — |
| 1193 | Applied AI Engineer, Fullstack | ramp | — | unscored | — | — | INELIGIBLE | — |
| 1194 | Software Engineer, Forward Deployed AI Solutions | ramp | — | unscored | — | — | INELIGIBLE | — |
| 1195 | Data Scientist, Finance | ramp | — | unscored | — | — | INELIGIBLE | — |
| 1196 | AI Solutions Strategist | ramp | — | unscored | — | — | INELIGIBLE | — |
| 1197 | Senior Member of Technical Staff, Multimodal AI | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1198 | Forward Deployed Engineer, Agentic Platform (Eur | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1199 | Forward Deployed Engineer, Agentic Platform | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1200 | Forward Deployed Engineer, Agentic Platform (Wes | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1201 | Forward Deployed Engineer, Agentic Platform | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1202 | Lead Data Scientist | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1203 | Technical Program Manager, AI Delivery, Korea | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1204 | Data Scientist, North Insights | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1205 | Member of Technical Staff, Agentic Environments | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1206 | Global Public Policy Manager, Compute, Infrastru | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1207 | Technical Program Manager, AI Delivery | cohere | — | unscored | — | — | INELIGIBLE | — |
| 1208 | Engineering Manager, Mobile AI | notion | — | unscored | — | — | INELIGIBLE | — |
| 1209 | Software Engineer, Early Career (AI) | notion | — | unscored | — | — | INELIGIBLE | — |
| 1210 | Software Engineer, AI Product Security | notion | — | unscored | — | — | INELIGIBLE | — |
| 1211 | AI Product Counsel | notion | — | unscored | — | — | INELIGIBLE | — |
| 1212 | Data Scientist, Growth | notion | — | unscored | — | — | INELIGIBLE | — |
| 1213 | Workflow + Process Designer (AI Enablement) | notion | — | unscored | — | — | INELIGIBLE | — |
| 1215 | Software Engineer, ML Research | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1216 | AI Deployment Manager | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1217 | Software Engineer, Agent Harness | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1218 | Regional Director, AI Deployment | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1219 | Software Engineer, ML Infrastructure | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1220 | Engineering Manager, ML | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1221 | Software Engineer, Agent Evaluation and Quality | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1222 | Engineering Manager, Agent & Product Security | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1223 | Software Engineer, ML Platform | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1224 | Full Stack Engineer, ML Research Tools | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1225 | AI Deployment Manager, Scale | cursor | — | unscored | — | — | INELIGIBLE | — |
| 1226 | Senior Software Engineer, AI Product | vanta | — | unscored | — | — | INELIGIBLE | — |
| 1227 | Sr. AI GTM Engineer | vanta | — | unscored | — | — | INELIGIBLE | — |
| 1228 | Senior Data Scientist | vanta | — | unscored | — | — | INELIGIBLE | — |
| 1229 | Senior Product Manager, Agent Ecosystem | vanta | — | unscored | — | — | INELIGIBLE | — |
| 1230 | Senior Product Designer, Agent Experience | vanta | — | unscored | — | — | INELIGIBLE | — |
| 1231 | Principal ML Platform Engineer | synthesia | — | unscored | — | — | INELIGIBLE | — |
| 1232 | Staff Research Engineer - Multimodal Generative  | synthesia | — | unscored | — | — | INELIGIBLE | — |
| 1233 | Machine Learning Engineer / ML Engineer - Rolepl | synthesia | — | unscored | — | — | INELIGIBLE | — |
| 1234 | Senior Software Engineer, AI Developer Experienc | sanity | — | unscored | — | — | INELIGIBLE | — |
| 1235 | Software Engineering Manager, AI Growth | sanity | — | unscored | — | — | INELIGIBLE | — |
| 1236 | Senior / Staff Product Engineer, AI | linear | — | unscored | — | — | INELIGIBLE | — |
| 1237 | Senior AI Solutions Manager, Enterprise | gorgias | — | unscored | — | — | INELIGIBLE | — |
| 1238 | AI Solution Manager - Commercial | gorgias | — | unscored | — | — | INELIGIBLE | — |
| 1239 | AI Deployment Manager, Commercial | gorgias | — | unscored | — | — | INELIGIBLE | — |
| 1240 | Data Scientist | We Are Meta | — | unscored | — | — | INELIGIBLE | — |
| 1241 | Staff AI Engineer | Capital One | — | unscored | — | — | INELIGIBLE | — |
| 1242 | Staff UX Writer, AI | Airbnb | — | unscored | — | — | INELIGIBLE | — |
| 1243 | Senior Backend Engineer, Home Surfaces | Spotify | — | unscored | — | — | INELIGIBLE | — |
| 1244 | Lead AI Engineer (LLM & Agents) | Trust Wallet | — | unscored | — | — | INELIGIBLE | — |
| 1245 | Data Scientist/Machine Learning Engineer | The Aerospace Corporatio | — | unscored | — | — | INELIGIBLE | — |
