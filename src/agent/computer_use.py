"""Browser automation for job applications using Claude Computer Use + Playwright.

Claude sees screenshots and decides what to click/type. Playwright executes the actions.
This gives Claude visual understanding of application forms while we maintain
programmatic browser control.
"""

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any

import anthropic
from playwright.async_api import Page, async_playwright

from src.agent.telegram_bot import request_approval, send_notification, send_photo

logger = logging.getLogger(__name__)

# Screen dimensions for Claude Computer Use
DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 800

# Beta header and tool version for Claude Computer Use
# Use latest version for Opus 4.6 / Sonnet 4.6 / Opus 4.5
BETA_HEADER = "computer-use-2025-11-24"
TOOL_VERSION = "20251124"
MODEL = "claude-sonnet-4-20250514"

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"


async def _take_screenshot(page: Page) -> str:
    """Take a screenshot and return as base64-encoded PNG."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_bytes = await page.screenshot(full_page=False)
    return base64.standard_b64encode(screenshot_bytes).decode("utf-8")


async def _save_screenshot(page: Page, name: str) -> str:
    """Take a screenshot and save to disk. Returns the file path."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOTS_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=False)
    return str(path)


async def _execute_action(page: Page, action: dict) -> str | None:
    """Execute a Computer Use action on the Playwright page.

    Returns base64 screenshot after action, or None if action is screenshot.
    """
    action_type = action.get("action")

    if action_type == "screenshot":
        return await _take_screenshot(page)

    elif action_type == "left_click":
        x, y = action["coordinate"]
        await page.mouse.click(x, y)

    elif action_type == "right_click":
        x, y = action["coordinate"]
        await page.mouse.click(x, y, button="right")

    elif action_type == "double_click":
        x, y = action["coordinate"]
        await page.mouse.dblclick(x, y)

    elif action_type == "middle_click":
        x, y = action["coordinate"]
        await page.mouse.click(x, y, button="middle")

    elif action_type == "mouse_move":
        x, y = action["coordinate"]
        await page.mouse.move(x, y)

    elif action_type == "type":
        text = action.get("text", "")
        await page.keyboard.type(text, delay=50)

    elif action_type == "key":
        key = action.get("text", "")
        # Map Claude's key names to Playwright key names
        key_map = {
            "Return": "Enter",
            "BackSpace": "Backspace",
            "space": " ",
            "Tab": "Tab",
            "Escape": "Escape",
            "Up": "ArrowUp",
            "Down": "ArrowDown",
            "Left": "ArrowLeft",
            "Right": "ArrowRight",
        }
        # Handle modifier combos like "ctrl+a"
        if "+" in key:
            parts = key.split("+")
            modifiers = []
            final_key = parts[-1]
            for mod in parts[:-1]:
                mod_lower = mod.lower().strip()
                if mod_lower in ("ctrl", "control"):
                    modifiers.append("Control")
                elif mod_lower in ("alt", "option"):
                    modifiers.append("Alt")
                elif mod_lower in ("shift",):
                    modifiers.append("Shift")
                elif mod_lower in ("meta", "super", "command", "cmd"):
                    modifiers.append("Meta")
            for m in modifiers:
                await page.keyboard.down(m)
            await page.keyboard.press(key_map.get(final_key, final_key))
            for m in reversed(modifiers):
                await page.keyboard.up(m)
        else:
            await page.keyboard.press(key_map.get(key, key))

    elif action_type == "scroll":
        x, y = action["coordinate"]
        direction = action.get("direction", "down")
        amount = action.get("amount", 3)
        delta = amount * 100
        if direction == "up":
            delta = -delta
        elif direction == "left":
            await page.mouse.move(x, y)
            await page.evaluate(f"window.scrollBy(-{delta}, 0)")
            await asyncio.sleep(0.3)
            return await _take_screenshot(page)
        elif direction == "right":
            await page.mouse.move(x, y)
            await page.evaluate(f"window.scrollBy({delta}, 0)")
            await asyncio.sleep(0.3)
            return await _take_screenshot(page)
        await page.mouse.move(x, y)
        await page.mouse.wheel(0, delta)

    elif action_type == "drag":
        sx, sy = action.get("start_coordinate", action.get("coordinate", [0, 0]))
        ex, ey = action["end_coordinate"]
        await page.mouse.move(sx, sy)
        await page.mouse.down()
        await page.mouse.move(ex, ey, steps=10)
        await page.mouse.up()

    elif action_type == "wait":
        await asyncio.sleep(action.get("duration", 2))

    # Brief pause after action, then screenshot
    await asyncio.sleep(0.5)
    return await _take_screenshot(page)


