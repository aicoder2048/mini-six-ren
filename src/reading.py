"""Validated interpretations and immutable local facts shared by both interfaces."""
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, model_validator

from hand_technique import Prediction
from utils.symbol_relations import describe_relation

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Supplement = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
MAX_SUPPLEMENTS = 5


class StrictRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)


class Reading(StrictRecord):
    answer: NonBlank
    actions: Annotated[
        tuple[NonBlank, ...],
        BeforeValidator(lambda value: tuple(value) if isinstance(value, list) else value),
        Field(min_length=1, max_length=3),
    ]
    rationale: NonBlank
    follow_up: NonBlank | None
    caution: NonBlank | None


class TransmissionFact(StrictRecord):
    name: NonBlank
    element: NonBlank
    keywords: NonBlank
    meaning: NonBlank


class RelationFact(StrictRecord):
    name: NonBlank
    explanation: NonBlank


class ReadingSnapshot(StrictRecord):
    question: NonBlank
    transmissions: tuple[TransmissionFact, TransmissionFact, TransmissionFact]
    relations: tuple[RelationFact, RelationFact]


class ReadingSession(StrictRecord):
    snapshot: ReadingSnapshot
    reading: Reading | None = None
    supplements: Annotated[tuple[Supplement, ...], Field(max_length=MAX_SUPPLEMENTS)] = ()

    @model_validator(mode='after')
    def require_reading_for_supplements(self) -> Self:
        if self.supplements and self.reading is None:
            raise ValueError('请先生成初次解读，再补充情况。')
        return self

    @classmethod
    def start(cls, prediction: Prediction, question: str) -> Self:
        symbols = prediction.symbols
        snapshot = ReadingSnapshot(
            question=question,
            transmissions=tuple(TransmissionFact(
                name=s.name, element=s.element.name, keywords=s.description, meaning=s.interpretation,
            ) for s in symbols),
            relations=tuple(RelationFact(
                name=relation, explanation=describe_relation(symbols[i], symbols[i + 1], relation),
            ) for i, relation in enumerate(prediction.relations)),
        )
        return cls(snapshot=snapshot)

    def validate_supplement(self, supplement: str) -> str:
        if self.reading is None:
            raise ValueError('请先生成初次解读，再补充情况。')
        if len(self.supplements) >= MAX_SUPPLEMENTS:
            raise ValueError('本次最多补充5次，请重新起课。')
        if not isinstance(supplement, str) or not supplement.strip():
            raise ValueError('请输入要补充的情况。')
        if len(supplement) > 1000:
            raise ValueError('每次补充最多1000字，请缩短后重试。')
        return supplement.strip()

    def accept(self, reading: Reading, *, supplement: str | None = None) -> Self:
        supplements = self.supplements
        if supplement is not None:
            supplements += (self.validate_supplement(supplement),)
        return type(self)(snapshot=self.snapshot, reading=reading, supplements=supplements)
