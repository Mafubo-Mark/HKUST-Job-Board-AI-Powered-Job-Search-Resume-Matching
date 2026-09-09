# HKUST Job Board Career Intelligence

A Python workflow that collects filtered opportunities from the HKUST Job Board and uses DeepSeek to assess how each job matches a PDF resume.

The project connects browser automation, job-data extraction, resume processing, and LLM scoring. It produces local JSON files containing exported jobs, generated prompts, and ranked model responses.

## Why this project

As an HKUST student searching for internships on the HKUST Job Board, I found it time-consuming to compare the many available positions with my skills, project experience, and research interests. Applying broadly can lead to interviews for roles whose requirements fall outside my background, making preparation less focused.

I built this project to use AI to compare job descriptions against my resume and prioritize relevant opportunities. The goal is to make my internship search more targeted: spend less time screening listings, focus on applications that better match my experience, and prepare for interviews with a clearer understanding of each role’s requirements.

## Features

- **Manual login with browser automation:** Opens Chrome and waits for the user to complete HKUST login and job-board declarations.
- **Filters:** Supports business nature, job nature, employment type, working location, qualification level, employment mode, and language.
- **Deadline screening:** Skips expired listings, recognizes several date formats and “until filled,” and checks detail pages when deadlines are unclear.
- **Concurrent detail retrieval:** Fetches candidate job pages within the authenticated browser session, with up to three attempts for failed fetches.
- **Resume-based prompts:** Extracts selectable PDF text and creates a separate evaluation prompt for each job with a nonempty description.
- **DeepSeek scoring:** Requests an overall score and application recommendation, then sorts replies by the extracted score.
- **Incremental saving:** Saves exported jobs after each result page and analysis results after each successful response.

## Technology

| Area | Components |
| --- | --- |
| Application | Python command-line workflow |
| Browser automation | Selenium WebDriver, Chrome, explicit waits, CSS selectors |
| Browser-side processing | JavaScript, Fetch API, `Promise.all`, `DOMParser`, DOM events; jQuery integration when available |
| LLM integration | OpenAI Python SDK configured for DeepSeek, `deepseek-chat`, HTTPS chat-completion requests |
| Resume extraction | `pypdf.PdfReader` |
| Validation and normalization | Python type checks, regular expressions, date parsing, text normalization |
| Local storage and utilities | JSON, `pathlib`, `datetime`, `time`, `getpass` |

The application uses local JSON files. It does not require a database, web backend, vector store, or agent framework.

## Source files

| File | Responsibility |
| --- | --- |
| `main.py` | Runs login, filtering, export, prompt generation, and scoring. Contains the embedded AI helper functions. |
| `login.py` | Creates Chrome and waits for the actual job board to appear after manual login. |
| `filter_jobs.py` | Reads filter options, validates terminal selections, applies filters, and submits searches. |
| `job_exporter.py` | Collects jobs, checks deadlines, retrieves details, handles pagination, and writes job JSON. |
| `ai_analyze.py` | Optional standalone entry point for generating prompts and scoring an existing job export. |

`main.py` already includes the AI logic, so it does not import or require `ai_analyze.py`. If both are maintained, changes to shared AI helpers need to be kept consistent.

## Setup

You will need Python, Google Chrome, access to the HKUST Job Board, a DeepSeek API key, and a PDF resume containing selectable text. The browser and API calls require network access.

1. Download or clone this repository and open a terminal in its directory.
2. Ensure the Python files have their canonical names: `main.py`, `login.py`, `filter_jobs.py`, and `job_exporter.py`. Remove downloaded copy suffixes such as `(2)` or `(8)` so imports resolve correctly.
3. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   macOS/Linux:

   ```bash
   source .venv/bin/activate
   ```

   Windows PowerShell:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

4. Install the packages imported by the application:

   ```bash
   python -m pip install selenium pypdf openai
   ```

5. Place your resume in the project directory as `resume.pdf`.

The source does not pin dependency versions. Chrome must be launchable through Selenium's `webdriver.Chrome()` in your environment.

## Run the complete workflow

```bash
python main.py
```

1. Complete HKUST login and the job-board declarations in Chrome. The script waits up to five minutes for the job list to appear.
2. Select filters in the terminal using comma-separated option numbers. Press Enter to skip a category, or enter `y` to confirm selections.
3. The program applies the filters and exports eligible jobs from the reachable result pages.
4. It extracts resume text and saves a prompt for each job with a nonempty description.
5. Enter your DeepSeek API key at the hidden-input prompt. The program sends prompts sequentially and saves ranked responses as processing proceeds.
6. Press Enter at the final prompt to close Chrome. Browser cleanup also runs if the workflow raises an error.

`main.py` sets the exporter's output path to the `hkust_jobs.json` beside `main.py`, ensuring the AI stage reads the same export. The supplied `job_exporter.py` contains an original machine-specific default path; update its `OUTPUT_FILE` if using the exporter independently.

### Analyze an existing export

If you keep the optional `ai_analyze.py`, place `resume.pdf` and `hkust_jobs.json` beside it and run:

```bash
python ai_analyze.py
```

This generates prompts and performs scoring without opening the career board. The helper `process_jobs(resume_file, input_json, output_json)` can also be called directly to generate prompts without an API request.

## Generated files

| File | Contents |
| --- | --- |
| `hkust_jobs.json` | Company, job title/nature, application deadline, and extracted details |
| `hkust_jobs_to_ai.json` | Company, job title/nature, and the complete resume/job prompt in `New_information` |
| `result.json` | Company, job title/nature, and the model reply in `deepseek result`, sorted by extracted score |

The prompt requests this response format:

```text
overall score: <integer from 0-100>/100
recommendation level: <Strongly recommend applying / Apply with targeted resume revision / Not recommended to apply>
```

The score is parsed into a temporary `_score` field for sorting. That field is removed before saving, so the saved score remains inside the `deepseek result` text. Replies without a recognized score sort below valid scores.

## Before publishing your copy

Keep your resume, generated prompts, job exports, model responses, and API credentials out of the public repository. Prompts include the extracted resume text, and the program also prints a resume preview in the terminal. Running scoring sends resume and job content to DeepSeek and may incur API usage charges.

Add the following entries to a `.gitignore` file before staging files:

```gitignore
.venv/
__pycache__/
*.py[cod]
.env
resume.pdf
hkust_jobs.json
hkust_jobs_to_ai.json
result.json
```

Ignore rules do not remove files already tracked by Git. Review staged files before publishing, and remove the original personal filesystem path from `job_exporter.py` if it is still present in your copy.

Use the Job board through your own authorized account. This project does not bypass login or declarations and is not affiliated with HKUST or DeepSeek.
