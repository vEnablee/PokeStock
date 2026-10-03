"""Tema scuro della dashboard.

Stessa direzione visiva della versione chiara — barra a pillola flottante, titoli
Inter molto pesanti, accento rosso, raggi ampi, ombre morbide e riflesso sui
pulsanti — resa su superficie scura.

Il riquadro dell'immagine resta volutamente CHIARO: e' l'unico modo per far
funzionare `mix-blend-mode: multiply`, che fonde un elemento con il suo backdrop.
Su backdrop scuro il multiply schiaccia il prodotto a nero (verificato); con il
riquadro chiaro isolato (`isolation:isolate`) i fondi bianchi delle foto spariscono
e i colori restano intatti.
"""

PALETTE = {
    'bg': '#0B0D12',
    'surface': '#15181F',
    'tint': 'rgba(239,68,68,.10)',
    'ink': '#F2F4F8',
    'ink_soft': '#A3ABBA',
    'muted': '#6B7489',
    'line': 'rgba(255,255,255,.085)',
    'accent': '#EF4444',
    'accent_dk': '#DC2626',
    'green': '#10E07E',
    'green_bg': 'rgba(16,224,126,.12)',
    'amber': '#F5A524',
    'amber_bg': 'rgba(245,165,36,.10)',
    'blue': '#60A5FA',
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
  --bg:#0B0D12; --surface:#15181F; --surface-2:#1A1E27; --tint:rgba(239,68,68,.10);
  --ink:#F2F4F8; --ink-soft:#A3ABBA; --muted:#6B7489; --line:rgba(255,255,255,.085);
  --accent:#EF4444; --accent-dk:#DC2626; --accent-soft:rgba(239,68,68,.16);
  --green:#10E07E; --green-bg:rgba(16,224,126,.12); --green-bd:rgba(16,224,126,.32);
  --amber:#F5A524; --amber-bg:rgba(245,165,36,.10); --amber-bd:rgba(245,165,36,.3);
  --blue:#60A5FA;
  --r-card:20px; --r-inner:14px; --r-pill:999px;
  --sh-sm:0 1px 2px rgba(0,0,0,.4);
  --sh-md:0 6px 20px rgba(0,0,0,.4), 0 1px 3px rgba(0,0,0,.3);
  --sh-lg:0 22px 50px rgba(0,0,0,.6), 0 4px 12px rgba(0,0,0,.4);
  --sh-red:0 10px 28px rgba(239,68,68,.34);
}

html, body, [class*="st-"], .stApp { font-family:'Inter',-apple-system,sans-serif; color:var(--ink); }
.stApp { background:
    radial-gradient(1200px 540px at 50% -16%, rgba(239,68,68,.20), transparent 64%),
    radial-gradient(820px 400px at 88% 2%,  rgba(239,68,68,.10), transparent 60%),
    var(--bg); }
/* Si nascondono i SINGOLI elementi del chrome di Streamlit, non l'intera
   toolbar: il pulsante che riapre la sidebar vive li' dentro, e visibility
   si eredita ai figli — nasconderla rendeva impossibile recuperare la barra
   laterale una volta chiusa. */
#MainMenu, footer { visibility:hidden; }
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"],
[data-testid="stToolbarActions"] { display:none !important; }
header, [data-testid="stHeader"] { background:transparent !important; }

