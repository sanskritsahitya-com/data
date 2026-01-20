"""
Chapter Summarizer using Google Gemini Batch API

This script generates chapter summaries for Sanskrit texts using the Gemini Batch API.
It aggregates verses by chapter, creates batch requests, submits them to the API,
and processes the results.
"""

import json
import os
import sys
import time
import argparse
from typing import Dict, List, Any, Optional

from google import genai
from google.genai import types
from file_utils import load_text, write_text


# Configuration Constants
DEFAULT_TEXT_FILE = "srimadbhagavadgita"
DEFAULT_MODE = "summarize"  # Options: "summarize" or "proofread"
MODEL_NAME = "gemini-3-flash-preview"
POLL_INTERVAL_SECONDS = 15

# Job State Constants
SUCCESS_STATES = ["SUCCEEDED", "COMPLETED"]
FAILURE_STATES = ["FAILED", "CANCELLED", "EXPIRED"]

SUMMARY_PROMPT_TEMPLATE = """
**Role:** You are a Sanskrit literature scholar tasked with writing a concise thematic summary of a text.

**Task:** Synthesize the chapter's content into a single paragraph of under 90 words.

**The Style Rules:**
1. **Direct Narrative:** Focus on the *concrete imagery and actions* in the text. Avoid abstract academic jargon like "crystallizes," "mirrors," "juxtaposes," or "paradigm."
2. **No Meta-Talk:** Do not mention the chapter name, number, or author. Begin directly with the subject matter.
3. **The "Program Note" Tone:** Write in a way that is informative but effortless. Use active, grounded verbs.
4. **Grounded Literary Facts:** If you mention a famous verse or literary device, weave it in as a factual detail rather than a "highlight." Use IAST romanization for all Sanskrit terms. Don't overuse Sanskrit terms.
5. **No Superlatives:** Avoid "purple prose" and hollow adjectives like "vivid," "masterful," "exquisite," or "profound." Let the specific details of the Sanskrit text carry the weight.

The subtitle should answer the question "What happens in this chapter? OR What is the theme of this chapter?" in under 10 words and high-school level English. When writing the subtitle, focus on factuality and matter-of-factness rather than lyrical value. 

Output format: You should output a json object with a single key matching the chapter number EXACTLY AS PROVIDED (including any decimal points) and the value should be an object containing the subtitle and summary.
Example: {{"{chapter_number}": {{"subtitle": "Subtitle for this chapter", "es": "Summary of this chapter" }} }}

IMPORTANT: The key in your JSON output MUST be exactly "{chapter_number}" - do not modify or truncate it.

Input:
Text Name: {text_name}
Chapter Number: {chapter_number}
Chapter Name: {chapter_name}
Verses and their summaries:

{verses}
"""

PROOFREADING_PROMPT_TEMPLATE = """
**Role:** You are a Philologist and Sanskrit Editor specializing in the precise, non-sectarian translation of classical Indian texts. Your goal is to audit a series of chapter summaries for factual accuracy and stylistic consistency.

**The Context:** You are reviewing summaries of {text_name}. The goal is to provide an overall summary for a reader that focuses on what the text *actually says* rather than interpretations.

**Your Audit Task:**
1.  **Factual Verification:** Ensure the characters, locations, and specific actions match the Sanskrit source.
2.  **Terminology Neutrality:** Avoid "Interpretation Creep." Do not use loaded philosophical labels and prefer the Sanskrit term if present. Use IAST for Sanskrit terms.
3.  **Check for "Academic Fluff":** Strip away any remaining abstract jargon (e.g., "This chapter explores the duality of...") and replace it with direct action (e.g., "Kṛṣṇa distinguishes between...").
4.  **IAST Audit:** Ensure all Sanskrit terms are in correct IAST (e.g., *Kṛṣṇa* not Krishna; *Sītā* not Sita).

The summary will be provided with the "es" key in the JSON object and the chapter subtitle with the "subtitle" key.

**The Style Constraints (Strict Adherence Required):**
*   **Length:** Each summary must remain under 90 words.
*   **Tone:** Grounded, factual, and effortless.
*   **No Superlatives:** Remove words like "profound," "incredible," "beautiful," or "essential."
*   **No Meta-talk:** No "In this chapter," or "The poet describes." Start with the action.
*   **Subtitle:** Factual, <10 words, high-school English.

Here is an example summary of the 6th canto of Raghuvansham: 

In a grand assembly, Indumatī moves past the kings of various lands. Kālidāsa uses the famous 'Dīpaśikhā' (lamp-flame) metaphor here: as Indumatī passes each suitor, his face falls into gloom like a building in the dark once the lamp has moved past. She finally chooses Aja, recognizing his intrinsic virtues. The union of the Ikṣvāku prince and the Vidarbha princess is described as the perfect marriage of 'gem and gold'.

**Input Format:** You will receive a JSON object of the current summaries.
**Output Format:** Produce an updated JSON object in the exact same format. For each chapter, add an additional key called "notes" where you will detail the changes you made.

{input_json_string}
"""


