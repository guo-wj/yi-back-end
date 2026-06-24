"""验证码邮件发送：标准库 smtplib + email，支持 SSL(465) / STARTTLS(587)。

发送是阻塞 IO，调用方应放到线程池中执行（asyncio.to_thread），避免阻塞事件循环。
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from config import settings


def _build_message(to_email: str, code: str) -> EmailMessage:
    minutes = max(1, settings.code_ttl_seconds // 60)
    msg = EmailMessage()
    msg["Subject"] = "【易鉴】邮箱验证码"
    msg["From"] = formataddr((settings.smtp_from_name, settings.smtp_from))
    msg["To"] = to_email

    text = (
        f"您的验证码是：{code}\n"
        f"有效期 {minutes} 分钟，请尽快完成验证。\n"
        f"若非本人操作，请忽略本邮件。"
    )
    html = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:auto">
  <h2 style="color:#7a5c2e">易鉴 · 邮箱验证</h2>
  <p>您的验证码是：</p>
  <p style="font-size:32px;font-weight:700;letter-spacing:8px;color:#b8860b">{code}</p>
  <p style="color:#666">有效期 {minutes} 分钟，请尽快完成验证。若非本人操作，请忽略本邮件。</p>
</div>"""

    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def send_code_email(to_email: str, code: str) -> None:
    """通过配置的 SMTP 发送验证码邮件。未配置 SMTP 时抛错，便于上层返回明确提示。"""
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        raise ValueError("未配置 SMTP（SMTP_HOST/SMTP_USER/SMTP_PASSWORD），无法发送验证码邮件。")

    msg = _build_message(to_email, code)
    context = ssl.create_default_context()

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls(context=context)
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise ValueError(
            f"SMTP 登录被拒（{e.smtp_code} {_decode_smtp_error(e.smtp_error)}）："
            "请确认已在邮箱设置中开启 SMTP 服务，且 SMTP_PASSWORD 填的是「授权码」而非登录密码。"
        ) from e
    except (smtplib.SMTPException, OSError) as e:
        raise ValueError(f"验证码邮件发送失败：{e}") from e


def _decode_smtp_error(raw: bytes | str) -> str:
    """网易等国内服务商的错误消息常用 GBK 编码。"""
    if isinstance(raw, str):
        return raw
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
