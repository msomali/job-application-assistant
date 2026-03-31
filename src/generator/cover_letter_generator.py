"""Generate tailored cover letters using Claude + LaTeX."""

import json
import logging
import re
import subprocess
from pathlib import Path

import anthropic
from anthropic import APIError, APITimeoutError, RateLimitError

from src.generator.resume_generator import _find_pdflatex
from src.models import CoverLetterContent, JobAnalysis, JobPosting
from src.privacy import PIIGuard
from src.utils import retry

logger = logging.getLogger(__name__)

MASTER_RESUME_PATH = Path(__file__).parent.parent.parent / "data" / "master_resume.json"
SCREENING_PATH = Path(__file__).parent.parent.parent / "data" / "screening_answers.json"

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "cover_letter.tex"

COVER_LETTER_SYSTEM_PROMPT = """\
You are an expert cover letter writer. Write a compelling, personalized cover letter.

Write a cover letter that sounds like a real person wrote it. Natural, warm, and confident.

IMPORTANT STYLE RULES:
- Write in a natural, human voice. No corporate jargon or AI-sounding phrases.
- DO NOT use hyphens or em dashes to connect ideas. Use normal sentence structure.
- Be genuine and specific. Avoid generic statements that could apply to any company.
- Keep it conversational but professional.

Content guidelines:
- Open with genuine enthusiasm for the specific role and company (no generic openings)
- Connect 2-3 of the candidate's strongest experiences directly to the job requirements
- Show knowledge of the company (infer from the job posting)
- Close with confidence and a clear call to action
- Keep it concise: 3-4 paragraphs total

Return a JSON object with these fields:
- "greeting": string (e.g., "Dear Hiring Manager,")
- "opening_paragraph": string
- "body_paragraphs": list of 1-2 strings
- "closing_paragraph": string
- "sign_off": string (e.g., "Sincerely,")

Return ONLY valid JSON, no markdown fences."""


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(APIError, APITimeoutError, RateLimitError))
def generate_cover_letter_content(
    job: JobPosting, analysis: JobAnalysis, master_resume: dict, *, redact: bool = True
) -> CoverLetterContent:
    """Use Claude to generate tailored cover letter content.

    Args:
        job: The job posting to write the cover letter for.
        analysis: The job analysis with matching skills.
        master_resume: The candidate's full resume data.
        redact: If True, redact PII before sending to Claude. Default True.
    """
    logger.info("Generating cover letter for %s at %s", job.title, job.company)
    client = anthropic.Anthropic()

    guard = None
    resume_for_llm = master_resume
    if redact:
        guard = PIIGuard.from_files(MASTER_RESUME_PATH, SCREENING_PATH)
        resume_for_llm = guard.redact_dict(master_resume)
        logger.info("PII redacted: %d fields protected", guard.field_count)

    requirements_text = "\n".join(f"- {r}" for r in job.requirements)
    matching_text = ", ".join(analysis.matching_skills)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=[
            {
                "type": "text",
                "text": COVER_LETTER_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"## Candidate Profile\n{json.dumps(resume_for_llm, separators=(',', ':'))}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"## Job Posting\nTitle: {job.title}\nCompany: {job.company}\n"
                            f"Location: {job.location or 'Not specified'}\n"
                            f"Description: {job.description}\n\n"
                            f"## Key Requirements\n{requirements_text}\n\n"
                            f"## Candidate's Matching Skills\n{matching_text}\n\n"
                            f"## Tailoring Strategy\n{analysis.tailoring_strategy}"
                        ),
                    },
                ],
            }
        ],
    )

    response_text = message.content[0].text.strip()
    # Strip markdown code fences if present
    response_text = re.sub(r"^\s*```(?:json)?\s*", "", response_text)
    response_text = re.sub(r"\s*```\s*$", "", response_text)
    if guard:
        response_text = guard.restore(response_text)

    data = json.loads(response_text)
    logger.info("Cover letter content generated successfully")
    return CoverLetterContent(**data)


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters."""
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def render_cover_letter(
    content: CoverLetterContent, master_resume: dict, output_dir: Path
) -> Path:
    """Render cover letter content to PDF via LaTeX."""
    logger.info("Rendering cover letter PDF to %s", output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    template = TEMPLATE_PATH.read_text()

    name = _escape_latex(master_resume.get("name", "Your Name"))
    contact = _escape_latex(master_resume.get("contact", ""))

    body_paragraphs = "\n\n".join(
        _escape_latex(p) for p in content.body_paragraphs
    )

    latex = template.replace("%%NAME%%", name)
    latex = latex.replace("%%CONTACT%%", contact)
    latex = latex.replace("%%GREETING%%", _escape_latex(content.greeting))
    latex = latex.replace(
        "%%OPENING%%", _escape_latex(content.opening_paragraph)
    )
    latex = latex.replace("%%BODY%%", body_paragraphs)
    latex = latex.replace(
        "%%CLOSING%%", _escape_latex(content.closing_paragraph)
    )
    latex = latex.replace("%%SIGNOFF%%", _escape_latex(content.sign_off))

    tex_file = output_dir / "cover_letter.tex"
    tex_file.write_text(latex)

    pdflatex = _find_pdflatex()
    subprocess.run(
        [pdflatex, "-interaction=nonstopmode", "-output-directory", str(output_dir), str(tex_file)],
        capture_output=True,
        check=True,
        timeout=30,
    )

    pdf_path = output_dir / "cover_letter.pdf"
    if not pdf_path.exists():
        logger.error("Cover letter PDF generation failed. Check %s for logs.", output_dir)
        raise RuntimeError(f"PDF generation failed. Check {output_dir} for logs.")
    logger.info("Cover letter PDF generated: %s", pdf_path)
    return pdf_path