def get_api_key() -> str:
    """Retrieve the Google API key from environment variables."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    return api_key


def aggregate_verses_by_chapter(text_data: Any) -> Dict[str, List[str]]:
    """
    Aggregate verses by chapter from text data.

    Args:
        text_data: Text data object containing verses and chapter information

    Returns:
        Dictionary mapping chapter numbers to lists of formatted verse strings
    """
    chapter_verse_map = {}

    for verse_data in text_data.data:
        # Skip verses without content
        if not verse_data.v:
            continue

        chapter_num = verse_data.c
        if chapter_num not in chapter_verse_map:
            chapter_verse_map[chapter_num] = []

        # Format: chapter.verse_num \t verse_text \t summary (if exists)
        summary_text = f"Summary: {verse_data.es}" if verse_data.es else ""
        verse_entry = f"{verse_data.c}.{verse_data.n}\t{verse_data.v}\t{summary_text}"
        chapter_verse_map[chapter_num].append(verse_entry)

    return chapter_verse_map


def create_batch_requests(
    text_data: Any, chapter_verse_map: Dict[str, List[str]]
) -> List[Dict[str, Any]]:
    """
    Create batch API request entries for each chapter (summarize mode).

    Args:
        text_data: Text data object containing title and chapter information
        chapter_verse_map: Dictionary mapping chapter numbers to verse lists

    Returns:
        List of batch request dictionaries
    """
    batch_requests = []
    text_name = text_data.title
    chapter_names = {chapter.number: chapter.name for chapter in text_data.chapters}

    for chapter_num, verses_list in chapter_verse_map.items():
        chapter_name = chapter_names.get(chapter_num, f"Chapter {chapter_num}")
        verses_text = "\n".join(verses_list)

        # Format the prompt with chapter-specific data
        final_prompt = SUMMARY_PROMPT_TEMPLATE.format(
            text_name=text_name,
            chapter_number=chapter_num,
            chapter_name=chapter_name,
            verses=verses_text,
        )

        # Create batch API request entry
        request_entry = {
            "custom_id": f"{text_name}-chapter-{chapter_num}",
            "request": {
                "contents": [{"role": "user", "parts": [{"text": final_prompt}]}]
            },
        }
        batch_requests.append(request_entry)

    return batch_requests


def create_proofread_batch_request(
    text_data: Any, final_output_file: str
) -> List[Dict[str, Any]]:
    """
    Create a single batch API request for proofreading all chapters.

    Args:
        text_data: Text data object containing title
        final_output_file: Path to the JSON file containing chapter summaries

    Returns:
        List containing a single batch request dictionary
    """
    # Load the existing summaries from the final output file
    try:
        with open(final_output_file, "r", encoding="utf-8") as f:
            chapters_json = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Cannot find {final_output_file}. Run in 'summarize' mode first."
        )

    # Convert the chapters JSON to a formatted string
    input_json_string = json.dumps(chapters_json, indent=2, ensure_ascii=False)

    # Format the proofreading prompt
    text_name = text_data.title
    final_prompt = PROOFREADING_PROMPT_TEMPLATE.format(
        text_name=text_name, input_json_string=input_json_string
    )

    # Create a single batch request
    request_entry = {
        "custom_id": f"{text_name}-proofread-all",
        "request": {"contents": [{"role": "user", "parts": [{"text": final_prompt}]}]},
    }

    return [request_entry]


def write_batch_requests_to_file(
    batch_requests: List[Dict[str, Any]], batch_input_file: str
) -> None:
    """
    Write batch requests to a JSONL file.

    Args:
        batch_requests: List of batch request dictionaries
        batch_input_file: Output filename for the JSONL file
    """
    with open(batch_input_file, "w", encoding="utf-8") as f:
        for request in batch_requests:
            f.write(json.dumps(request) + "\n")

    print(f"Prepared {len(batch_requests)} requests in {batch_input_file}")


def create_or_resume_batch_job(
    client: genai.Client,
    batch_job_display_name: str,
    job_name: Optional[str] = None,
    batch_input_file: Optional[str] = None,
) -> Any:
    """
    Create a new batch job or resume an existing one.

    Args:
        client: Gemini API client
        batch_job_display_name: Display name for the batch job
        job_name: Optional job name to resume an existing job
        batch_input_file: Input JSONL file for new jobs

    Returns:
        Batch job object
    """
    if job_name:
        print(f"Resuming monitoring for existing job: {job_name}")
        try:
            return client.batches.get(name=job_name)
        except Exception as e:
            raise RuntimeError(f"Error finding job {job_name}: {e}")

    # Create new batch job
    print("Uploading file to Google GenAI...")
    batch_file = client.files.upload(
        file=batch_input_file, config={"mime_type": "text/plain"}
    )
    print(f"File uploaded: {batch_file.name}")

    print("Submitting Batch Job...")
    try:
        job = client.batches.create(
            model=MODEL_NAME,
            src=batch_file.name,
            config=types.CreateBatchJobConfig(display_name=batch_job_display_name),
        )
    except Exception as e:
        raise RuntimeError(f"Error creating batch job: {e}")

    print(f"Batch Job created successfully!")
    print(f"Job Name: {job.name}")
    return job


def poll_job_until_complete(client: genai.Client, job: Any) -> Any:
    """
    Poll the batch job until it reaches a terminal state.

    Args:
        client: Gemini API client
        job: Batch job object

    Returns:
        Completed job object

    Raises:
        RuntimeError: If job fails or is cancelled
    """
    print(f"Initial State: {job.state}")
    print("Waiting for batch job to complete...")

    while True:
        try:
            job = client.batches.get(name=job.name)
        except Exception as e:
            print(f"Error checking status: {e}. Retrying...")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        state_str = str(job.state)
        print(f"Current State: {state_str}")

        # Check for success
        if any(success_state in state_str for success_state in SUCCESS_STATES):
            print("Job completed successfully!")
            return job

        # Check for failure
        if any(failure_state in state_str for failure_state in FAILURE_STATES):
            error_msg = f"Job ended with failure state: {state_str}"
            if hasattr(job, "error") and job.error:
                error_msg += f"\nError details: {job.error}"
            raise RuntimeError(error_msg)

        time.sleep(POLL_INTERVAL_SECONDS)


def extract_text_from_response(batch_item: Dict[str, Any]) -> Optional[str]:
    """
    Extract text content from a batch API response item.

    Args:
        batch_item: Single batch response item

    Returns:
        Extracted text content or None if extraction fails
    """
    try:
        response = batch_item.get("response", {})
        candidates = response.get("candidates", [])

        if not candidates:
            return None

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        if not parts:
            return None

        return parts[0].get("text")
    except (KeyError, IndexError, TypeError):
        return None


def clean_json_response(text: str) -> str:
    """
    Clean markdown code blocks from JSON response text.

    Args:
        text: Raw response text

    Returns:
        Cleaned text without markdown code blocks
    """
    return text.replace("```json", "").replace("```", "").strip()


def parse_batch_results(content: bytes) -> Dict[str, Any]:
    """
    Parse batch API results from JSONL content.

    Args:
        content: Raw JSONL content from batch API

    Returns:
        Dictionary of merged chapter summaries
    """
    merged_results = {}

    for line in content.splitlines():
        if not line.strip():
            continue

        try:
            batch_item = json.loads(line)
            text_response = extract_text_from_response(batch_item)

            if not text_response:
                continue

            clean_text = clean_json_response(text_response)

            try:
                chapter_data = json.loads(clean_text)
                merged_results.update(chapter_data)
            except json.JSONDecodeError as je:
                custom_id = batch_item.get("custom_id", "unknown")
                print(f"JSON decode error for {custom_id}: {je}")
        except Exception as e:
            print(f"Error processing line: {e}")

    return merged_results


def sort_results_by_chapter(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sort results by chapter number (numerically if possible).

    Args:
        results: Unsorted results dictionary

    Returns:
        Sorted results dictionary
    """
    try:
        return dict(sorted(results.items(), key=lambda item: int(item[0])))
    except ValueError:
        return results


