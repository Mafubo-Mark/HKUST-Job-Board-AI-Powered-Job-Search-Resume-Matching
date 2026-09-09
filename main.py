"""HKUST job search, export, resume prompts, and DeepSeek scoring.

Keep main.py, login.py, filter_jobs.py, job_exporter.py, and resume.pdf
in the same folder. Install dependencies with:
    pip install selenium pypdf openai
Run with:
    python main.py

Log in and accept declarations in Chrome, choose filters in the terminal,
and enter your DeepSeek API key when prompted. This workflow sends the
resume and job text to DeepSeek. resume.pdf must contain selectable text.

Outputs beside this file (overwritten on each run):
    hkust_jobs.json - exported jobs
    hkust_jobs_to_ai.json - generated prompts
    result.json - replies ranked by extracted score, highest first

All ai_analyze helpers are embedded; a separate ai_analyze.py is unnecessary.
The exporter output path is aligned with the AI input before export.
"""

from login import (
    create_driver,
    login_to_hkust
)

from filter_jobs import (
    # Choose
    choose_business_natures,
    choose_job_natures,
    choose_employment_types,
    choose_working_locations,
    choose_qualification_levels,
    choose_employment_modes,
    choose_languages,

    # Apply
    apply_business_natures,
    apply_job_natures,
    apply_employment_types,
    apply_working_locations,
    apply_qualification_levels,
    apply_employment_modes,
    apply_languages,

    # Search
    submit_filter
)

import job_exporter


import json
import re
from pathlib import Path
from getpass import getpass

BASE_DIR = Path(__file__).resolve().parent
RESUME_PDF = BASE_DIR / "resume.pdf"
INPUT_JSON = BASE_DIR / "hkust_jobs.json"
PROMPTS_JSON = BASE_DIR / "hkust_jobs_to_ai.json"
OUTPUT_JSON = BASE_DIR / "result.json"

def extract_pdf_text(pdf_file):
    """
    Extract all selectable text from a PDF.
    """

    if not pdf_file.exists():
        raise FileNotFoundError(
            f"Resume PDF not found:\n{pdf_file}"
        )

    from pypdf import PdfReader

    reader = PdfReader(str(pdf_file))

    text_parts = []

    for page_number, page in enumerate(reader.pages, start=1):

        text = page.extract_text()

        if text and text.strip():
            text_parts.append(text.strip())

            print(
                f"PDF page {page_number}: "
                f"{len(text)} characters extracted"
            )

        else:
            print(
                f"Warning: No text extracted from "
                f"PDF page {page_number}"
            )

    full_text = "\n\n".join(text_parts).strip()

    if not full_text:
        raise ValueError(
            "No text could be extracted from resume.pdf."
        )

    return full_text



def value_to_text(value):

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):

        parts = []

        for item in value:
            text = value_to_text(item)

            if text:
                parts.append(text)

        return "\n".join(parts)

    if isinstance(value, dict):

        parts = []

        for key, val in value.items():

            text = value_to_text(val)

            if text:
                parts.append(f"{key}: {text}")

        return "\n".join(parts)

    return str(value).strip()



def create_ai_context(resume_text, job_description):
    """
    Create one complete prompt for one job.
    """

    prompt = f"""Act as an experienced senior HR recruiter.

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
"""

    return prompt.strip()



