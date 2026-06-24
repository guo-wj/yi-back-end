"""抽签与解签：先从文库随机出签，再调用模型紧扣签文解签。"""

import secrets
from dataclasses import dataclass
from datetime import date

from services.deepseek_client import chat_completion
from services.lottery_data import LOTTERY_SLIPS, SlipRecord
from services import prompts
from utils.lunar import format_lunar_display, solar_to_lunar


@dataclass(frozen=True)
class DrawContext:
    solar_date: date
    solar_date_str: str
    lunar_summary: str
    lunar_label: str


def _build_context(d: date) -> DrawContext:
    info = solar_to_lunar(d)
    return DrawContext(
        solar_date=d,
        solar_date_str=d.isoformat(),
        lunar_summary=format_lunar_display(d),
        lunar_label=f"农历{info.lunar_year}年{info.label()}",
    )


def draw_slip() -> SlipRecord:
    """从签库随机抽一支签（真随机）。"""
    return secrets.choice(LOTTERY_SLIPS)


async def interpret_slip(
    slip: SlipRecord,
    ctx: DrawContext,
    *,
    name: str | None,
    focus: str | None,
    question: str | None,
) -> str:
    """据已定签文与问卜语境解签。"""
    user = prompts.lottery_interpret_user(
        slip_id=slip["id"],
        slip_tier=slip["tier"],
        slip_title=slip["title"],
        slip_poem=slip["poem"],
        solar_date=ctx.solar_date_str,
        lunar_hint=ctx.lunar_label,
        name=name,
        focus=focus,
        question=question,
    )
    return await chat_completion(prompts.lottery_interpret_system(), user)


async def draw_and_interpret(
    *,
    solar_date: date | None,
    name: str | None,
    focus: str | None,
    question: str | None,
) -> tuple[SlipRecord, DrawContext, str]:
    d = solar_date or date.today()
    ctx = _build_context(d)
    slip = draw_slip()
    text = await interpret_slip(slip, ctx, name=name, focus=focus, question=question)
    return slip, ctx, text
