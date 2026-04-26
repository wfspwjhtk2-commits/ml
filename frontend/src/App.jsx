import { useState, useEffect, useCallback } from "react";

const COLORS = {
  USD:"#4f8ef7",EUR:"#f5a623",JPY:"#f74f4f",GBP:"#a855f7",
  CHF:"#10d48e",AUD:"#f97316",CAD:"#06b6d4",CNY:"#f472b6"
};
const FLAGS = {
  USD:"🇺🇸",EUR:"🇪🇺",JPY:"🇯🇵",GBP:"🇬🇧",
  CHF:"🇨🇭",AUD:"🇦🇺",CAD:"🇨🇦",CNY:"🇨🇳"
};
const MEDALS = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣"];
const C = {bg:"#030608",card:"#06090f",border:"#0d1525",t:"#b0c8e8",dim:"#283050"};

// Fallback-Daten wenn API noch lädt
const FALLBACK_CURRENCIES = [
  {code:"CHF",score:75,z:1.82,regime:"BULL",kelly:0.18,realRate:"-0.55",sentiment:{signal:"neutral",score:0,n_relevant:0,headlines:[]}},
  {code:"EUR",score:68,z:1.21,regime:"BULL",kelly:0.14,realRate:"-0.05",sentiment:{signal:"neutral",score:0,n_relevant:0,headlines:[]}},
  {code:"GBP",score:56,z:0.39,regime:"SIDEWAYS",kelly:0.08,realRate:"0.65",sentiment:{signal:"neutral",score:0,n_relevant:0,headlines:[]}},
  {code:"AUD",score:50,z:0.00,regime:"SIDEWAYS",kelly:0.05,realRate:"0.70",sentiment:{signal:"neutral",score:0,n_relevant:0,headlines:[]}},
  {code:"JPY",score:44,z:-0.39,regime:"SIDEWAYS",kelly:0.03,realRate:"-2.40",sentiment:{signal:"neutral",score:0,n_relevant:0,headlines:[]}},
  {code:"CAD",score:43,z:-0.46,regime:"SIDEWAYS",kelly:0.03,realRate:"0.25",sentiment:{signal:"neutral",score:0,n_relevant:0,headlines:[]}},
  {code:"USD",score:40,z:-0.66,regime:"BEAR",kelly:0.02,realRate:"0.825",sentiment:{signal:"neutral",score:0,n_relevant:0,headlines:[]}},
  {code:"CNY",score:38,z:-0.79,regime:"BEAR",kelly:0.01,realRate:"-2.60",sentiment:{signal:"neutral",score:0,n_relevant:0,headlines:[]}},
];

function scoreColor(s) {
  if (s>=70) return "#10d48e";
  if (s>=55) return "#7ef542";
  if (s>=45) return "#f5c842";
  if (s>=35) return "#f58c42";
  return "#f54242";
}
function scoreLabel(s) {
  if (s>=70) return "STARK LONG";
  if (s>=55) return "LONG";
  if (s>=45) return "NEUTRAL";
  if (s>=35) return "SHORT";
  return "STARK SHORT";
}
function sentimentColor(sig) {
  if (sig==="bullish") return "#10d48e";
  if (sig==="bearish") return "#f54242";
  return "#f5c842";
}

