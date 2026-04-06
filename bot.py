import os, re, sqlite3, logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
 
BOT_TOKEN = os.environ["BOT_TOKEN"]
DB = Path("/tmp/ops.db")
 
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
 
OP_RE = re.compile(
    r'\b(compro|compra|vendo|venta)\b\s+'
    r'(?:([\d][\d.,]*)\s+(\w+)|(\w+)\s+([\d][\d.,]*))'
    r'\s+[xXaA@]\s*([\d][\d.,]*)',
    re.IGNORECASE
)
 
def num(s):
    s = s.strip().replace(" ", "")
    if s.count(".") == 1 and len(s.split(".")[1]) == 3:
        s = s.replace(".", "")
    elif s.count(",") == 1 and len(s.split(",")[1]) == 3:
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return float(s.replace(".","").replace(",",""))
 
def fmt(n):
    return f"{abs(n):,.0f}".replace(",",".")
 
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn
 
def setup():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS cfg (k TEXT PRIMARY KEY, v REAL DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS ops (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, hora TEXT, de TEXT, tipo TEXT, contra TEXT, usd REAL, tc REAL, ars REAL, msg TEXT)")
        c.execute("INSERT OR IGNORE INTO cfg VALUES ('usd',0)")
        c.execute("INSERT OR IGNORE INTO cfg VALUES ('ars',0)")
        c.commit()
 
def cfg(k):
    with db() as c:
        r = c.execute("SELECT v FROM cfg WHERE k=?", (k,)).fetchone()
        return r["v"] if r else 0.0
 
def setcfg(k, v):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO cfg VALUES (?,?)", (k,v))
        c.commit()
 
def guardar(de, tipo, contra, usd, tc, msg):
    now = datetime.now()
    with db() as c:
        c.execute("INSERT INTO ops (fecha,hora,de,tipo,contra,usd,tc,ars,msg) VALUES (?,?,?,?,?,?,?,?,?)",
                  (now.strftime("%d/%m/%Y"), now.strftime("%H:%M:%S"), de, tipo, contra, usd, tc, usd*tc, msg))
        c.commit()
 
def posicion():
    pu, pa = cfg("usd"), cfg("ars")
    with db() as c:
        for r in c.execute("SELECT tipo,usd,ars FROM ops ORDER BY id").fetchall():
            if r["tipo"] == "Compra":
                pu += r["usd"]; pa -= r["ars"]
            else:
                pu -= r["usd"]; pa += r["ars"]
    return pu, pa
 
async def start(u: Update, _):
    await u.message.reply_text(
        "Bot USD/ARS activo\n\n"
        "Manda operaciones asi:\n"
        "compro Melania 3000 x 1350\n"
        "vendo Raul 5000 x 1382\n\n"
        "/posicion - ver posicion\n"
        "/historial - ver operaciones\n"
        "/excel - bajar Excel\n"
        "/inicio USD ARS - fijar saldo inicial\n"
        "/borrar ID - borrar operacion"
    )
 
async def pos_cmd(u: Update, _):
    pu, pa = posicion()
    signo_usd = "+" if pu >= 0 else ""
    signo_ars = "+" if pa >= 0 else ""
    await u.message.reply_text(
        f"POSICION DE CAJA\n"
        f"USD: {signo_usd}{fmt(pu)}\n"
        f"ARS: {signo_ars}{fmt(pa)}"
    )
 
async def hist_cmd(u: Update, ctx):
    n = int(ctx.args[0]) if ctx.args else 10
    with db() as c:
        rows = c.execute("SELECT * FROM ops ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    if not rows:
        await u.message.reply_text("No hay operaciones.")
        return
    txt = f"Ultimas {len(rows)} operaciones:\n\n"
    for r in reversed(rows):
        e = "COMPRA" if r["tipo"]=="Compra" else "VENTA"
        txt += f"#{r['id']} {r['fecha']} {r['hora'][:5]} | {e} {r['contra']} USD {fmt(r['usd'])} x {fmt(r['tc'])}\n"
    await u.message.reply_text(txt)
 
async def inicio_cmd(u: Update, ctx):
    if len(ctx.args) < 2:
        await u.message.reply_text("Uso: /inicio USD ARS\nEj: /inicio 5000 500000")
        return
    try:
        usd_i = num(ctx.args[0]); ars_i = num(ctx.args[1])
        setcfg("usd", usd_i); setcfg("ars", ars_i)
        await u.message.reply_text(f"Saldo inicial:\nUSD: {fmt(usd_i)}\nARS: {fmt(ars_i)}")
    except Exception as e:
        await u.message.reply_text(f"Error: {e}")
 
async def borrar_cmd(u: Update, ctx):
    if not ctx.args:
        await u.message.reply_text("Uso: /borrar ID")
        return
    with db() as c:
        c.execute("DELETE FROM ops WHERE id=?", (ctx.args[0],))
        c.commit()
    await u.message.reply_text(f"Operacion #{ctx.args[0]} eliminada.")
    await pos_cmd(u, None)
 
async def excel_cmd(u: Update, _):
    await u.message.reply_text("Generando Excel...")
    with db() as c:
        rows = c.execute("SELECT * FROM ops ORDER BY id").fetchall()
    usd_i, ars_i = cfg("usd"), cfg("ars")
    wb = Workbook(); ws = wb.active; ws.title = "Operaciones"
    navy = "1F4E79"
    def tb():
        s = Side(style="thin", color="CCCCCC")
        return Border(left=s,right=s,top=s,bottom=s)
    hdrs = ["#","Fecha","Hora","Enviado por","Tipo","Contraparte","USD","TC","ARS","Pos USD","Pos ARS"]
    hf = PatternFill("solid", start_color=navy)
    for c2, h in enumerate(hdrs, 1):
        cell = ws.cell(row=1, column=c2, value=h)
        cell.font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
        cell.fill = hf; cell.border = tb()
        cell.alignment = Alignment(horizontal="center")
    DS = 2
    for i, r in enumerate(rows):
        row = DS + i
        alt = PatternFill("solid", start_color="EBF3FB" if i%2==0 else "FFFFFF")
        b = tb()
        vals = [r["id"], r["fecha"], r["hora"], r["de"], r["tipo"], r["contra"], r["usd"], r["tc"]]
        for c2, v in enumerate(vals, 1):
            cell = ws.cell(row=row, column=c2, value=v)
            cell.fill = alt; cell.border = b
            cell.alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=9, value=f"=G{row}*H{row}").number_format = "#,##0.00"
        ws.cell(row=row, column=9).fill = alt; ws.cell(row=row, column=9).border = b
        if row == DS:
            pu = f"={usd_i}+IF(E{row}=\"Compra\",G{row},-G{row})"
            pa = f"={ars_i}+IF(E{row}=\"Compra\",-I{row},I{row})"
        else:
            pu = f"=J{row-1}+IF(E{row}=\"Compra\",G{row},-G{row})"
            pa = f"=K{row-1}+IF(E{row}=\"Compra\",-I{row},I{row})"
        for c2, f2 in [(10, pu), (11, pa)]:
            cell = ws.cell(row=row, column=c2, value=f2)
            cell.fill = alt; cell.border = b; cell.number_format = "#,##0.00"
            cell.alignment = Alignment(horizontal="center")
    for c2, w in enumerate([4,12,9,18,10,14,12,12,14,13,13], 1):
        ws.column_dimensions[get_column_letter(c2)].width = w
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    fname = f"operaciones_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    await u.message.reply_document(document=buf.read(), filename=fname)
 
async def mensaje(u: Update, ctx):
    try:
        text = u.message.text
        sender = u.effective_user.first_name or u.effective_user.username or "?"
        log.info(f"MSG de {sender}: {text!r}")
        m = OP_RE.search(text)
        if not m:
            log.info("Sin match")
            return
        kw, a1, n1, n2, a2, tc_s = m.groups()
        usd_v = num(a1 if a1 else a2)
        contra = (n1 if n1 else n2).capitalize()
        tc_v = num(tc_s)
        tipo = "Compra" if kw.lower() in ("compro","compra") else "Venta"
        guardar(sender, tipo, contra, usd_v, tc_v, text)
        pu, pa = posicion()
        e = "COMPRA" if tipo=="Compra" else "VENTA"
        sp = "+" if tipo=="Compra" else "-"
        sp2 = "-" if tipo=="Compra" else "+"
        resp = (
            f"{'OK COMPRA' if tipo=='Compra' else 'OK VENTA'}\n"
            f"{contra} | USD {fmt(usd_v)} x $ {fmt(tc_v)}\n"
            f"{sp}USD {fmt(usd_v)} / {sp2}$ {fmt(usd_v*tc_v)}\n\n"
            f"POSICION DE CAJA\n"
            f"USD: {('+' if pu>=0 else '')}{fmt(pu)}\n"
            f"ARS: {('+' if pa>=0 else '')}{fmt(pa)}"
        )
        await u.message.reply_text(resp)
        log.info("Respuesta enviada")
    except Exception as e:
        log.error(f"ERROR: {e}", exc_info=True)
        try:
            await u.message.reply_text(f"Error: {e}")
        except:
            pass
 
def main():
    setup()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("posicion", pos_cmd))
    app.add_handler(CommandHandler("historial", hist_cmd))
    app.add_handler(CommandHandler("excel", excel_cmd))
    app.add_handler(CommandHandler("inicio", inicio_cmd))
    app.add_handler(CommandHandler("borrar", borrar_cmd))
    app.add_handler(MessageHandler(filters.ALL, mensaje))
    log.info("Bot iniciado")
    app.run_polling()
 
if __name__ == "__main__":
    main()