/* Il controllo per riaprire la sidebar resta sempre raggiungibile e visibile. */
[data-testid="stExpandSidebarButton"],
[data-testid="stExpandSidebarButton"] * { visibility:visible !important; }
/* stExpandSidebarButton E' il bottone, non un contenitore: lo si stila
   direttamente. stSidebarCollapsedControl copre le versioni di Streamlit
   in cui il controllo e' avvolto in un wrapper. */
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"] button {
    width:34px !important; height:34px !important;
    background-color:rgba(21,24,31,.92) !important;
    background-image:url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23F2F4F8%22%20stroke-width%3D%222.1%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M4%206h10%22%2F%3E%3Cpath%20d%3D%22M4%2012h16%22%2F%3E%3Cpath%20d%3D%22M4%2018h10%22%2F%3E%3Cpath%20d%3D%22m17%209%203%203-3%203%22%2F%3E%3C%2Fsvg%3E") !important;
    background-repeat:no-repeat !important; background-position:center !important;
    background-size:18px 18px !important;
    border:1px solid var(--line) !important; border-radius:12px !important;
    box-shadow:var(--sh-md) !important; backdrop-filter:blur(10px);
    /* Streamlit disegna l'icona con una legatura del font Material Symbols.
       Se quel font non si carica (rete lenta o bloccata) compare il testo grezzo
       "double_arrow_right". font-size:0 lo azzera e l'icona la disegna il
       background-image qui sopra, che non dipende da risorse esterne. */
    font-size:0 !important; color:transparent !important;
    transition:border-color .2s, background-image .2s, transform .2s; }
[data-testid="stExpandSidebarButton"] *,
[data-testid="stSidebarCollapsedControl"] button * { display:none !important; }
[data-testid="stExpandSidebarButton"]:hover,
[data-testid="stSidebarCollapsedControl"] button:hover {
    border-color:rgba(239,68,68,.5) !important;
    background-image:url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23EF4444%22%20stroke-width%3D%222.1%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M4%206h10%22%2F%3E%3Cpath%20d%3D%22M4%2012h16%22%2F%3E%3Cpath%20d%3D%22M4%2018h10%22%2F%3E%3Cpath%20d%3D%22m17%209%203%203-3%203%22%2F%3E%3C%2Fsvg%3E") !important;
    transform:translateY(-1px); }

/* Il pulsante che CHIUDE la sidebar soffre della stessa legatura Material
   ("keyboard_double_arrow_left"): se il font non carica compare il testo grezzo.
   Stesso rimedio: testo azzerato e icona disegnata da un SVG inline. */
[data-testid="stSidebarCollapseButton"] button {
    width:32px !important; height:32px !important;
    background-color:rgba(255,255,255,.05) !important;
    background-image:url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23A3ABBA%22%20stroke-width%3D%222.1%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22m7%209-3%203%203%203%22%2F%3E%3Cpath%20d%3D%22m12%209-3%203%203%203%22%2F%3E%3C%2Fsvg%3E") !important;
    background-repeat:no-repeat !important; background-position:center !important;
    background-size:17px 17px !important;
    border:1px solid var(--line) !important; border-radius:10px !important;
    font-size:0 !important; color:transparent !important;
    transition:border-color .2s, background-image .2s; }