def _build_tools() -> list[dict]:
    """Build the Computer Use tool definition."""
    return [
        {
            "type": f"computer_{TOOL_VERSION}",
            "name": "computer",
            "display_width_px": DISPLAY_WIDTH,
            "display_height_px": DISPLAY_HEIGHT,
        }
    ]


async def _computer_use_loop(
    page: Page,
    task_prompt: str,
    master_resume: dict,
    resume_path: str,
    cover_letter_path: str,
    max_steps: int = 50,
) -> dict[str, Any]:
    """Run the Computer Use agentic loop.

    Claude sees screenshots, decides actions, we execute them via Playwright.
    Stops when Claude says it's done or we hit max_steps.
    """
    logger.info("Starting computer use loop (max_steps=%d)", max_steps)
    client = anthropic.Anthropic()

    # Take initial screenshot
    initial_screenshot = await _take_screenshot(page)

    # Load screening answers knowledge base
    qa_path = Path(__file__).parent.parent.parent / "data" / "screening_answers.json"
    screening_answers = {}
    if qa_path.exists():
        screening_answers = json.loads(qa_path.read_text())

    # Build contact info from either structured or string contact field
    contact = master_resume.get("contact", "")
    if isinstance(contact, dict):
        contact_info = (
            f"- Name: {master_resume.get('name', '')}\n"
            f"- Email: {contact.get('email', '')}\n"
            f"- Phone: {contact.get('phone', '')}\n"
            f"- Location: {contact.get('city', '')}, {contact.get('state', '')}\n"
            f"- LinkedIn: {contact.get('linkedin', '')}\n"
            f"- GitHub: {contact.get('github', '')}\n"
            f"- Website: {contact.get('website', '')}"
        )
    else:
        personal = screening_answers.get("personal", {})
        contact_info = (
            f"- Name: {personal.get('full_name', master_resume.get('name', ''))}\n"
            f"- Email: {personal.get('email', '')}\n"
            f"- Phone: {personal.get('phone', '')}\n"
            f"- Location: {personal.get('city', '')}, {personal.get('state', '')}\n"
            f"- LinkedIn: {personal.get('linkedin', '')}\n"
            f"- GitHub: {personal.get('github', '')}\n"
            f"- Website: {personal.get('website', '')}"
        )

    # Format screening Q&A for the prompt
    qa_sections = []
    if screening_answers.get("work_authorization"):
        wa = screening_answers["work_authorization"]
        qa_sections.append(
            "WORK AUTHORIZATION:\n"
            f"- Authorized to work in US: {'Yes' if wa.get('authorized_to_work_in_us') else 'No'}\n"
            f"- Require sponsorship: {'Yes' if wa.get('require_sponsorship') else 'No'}\n"
            f"- Visa status: {wa.get('visa_status', 'N/A')}"
        )
    if screening_answers.get("experience"):
        exp = screening_answers["experience"]
        exp_lines = [f"- {k.replace('years_', '').replace('_', ' ').title()}: {v}" for k, v in exp.items()]
        qa_sections.append("YEARS OF EXPERIENCE:\n" + "\n".join(exp_lines))
    if screening_answers.get("education"):
        edu = screening_answers["education"]
        qa_sections.append(
            "EDUCATION:\n"
            f"- Highest degree: {edu.get('highest_degree', '')}\n"
            f"- Field: {edu.get('degree_field', '')}\n"
            f"- University: {edu.get('university', '')}\n"
            f"- Graduation: {edu.get('graduation_year', '')}"
        )
    if screening_answers.get("job_preferences"):
        pref = screening_answers["job_preferences"]
        qa_sections.append(
            "JOB PREFERENCES:\n"
            f"- Desired salary: {pref.get('desired_salary', 'Negotiable')}\n"
            f"- Start date: {pref.get('start_date', 'Flexible')}\n"
            f"- Willing to relocate: {'Yes' if pref.get('willing_to_relocate') else 'No'}\n"
            f"- Remote preference: {pref.get('remote_preference', 'Open')}\n"
            f"- Travel: {pref.get('travel_percentage', 'N/A')}"
        )
    if screening_answers.get("common_questions"):
        cq = screening_answers["common_questions"]
        cq_lines = []
        for k, v in cq.items():
            if isinstance(v, bool):
                v = "Yes" if v else "No"
            label = k.replace("_", " ").title()
            cq_lines.append(f"Q: {label}\nA: {v}")
        qa_sections.append("COMMON SCREENING QUESTIONS:\n" + "\n\n".join(cq_lines))
    if screening_answers.get("diversity"):
        div = screening_answers["diversity"]
        qa_sections.append(
            "EEO/DIVERSITY (only if required):\n"
            f"- Gender: {div.get('gender', 'Prefer not to say')}\n"
            f"- Race/Ethnicity: {div.get('race_ethnicity', 'Prefer not to say')}\n"
            f"- Veteran: {div.get('veteran_status', 'Prefer not to say')}\n"
            f"- Disability: {div.get('disability_status', 'Prefer not to say')}"
        )

    qa_block = "\n\n".join(qa_sections)

    # Load cached answers from database
    from src.db.database import init_db as _init_db, list_answers
    _init_db()
    cached = list_answers(limit=100)
    cached_block = ""
    if cached:
        cached_lines = []
        for a in cached:
            cached_lines.append(f"Q: {a['question']}\nA: {a['answer']}")
        cached_block = "\n\n".join(cached_lines)

    system_prompt = f"""\
You are filling out a job application form in a web browser. You can see the page via screenshots and control it with mouse/keyboard actions.

Your task: {task_prompt}

APPLICANT INFORMATION:
{contact_info}

Resume PDF: {resume_path}
Cover Letter PDF: {cover_letter_path}

SCREENING ANSWERS KNOWLEDGE BASE:
{qa_block}

CACHED ANSWERS (previously used — prefer these for consistency):
{cached_block if cached_block else "No cached answers yet."}

ATS SYSTEM TIPS:
- Greenhouse (boards.greenhouse.io): Multi-step forms. Look for "Apply for this Job" button first. Resume upload usually on first page. Custom questions on later pages.
- Lever (jobs.lever.co): Single-page form usually. Resume upload + basic info + optional questions.
- Ashby (jobs.ashbyhq.com): Clean single-page forms. Resume upload with drag-and-drop or file picker.
- Workday (myworkdayjobs.com): Multi-step wizard. Often requires creating an account first — if login/signup appears, say BLOCKED.
- Taleo (taleo.net): Legacy multi-page forms. May have "autofill from resume" option — skip it, fill manually.
- iCIMS: Similar to Workday, may require account creation.
- If the form requires creating an account or logging in, say "BLOCKED: requires account creation" — do not create accounts.

Instructions:
1. Fill in all required fields using the applicant's information above
2. Upload the resume PDF when asked for a resume
3. Upload the cover letter PDF when asked for a cover letter
4. For screening questions, use the knowledge base above for consistent answers
5. For questions not in the knowledge base, answer based on the applicant's experience or select "Prefer not to say"
6. For salary fields, enter a reasonable range or leave blank if optional
7. For dropdown menus, click to open then select the closest matching option
8. If a field has autocomplete suggestions, type slowly and select the right match
9. When you reach the final submit button, STOP and say "READY_TO_SUBMIT" — do NOT click submit
10. If you encounter an error or get stuck, say "BLOCKED: <reason>"
11. Be careful and methodical. Check each field before moving on.
"""

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Here is the current state of the application page. Please start filling it out.",
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": initial_screenshot,
                    },
                },
            ],
        }
    ]

    result = {
        "status": "in_progress",
        "steps_taken": 0,
        "screenshots": [],
    }

    for step in range(max_steps):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=_build_tools(),
            messages=messages,
            betas=[BETA_HEADER],
        )

        # Process response
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Check if Claude is done (no tool use, just text)
        tool_uses = [b for b in assistant_content if b.type == "tool_use"]

        if not tool_uses:
            # Claude sent only text — check for completion signals
            text_blocks = [b for b in assistant_content if b.type == "text"]
            full_text = " ".join(b.text for b in text_blocks)

            if "READY_TO_SUBMIT" in full_text:
                result["status"] = "ready_to_submit"
                result["steps_taken"] = step + 1
                logger.info("Application form ready to submit after %d steps", step + 1)
                break
            elif "BLOCKED" in full_text:
                result["status"] = "blocked"
                result["message"] = full_text
                logger.warning("Application blocked after %d steps: %s", step + 1, full_text[:200])
                result["steps_taken"] = step + 1
                break
            else:
                result["status"] = "completed"
                result["message"] = full_text
                result["steps_taken"] = step + 1
                break

        # Execute each tool use
        tool_results = []
        for tool_use in tool_uses:
            if tool_use.name == "computer":
                action = tool_use.input

                # Special handling for file upload
                if action.get("action") == "left_click":
                    # Check if we need to handle file upload after click
                    screenshot_b64 = await _execute_action(page, action)

                    # Check for file dialog
                    try:
                        file_chooser = page.expect_file_chooser(timeout=2000)
                        async with file_chooser as fc:
                            chooser = await fc
                            # Determine which file to upload
                            if resume_path and ("resume" in str(await page.content()).lower()):
                                await chooser.set_files(resume_path)
                            elif cover_letter_path:
                                await chooser.set_files(cover_letter_path)
                    except Exception as e:
                        logger.debug("No file dialog appeared (expected): %s", e)

                    if screenshot_b64:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": screenshot_b64,
                                    },
                                }
                            ],
                        })
                    else:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": [{"type": "text", "text": "Action executed."}],
                        })
                else:
                    screenshot_b64 = await _execute_action(page, action)
                    if screenshot_b64:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": screenshot_b64,
                                    },
                                }
                            ],
                        })
                    else:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": [{"type": "text", "text": "Action executed."}],
                        })

        messages.append({"role": "user", "content": tool_results})
        result["steps_taken"] = step + 1

    else:
        result["status"] = "max_steps_reached"

    # Save final screenshot
    final_path = await _save_screenshot(page, "final_application_state")
    result["final_screenshot"] = final_path
    result["screenshots"].append(final_path)

    return result


