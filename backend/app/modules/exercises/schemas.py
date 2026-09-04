"""Exercise catalog schemas."""

from pydantic import BaseModel


class ExerciseOut(BaseModel):
    slug: str
    title_fa: str
    title_en: str = ""
    description: str = ""
    is_active: bool = True

    model_config = {"from_attributes": True}
