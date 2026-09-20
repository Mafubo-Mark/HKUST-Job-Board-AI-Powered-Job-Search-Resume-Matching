"""Match exported jobs to resume.pdf using DeepSeek and rank the results.

Install: python3 -m pip install pypdf openai
Run: python3 job_matcher.py (uses the existing hkust_jobs.json beside this file).
Writes hkust_jobs_to_ai.json (prompts) and result.json (highest scores first).
The API key is entered privately; resume and job text are sent to DeepSeek.
"""

import json  # Read job data and save prompts/results.
import re  # Extract numeric scores from AI responses.
from getpass import getpass  # Hide the API key while it is typed.
from pathlib import Path  # Resolve all files relative to this script.

BASE_DIR = Path(__file__).resolve().parent
RESUME_PDF = BASE_DIR / "resume.pdf"
INPUT_JSON = BASE_DIR / "hkust_jobs.json"
PROMPTS_JSON = BASE_DIR / "hkust_jobs_to_ai.json"
OUTPUT_JSON = BASE_DIR / "result.json"
JOB_FIELDS = ("Company/Organization", "Job Title/Job Nature")


def save_json(path, data):
    # Serialize UTF-8 JSON, then replace the destination so partial writes stay separate.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def extract_pdf_text(pdf_file):
    # pypdf reads selectable text; scanned image-only PDFs require OCR beforehand.
    from pypdf import PdfReader

    parts = []
    for number, page in enumerate(PdfReader(str(pdf_file)).pages, 1):
        text = (page.extract_text() or "").strip()
        print(f"PDF page {number}: {len(text)} characters extracted")
        if text:
            parts.append(text)
    if not parts:
        raise ValueError(f"No selectable text could be extracted from {pdf_file}.")
    return "\n\n".join(parts)


def value_to_text(value):
    # Recursively turn strings, nested lists, and dictionaries into readable text.
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(filter(None, map(value_to_text, value)))
    if isinstance(value, dict):
        parts = ((key, value_to_text(item)) for key, item in value.items())
        return "\n".join(f"{key}: {text}" for key, text in parts if text)
    return str(value).strip()


