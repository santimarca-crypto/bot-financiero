#!/usr/bin/env python3
"""
Bot de Telegram - Registro de operaciones USD/ARS
================================================
Comandos disponibles:
  /inicio USD ARS   → fijar saldo inicial (ej: /inicio 5000 500000)
  /posicion         → ver posición actual de caja
  /historial [N]    → ver últimas N operaciones (default 10)
  /excel            → el bot manda el Excel completo al chat
  /borrar ID        → borrar una operación por ID
  /reset            → borrar todo y empezar de cero (pide confirmación)

Formatos de operación reconocidos (en cualquier mensaje):
  compro Melania 3000 x 1350
  vendo 3000 Raul x 1382
  compra 3.000 carlos a 1.355
  venta jose 5000 x 1390
"""

import os
import re
import sqlite3
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ─── Config ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")          # pegá tu token acá o en .env
DB_FILE   = Path(__file__).parent / "operaciones.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ─── Regex de operaciones ─────────────────────────────────────────────────────
OP_RE = re.compile(
    r'\b(compro|compra|vendo|venta)\b\s+'
    r'(?:'
    r'([\d][\d.,]*)\s+([a-záéíóúüñA-ZÁÉÍÓÚÜÑ\w]+)'   # amount name
    r'|'
    r'([a-záéíóúüñA-ZÁÉÍÓÚÜÑ\w]+)\s+([\d][\d.,]*)'   # name amount
    r')'
    r'\s+[xXaA@]\s*([\d][\d.,]*)',
    re.IGNORECASE | re.UNICODE
)


def parse_number(s: str) -> float:
    s = s.strip()
    dot, comma = s.count('.'), s.count(',')
    if dot == 1 and comma == 0:
        return float(s) if len(s.split('.')[1]) != 3 else float(s.replace('.', ''))
    if comma == 1 and dot == 0:
        after = s.split(',')[1]
        return float(s.replace(',', '.')) if len(after) != 3 else float(s.replace(',', ''))
    return float(s.replace('.', '').replace(',', ''))


