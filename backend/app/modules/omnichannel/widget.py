"""Per-tenant widget tokens and embed script generation.

Widget sessions are unauthenticated browser contexts, so they carry a
short-lived, widget-audience JWT — cryptographically distinct from both
tenant access tokens and operator tokens.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import Settings, get_settings

WIDGET_AUDIENCE = "propflow-widgets"
WIDGET_TOKEN_TYPE = "widget_session"
WIDGET_TOKEN_EXPIRE_HOURS = 24


def create_widget_token(
    *,
    tenant_id: UUID,
    conversation_id: UUID,
    visitor_id: str,
    project_id: UUID | None,
    settings: Settings | None = None,
) -> str:
    config = settings or get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": visitor_id,
            "type": WIDGET_TOKEN_TYPE,
            "tid": str(tenant_id),
            "cid": str(conversation_id),
            "pid": str(project_id) if project_id else None,
            "iat": now,
            "exp": now + timedelta(hours=WIDGET_TOKEN_EXPIRE_HOURS),
            "iss": config.jwt_issuer,
            "aud": WIDGET_AUDIENCE,
        },
        config.jwt_secret_key.get_secret_value(),
        algorithm=config.jwt_algorithm,
    )


def decode_widget_token(token: str, *, settings: Settings | None = None) -> dict:
    config = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            config.jwt_secret_key.get_secret_value(),
            algorithms=[config.jwt_algorithm],
            audience=WIDGET_AUDIENCE,
            issuer=config.jwt_issuer,
            options={"require": ["sub", "type", "tid", "cid", "iat", "exp", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid widget session token.") from exc
    if payload.get("type") != WIDGET_TOKEN_TYPE:
        raise ValueError("Not a widget session token.")
    return payload


def render_embed_script(*, widget_base_url: str, tenant_slug: str, branding: dict) -> str:
    """Build the per-tenant, self-installing embeddable chat + form script."""

    brand_name = str(branding.get("brand_name") or "Sales Team").replace("</", "<\\/")
    primary = str(branding.get("primary_color") or "#2563eb").replace('"', "")
    welcome = str(
        branding.get("welcome_message") or "Hi! Have a question about our projects?"
    ).replace("</", "<\\/").replace('"', "&quot;")
    return _EMBED_TEMPLATE.replace("__BASE__", widget_base_url.rstrip("/")) \
        .replace("__SLUG__", tenant_slug) \
        .replace("__BRAND__", brand_name) \
        .replace("__COLOR__", primary) \
        .replace("__WELCOME__", welcome)


_EMBED_TEMPLATE = r"""(function(){
  if (window.__propflowWidget) return; window.__propflowWidget = true;
  var BASE = "__BASE__", SLUG = "__SLUG__", S = window.localStorage;
  var style = document.createElement("style");
  style.textContent = ".pf-bubble{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;background:__COLOR__;color:#fff;border:0;cursor:pointer;font-size:24px;z-index:99998;box-shadow:0 6px 20px rgba(0,0,0,.25)}.pf-panel{position:fixed;right:20px;bottom:88px;width:340px;max-width:calc(100vw - 24px);height:480px;background:#fff;border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.3);display:none;flex-direction:column;overflow:hidden;font-family:system-ui,-apple-system,sans-serif;z-index:99999}.pf-open .pf-panel{display:flex}.pf-head{background:__COLOR__;color:#fff;padding:12px 14px;font-weight:600}.pf-msgs{flex:1;overflow-y:auto;padding:12px;background:#f7f8fa}.pf-m{max-width:85%;padding:8px 10px;border-radius:10px;margin:4px 0;white-space:pre-wrap;word-break:break-word;font-size:14px}.pf-in{background:#fff;float:left}.pf-out{background:__COLOR__;color:#fff;float:right;clear:both}.pf-form{padding:10px;border-top:1px solid #e5e7eb;font-size:13px;clear:both}.pf-form input{width:100%;padding:7px 8px;margin:3px 0;border:1px solid #d1d5db;border-radius:7px;box-sizing:border-box;font-size:13px}.pf-form label{display:flex;gap:6px;align-items:flex-start;font-size:12px;color:#4b5563;margin:4px 0}.pf-btn{background:__COLOR__;color:#fff;border:0;border-radius:7px;padding:8px 12px;cursor:pointer;width:100%;font-weight:600;margin-top:4px}";
  document.head.appendChild(style);
  var root = document.createElement("div");
  root.innerHTML = '<button class="pf-bubble" aria-label="Chat with __BRAND__">&#128172;</button>'
    + '<div class="pf-panel"><div class="pf-head">__BRAND__</div><div class="pf-msgs"></div>'
    + '<div class="pf-form"><input name="name" placeholder="Your name" autocomplete="name">'
    + '<input name="phone" placeholder="Phone (+91...)" autocomplete="tel">'
    + '<input name="email" placeholder="Email (optional)" autocomplete="email">'
    + '<input name="msg" placeholder="Type your message..." autocomplete="off">'
    + '<label><input type="checkbox" name="consent" style="width:auto"> I agree to be contacted about projects and offers.</label>'
    + '<button class="pf-btn pf-send-chat">Send message</button><button class="pf-btn pf-send-lead" style="margin-top:6px;background:#111">Get a call back</button></div></div>';
  document.body.appendChild(root);
  var panel = root.querySelector(".pf-panel"), msgs = root.querySelector(".pf-msgs");
  var token = S.getItem("pf:" + SLUG + ":tok"), visitor = S.getItem("pf:" + SLUG + ":vid");
  root.querySelector(".pf-bubble").onclick = function(){ root.classList.toggle("pf-open"); };
  function add(text, dir){ var d = document.createElement("div"); d.className = "pf-m pf-" + dir; d.textContent = text; msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; }
  add("__WELCOME__", "in");
  function api(path, body){
    return fetch(BASE + "/api/v1/widget/" + SLUG + path, {
      method: "POST", headers: {"Content-Type": "application/json",
        ...(token ? {Authorization: "Bearer " + token} : {})},
      body: JSON.stringify(body)
    }).then(function(r){ return r.json().then(function(j){ return {ok: r.ok, j: j}; }); });
  }
  function ensureSession(){
    if (token) return Promise.resolve();
    return api("/session", {visitor_id: visitor || undefined})
      .then(function(res){ if (!res.ok) throw new Error(res.j.detail || "session failed");
        token = res.j.widget_token; visitor = res.j.visitor_id;
        S.setItem("pf:" + SLUG + ":tok", token); S.setItem("pf:" + SLUG + ":vid", visitor); });
  }
  root.querySelector(".pf-send-chat").onclick = function(){
    var f = root.querySelector(".pf-form"); var msg = f.msg.value.trim(); if (!msg) return;
    f.msg.value = "";
    ensureSession().then(function(){
      add(msg, "out");
      return api("/chat", {message: msg});
    }).then(function(res){ if (res.ok) add(res.j.reply, "in"); else add("Sorry, please try again.", "in"); })
      .catch(function(){});
  };
  root.querySelector(".pf-send-lead").onclick = function(){
    var f = root.querySelector(".pf-form");
    var data = {full_name: f.name.value.trim(), phone: f.phone.value.trim(),
      email: f.email.value.trim() || null, consent_to_contact: f.consent.checked};
    if (!data.full_name || !data.phone) { add("Please enter your name and phone.", "in"); return; }
    if (!data.consent_to_contact) { add("Please tick the consent box so we can contact you.", "in"); return; }
    ensureSession().then(function(){ return api("/lead", data); })
      .then(function(res){ add(res.ok ? "Thanks! A __BRAND__ advisor will call you shortly." : "Could not submit — please try again.", "in"); })
      .catch(function(){});
  };
})();"""