def load_jobs(json_file):

    if not json_file.exists():
        raise FileNotFoundError(
            f"JSON file not found:\n{json_file}"
        )

    with open(
        json_file,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    # JSON is already a list
    if isinstance(data, list):
        return data

    # JSON may contain jobs inside another object
    if isinstance(data, dict):

        possible_keys = [
            "jobs",
            "Jobs",
            "data",
            "results",
            "items"
        ]

        for key in possible_keys:

            if (
                key in data
                and isinstance(data[key], list)
            ):
                return data[key]

        # One dictionary = one job
        return [data]

    raise ValueError(
        "Unsupported JSON format."
    )



def get_job_value(job, target_key):
    """
    Find a JSON key while ignoring capitalization
    and leading/trailing spaces.
    """

    target = target_key.strip().lower()

    for key, value in job.items():

        if str(key).strip().lower() == target:
            return value

    return ""



def process_jobs(
    resume_file,
    input_json,
    output_json
):

    print("=" * 60)
    print("FILES")
    print("=" * 60)

    print("Resume:")
    print(resume_file)

    print("\nInput JSON:")
    print(input_json)

    print("\nOutput JSON:")
    print(output_json)

    # --------------------------------------------------------
    # Read resume
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("EXTRACTING RESUME")
    print("=" * 60)

    resume_text = extract_pdf_text(
        resume_file
    )

    print(
        f"\nResume extracted successfully: "
        f"{len(resume_text):,} characters"
    )

    print("\nResume preview:")
    print("-" * 40)
    print(resume_text[:500])
    print("-" * 40)

    # --------------------------------------------------------
    # Read jobs
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("READING JOB DATA")
    print("=" * 60)

    jobs = load_jobs(input_json)

    print(f"Jobs found: {len(jobs)}")

    if jobs and isinstance(jobs[0], dict):

        print("\nKeys in first job:")

        for key in jobs[0].keys():
            print(f"  - {repr(key)}")

    # --------------------------------------------------------
    # Process each job
    # --------------------------------------------------------

    output_objects = []

    skipped = 0

    for index, job in enumerate(
        jobs,
        start=1
    ):

        if not isinstance(job, dict):

            print(
                f"\nSkipping job #{index}: "
                "not a JSON object."
            )

            skipped += 1
            continue

        company = value_to_text(
            get_job_value(
                job,
                "Company/Organization"
            )
        )

        job_title = value_to_text(
            get_job_value(
                job,
                "Job Title/Job Nature"
            )
        )

        other_information = value_to_text(
            get_job_value(
                job,
                "Other information"
            )
        )

        # ----------------------------------------------------
        # Require a job description
        # ----------------------------------------------------

        if not other_information:

            print(
                f"\nSkipping job #{index}: "
                "'Other information' is empty."
            )

            print(
                "Available keys:",
                list(job.keys())
            )

            skipped += 1
            continue

        # ----------------------------------------------------
        # Generate NEW prompt
        # ----------------------------------------------------

        new_context = create_ai_context(
            resume_text=resume_text,
            job_description=other_information
        )

        # ----------------------------------------------------
        # Verify new prompt is being used
        # ----------------------------------------------------

        print("\n" + "-" * 60)

        print(
            f"[{index}/{len(jobs)}] "
            f"{company} | {job_title}"
        )

        print(
            "Job description length:",
            len(other_information)
        )

        print(
            "Generated prompt length:",
            len(new_context)
        )

        print("\nPrompt ending:")
        print(new_context[-500:])

        print("-" * 60)

        # ----------------------------------------------------
        # Output object
        # ----------------------------------------------------

        new_object = {
            "Company/Organization": company,
            "Job Title/Job Nature": job_title,
            "New_information": new_context
        }

        output_objects.append(
            new_object
        )

    # --------------------------------------------------------
    # Delete old output explicitly
    # --------------------------------------------------------

    if output_json.exists():
        output_json.unlink()

        print(
            "\nOld output JSON deleted."
        )

    # --------------------------------------------------------
    # Write new JSON
    # --------------------------------------------------------

    with open(
        output_json,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output_objects,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("\n" + "=" * 60)
    print("FINISHED")
    print("=" * 60)

    print(
        f"Created: {len(output_objects)} prompts"
    )

    print(
        f"Skipped: {skipped}"
    )

    print(
        "\nNew file saved to:"
    )

    print(
        output_json.resolve()
    )


    return output_objects


def get_deepseek_client():

    print("=" * 70)
    print("DeepSeek Job Analyzer")
    print("=" * 70)

    api_key = getpass(
        "\nEnter your DeepSeek API key: "
    ).strip()

    if not api_key:
        raise ValueError(
            "API key cannot be empty."
        )

    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    return client



def load_prompt_jobs():

    if not PROMPTS_JSON.exists():
        raise FileNotFoundError(
            f"Cannot find:\n{PROMPTS_JSON}"
        )

    with open(
        PROMPTS_JSON,
        "r",
        encoding="utf-8"
    ) as file:

        jobs = json.load(file)

    if not isinstance(jobs, list):
        raise ValueError(
            "hkust_jobs_to_ai.json must contain a JSON list."
        )

    return jobs



def ask_deepseek(client, prompt):

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content



def extract_score(reply):
    """
    Example expected reply:

    overall score: 82/100
    recommendation level: Strongly recommend applying

    Returns:
        82

    If no valid score is found:
        returns -1
    """

    if not reply:
        return -1

    # First try to find:
    # overall score: 82/100

    match = re.search(
        r"overall\s*score\s*:\s*(\d{1,3})\s*/\s*100",
        reply,
        re.IGNORECASE
    )

    if match:
        score = int(match.group(1))

        if 0 <= score <= 100:
            return score

    # Backup:
    # Try to find any "82/100"
    match = re.search(
        r"\b(\d{1,3})\s*/\s*100\b",
        reply
    )

    if match:
        score = int(match.group(1))

        if 0 <= score <= 100:
            return score

    return -1



def save_results(results):

    # Sort by temporary _score
    # Highest score first

    results.sort(
        key=lambda item: item["_score"],
        reverse=True
    )

    # Remove temporary _score before saving
    final_results = []

    for item in results:

        final_results.append(
            {
                "Company/Organization":
                    item["Company/Organization"],

                "Job Title/Job Nature":
                    item["Job Title/Job Nature"],

                "deepseek result":
                    item["deepseek result"]
            }
        )

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            final_results,
            file,
            ensure_ascii=False,
            indent=2
        )



def analyze_jobs():

    # --------------------------------------------------------
    # Ask for API key
    # --------------------------------------------------------


    # --------------------------------------------------------
    # Read jobs
    # --------------------------------------------------------

    jobs = load_prompt_jobs()

    print(
        f"\nFound {len(jobs)} jobs."
    )

    results = []

    if not jobs:
        save_results(results)
        print("No prompts to analyze. Saved an empty result.json.")
        return results

    client = get_deepseek_client()

    # --------------------------------------------------------
    # Analyze every job
    # --------------------------------------------------------

    for index, job in enumerate(
        jobs,
        start=1
    ):

        if not isinstance(job, dict):

            print(
                f"\nSkipping item {index}: "
                "not a JSON object."
            )

            continue

        # ----------------------------------------------------
        # Extract original job information
        # ----------------------------------------------------

        company = job.get(
            "Company/Organization",
            "Unknown Company"
        )

        job_title = job.get(
            "Job Title/Job Nature",
            "Unknown Job"
        )

        prompt = job.get(
            "New_information",
            ""
        )

        # ----------------------------------------------------
        # Check prompt
        # ----------------------------------------------------

        if not prompt or not str(prompt).strip():

            print(
                f"\nSkipping job {index}: "
                "New_information is empty."
            )

            continue

        prompt = str(prompt).strip()

        # ----------------------------------------------------
        # Display current job
        # ----------------------------------------------------

        print("\n")
        print("=" * 70)

        print(
            f"JOB {index}/{len(jobs)}"
        )

        print("=" * 70)

        print(
            f"Company: {company}"
        )

        print(
            f"Job Title: {job_title}"
        )

        print(
            "\nSending to DeepSeek..."
        )

        # ----------------------------------------------------
        # Ask DeepSeek
        # ----------------------------------------------------

        try:

            reply = ask_deepseek(
                client,
                prompt
            )

            if not isinstance(reply, str) or not reply.strip():
                raise ValueError("DeepSeek returned an empty response.")

            # -----------------------------------------------
            # Extract overall score
            # -----------------------------------------------

            score = extract_score(reply)

            # -----------------------------------------------
            # Display response
            # -----------------------------------------------

            print("\nDeepSeek reply:")
            print("-" * 70)

            print(reply)

            print("-" * 70)

            if score >= 0:

                print(
                    f"Detected score: {score}/100"
                )

            else:

                print(
                    "WARNING: Could not detect "
                    "an overall score."
                )

            # -----------------------------------------------
            # Store result
            # -----------------------------------------------

            results.append(
                {
                    "Company/Organization":
                        company,

                    "Job Title/Job Nature":
                        job_title,

                    "deepseek result":
                        reply.strip(),

                    # Temporary field used ONLY for sorting
                    "_score":
                        score
                }
            )

            # -----------------------------------------------
            # Save progress after every successful request
            # -----------------------------------------------

            save_results(results)

            print(
                f"Progress saved to result.json "
                f"({len(results)} results)"
            )

        except Exception as error:

            print(
                "\nDeepSeek API error:"
            )

            print(
                f"{type(error).__name__}: "
                f"{error}"
            )

    # --------------------------------------------------------
    # Final sorting + save
    # --------------------------------------------------------

    save_results(results)

    print("\n")
    print("=" * 70)
    print("FINISHED")
    print("=" * 70)

    print(
        f"Successfully analyzed: "
        f"{len(results)} jobs"
    )

    print(
        "\nResults sorted from "
        "highest score to lowest score."
    )

    print(
        f"\nSaved to:\n{OUTPUT_JSON}"
    )


    return results


def ai_analyze():
    """Generate and save prompts, then analyze and save sorted replies."""
    process_jobs(
        resume_file=RESUME_PDF,
        input_json=INPUT_JSON,
        output_json=PROMPTS_JSON,
    )
    return analyze_jobs()



def main():

    # ========================================================
    # Create Chrome
    # ========================================================

    # Keep the exporter and AI input on the same file, regardless of the
    # original exporter's hard-coded output directory.
    job_exporter.OUTPUT_FILE = INPUT_JSON

    driver = create_driver()


    try:

        # ====================================================
        # 1. Login
        # ====================================================

        login_to_hkust(
            driver
        )


        # ====================================================
        # 2. Business Nature
        # ====================================================

        selected_business_natures = (
            choose_business_natures(
                driver
            )
        )


        # ====================================================
        # 3. Job Nature
        # ====================================================

        selected_job_natures = (
            choose_job_natures(
                driver
            )
        )


        # ====================================================
        # 4. Employment Type
        # ====================================================

        selected_employment_types = (
            choose_employment_types(
                driver
            )
        )


        # ====================================================
        # 5. Working Location
        # ====================================================

        selected_working_locations = (
            choose_working_locations(
                driver
            )
        )


        # ====================================================
        # 6. Levels of Qualification
        # ====================================================

        selected_qualification_levels = (
            choose_qualification_levels(
                driver
            )
        )


        # ====================================================
        # 7. Employment Mode
        # ====================================================

        selected_employment_modes = (
            choose_employment_modes(
                driver
            )
        )


        # ====================================================
        # 8. Language
        # ====================================================

        selected_languages = (
            choose_languages(
                driver
            )
        )


        # ====================================================
        # Filters completed
        # ====================================================

        print()
        print("=" * 70)

        print(
            "All filter conditions have been selected."
        )

        print("=" * 70)

        print()
        print(
            "Applying filters to the HKUST Job Board..."
        )


        # ====================================================
        # Apply Business Nature
        # ====================================================

        apply_business_natures(
            driver,
            selected_business_natures
        )


        # ====================================================
        # Apply Job Nature
        # ====================================================

        apply_job_natures(
            driver,
            selected_job_natures
        )


        # ====================================================
        # Apply Employment Type
        # ====================================================

        apply_employment_types(
            driver,
            selected_employment_types
        )


        # ====================================================
        # Apply Working Location
        # ====================================================

        apply_working_locations(
            driver,
            selected_working_locations
        )


        # ====================================================
        # Apply Qualification
        # ====================================================

        apply_qualification_levels(
            driver,
            selected_qualification_levels
        )


        # ====================================================
        # Apply Employment Mode
        # ====================================================

        apply_employment_modes(
            driver,
            selected_employment_modes
        )


        # ====================================================
        # Apply Language
        # ====================================================

        apply_languages(
            driver,
            selected_languages
        )


        # ====================================================
        # 9. Submit search
        # ====================================================

        submit_filter(
            driver
        )


        # ====================================================
        # 10. Generate JSON
        #
        # This function:
        #
        # 1. Collects jobs from all reachable result pages
        # 2. Reads all job detail pages
        # 3. Retries failed jobs
        # 4. Generates the JSON result
        # 5. Saves JSON to the specified folder
        #
        # No 20-job detail output is used.
        # ====================================================

        all_job_data = (
            job_exporter.print_first_two_pages_job_details(
                driver
            )
        )


        # ====================================================
        # 11. Generate prompts and analyze the exported jobs
        # ====================================================

        if all_job_data:
            analysis_results = ai_analyze()
        else:
            # Do not analyze stale output or request a key for empty results.
            with PROMPTS_JSON.open("w", encoding="utf-8") as file:
                json.dump([], file, ensure_ascii=False, indent=2)
            save_results([])
            analysis_results = []
            print("No jobs exported. Saved empty prompt and result files.")

        print()
        print("=" * 70)

        print(
            f"Finished. "
            f"{len(all_job_data)} jobs were written to JSON."
        )

        print()

        print(
            "JSON file location:"
        )

        print(
            INPUT_JSON
        )

        print("=" * 70)


        # ====================================================
        # Keep browser open until user finishes
        # ====================================================

        print(f"\nAI responses saved: {len(analysis_results)}")
        print(f"Prompts: {PROMPTS_JSON}")
        print(f"Ranked results: {OUTPUT_JSON}")

        input(
            "\nPress Enter to close the browser..."
        )

        return analysis_results


    finally:

        driver.quit()



if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram stopped by user. Any saved progress is retained.")
        raise SystemExit(130)
    except Exception as error:
        print(f"\nProgram error: {type(error).__name__}: {error}")
        raise SystemExit(1)