[data-testid="stSidebarCollapseButton"] button * { display:none !important; }
[data-testid="stSidebarCollapseButton"] button:hover {
    border-color:rgba(239,68,68,.5) !important;
    background-image:url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23EF4444%22%20stroke-width%3D%222.1%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22m7%209-3%203%203%203%22%2F%3E%3Cpath%20d%3D%22m12%209-3%203%203%203%22%2F%3E%3C%2Fsvg%3E") !important; }

/* Stessa protezione per le icone a legatura di expander e widget. */
[data-testid="stExpanderToggleIcon"] { font-size:1.1rem; }
.block-container { padding-top:2.6rem; max-width:1520px; }

/* ---------- intestazione a pillola ---------- */
.bar { display:flex; align-items:center; justify-content:space-between; gap:1rem;
       flex-wrap:wrap; padding:.85rem 1.5rem; margin:.2rem 0 1.8rem; border-radius:var(--r-pill);
       background:rgba(21,24,31,.82); backdrop-filter:blur(16px);
       border:1px solid rgba(255,255,255,.08); box-shadow:var(--sh-lg);
       animation:rise .5s ease-out backwards; }
.brand { display:flex; align-items:center; gap:.7rem; font-size:1.18rem;
         font-weight:800; letter-spacing:-.03em; color:var(--ink); }
.brand .mk { display:grid; place-items:center; width:32px; height:32px; border-radius:10px;
             background:linear-gradient(145deg,var(--accent),#FB7185); color:#fff;
             box-shadow:var(--sh-red); }
.brand .mk svg { width:17px; height:17px; }
.brand b { color:var(--accent); font-weight:800; }
.bar .meta { font-size:.78rem; color:var(--ink-soft); font-weight:500; }

/* ---------- titolo ---------- */
.lede { text-align:center; margin:.4rem 0 2rem; animation:rise .55s ease-out backwards; }
.lede h1 { font-size:clamp(2.1rem,4.6vw,3.4rem); font-weight:900; letter-spacing:-.045em;
           line-height:.98; margin:0; color:var(--ink); }
.lede h1 em { font-style:normal; color:var(--accent); display:block; }
.lede p { color:var(--ink-soft); font-size:.97rem; margin:.85rem auto 0; max-width:620px; }
.lede p b { color:var(--ink); font-weight:700; }

/* ---------- badge live ---------- */
.live { display:inline-flex; align-items:center; gap:.5rem; padding:.44rem .9rem;
        border-radius:var(--r-pill); background:var(--green-bg); color:var(--green);
        border:1px solid var(--green-bd); font-size:.76rem; font-weight:700; white-space:nowrap; }
.live.off { background:rgba(255,255,255,.05); color:var(--muted); border-color:var(--line); }
.dot { width:7px; height:7px; border-radius:50%; background:var(--green);
       box-shadow:0 0 0 0 rgba(16,224,126,.6); animation:pulse 2s infinite; }
.dot.idle { background:var(--muted); animation:none; box-shadow:none; }
@keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(16,224,126,.6)}
                   70%{box-shadow:0 0 0 10px rgba(16,224,126,0)}
                   100%{box-shadow:0 0 0 0 rgba(16,224,126,0)} }

/* ---------- KPI ---------- */
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(214px,1fr));
            gap:1rem; margin-bottom:1.5rem; }
.kpi { padding:1.2rem 1.3rem; border-radius:var(--r-card); background:var(--surface);
       border:1px solid var(--line); box-shadow:var(--sh-md);
       animation:rise .5s ease-out backwards;
       transition:transform .26s cubic-bezier(.2,.8,.2,1), box-shadow .26s, border-color .26s; }
.kpi:hover { transform:translateY(-3px); box-shadow:var(--sh-lg);
             border-color:rgba(239,68,68,.35); background:var(--surface-2); }
.kpi .label { color:var(--muted); font-size:.69rem; font-weight:700;
              text-transform:uppercase; letter-spacing:.08em; }
.kpi .value { font-size:2.05rem; font-weight:800; letter-spacing:-.035em;
              margin:.35rem 0 .2rem; line-height:1; color:var(--ink); }
.kpi .sub { font-size:.75rem; color:var(--ink-soft); }
.kpi.k2 .value { color:var(--green); }
.kpi.k3 .value { color:var(--blue); }
.kpi.k4 .value { color:var(--accent); }
.kpi:nth-child(2){animation-delay:.05s} .kpi:nth-child(3){animation-delay:.1s}
.kpi:nth-child(4){animation-delay:.15s}

/* ---------- griglia ---------- */
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:1.1rem; }

.card { display:flex; flex-direction:column; justify-content:space-between;
        border-radius:var(--r-card); background:var(--surface); border:1px solid var(--line);
        overflow:hidden; box-shadow:var(--sh-sm); animation:rise .4s ease-out backwards;
        transition:transform .26s cubic-bezier(.2,.8,.2,1), box-shadow .26s, border-color .26s; }
.card:hover { transform:translateY(-5px); box-shadow:var(--sh-lg);
              border-color:rgba(239,68,68,.35); background:var(--surface-2); }
.card:hover .shot { transform:scale(1.05); }

