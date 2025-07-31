from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Set up Jinja2 environment to load from src/prompts/
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))

def render_prompt(name: str, context: dict) -> str:
    """
    Load and render a Jinja2 prompt template from src/prompts/.

    Args:
        name: File name without .txt extension (e.g., 'highlight_extraction')
        context: Dict with variables to fill into the template

    Returns:
        Rendered prompt string
    """
    try:
        template = env.get_template(f"{name}.txt")
        return template.render(**context)
    except Exception as e:
        raise RuntimeError(f"Failed to render prompt '{name}': {e}")