async def fill_application(
    application_url: str,
    master_resume: dict,
    resume_path: str,
    cover_letter_path: str,
    job_id: int,
    headless: bool = False,
) -> dict[str, Any]:
    """Fill out a job application form using Claude Computer Use.

    Args:
        application_url: URL of the application page
        master_resume: User's master resume data
        resume_path: Path to the tailored resume PDF
        cover_letter_path: Path to the tailored cover letter PDF
        job_id: Job ID for tracking
        headless: Run browser without visible window

    Returns:
        Dict with status, screenshots, and result info
    """
    logger.info("Starting application fill for job %d at %s", job_id, application_url)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[f"--window-size={DISPLAY_WIDTH},{DISPLAY_HEIGHT}"],
        )
        context = await browser.new_context(
            viewport={"width": DISPLAY_WIDTH, "height": DISPLAY_HEIGHT},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        try:
            # Navigate to application page
            await page.goto(application_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # Let page fully render

            # Run the Computer Use loop
            result = await _computer_use_loop(
                page=page,
                task_prompt=(
                    f"Fill out this job application form at {application_url}. "
                    "Fill in all fields with the applicant's information. "
                    "Upload the resume and cover letter when prompted. "
                    "Do NOT click the final submit button — stop and say READY_TO_SUBMIT."
                ),
                master_resume=master_resume,
                resume_path=resume_path,
                cover_letter_path=cover_letter_path,
            )

            # If ready to submit, send screenshot for approval
            if result["status"] == "ready_to_submit":
                screenshot_path = result.get("final_screenshot")
                if screenshot_path:
                    await send_photo(
                        screenshot_path,
                        caption=f"Application for job #{job_id} is ready. Review the form above.",
                    )

                approved = await request_approval(
                    job_id,
                    f"Application form for job #{job_id} has been filled out. "
                    "A screenshot of the form was sent. "
                    "Reply *submit* to confirm submission or *skip* to cancel.",
                )

                if approved:
                    # Find and click the submit button
                    submit_screenshot = await _take_screenshot(page)
                    submit_response = anthropic.Anthropic().beta.messages.create(
                        model=MODEL,
                        max_tokens=1024,
                        system="Click the submit/apply button on this page. Just click it, nothing else.",
                        tools=_build_tools(),
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/png",
                                            "data": submit_screenshot,
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": "Click the submit/apply button now.",
                                    },
                                ],
                            }
                        ],
                        betas=[BETA_HEADER],
                    )

                    # Execute the submit click
                    for block in submit_response.content:
                        if block.type == "tool_use" and block.name == "computer":
                            await _execute_action(page, block.input)

                    await asyncio.sleep(3)
                    confirmation_path = await _save_screenshot(page, f"submitted_{job_id}")
                    result["status"] = "submitted"
                    result["confirmation_screenshot"] = confirmation_path
                    logger.info("Application submitted for job %d", job_id)

                    await send_photo(
                        confirmation_path,
                        caption=f"Application for job #{job_id} has been submitted.",
                    )
                    await send_notification(f"Application for job #{job_id} submitted successfully.")
                else:
                    result["status"] = "skipped_by_user"
                    logger.info("Application skipped by user for job %d", job_id)
                    await send_notification(f"Application for job #{job_id} was skipped.")

        except Exception as e:
            logger.exception("Application error for job %d", job_id)
            result = {
                "status": "error",
                "error": str(e),
                "steps_taken": 0,
            }
            # Save error screenshot
            try:
                error_path = await _save_screenshot(page, f"error_{job_id}")
                result["error_screenshot"] = error_path
            except Exception as e2:
                logger.warning("Could not save error screenshot: %s", e2)

        finally:
            await browser.close()

    return result