def download_and_process_results(
    client: genai.Client,
    job: Any,
    text_data: Any,
    text_file_name: str,
    raw_output_file: str,
    final_output_file: str,
    mode: str = "summarize",
) -> None:
    """
    Download batch job results and process them.

    Args:
        client: Gemini API client
        job: Completed batch job
        text_data: Text data object to update with summaries
        text_file_name: Name of the text file to save
        raw_output_file: Path to save raw JSONL output
        final_output_file: Path to save final JSON output
        mode: Processing mode ("summarize" or "proofread")
    """
    if not job.dest.file_name:
        raise RuntimeError("Job finished but no output file found")

    print(f"Downloading results from {job.dest.file_name}...")
    content = client.files.download(file=job.dest.file_name)

    # Save raw output
    with open(raw_output_file, "wb") as f:
        f.write(content)
    print(f"Raw results saved to {raw_output_file}")

    # Parse and merge results
    merged_results = parse_batch_results(content)
    sorted_results = sort_results_by_chapter(merged_results)

    # Save final output
    with open(final_output_file, "w", encoding="utf-8") as f:
        json.dump(sorted_results, f, indent=2, ensure_ascii=False)
    print(f"Parsed and merged results saved to {final_output_file}")

    # Update text data with summaries
    for chapter in text_data.chapters:
        chapter_key = chapter.number
        if chapter_key in sorted_results:
            # In proofread mode, the keys might be 'subtitle' and 'summary' or 'es'
            if "subtitle" in sorted_results[chapter_key]:
                chapter.subtitle = sorted_results[chapter_key]["subtitle"]
            if "summary" in sorted_results[chapter_key]:
                chapter.es = sorted_results[chapter_key]["summary"]
            elif "es" in sorted_results[chapter_key]:
                chapter.es = sorted_results[chapter_key]["es"]

    write_text(text_data, text_file_name)
    print(f"Text data updated with summaries saved to {text_file_name}")


