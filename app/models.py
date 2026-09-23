from math import isclose

from pydantic import BaseModel, model_validator


class Topic(BaseModel):
    title: str
    description: str
    estimated_minutes: float


class Participant(BaseModel):
    name: str
    topics: list[str]
    estimated_minutes: float


class Slide(BaseModel):
    number: int
    title: str
    content: list[str]
    participant: str
    estimated_minutes: float


class SeminarRequest(BaseModel):
    title: str
    participants: int
    duration_minutes: float
    mandatory_topics: list[str] = []
    references: list[str] = []


class SeminarPlan(BaseModel):
    title: str
    topics: list[Topic]
    participants: list[Participant]
    slides: list[Slide]
    total_duration_minutes: float
    references: list[str]
    mandatory_topics: list[str]

    @model_validator(mode="after")
    def validate_duration(self):
        participant_time = sum(
            participant.estimated_minutes
            for participant in self.participants
        )

        slide_time = sum(
            slide.estimated_minutes
            for slide in self.slides
        )

        if not isclose(
            participant_time,
            self.total_duration_minutes,
            abs_tol=0.01,
        ):
            raise ValueError(
                "A soma do tempo dos participantes "
                "deve ser igual à duração total."
            )

        if not isclose(
            slide_time,
            self.total_duration_minutes,
            abs_tol=0.01,
        ):
            raise ValueError(
                "A soma do tempo dos slides "
                "deve ser igual à duração total."
            )

        for participant in self.participants:
            participant_slide_time = sum(
                slide.estimated_minutes
                for slide in self.slides
                if slide.participant == participant.name
            )

            if not isclose(
                participant_slide_time,
                participant.estimated_minutes,
                abs_tol=0.01,
            ):
                raise ValueError(
                    f"O tempo dos slides de {participant.name} "
                    "não corresponde ao seu tempo total."
                )

        return self