/* Riquadro immagine: altezza FISSA, cosi' i pulsanti restano allineati fra card.
   isolation:isolate crea un contesto di fusione proprio: solo cosi' il multiply
   dell'immagine agisce sul riquadro chiaro e non sulla card. Senza, il prodotto
   verrebbe schiacciato a nero. */
.frame { position:relative; height:180px; margin:.7rem .7rem 0; border-radius:var(--r-inner);
         background:linear-gradient(158deg,#FBFCFE 0%,#EFF2F7 100%);
         border:1px solid rgba(255,255,255,.06); overflow:hidden; isolation:isolate; }
.shot { position:absolute; inset:7%; background-size:contain; background-repeat:no-repeat;
        background-position:center; mix-blend-mode:multiply;
        filter:contrast(104%) saturate(104%);
        transition:transform .28s cubic-bezier(.2,.8,.2,1); }
.noimg { position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
         color:#C2C9D6; }
.noimg svg { width:40px; height:40px; }

.tags { position:absolute; top:.55rem; left:.55rem; right:.55rem; z-index:2;
        display:flex; align-items:flex-start; justify-content:space-between; gap:.35rem; }
.tag { font-size:.61rem; font-weight:800; letter-spacing:.04em; text-transform:uppercase;
       padding:.3rem .52rem; border-radius:var(--r-pill); white-space:nowrap;
       box-shadow:var(--sh-sm); }
.tag.stock { background:var(--green); color:#fff; }
.tag.out   { background:rgba(255,255,255,.07); color:var(--ink-soft);
             border:1px solid var(--line); }
.tag.pre   { background:var(--blue); color:#fff; }
.tag.msrp  { background:var(--green-bg); color:var(--green); border:1px solid var(--green-bd); }
.tag.over  { background:var(--amber-bg); color:var(--amber); border:1px solid var(--amber-bd); }
.tag.save  { background:var(--accent); color:#fff; }

.body { padding:.85rem .95rem 1rem; display:flex; flex-direction:column; gap:.5rem; flex:1; }
.title { font-size:.9rem; font-weight:650; line-height:1.34; color:var(--ink);
         display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
         overflow:hidden; text-overflow:ellipsis; min-height:2.42em; }
.meta { display:flex; align-items:baseline; justify-content:space-between; gap:.5rem; }
.price { font-size:1.45rem; font-weight:800; letter-spacing:-.03em; color:var(--green); }
.price.over { color:var(--amber); }
.seen { font-size:.68rem; color:var(--muted); white-space:nowrap; }
.delta { font-size:.72rem; color:var(--ink-soft); }
.delta.gain { color:var(--green); font-weight:600; }
.delta.loss { color:var(--amber); font-weight:600; }
.store { display:flex; align-items:center; gap:.4rem; font-size:.7rem; font-weight:600;
         color:var(--ink-soft); padding-top:.4rem; border-top:1px solid var(--line);
         margin-top:.1rem; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.store svg { width:13px; height:13px; color:var(--muted); flex-shrink:0; }
.plat { color:var(--muted); font-weight:500; }

.cta, .cta:hover, .cta:visited { text-decoration:none !important; }
.cta { display:flex; align-items:center; justify-content:center; gap:.4rem; margin-top:auto;
       padding:.68rem .8rem; border-radius:var(--r-pill); font-size:.78rem; font-weight:800;
       letter-spacing:.015em; color:#fff !important; position:relative; overflow:hidden;
       background:linear-gradient(135deg,var(--accent),#FB7185);
       box-shadow:0 6px 18px rgba(239,68,68,.38);
       transition:transform .2s, box-shadow .2s, filter .2s; }
.cta svg { width:14px; height:14px; }
.cta:hover { transform:translateY(-2px); filter:brightness(1.08);
             box-shadow:0 12px 30px rgba(239,68,68,.52); }
.cta::after { content:''; position:absolute; top:0; left:-120%; width:55%; height:100%;
              background:linear-gradient(90deg,transparent,rgba(255,255,255,.45),transparent);
              transform:skewX(-22deg); transition:left .55s ease; }
.cta:hover::after { left:140%; }
.cta.muted { background:rgba(255,255,255,.06); color:var(--ink-soft) !important;
             box-shadow:none; border:1px solid var(--line); }
.cta.muted:hover { transform:none; filter:none; box-shadow:var(--sh-sm); }

/* ---------- skeleton ---------- */
.sk { border-radius:var(--r-card); border:1px solid var(--line); background:var(--surface);
      overflow:hidden; box-shadow:var(--sh-sm); }
.sk .sk-img { height:180px; margin:.7rem .7rem 0; border-radius:var(--r-inner); }
.sk .sk-line { height:10px; margin:.7rem .95rem; border-radius:999px; }
.sk .sk-line.short { width:55%; }
.shimmer { background:linear-gradient(90deg,rgba(255,255,255,.04) 25%,rgba(255,255,255,.1) 50%,rgba(255,255,255,.04) 75%);
           background-size:200% 100%; animation:shimmer 1.4s infinite; }
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
@keyframes rise { from{opacity:0; transform:translateY(12px)} to{opacity:1; transform:none} }

/* ---------- sezioni, avvisi, vuoto ---------- */
.sec { display:flex; align-items:center; gap:.55rem; font-size:1.05rem; font-weight:800;
       letter-spacing:-.02em; margin:1.5rem 0 .9rem; color:var(--ink); }
.sec svg { width:17px; height:17px; color:var(--accent); }
.sec .n { font-size:.7rem; font-weight:700; color:var(--ink-soft); background:rgba(255,255,255,.05);
          padding:.2rem .55rem; border-radius:var(--r-pill); border:1px solid var(--line); }
.notice { display:flex; align-items:center; gap:.55rem; padding:.7rem .95rem; margin-bottom:.85rem;
          border-radius:var(--r-inner); font-size:.79rem; color:#FFD9A0;
          background:var(--amber-bg); border:1px solid var(--amber-bd); }
.notice svg { width:15px; height:15px; flex-shrink:0; color:var(--amber); }
.empty { text-align:center; padding:3.2rem 1rem; color:var(--ink-soft); background:var(--surface);
         border:1px dashed rgba(255,255,255,.12); border-radius:var(--r-card); }
.empty svg { width:40px; height:40px; color:#3A4152; }
.ic { width:1em; height:1em; vertical-align:-.12em; flex-shrink:0; }

/* ---------- controlli Streamlit ---------- */
section[data-testid="stSidebar"] { background:rgba(13,15,20,.96); border-right:1px solid var(--line); }
section[data-testid="stSidebar"] .block-container { padding-top:1.3rem; }
section[data-testid="stSidebar"] h3 { font-size:.82rem; font-weight:800; letter-spacing:.07em;
                                      text-transform:uppercase; color:var(--muted); }

/* Tab come controllo segmentato.
   Streamlit 1.64 non espone piu' gli attributi data-baseweb: i selettori stabili
   sono role="tablist" / data-testid="stTab". Si tengono anche i vecchi per
   compatibilita' con versioni precedenti. */
.stTabs [role="tablist"], .stTabs [data-baseweb="tab-list"] {
    display:inline-flex !important; gap:.25rem; padding:.3rem;
    margin:0 0 .6rem;
    /* width:auto non basta: il contenitore flex genitore lo stirava a tutta
       larghezza (1040px per 498px di tab). fit-content lo fa aderire. */
    width:fit-content !important; flex:0 0 auto !important; align-self:flex-start;
    background:rgba(255,255,255,.045); border:1px solid var(--line);
    border-radius:var(--r-pill); box-shadow:var(--sh-sm); }

.stTabs [data-testid="stTab"], .stTabs [role="tab"], .stTabs [data-baseweb="tab"] {
    height:auto !important; padding:.52rem 1.15rem !important;
    border-radius:var(--r-pill) !important; border:none !important;
    font-size:.78rem; font-weight:700; letter-spacing:.045em;
    color:var(--muted); background:transparent;
    white-space:nowrap; cursor:pointer;
    transition:color .2s, background .2s, box-shadow .2s; }
.stTabs [data-testid="stTab"] p, .stTabs [role="tab"] p {
    font-size:inherit !important; font-weight:inherit !important;
    letter-spacing:inherit; margin:0; color:inherit; }

.stTabs [role="tab"]:hover { color:var(--ink); background:rgba(255,255,255,.055); }

.stTabs [role="tab"][aria-selected="true"],
.stTabs [data-testid="stTab"][data-selected="true"] {
    color:#fff !important;
    background:linear-gradient(135deg,var(--accent),#FB7185) !important;
    box-shadow:0 4px 14px rgba(239,68,68,.34); }
.stTabs [role="tab"][aria-selected="true"] p { color:#fff !important; }

/* Con le pillole l'indicatore di selezione non serve: in Streamlit 1.64 e'
   un div.react-aria-SelectionIndicator alto 2px dentro la tab attiva. */
.stTabs .react-aria-SelectionIndicator,
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {
    display:none !important; }
.stTabs [data-testid="stTab"]::after, .stTabs [role="tab"]::after { display:none !important; }

/* pulsanti: pillola rossa per il primario, pillola bianca per i secondari */
.stButton > button { border-radius:var(--r-pill); font-weight:700; font-size:.78rem;
                     border:1px solid var(--line); background:rgba(255,255,255,.055); color:var(--ink);
                     transition:transform .2s, box-shadow .2s, border-color .2s; }
.stButton > button:hover { transform:translateY(-1px); box-shadow:var(--sh-md);
                           border-color:rgba(239,68,68,.45); color:var(--accent);
                           background:var(--accent-soft); }
.stButton > button[kind="primary"] { background:linear-gradient(135deg,var(--accent),#F43F5E);
                                     color:#fff; border:none; box-shadow:var(--sh-red); }
.stButton > button[kind="primary"] { background:linear-gradient(135deg,var(--accent),#FB7185); }
.stButton > button[kind="primary"]:hover { color:#fff; filter:brightness(1.06);
                                           box-shadow:0 14px 34px rgba(239,68,68,.5); }
.stDownloadButton > button { border-radius:var(--r-pill); font-weight:700; }

/* slider in rosso */
[data-testid="stSlider"] [role="slider"] { background-color:var(--accent) !important;
                                           box-shadow:0 0 0 4px rgba(239,68,68,.22) !important; }
[data-testid="stSlider"] [data-baseweb="slider"] div[style*="background"] { }
.stSlider [data-testid="stTickBar"] { background:transparent; }

/* campi */
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div {
    border-radius:var(--r-inner) !important; border-color:var(--line) !important; }
.stTextInput input:focus { border-color:var(--accent) !important;
                           box-shadow:0 0 0 3px rgba(239,68,68,.18) !important; }

/* riquadro errori di scansione */
.errbox { padding:.8rem .9rem; border-radius:var(--r-inner);
          background:var(--amber-bg); border:1px solid var(--amber-bd); }
.errbox .hd { display:flex; align-items:center; gap:.4rem; font-size:.76rem; font-weight:800;
              color:var(--amber); margin-bottom:.45rem; }
.errbox .hd svg { width:14px; height:14px; }
.errbox .rw { display:flex; justify-content:space-between; gap:.5rem; font-size:.73rem;
              color:var(--ink-soft); padding:.16rem 0; }
.errbox .rw b { color:var(--amber); font-weight:700; }
.errbox .ft { font-size:.68rem; color:var(--muted); margin-top:.45rem; }

.spin { display:inline-block; animation:spin 1s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

/* tabelle piu' arieggiate */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    border-radius:var(--r-inner); overflow:hidden; border:1px solid var(--line); }
</style>
"""
