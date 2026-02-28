import json


def build_master_scenario_prompt(
    *,
    prompt: str,
    slide_count: int,
    work_type: str,
    show_script: bool,
    file_keys: list[str],
    file_hints: list[dict],
) -> str:
    return (
        "You are the MASTER content agent for final presentation decks. "
        "Primary goal: produce meaningful slide content about the user's topic. "
        "Forbidden: explaining how to make presentations, checklist text, lesson-plan text, or meta instructions. "
        "Output strict JSON only (double quotes, valid JSON). No markdown, no comments, no prose outside JSON. "
        "Top-level schema: "
        "{globalStyle:{theme,fontFamily,background,palette:{bg,surface,primary,accent,text,muted,border}},slides:[...]} . "
        "slides length must be exactly "
        f"{slide_count}. "
        "For each slide provide fields: "
        "title, subtitle, mainText, bullets(array 3-5), kicker, layoutHint, speakerNotes, "
        "style(optional), composition(optional), "
        "assets:{useFiles:[{key,slot,usage}],generateImages:[{prompt,slot,purpose}]}. "
        "Content requirements: each slide must move the narrative forward and describe the topic itself. "
        "No generic placeholders like 'Контекст и цель' unless explicitly requested. "
        "Do not copy the full user prompt into slide text; summarize into clear claims and facts. "
        "All slides must be semantically different. "
        f"workType={work_type}. showScript={show_script}. "
        "If showScript is false, speakerNotes must be empty strings. "
        "Use Russian if the user prompt is in Russian. "
        f"Allowed file keys for assets.useFiles: {file_keys}. "
        f"File key hints: {json.dumps(file_hints, ensure_ascii=False)}. "
        "Use only these keys; never invent unknown keys. Reuse one key on multiple slides if requested. "
        "If some requested image does not exist in available keys, use generateImages with a concrete prompt. "
        f"User topic/request: {prompt}"
    )


def build_worker_html_prompt(*, worker_payload: dict) -> str:
    prompt_payload = {
        "layout": worker_payload["layout"],
        "canvas": worker_payload["canvas"],
        "theme": worker_payload["theme"],
        "content": worker_payload["content"],
        "blocks": worker_payload["blocks"],
        "availableImageSlots": sorted(worker_payload["images"].keys()),
    }
    return (
        "You are the WORKER agent. Build HTML only for one slide. "
        "Return a complete standalone HTML document (doctype/html/head/body). "
        "No markdown fences, no explanations. "
        "Rules: 1280x720 fixed slide, inline CSS only, no external assets/scripts/fonts. "
        "Use theme colors exactly from payload; do not replace with your own fixed palette. "
        "Use theme fontFamily exactly from payload; do not fallback to Arial unless payload asks for it. "
        "Respect per-slide visual differences in palette and block geometry. "
        "Use the exact coordinates and styles from blocks. "
        "Do not invent text: use only provided content fields. "
        "For images use src placeholders like {{image_primary}} or another available slot. "
        "Never print raw data URI text as visible text. Images must be rendered via <img src='{{slot}}'>. "
        "If no image is available for a block, render a visible placeholder. "
        f"Worker payload JSON: {json.dumps(prompt_payload, ensure_ascii=False)}"
    )
