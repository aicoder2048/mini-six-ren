"""Handwritten offline answers, not outputs of the implementation under test."""
import json

READING_DATA = {
    'answer': '先核实合作条件，再决定是否推进。',
    'actions': ['确认分工与沟通方式。', '把尚未谈妥的条件列出来。'],
    'rationale': '大安木提示求稳，留连木延续这一主题，木木比和。赤口金提示沟通制约，中末为被克，即金克木，不能据此断定合作必败。',
    'follow_up': '目前最需要确认的是分工还是报酬？',
    'caution': None,
}


def reading(**changes):
    from reading import Reading
    return Reading.model_validate_json(json.dumps(READING_DATA | changes, ensure_ascii=False))


def complete(session, *, supplement=None, **changes):
    return session.accept(reading(**changes), supplement=supplement)


def json_response(data=READING_DATA):
    """Answer like a real provider under prompted output: JSON in a plain text part, no tool call."""
    from pydantic_ai.messages import ModelResponse, TextPart

    def respond(messages, info):
        return ModelResponse(parts=[TextPart(json.dumps(data, ensure_ascii=False))])

    return respond
