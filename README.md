# HKUST-Job-Board-AI-Powered-Job-Search-Resume-Matching
Python workflow that finds relevant opportunities on the HKUST Job Board using automated job filtering, AI-powered resume matching, and ranked job recommendations.
A Python workflow that collects filtered opportunities from the HKUST Career Board and uses DeepSeek to assess how each job matches a PDF resume.

The project connects browser automation, job-data extraction, resume processing, and LLM scoring. It produces local JSON files containing exported jobs, generated prompts, and ranked model responses.

Why this project

Reviewing career-board listings involves repeatedly opening job pages, checking application deadlines, and comparing requirements against a resume. This project brings those steps into one workflow while keeping login, declarations, and filter selection under the user's control.

It is a scripted LLM-assisted pipeline. It does not autonomously plan tasks, submit applications, or modify resumes.

Features

Manual login with browser automation: Opens Chrome and waits for the user to complete HKUST login and job-board declarations.

Interactive filtering: Supports business nature, job nature, employment type, working location, qualification level, employment mode, and language.

Multi-page collection: Attempts to follow result pages using several pagination selectors and page-change checks.

Deadline screening: Skips expired listings, recognizes several date formats and “until filled,” and checks detail pages when deadlines are unclear.

Concurrent detail retrieval: Fetches candidate job pages within the authenticated browser session, with up to three attempts for failed fetches.

Resume-based prompts: Extracts selectable PDF text and creates a separate evaluation prompt for each job with a nonempty description.

DeepSeek scoring: Requests an overall score and application recommendation, then sorts replies by the extracted score.

Incremental saving: Saves exported jobs after each result page and analysis results after each successful response.

Technology

Area

Components

Application

Python command-line workflow

Browser automation

Selenium WebDriver, Chrome, explicit waits, CSS selectors

Browser-side processing

JavaScript, Fetch API, Promise.all, DOMParser, DOM events; jQuery integration when available

LLM integration

OpenAI Python SDK configured for DeepSeek, deepseek-chat, HTTPS chat-completion requests

Resume extraction

pypdf.PdfReader

Validation and normalization

Python type checks, regular expressions, date parsing, text normalization

Local storage and utilities

JSON, pathlib, datetime, time, getpass

The application uses local JSON files. It does not require a database, web backend, vector store, or agent framework.

Source files

File

Responsibility

main.py

Runs login, filtering, export, prompt generation, and scoring. Contains the embedded AI helper functions.

login.py

Creates Chrome and waits for the actual job board to appear after manual login.

filter_jobs.py

Reads filter options, validates terminal selections, applies filters, and submits searches.

job_exporter.py

Collects jobs, checks deadlines, retrieves details, handles pagination, and writes job JSON.

ai_analyze.py

Optional standalone entry point for generating prompts and scoring an existing job export.

main.py already includes the AI logic, so it does not import or require ai_analyze.py. If both are maintained, changes to shared AI helpers need to be kept consistent.

Setup

You will need Python 3, Google Chrome, access to the HKUST Career Board, a DeepSeek API key, and a PDF resume containing selectable text. The browser and API calls require network access.

Download or clone this repository and open a terminal in its directory.

Ensure the Python files have their canonical names: main.py, login.py, filter_jobs.py, and job_exporter.py. Remove downloaded copy suffixes such as (2) or (8) so imports resolve correctly.

Create and activate a virtual environment:

python -m venv .venv

macOS/Linux:

source .venv/bin/activate

Windows PowerShell:

.venv\Scripts\Activate.ps1

Install the packages imported by the application:

python -m pip install selenium pypdf openai

Place your resume in the project directory as resume.pdf.

The source does not pin dependency versions. Chrome must be launchable through Selenium's webdriver.Chrome() in your environment.

Run the complete workflow

python main.py

Complete HKUST login and the job-board declarations in Chrome. The script waits up to five minutes for the job list to appear.

Select filters in the terminal using comma-separated option numbers. Press Enter to skip a category, or enter y to confirm selections.

The program applies the filters and exports eligible jobs from the reachable result pages.

It extracts resume text and saves a prompt for each job with a nonempty description.

Enter your DeepSeek API key at the hidden-input prompt. The program sends prompts sequentially and saves ranked responses as processing proceeds.

Press Enter at the final prompt to close Chrome. Browser cleanup also runs if the workflow raises an error.

main.py sets the exporter's output path to the hkust_jobs.json beside main.py, ensuring the AI stage reads the same export. The supplied job_exporter.py contains an original machine-specific default path; update its OUTPUT_FILE if using the exporter independently.

Analyze an existing export

If you keep the optional ai_analyze.py, place resume.pdf and hkust_jobs.json beside it and run:

python ai_analyze.py

This generates prompts and performs scoring without opening the career board. The helper process_jobs(resume_file, input_json, output_json) can also be called directly to generate prompts without an API request.

Generated files

File

Contents

hkust_jobs.json

Company, job title/nature, application deadline, and extracted details

hkust_jobs_to_ai.json

Company, job title/nature, and the complete resume/job prompt in New_information

result.json

Company, job title/nature, and the model reply in deepseek result, sorted by extracted score

The prompt requests this response format:

overall score: <integer from 0-100>/100
recommendation level: <Strongly recommend applying / Apply with targeted resume revision / Not recommended to apply>

The score is parsed into a temporary _score field for sorting. That field is removed before saving, so the saved score remains inside the deepseek result text. Replies without a recognized score sort below valid scores.

Reliability and current limitations

Partial progress: Page exports and successful analysis replies are saved incrementally. Files are overwritten during subsequent runs; there is no automatic resume, version history, or rollback.

Browser dependencies: Collection depends on the website's HTML structure. Pagination failures can end collection early, so the export is not guaranteed to contain every result.

Empty searches: The exporter waits for at least one job row and can time out when a search returns no rows. The main workflow handles an empty returned export, but does not remove this exporter timeout.

Deadline interpretation: Date comparisons use the local computer's date. Unknown deadlines are excluded unless verified as valid from detail text; deadlines already classified as valid on the listing are not rechecked against the detail page.

Detail-fetch failures: Eligible job summaries can be retained with an error message when details cannot be fetched. This error text is nonempty and may subsequently be passed to the scoring stage.

PDF limitations: Scanned/image-only resumes require external OCR. The code extracts selectable text and does not implement OCR.

LLM output: Prompt instructions discourage invented qualifications, but do not guarantee factual or calibrated assessments. The code validates extracted score ranges rather than enforcing the entire two-line response format.

API failures: Individual analysis errors are printed and processing continues. The explicit three-attempt retry loop applies to job-page fetches, not DeepSeek scoring.

Data extraction: Job details are flattened page text and may include navigation or footer content. Job URLs are used internally for deduplication but are not saved in the final job schema.

Performance: Detail fetches are concurrent within each page; LLM requests are sequential. No throughput or scoring-accuracy benchmarks are included.

Before publishing your copy

Keep your resume, generated prompts, job exports, model responses, and API credentials out of the public repository. Prompts include the extracted resume text, and the program also prints a resume preview in the terminal. Running scoring sends resume and job content to DeepSeek and may incur API usage charges.

Add the following entries to a .gitignore file before staging files:

.venv/
__pycache__/
*.py[cod]
.env
resume.pdf
hkust_jobs.json
hkust_jobs_to_ai.json
result.json

Ignore rules do not remove files already tracked by Git. Review staged files before publishing, and remove the original personal filesystem path from job_exporter.py if it is still present in your copy.

Use the career board through your own authorized account. This project does not bypass login or declarations and is not affiliated with HKUST or DeepSeek.