def load_jobs(json_file):
    # Accept a JSON list, a wrapper such as {"jobs": [...]}, or one job object.
    data = json.loads(Path(json_file).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return next((data[key] for key in ("jobs", "Jobs", "data", "results", "items")
                     if isinstance(data.get(key), list)), [data])
    raise ValueError("Job JSON must contain a list or an object.")


def create_ai_context(resume_text, job_description):
    # Keep the original evaluation criteria and two-line response format unchanged.
    return f"""Act as an experienced senior HR recruiter.

Your task is to evaluate how well the candidate's resume matches the given job description and generate an objective job-fit assessment.

[Full Resume]

{resume_text}

[Job Description & Requirements]

{job_description}

Evaluate the candidate based on:

- educational background match
- technical skill match
- project experience match
- soft-skill and background match
- business-role understanding match

Important evaluation rules:

- Score objectively and rigorously.
- Avoid inflated ratings.
- Compare strictly using the resume and job description above.
- Do not invent skills, qualifications, achievements, education, projects, or experience.
- Missing requirements should reduce the score.

Your response MUST contain EXACTLY two lines.

Use this exact format:

overall score: <integer from 0-100>/100
recommendation level: <Strongly recommend applying / Apply with targeted resume revision / Not recommended to apply>

Do not provide explanations.
Do not provide markdown.
Do not provide bullet points.
Do not provide any other text.
""".strip()


def process_jobs(resume_file=RESUME_PDF, input_json=INPUT_JSON, output_json=PROMPTS_JSON):
    # Build prompts locally; no API requests occur in this step.
    jobs = load_jobs(input_json)
    resume = extract_pdf_text(resume_file) if jobs else ""
    prompts = []
    for index, job in enumerate(jobs, 1):
        # Normalize field names once, accepting capitalization and surrounding spaces.
        if not isinstance(job, dict):
            print(f"Skipping job {index}: not a JSON object.")
            continue
        fields = {str(key).strip().lower(): value_to_text(value) for key, value in job.items()}
        description = fields.get("other information", "")
        if not description:
            print(f"Skipping job {index}: Other information is empty.")
            continue
        prompts.append({**{key: fields.get(key.lower(), "") for key in JOB_FIELDS},
                        "New_information": create_ai_context(resume, description)})
    save_json(output_json, prompts)
    print(f"Created {len(prompts)} prompts; skipped {len(jobs) - len(prompts)}. Saved to {output_json}")
    return prompts


def get_deepseek_client():
    # The OpenAI-compatible SDK sends requests to DeepSeek's endpoint, not OpenAI's.
    from openai import OpenAI

    key = getpass("Enter your DeepSeek API key: ").strip()
    if not key:
        raise ValueError("API key cannot be empty.")
    return OpenAI(api_key=key, base_url="https://api.deepseek.com")


def extract_score(reply):
    # Prefer the labeled score; fall back to any N/100. Invalid scores sort last.
    patterns = (r"overall\s*score\s*:\s*(\d{1,3})\s*/\s*100", r"\b(\d{1,3})\s*/\s*100\b")
    for pattern in patterns:
        match = re.search(pattern, reply or "", re.IGNORECASE)
        if match and 0 <= int(match[1]) <= 100:
            return int(match[1])
    return -1


def save_results(results, output_json=OUTPUT_JSON):
    # Keep the original three output fields; _score is used only for sorting.
    results.sort(key=lambda item: item["_score"], reverse=True)
    save_json(output_json, [{key: item[key] for key in (*JOB_FIELDS, "deepseek result")}
                           for item in results])


def analyze_jobs(jobs=None, output_json=OUTPUT_JSON):
    # Score supplied prompts, or load the saved prompt file when called separately.
    if jobs is None:
        jobs = json.loads(PROMPTS_JSON.read_text(encoding="utf-8"))
    if not isinstance(jobs, list):
        raise ValueError("Prompts must be a JSON list.")
    results = []
    if not jobs:
        save_results(results, output_json)
        print("No prompts to analyze. Saved empty results.")
        return results
    # A context manager closes HTTP connections even when interrupted with Ctrl+C.
    with get_deepseek_client() as client:
        for index, job in enumerate(jobs, 1):
            if not isinstance(job, dict) or not str(job.get("New_information") or "").strip():
                print(f"Skipping prompt {index}: missing or invalid content.")
                continue
            record = {key: job.get(key, default) for key, default in
                      zip(JOB_FIELDS, ("Unknown Company", "Unknown Job"))}
            print(f"[{index}/{len(jobs)}] " + " | ".join(str(record[key]) for key in JOB_FIELDS))
            try:
                # Send one prompt per job using the same model and API arguments as before.
                response = client.chat.completions.create(model="deepseek-chat", messages=[
                    {"role": "user", "content": str(job["New_information"]).strip()}])
                reply = response.choices[0].message.content
                if not isinstance(reply, str) or not reply.strip():
                    raise ValueError("DeepSeek returned an empty response.")
            except Exception as error:
                print(f"DeepSeek API error: {type(error).__name__}: {error}")
                continue
            results.append({**record, "deepseek result": reply.strip(), "_score": extract_score(reply)})
            # Save after each success; disk errors propagate instead of looking like API errors.
            save_results(results, output_json)
            print(f"{reply.strip()}\nSaved {len(results)} results.")
    save_results(results, output_json)
    print(f"Analyzed {len(results)} jobs. Ranked results: {output_json}")
    return results


def main():
    # Generate prompts, then pass them directly to scoring without rereading the file.
    return analyze_jobs(process_jobs())


if __name__ == "__main__":
    # Importing this module never starts analysis or requests an API key.
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Saved progress is retained.")
        raise SystemExit(130)
    except Exception as error:
        print(f"Program error: {type(error).__name__}: {error}")
        raise SystemExit(1)
