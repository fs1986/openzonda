"""Ops de Jira por API REST para OpenZonda (dev tooling, NO parte del producto).

Permite a Claude Code leer y transicionar tarjetas del proyecto OZ sin depender del conector
de claude.ai (que suele fallar). Usa solo stdlib (`urllib`): ninguna dependencia nueva.

## Credenciales — el token NUNCA vive en el repo ni se imprime

Las lee, en este orden:
  1. Variables de entorno `JIRA_EMAIL` y `JIRA_API_TOKEN`.
  2. Un archivo `KEY=VALUE` **fuera del repo**: por defecto `~/.openzonda/jira.env`
     (o la ruta en `JIRA_ENV_FILE`). Formato:
         JIRA_EMAIL=tu-cuenta@dominio
         JIRA_API_TOKEN=el-token-de-atlassian
         JIRA_BASE_URL=https://fs1986.atlassian.net   (opcional; este es el default)

El token se genera en https://id.atlassian.com/manage-profile/security/api-tokens
El script no imprime el token ni lo escribe a ningún lado; solo lo usa para el header Basic.

## Uso

    python scripts/jira_ops.py whoami
    python scripts/jira_ops.py get OZ-36
    python scripts/jira_ops.py transitions OZ-36
    python scripts/jira_ops.py transition OZ-36 "Review"
    python scripts/jira_ops.py comment OZ-36 "texto del comentario"

Sale con código 0 si la operación fue OK, !=0 si falló (con el motivo en stderr).
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# La consola de Windows usa cp1252 por defecto y revienta con →, ±, etc. que aparecen en los
# resúmenes de las tarjetas. Forzar UTF-8 en la salida evita ese crash.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

DEFAULT_BASE_URL = "https://fs1986.atlassian.net"
DEFAULT_ENV_FILE = Path.home() / ".openzonda" / "jira.env"


class JiraError(RuntimeError):
    pass


def _cargar_credenciales() -> tuple[str, str, str]:
    """Devuelve (base_url, email, token). El token no se registra ni se imprime."""
    valores: dict[str, str] = {}
    ruta = Path(os.environ.get("JIRA_ENV_FILE", str(DEFAULT_ENV_FILE)))
    if ruta.is_file():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            valores[clave.strip()] = valor.strip().strip('"').strip("'")

    email = os.environ.get("JIRA_EMAIL") or valores.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN") or valores.get("JIRA_API_TOKEN", "")
    base = os.environ.get("JIRA_BASE_URL") or valores.get("JIRA_BASE_URL", DEFAULT_BASE_URL)

    if not email or not token:
        raise JiraError(
            "Faltan credenciales. Definí JIRA_EMAIL y JIRA_API_TOKEN en el entorno o en "
            f"{ruta} (formato KEY=VALUE). El token se genera en "
            "https://id.atlassian.com/manage-profile/security/api-tokens"
        )
    return base.rstrip("/"), email, token


def _peticion(metodo: str, url: str, email: str, token: str, cuerpo: dict | None = None) -> object:
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    credencial = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
    req = urllib.request.Request(url, data=datos, method=metodo)
    req.add_header("Authorization", f"Basic {credencial}")
    req.add_header("Accept", "application/json")
    if datos is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            crudo = resp.read()
            return json.loads(crudo) if crudo else None
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:500]
        raise JiraError(f"HTTP {e.code} en {metodo} {url}: {detalle}") from e
    except urllib.error.URLError as e:
        raise JiraError(f"No se pudo conectar a Jira: {e.reason}") from e


def _api3(base: str, ruta: str) -> str:
    return f"{base}/rest/api/3{ruta}"


def cmd_whoami(base: str, email: str, token: str, _args: list[str]) -> int:
    yo = _peticion("GET", _api3(base, "/myself"), email, token)
    assert isinstance(yo, dict)
    print(f"OK: autenticado como {yo.get('displayName')} <{yo.get('emailAddress')}> en {base}")
    return 0


def cmd_get(base: str, email: str, token: str, args: list[str]) -> int:
    clave = args[0]
    url = _api3(base, f"/issue/{clave}?fields=summary,status,assignee")
    issue = _peticion("GET", url, email, token)
    assert isinstance(issue, dict)
    campos = issue["fields"]
    estado = campos["status"]["name"]
    asignado = (campos.get("assignee") or {}).get("displayName", "sin asignar")
    print(f"{clave}: {campos['summary']}")
    print(f"  Estado: {estado} · Asignado: {asignado}")
    return 0


def cmd_transitions(base: str, email: str, token: str, args: list[str]) -> int:
    clave = args[0]
    data = _peticion("GET", _api3(base, f"/issue/{clave}/transitions"), email, token)
    assert isinstance(data, dict)
    print(f"Transiciones disponibles para {clave}:")
    for t in data["transitions"]:
        print(f"  {t['id']:>4}  -> {t['to']['name']}   (nombre: {t['name']})")
    return 0


def cmd_transition(base: str, email: str, token: str, args: list[str]) -> int:
    clave, objetivo = args[0], args[1]
    data = _peticion("GET", _api3(base, f"/issue/{clave}/transitions"), email, token)
    assert isinstance(data, dict)
    elegido = next(
        (
            t
            for t in data["transitions"]
            if objetivo.lower() in (t["id"].lower(), t["name"].lower(), t["to"]["name"].lower())
        ),
        None,
    )
    if elegido is None:
        disponibles = ", ".join(f"{t['to']['name']}" for t in data["transitions"])
        raise JiraError(
            f"No hay transición a {objetivo!r} desde el estado actual de {clave}. "
            f"Disponibles: {disponibles or '(ninguna)'}"
        )
    _peticion(
        "POST",
        _api3(base, f"/issue/{clave}/transitions"),
        email,
        token,
        {"transition": {"id": elegido["id"]}},
    )
    print(f"OK: {clave} -> {elegido['to']['name']}")
    return 0


def cmd_comment(base: str, email: str, token: str, args: list[str]) -> int:
    clave, texto = args[0], args[1]
    # ADF mínimo (Jira Cloud v3 exige documento estructurado, no texto plano).
    adf = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": texto}]}],
        }
    }
    _peticion("POST", _api3(base, f"/issue/{clave}/comment"), email, token, adf)
    print(f"OK: comentario agregado a {clave}")
    return 0


def cmd_assign(base: str, email: str, token: str, args: list[str]) -> int:
    """Asigna una tarjeta. `quien` = 'me' (el dueño del token), un email, o un accountId."""
    clave, quien = args[0], args[1]
    if quien.lower() == "me":
        yo = _peticion("GET", _api3(base, "/myself"), email, token)
        assert isinstance(yo, dict)
        account_id = yo["accountId"]
    elif "@" in quien:
        consulta = urllib.parse.quote(quien)
        res = _peticion("GET", _api3(base, f"/user/search?query={consulta}"), email, token)
        if not isinstance(res, list) or not res:
            raise JiraError(f"No encontré ningún usuario para {quien!r}.")
        account_id = res[0]["accountId"]
    else:
        account_id = quien
    _peticion(
        "PUT", _api3(base, f"/issue/{clave}/assignee"), email, token, {"accountId": account_id}
    )
    print(f"OK: {clave} asignada a {quien}")
    return 0


_COMANDOS = {
    "whoami": (cmd_whoami, 0),
    "get": (cmd_get, 1),
    "transitions": (cmd_transitions, 1),
    "transition": (cmd_transition, 2),
    "comment": (cmd_comment, 2),
    "assign": (cmd_assign, 2),
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in _COMANDOS:
        print(f"Uso: python {argv[0]} <{'|'.join(_COMANDOS)}> [args...]", file=sys.stderr)
        return 2
    handler, n_args = _COMANDOS[argv[1]]
    args = argv[2:]
    if len(args) < n_args:
        print(f"'{argv[1]}' necesita {n_args} argumento(s).", file=sys.stderr)
        return 2
    try:
        base, email, token = _cargar_credenciales()
        return handler(base, email, token, args)
    except JiraError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