# ─── Base de datos ────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value REAL NOT NULL DEFAULT 0
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS operaciones (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha       TEXT NOT NULL,
                hora        TEXT NOT NULL,
                remitente   TEXT NOT NULL,
                tipo        TEXT NOT NULL,   -- Compra / Venta
                contraparte TEXT NOT NULL,
                usd         REAL NOT NULL,
                rate        REAL NOT NULL,
                ars         REAL NOT NULL,
                mensaje     TEXT
            )
        """)
        # saldo inicial default 0
        db.execute("INSERT OR IGNORE INTO config VALUES ('usd_inicial', 0)")
        db.execute("INSERT OR IGNORE INTO config VALUES ('ars_inicial', 0)")
        db.commit()


def get_config(key: str) -> float:
    with get_db() as db:
        row = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else 0.0


def set_config(key: str, value: float):
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (key, value))
        db.commit()


def insert_op(remitente, tipo, contraparte, usd, rate, mensaje=""):
    ars = usd * rate
    now = datetime.now()
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO operaciones (fecha,hora,remitente,tipo,contraparte,usd,rate,ars,mensaje) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (now.strftime("%d/%m/%Y"), now.strftime("%H:%M:%S"),
             remitente, tipo, contraparte, usd, rate, ars, mensaje)
        )
        db.commit()
        return cur.lastrowid


def get_posicion():
    usd_i = get_config("usd_inicial")
    ars_i = get_config("ars_inicial")
    with get_db() as db:
        rows = db.execute("SELECT tipo, usd, ars FROM operaciones ORDER BY id").fetchall()
    pos_usd, pos_ars = usd_i, ars_i
    for r in rows:
        if r["tipo"] == "Compra":
            pos_usd += r["usd"]
            pos_ars -= r["ars"]
        else:
            pos_usd -= r["usd"]
            pos_ars += r["ars"]
    return pos_usd, pos_ars


def get_historial(limit=10):
    with get_db() as db:
        return db.execute(
            "SELECT * FROM operaciones ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def delete_op(op_id: int) -> bool:
    with get_db() as db:
        cur = db.execute("DELETE FROM operaciones WHERE id=?", (op_id,))
        db.commit()
        return cur.rowcount > 0


def reset_all():
    with get_db() as db:
        db.execute("DELETE FROM operaciones")
        db.execute("UPDATE config SET value=0")
        db.commit()


# ─── Formateo ────────────────────────────────────────────────────────────────
def fmt_num(n: float, decimals=0) -> str:
    if decimals:
        return f"{n:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{n:,.0f}".replace(",", "X").replace("X", ".")


def posicion_msg(op_tipo=None, op_usd=None, op_rate=None, op_contra=None) -> str:
    pos_usd, pos_ars = get_posicion()
    lines = []
    if op_tipo:
        emoji = "🟢" if op_tipo == "Compra" else "🔴"
        signo_usd = "+" if op_tipo == "Compra" else "-"
        signo_ars = "-" if op_tipo == "Compra" else "+"
        ars_op = op_usd * op_rate
        lines += [
            f"{emoji} *{op_tipo.upper()} registrada*",
            f"👤 {op_contra}  |  USD {fmt_num(op_usd)} x $ {fmt_num(op_rate)}",
            f"   {signo_usd}USD {fmt_num(op_usd)}  /  {signo_ars}$ {fmt_num(ars_op)}",
            "",
        ]
    lines += [
        "📊 *POSICIÓN DE CAJA*",
        f"💵  USD  `{'%+,.0f' % pos_usd}` ({fmt_num(pos_usd)})",
        f"💰  ARS  `{'%+,.0f' % pos_ars}` ({fmt_num(pos_ars)})",
    ]
    return "\n".join(lines)


# ─── Generador Excel ──────────────────────────────────────────────────────────
NAVY  = "1F4E79"
LBLUE = "BDD7EE"
ALT   = "EBF3FB"
YELL  = "FFFF00"

def _tb():
    s = Side(style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)

def build_excel_bytes() -> bytes:
    with get_db() as db:
        ops = db.execute("SELECT * FROM operaciones ORDER BY id").fetchall()
    usd_i = get_config("usd_inicial")
    ars_i = get_config("ars_inicial")

    wb = Workbook()
    ws = wb.active
    ws.title = "Operaciones"
    ws.freeze_panes = "A7"

    # Title
    ws["A1"] = f"REGISTRO USD/ARS  —  generado {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A1"].font = Font(name="Arial", bold=True, size=13, color=NAVY)
    ws.merge_cells("A1:K1")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    # Saldo inicial
    ws["A3"] = "SALDO INICIAL"
    ws["A3"].font = Font(name="Arial", bold=True, size=10, color=NAVY)
    for lbl, col_l, col_v, val in [("USD Inicial", "A", "B", usd_i), ("ARS Inicial", "D", "E", ars_i)]:
        ws[f"{col_l}4"] = lbl + ":"
        ws[f"{col_l}4"].font = Font(name="Arial", bold=True, size=10)
        ws[f"{col_l}4"].alignment = Alignment(horizontal="right")
        c = ws[f"{col_v}4"]
        c.value = val
        c.font = Font(name="Arial", bold=True, size=10, color="0000FF")
        c.fill = PatternFill("solid", start_color=YELL)
        c.number_format = "#,##0.00"
        c.border = _tb()
        c.alignment = Alignment(horizontal="center")

    # Headers
    HDR = ["#", "Fecha", "Hora", "Remitente", "Tipo", "Contraparte",
           "USD", "TC", "ARS", "Posición USD", "Posición ARS"]
    HROW = 6
    hf = PatternFill("solid", start_color=NAVY)
    for c, h in enumerate(HDR, 1):
        cell = ws.cell(row=HROW, column=c, value=h)
        cell.font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
        cell.fill = hf
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _tb()
    ws.row_dimensions[HROW].height = 24

    DS = 7
    mid = Alignment(horizontal="center", vertical="center")
    lft = Alignment(horizontal="left", vertical="center")

    for i, op in enumerate(ops):
        row = DS + i
        alt = i % 2 == 0
        rf  = PatternFill("solid", start_color=ALT if alt else "FFFFFF")
        b   = _tb()

        def c(col, val, fmt=None, fnt=None, aln=None):
            cell = ws.cell(row=row, column=col, value=val)
            cell.fill = rf; cell.border = b
            if fmt: cell.number_format = fmt
            if fnt: cell.font = fnt
            if aln: cell.alignment = aln
            return cell

        c(1,  op["id"],         None,       Font(name="Arial", size=9, color="888888"), mid)
        c(2,  op["fecha"],      None,       Font(name="Arial", size=10), mid)
        c(3,  op["hora"],       None,       Font(name="Arial", size=10), mid)
        c(4,  op["remitente"],  None,       Font(name="Arial", size=10), lft)

        color = "0070C0" if op["tipo"] == "Compra" else "C00000"
        tc = ws.cell(row=row, column=5, value=op["tipo"])
        tc.fill = rf; tc.border = b; tc.alignment = mid
        tc.font = Font(name="Arial", bold=True, size=10, color=color)

        c(6,  op["contraparte"], None,      Font(name="Arial", size=10), lft)
        c(7,  op["usd"],        "#,##0.00", Font(name="Arial", size=10, color="0000FF"), mid)
        c(8,  op["rate"],       "#,##0.00", Font(name="Arial", size=10, color="0000FF"), mid)
        c(9,  f"=G{row}*H{row}","#,##0.00", Font(name="Arial", size=10), mid)

        # Posición USD acumulada
        if row == DS:
            pu = f"=B4+IF(E{row}=\"Compra\",G{row},-G{row})"
        else:
            pu = f"=J{row-1}+IF(E{row}=\"Compra\",G{row},-G{row})"
        c(10, pu, "#,##0.00", Font(name="Arial", size=10, bold=True), mid)

        # Posición ARS acumulada
        if row == DS:
            pa = f"=E4+IF(E{row}=\"Compra\",-I{row},I{row})"
        else:
            pa = f"=K{row-1}+IF(E{row}=\"Compra\",-I{row},I{row})"
        c(11, pa, "#,##0.00", Font(name="Arial", size=10, bold=True), mid)

    # Totals
    if ops:
        tr = DS + len(ops)
        last = tr - 1
        tf = PatternFill("solid", start_color=LBLUE)
        for col in range(1, 12):
            cell = ws.cell(row=tr, column=col)
            cell.fill = tf; cell.border = _tb()
            cell.font = Font(name="Arial", bold=True, size=10, color=NAVY)
            cell.alignment = Alignment(horizontal="center")
        ws.cell(row=tr, column=6).value = "TOTALES"
        for col, formula in [(7, f"=SUM(G{DS}:G{last})"),
                              (9, f"=SUM(I{DS}:I{last})"),
                              (10, f"=J{last}"),
                              (11, f"=K{last}")]:
            cell = ws.cell(row=tr, column=col)
            cell.value = formula
            cell.number_format = "#,##0.00"

    for col, w in zip(range(1, 12), [5, 12, 9, 20, 10, 16, 13, 13, 16, 15, 16]):
        ws.column_dimensions[get_column_letter(col)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ─── Handlers de Telegram ─────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Bot USD/ARS activo*\n\n"
        "Mandá operaciones así:\n"
        "  `compro Melania 3000 x 1350`\n"
        "  `vendo Raul 5000 x 1382`\n\n"
        "Comandos:\n"
        "  /posicion — posición actual\n"
        "  /historial — últimas operaciones\n"
        "  /excel — descargar Excel\n"
        "  /inicio USD ARS — fijar saldo inicial\n"
        "  /borrar ID — eliminar operación",
        parse_mode="Markdown"
    )


async def cmd_posicion(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(posicion_msg(), parse_mode="Markdown")


async def cmd_historial(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    n = 10
    if ctx.args:
        try: n = int(ctx.args[0])
        except: pass
    rows = get_historial(n)
    if not rows:
        await update.message.reply_text("No hay operaciones registradas.")
        return
    lines = [f"📋 *Últimas {len(rows)} operaciones*\n"]
    for r in reversed(rows):
        emoji = "🟢" if r["tipo"] == "Compra" else "🔴"
        lines.append(
            f"{emoji} `#{r['id']}` {r['fecha']} {r['hora'][:5]} | "
            f"*{r['tipo']}* {r['contraparte']} "
            f"USD {fmt_num(r['usd'])} x {fmt_num(r['rate'])} "
            f"= $ {fmt_num(r['ars'])}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_excel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generando Excel... ⏳")
    data = build_excel_bytes()
    fname = f"operaciones_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    await update.message.reply_document(
        document=data,
        filename=fname,
        caption=f"📊 Registro completo — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )


async def cmd_inicio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Uso: /inicio USD ARS\nEj: /inicio 5000 500000")
        return
    try:
        usd = parse_number(ctx.args[0])
        ars = parse_number(ctx.args[1])
    except:
        await update.message.reply_text("❌ Formato inválido. Ej: /inicio 5000 500000")
        return
    set_config("usd_inicial", usd)
    set_config("ars_inicial", ars)
    await update.message.reply_text(
        f"✅ Saldo inicial fijado:\n"
        f"💵 USD: {fmt_num(usd)}\n"
        f"💰 ARS: {fmt_num(ars)}",
        parse_mode="Markdown"
    )


async def cmd_borrar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Uso: /borrar ID  (ej: /borrar 5)")
        return
    try:
        op_id = int(ctx.args[0])
    except:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return
    if delete_op(op_id):
        pos_usd, pos_ars = get_posicion()
        await update.message.reply_text(
            f"🗑 Operación #{op_id} eliminada.\n\n" + posicion_msg(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ No encontré la operación #{op_id}.")


_reset_pending = set()

async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in _reset_pending:
        _reset_pending.discard(uid)
        reset_all()
        await update.message.reply_text("✅ Todo borrado. Posición en cero.")
    else:
        _reset_pending.add(uid)
        await update.message.reply_text(
            "⚠️ Esto borra TODAS las operaciones.\n"
            "Mandá /reset de nuevo para confirmar."
        )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text
    sender = update.effective_user.first_name or update.effective_user.username or "?"

    m = OP_RE.search(text)
    if not m:
        return

    keyword, amt1, name1, name2, amt2, rate_s = m.groups()
    if amt1:
        usd        = parse_number(amt1)
        contraparte = name1.capitalize()
    else:
        usd        = parse_number(amt2)
        contraparte = name2.capitalize()
    rate = parse_number(rate_s)
    tipo = "Compra" if keyword.lower() in ("compro", "compra") else "Venta"

    insert_op(sender, tipo, contraparte, usd, rate, text)
    msg = posicion_msg(tipo, usd, rate, contraparte)
    await update.message.reply_text(msg, parse_mode="Markdown")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("ERROR: falta BOT_TOKEN.")
        print("Pasos:")
        print("  1. Abrí Telegram y buscá @BotFather")
        print("  2. Mandá /newbot y seguí las instrucciones")
        print("  3. Copiá el token y pegalo en el archivo .env:")
        print("       BOT_TOKEN=123456:ABC-tu-token-acá")
        return

    init_db()
    log.info("Iniciando bot...")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("posicion", cmd_posicion))
    app.add_handler(CommandHandler("historial",cmd_historial))
    app.add_handler(CommandHandler("excel",    cmd_excel))
    app.add_handler(CommandHandler("inicio",   cmd_inicio))
    app.add_handler(CommandHandler("borrar",   cmd_borrar))
    app.add_handler(CommandHandler("reset",    cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot corriendo. Ctrl+C para detener.")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