// ── Komponente: Currency Card ─────────────────────────────────────────
function CurrencyCard({ c, rank, expanded, onToggle }) {
  const sc = scoreColor(c.score);
  const sent = c.sentiment || {};
  const sentCol = sentimentColor(sent.signal);
  const comp = c.components || {};

  return (
    <div
      onClick={onToggle}
      style={{
        background:C.card,
        border:`1px solid ${expanded ? sc+"88" : sc+"22"}`,
        borderRadius:8,
        padding:"12px 14px",
        cursor:"pointer",
        transition:"border-color 0.2s",
      }}
    >
      {/* Header */}
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
        <span style={{fontSize:14}}>{MEDALS[rank]}</span>
        <span style={{fontSize:22}}>{FLAGS[c.code]}</span>
        <div style={{flex:1}}>
          <div style={{fontSize:11,fontWeight:800,color:COLORS[c.code]}}>{c.code}</div>
          <div style={{fontSize:7,color:C.dim}}>{scoreLabel(c.score)}</div>
        </div>
        <div style={{textAlign:"right"}}>
          <div style={{fontSize:20,fontWeight:900,color:sc}}>{c.score}</div>
          <div style={{fontSize:7,color:sc}}>{c.z>=0?"+":""}{c.z} σ</div>
        </div>
      </div>

      {/* Score Bar */}
      <div style={{height:8,background:"#030608",borderRadius:4,overflow:"hidden",marginBottom:6}}>
        <div style={{
          height:"100%",width:`${c.score}%`,
          background:`linear-gradient(90deg,${sc}44,${sc})`,
          borderRadius:4,transition:"width 1.5s ease",
        }}/>
      </div>

      {/* Tags */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",fontSize:7,marginBottom:expanded?8:0}}>
        <span style={{
          color:c.regime==="BULL"?"#10d48e":c.regime==="BEAR"?"#f54242":"#f5c842",
          padding:"1px 5px",borderRadius:2,fontWeight:700,
          background:c.regime==="BULL"?"#10d48e18":c.regime==="BEAR"?"#f5424218":"#f5c84218",
        }}>{c.regime}</span>

        <span style={{
          color:sentCol,padding:"1px 5px",borderRadius:2,fontWeight:700,
          background:`${sentCol}18`,
        }}>
          {sent.signal==="bullish"?"📰 BULLISH":sent.signal==="bearish"?"📰 BEARISH":"📰 NEUTRAL"}
          {sent.n_relevant>0&&` (${sent.n_relevant})`}
        </span>

        <span style={{color:"#3a5070"}}>Kelly {(c.kelly*100).toFixed(1)}%</span>
        <span style={{color:"#3a5070"}}>Real {c.realRate}%</span>
      </div>

      {/* Expanded: Details */}
      {expanded && (
        <div style={{
          borderTop:`1px solid ${sc}22`,
          paddingTop:8,
          marginTop:4,
        }}>
          {/* Score-Komponenten */}
          <div style={{fontSize:7,color:C.dim,marginBottom:4,letterSpacing:1}}>
            ML-SCORE BREAKDOWN:
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:4,marginBottom:8}}>
            {[
              ["Fundamental", comp.fundamental, "#5080d0"],
              ["News/Sentiment", comp.news_impact, "#f5a623"],
              ["FX-Momentum", comp.fx_momentum, "#10d48e"],
              ["Risk-Sentiment", comp.fg_impact, "#a855f7"],
            ].map(([l,v,col])=>(
              <div key={l} style={{background:"#030608",borderRadius:4,padding:"5px",textAlign:"center"}}>
                <div style={{fontSize:5,color:C.dim,marginBottom:2}}>{l}</div>
                <div style={{fontSize:10,fontWeight:700,
                             color:v===undefined||v===null?"#3a5070":v>=0?col:"#f54242"}}>
                  {v===undefined||v===null?"–":`${v>=0?"+":""}${typeof v==="number"?v.toFixed(1):v}`}
                </div>
              </div>
            ))}
          </div>

          {/* News Headlines */}
          {sent.headlines && sent.headlines.length>0 && (
            <div>
              <div style={{fontSize:7,color:C.dim,marginBottom:4,letterSpacing:1}}>
                TOP NEWS ({sent.n_relevant} relevant):
              </div>
              {sent.headlines.map((h,i)=>(
                <div key={i} style={{
                  fontSize:7,color:"#4a6080",
                  padding:"3px 6px",
                  background:"#040710",
                  borderRadius:3,
                  marginBottom:3,
                  borderLeft:`2px solid ${h.hawkish_dovish>0?"#f54242":h.hawkish_dovish<0?"#10d48e":"#3a5070"}`,
                }}>
                  {h.text?.substring(0,100)}
                  {h.hawkish_dovish!==0&&(
                    <span style={{
                      marginLeft:4,
                      color:h.hawkish_dovish>0?"#f54242":"#10d48e",
                      fontWeight:700,fontSize:6,
                    }}>
                      {h.hawkish_dovish>0?"🦅 HAWKISH":"🕊 DOVISH"}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Komponente: Signal Card ───────────────────────────────────────────
function SignalCard({ p }) {
  const c = p.edge>1.8?"#10d48e":p.edge>1.2?"#f5c842":"#f58c42";
  return (
    <div style={{background:C.card,border:`1px solid ${c}28`,borderRadius:8,padding:"12px 14px"}}>
      <div style={{display:"flex",justifyContent:"space-between",marginBottom:4}}>
        <div>
          <span style={{fontSize:14,fontWeight:900,color:"#5080a0"}}>{p.pair}</span>
          <span style={{marginLeft:8,fontSize:12,fontWeight:900,color:"#10d48e"}}>▲ LONG</span>
        </div>
        <span style={{fontSize:8,color:c,fontWeight:700}}>Edge {p.edge}</span>
      </div>
      <div style={{fontSize:7,color:C.dim,marginBottom:5}}>
        Konfidenz {p.confidence}%
      </div>
      <div style={{height:4,background:"#030608",borderRadius:2,overflow:"hidden"}}>
        <div style={{height:"100%",width:`${p.confidence}%`,background:c,transition:"width 1s"}}/>
      </div>
    </div>
  );
}

// ── MAIN APP ──────────────────────────────────────────────────────────
export default function App() {
  const [data, setData]         = useState({currencies: FALLBACK_CURRENCIES, pairs:[], market:{}, newsAnalyzed:0});
  const [loading, setLoading]   = useState(true);
  const [status, setStatus]     = useState("🟡 Laden...");
  const [lastUp, setLastUp]     = useState(null);
  const [tab, setTab]           = useState("ranking");
  const [expanded, setExpanded] = useState(null);
  const [countdown, setCountdown] = useState(60);

  const refresh = useCallback(async () => {
    setStatus("⏳ Analysiere News...");
    setCountdown(60);
    try {
      const r = await fetch("/api/score");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setData(j);
      setLastUp(new Date());
      setStatus(`🟢 LIVE · ${j.newsAnalyzed} News analysiert`);
    } catch (e) {
      setStatus(`🟡 Fallback (${e.message})`);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial + 60-Sekunden-Refresh
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 60_000);
    return () => clearInterval(id);
  }, [refresh]);

  // Countdown-Timer
  useEffect(() => {
    const id = setInterval(() => setCountdown(c => c > 0 ? c-1 : 60), 1000);
    return () => clearInterval(id);
  }, []);

  const { currencies=[], pairs=[], market={}, newsAnalyzed=0 } = data;

  return (
    <div style={{minHeight:"100vh",background:C.bg,color:C.t,
                 fontFamily:"'IBM Plex Mono',monospace,sans-serif",fontSize:12}}>

      {/* TOPBAR */}
      <div style={{background:C.card,borderBottom:`1px solid ${C.border}`,
                   padding:"8px 16px",position:"sticky",top:0,zIndex:99}}>
        <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap",marginBottom:6}}>

          {/* Logo */}
          <div style={{display:"flex",gap:8,alignItems:"center"}}>
            <div style={{width:30,height:30,borderRadius:6,
                         background:"linear-gradient(135deg,#1040e0,#00a0d0)",
                         display:"flex",alignItems:"center",justifyContent:"center",
                         fontSize:10,fontWeight:900,color:"#fff"}}>SQ</div>
            <div>
              <div style={{fontSize:9,fontWeight:800,letterSpacing:3,color:"#5080d0"}}>SENTINEL v19</div>
              <div style={{fontSize:6,color:C.dim}}>ML · News · FX · Live</div>
            </div>
          </div>

          {/* Marktdaten */}
          {[
            ["F&G", market.fearGreed||63, (market.fearGreed||63)>60?"#10d48e":"#f58c42"],
            ["EUR/USD", market.eurusd||"–", "#f5a623"],
            ["USD/JPY", market.usdjpy||"–", "#f74f4f"],
            ["GBP/USD", market.gbpusd||"–", "#a855f7"],
          ].map(([l,v,c])=>(
            <div key={l} style={{padding:"2px 7px",background:C.bg,
                                  border:`1px solid ${C.border}`,borderRadius:3,fontSize:8}}>
              <span style={{color:C.dim}}>{l} </span>
              <span style={{color:c,fontWeight:700}}>{v}</span>
            </div>
          ))}

          {/* Status */}
          <div style={{marginLeft:"auto",display:"flex",gap:8,alignItems:"center"}}>
            <span style={{fontSize:7,color:C.dim}}>{status}</span>
            {lastUp&&(
              <span style={{fontSize:7,color:"#2a3850"}}>
                {lastUp.toLocaleTimeString("de-DE")} · nächste in {countdown}s
              </span>
            )}
            <button onClick={refresh} style={{
              padding:"3px 8px",background:"#1040e018",
              border:"1px solid #1040e0",borderRadius:3,
              color:"#5080d0",fontSize:7,cursor:"pointer",fontFamily:"inherit",
            }}>↻</button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{display:"flex",gap:3}}>
          {["ranking","signale","news"].map(t=>(
            <button key={t} onClick={()=>setTab(t)} style={{
              padding:"3px 10px",
              background:tab===t?"#1040e022":"transparent",
              border:`1px solid ${tab===t?"#1040e0":C.border}`,
              borderRadius:3,color:tab===t?"#5080d0":C.dim,
              fontSize:7,cursor:"pointer",fontFamily:"inherit",
            }}>{t.toUpperCase()}</button>
          ))}
        </div>
      </div>

      <div style={{padding:"14px 16px",maxWidth:1000,margin:"0 auto"}}>

        {loading && (
          <div style={{textAlign:"center",padding:"40px",color:C.dim,fontSize:9}}>
            ⏳ ML-Modell analysiert Live-News... (erste Anfrage ~5 Sek)
          </div>
        )}

        {/* ══ RANKING ══ */}
        {tab==="ranking" && !loading && (
          <div style={{display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:8}}>
            {currencies.map((c,i) => (
              <CurrencyCard
                key={c.code}
                c={c}
                rank={i}
                expanded={expanded===c.code}
                onToggle={()=>setExpanded(expanded===c.code?null:c.code)}
              />
            ))}
          </div>
        )}

        {/* ══ SIGNALE ══ */}
        {tab==="signale" && !loading && (
          <div>
            <div style={{background:C.card,border:`1px solid ${C.border}`,borderRadius:8,
                         padding:"8px 12px",marginBottom:10,fontSize:8,color:"#3a5080",lineHeight:1.8}}>
              ⚡ ML-Score = Fundamental (40%) + News-Sentiment (25%) + FX-Momentum (20%) + Risk-Sentiment (15%)
            </div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:8}}>
              {pairs.map((p,i) => <SignalCard key={i} p={p}/>)}
            </div>
          </div>
        )}

        {/* ══ NEWS ══ */}
        {tab==="news" && !loading && (
          <div>
            <div style={{background:C.card,border:`1px solid ${C.border}`,borderRadius:8,
                         padding:"8px 12px",marginBottom:10,fontSize:8,color:"#3a5080",lineHeight:1.8}}>
              📰 {newsAnalyzed} Headlines analysiert · Hawkish = Zinsen rauf → Währung stärker · Dovish = Zinsen runter → schwächer
            </div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:8}}>
              {currencies.map(c => {
                const sent = c.sentiment||{};
                if (!sent.headlines?.length) return null;
                const sc = sentimentColor(sent.signal);
                return (
                  <div key={c.code} style={{background:C.card,border:`1px solid ${sc}22`,
                                            borderRadius:8,padding:"12px 14px"}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                      <span style={{fontSize:20}}>{FLAGS[c.code]}</span>
                      <div style={{flex:1}}>
                        <span style={{fontSize:11,fontWeight:800,color:COLORS[c.code]}}>{c.code}</span>
                        <span style={{marginLeft:8,fontSize:7,color:sc,fontWeight:700}}>
                          {sent.signal?.toUpperCase()} ({sent.n_relevant} relevant)
                        </span>
                      </div>
                      <div style={{fontSize:11,fontWeight:700,
                                   color:sent.score>0?"#10d48e":sent.score<0?"#f54242":"#f5c842"}}>
                        {sent.score>0?"+":""}{sent.score?.toFixed(1)} Pkt
                      </div>
                    </div>
                    {sent.headlines.map((h,i)=>(
                      <div key={i} style={{
                        fontSize:7,color:"#4a6080",padding:"4px 6px",
                        background:"#040710",borderRadius:3,marginBottom:3,
                        borderLeft:`2px solid ${h.hawkish_dovish>0?"#f54242":h.hawkish_dovish<0?"#10d48e":"#3a5070"}`,
                      }}>
                        {h.text?.substring(0,110)}
                        {h.hawkish_dovish!==0&&(
                          <span style={{
                            marginLeft:4,fontWeight:700,fontSize:6,
                            color:h.hawkish_dovish>0?"#f54242":"#10d48e",
                          }}>
                            {h.hawkish_dovish>0?"🦅":"🕊"}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div style={{marginTop:12,textAlign:"center",fontSize:6,color:"#080c16"}}>
          SENTINEL v19 · ML: Fundamental+News+FX+Sentiment · Kein Finanzberater
        </div>
      </div>
    </div>
  );
}
