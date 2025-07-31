"""
Highlight Schema - Defines structured fields extracted from conversations

Used to guide LLM extraction and validate structured memory.
"""
class HighlightSchema:
    """Defines the structured fields that can be extracted from conversations"""

    STRUCTURED_FIELDS = {
        "allergies": {
            "type": "list",
            "description": "Food allergies, environmental allergies, or medication allergies",
            "examples": ["dairy", "peanuts", "pollen"]
        },
        "work_schedule": {
            "type": "string",
            "description": "Work hours, shift patterns, or schedule constraints",
            "examples": ["9-5 weekdays", "late shifts ending 10 PM", "rotating shifts"]
        },
        "exercise_preferences": {
            "type": "string",
            "description": "Preferred activities, times, or workout types",
            "examples": ["yoga in mornings", "running outdoors", "gym 3x/week"]
        },
        "health_concerns": {
            "type": "list",
            "description": "Specific health issues, conditions, or areas of focus",
            "examples": ["family heart disease history", "high blood pressure", "back pain"]
        },
        "sleep_schedule": {
            "type": "string",
            "description": "Bedtime routines, wake times, or sleep preferences",
            "examples": ["11 PM bedtime, 6 AM wake", "trouble falling asleep", "needs 8+ hours"]
        },
        "nutrition_preferences": {
            "type": "string",
            "description": "Dietary habits, meal timing, or food preferences",
            "examples": ["vegetarian", "intermittent fasting", "meal prep Sundays"]
        },
        "stress_sources": {
            "type": "list",
            "description": "Sources of stress or factors affecting wellbeing",
            "examples": ["work deadlines", "family responsibilities", "financial concerns"]
        },
        "medications": {
            "type": "list",
            "description": "Medications, supplements, or treatments mentioned",
            "examples": ["vitamin D", "blood pressure medication", "melatonin"]
        },
        "family_health": {
            "type": "string",
            "description": "Relevant family health history or genetic considerations",
            "examples": ["diabetes runs in family", "mother had heart disease"]
        },
        "goals_mentioned": {
            "type": "list",
            "description": "Specific health or fitness goals mentioned in conversation",
            "examples": ["lose 10 pounds", "run 5K", "improve sleep quality", "10k steps daily"]
        },
        "communication_style": {
            "type": "string",
            "description": "How user prefers to receive information and feedback",
            "examples": ["encouraging and positive", "analytical with data", "casual and brief"]
        },
        "motivation_factors": {
            "type": "string",
            "description": "What motivates or drives this user",
            "examples": ["health scare motivation", "wants to keep up with kids", "competitive nature"]
        }
    }

    @classmethod
    def get_field_names(cls):
        """Get list of all structured field names"""
        return list(cls.STRUCTURED_FIELDS.keys())

    @classmethod
    def get_field_description(cls, field_name):
        """Get description for a specific field"""
        return cls.STRUCTURED_FIELDS.get(field_name, {}).get("description", "")

    @classmethod
    def validate_structured_data(cls, data):
        """Validate that structured data contains only known fields"""
        if not isinstance(data, dict):
            return False

        unknown_fields = set(data.keys()) - set(cls.STRUCTURED_FIELDS.keys())
        if unknown_fields:
            raise ValueError(f"Unknown structured fields: {unknown_fields}")

        return True

    @classmethod
    def get_extraction_template(cls):
        """Generate template for LLM extraction"""
        template = {}
        for field_name in cls.STRUCTURED_FIELDS.keys():
            template[field_name] = None
        return template

    @classmethod
    def get_prompt_description(cls):
        """Generate field descriptions for LLM prompt"""
        descriptions = []
        for field_name, field_info in cls.STRUCTURED_FIELDS.items():
            desc = field_info["description"]
            examples = ", ".join(field_info.get("examples", [])[:2])
            if examples:
                descriptions.append(f"- {field_name}: {desc} (e.g., {examples})")
            else:
                descriptions.append(f"- {field_name}: {desc}")
        return "\n".join(descriptions)