def cleanup_temporary_files(batch_input_file: str, raw_output_file: str) -> None:
    """
    Remove temporary files created during batch processing.

    Args:
        batch_input_file: Path to batch input JSONL file
        raw_output_file: Path to raw output JSONL file
    """
    temp_files = [batch_input_file, raw_output_file]

    for file_path in temp_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            print(f"Warning: Could not remove {file_path}: {e}")


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Generate or proofread chapter summaries for Sanskrit texts using Google Gemini Batch API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate summaries for Bhagavad Gita
  python genai_chapter_summarizer.py --text-name srimadbhagavadgita --mode summarize
  
  # Proofread existing summaries
  python genai_chapter_summarizer.py --text-name srimadbhagavadgita --mode proofread
  
  # Resume an existing job
  python genai_chapter_summarizer.py --text-name raghuvansham --mode summarize --job-name projects/123/locations/us-central1/batchPredictionJobs/456
        """,
    )

    parser.add_argument(
        "--text-name",
        type=str,
        default=DEFAULT_TEXT_FILE,
        help=f"Name of the text file to process (default: {DEFAULT_TEXT_FILE})",
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["summarize", "proofread"],
        default=DEFAULT_MODE,
        help=f"Processing mode: 'summarize' to generate summaries, 'proofread' to audit existing summaries (default: {DEFAULT_MODE})",
    )

    parser.add_argument(
        "--job-name",
        type=str,
        default=None,
        help="Optional job name to resume an existing batch job (e.g., projects/123/locations/us-central1/batchPredictionJobs/456)",
    )

    return parser.parse_args()


def main() -> None:
    """Main execution function."""
    try:
        # Parse command line arguments
        args = parse_arguments()

        text_file_name = args.text_name
        mode = args.mode
        job_name = args.job_name

        print(f"Running in {mode.upper()} mode for text: {text_file_name}")

        # Generate file paths based on text name
        batch_input_file = text_file_name + "_batch_input.jsonl"
        raw_output_file = text_file_name + "_summary_results_raw.jsonl"
        final_output_file = text_file_name + "summary_final.json"
        batch_job_display_name = text_file_name + "summary_batch"

        # Load text data
        text_data = load_text(text_file_name)

        # Create batch requests based on mode
        if mode == "summarize":
            # Aggregate verses by chapter
            chapter_verse_map = aggregate_verses_by_chapter(text_data)
            # Create batch requests for summarization
            batch_requests = create_batch_requests(text_data, chapter_verse_map)
        elif mode == "proofread":
            # Create a single batch request for proofreading
            batch_requests = create_proofread_batch_request(
                text_data, final_output_file
            )
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'summarize' or 'proofread'.")

        write_batch_requests_to_file(batch_requests, batch_input_file)

        # Initialize Gemini client
        api_key = get_api_key()
        client = genai.Client(api_key=api_key)

        # Create or resume batch job
        job = create_or_resume_batch_job(
            client, batch_job_display_name, job_name, batch_input_file
        )

        # Poll until completion
        job = poll_job_until_complete(client, job)

        # Download and process results
        download_and_process_results(
            client,
            job,
            text_data,
            text_file_name,
            raw_output_file,
            final_output_file,
            mode,
        )

        # Clean up temporary files
        cleanup_temporary_files(batch_input_file, raw_output_file)

        print(f"\n✓ {mode.upper()} process completed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
