import { FormEvent, useEffect, useMemo, useState } from 'react'

type Fixture = { id:number; provider:string; external_id:string; home_name:string; away_name:string; kickoff_at:string; match_id:number|null; home_team_id:number|null; away_team_id:number|null; timing_accuracy:string; status:string }
type Prediction = { model_version:string; expected_goals_home:number; expected_goals_away:number; home_win_probability:number; draw_probability:number; away_win_probability:number; home_qualification_probability:number; away_qualification_probability:number; extra_time_probability:number; penalties_probability:number; projected_home_goals:number; projected_away_goals:number; model_inputs:Record<string,number|null>; top_feature_importance:Record<string,[string,number][]> }
type Heatmap = { columns:number; rows:number; cells:number[]; sample_events:number; sample_matches:number; orientation:string }
type Player = { player_id:number; player_name:string; assigned_role:string; confidence:number }
type Battle = { label:string; home_player:Player|null; away_player:Player|null; home_advantage:number|null; confidence:number; spatial_overlap:number|null; explanation:string; home_heatmap:Heatmap|null; away_heatmap:Heatmap|null; direct_h2h?:{sample_matches:number; confidence:number}; similarity_evidence?:{analogous_players:string[]; confidence:number} }
type Matchups = { average_confidence:number; evidence_coverage:number; overall_home_advantage:number|null; evidence_scope:string; club_h2h_available:boolean; battles:Battle[]; warnings:string[] }
type Lineups = { mode:string; provider_status:string; home:Player[]; away:Player[] }
type Live = { status:string; minute:number|null; home_score:number|null; away_score:number|null; events:{minute:number; type:string; player?:string; team?:string}[] }

const api = async <T,>(path:string, options?:RequestInit):Promise<T> => {
  const response = await fetch(path, { credentials:'include', headers:{'Content-Type':'application/json'}, ...options })
  if (!response.ok) { const body = await response.json().catch(()=>({detail:'Request failed'})); throw new Error(body.detail || 'Request failed') }
  return response.json()
}

const pct = (value:number) => `${(value * 100).toFixed(1)}%`
const pretty = (key:string) => key.replace(/^(home|away|delta)_/, '').replaceAll('_',' ').replace(/\b\w/g, c=>c.toUpperCase())
const UK_TIME_ZONE = 'Europe/London'
const formatUKKickoff = (kickoff:string) => new Intl.DateTimeFormat('en-GB', {
  weekday:'long', day:'numeric', month:'long', year:'numeric', hour:'2-digit', minute:'2-digit',
  timeZone:UK_TIME_ZONE, timeZoneName:'short', hourCycle:'h23'
}).format(new Date(kickoff))

// Convert a timezone-less datetime-local value entered as UK wall-clock time to UTC.
function ukLocalToISOString(value:string) {
  const [datePart,timePart] = value.split('T')
  const [year,month,day] = datePart.split('-').map(Number)
  const [hour,minute] = timePart.split(':').map(Number)
  const wallClockUTC = Date.UTC(year,month-1,day,hour,minute)
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone:UK_TIME_ZONE, year:'numeric', month:'2-digit', day:'2-digit',
    hour:'2-digit', minute:'2-digit', second:'2-digit', hourCycle:'h23'
  }).formatToParts(new Date(wallClockUTC))
  const part = (type:string) => Number(parts.find(item=>item.type===type)?.value)
  const londonAtGuess = Date.UTC(part('year'),part('month')-1,part('day'),part('hour'),part('minute'),part('second'))
  return new Date(wallClockUTC-(londonAtGuess-wallClockUTC)).toISOString()
}

function useCountdown(kickoff?:string) {
  const [now,setNow] = useState(Date.now())
  useEffect(()=>{ const id=setInterval(()=>setNow(Date.now()),1000); return()=>clearInterval(id)},[])
  if (!kickoff) return null
  const remaining = Math.max(0,new Date(kickoff).getTime()-now)
  const total=Math.floor(remaining/1000)
  return { ended:remaining===0, days:Math.floor(total/86400), hours:Math.floor(total%86400/3600), minutes:Math.floor(total%3600/60), seconds:total%60 }
}

function HeatmapView({map}:{map:Heatmap|null}) {
  if (!map) return <div className="heatmap empty">No spatial map</div>
  const max=Math.max(...map.cells,0.001)
  return <div className="heatmap" style={{gridTemplateColumns:`repeat(${map.columns},1fr)`}} title={`${map.sample_events} events across ${map.sample_matches} matches`}>
    {map.cells.map((cell,index)=><i key={index} style={{opacity:.08+.92*cell/max}} />)}
  </div>
}

const rolePosition:Record<string,[number,number]> = { GK:[50,90], RB:[82,73], RCB:[61,76], LCB:[39,76], LB:[18,73], DM:[50,57], RCM:[67,45], LCM:[33,45], RW:[82,24], ST:[50,14], LW:[18,24] }
function Pitch({players,flip=false}:{players:Player[];flip?:boolean}) {
  return <div className={`pitch ${flip?'flip':''}`}><div className="pitch-lines" />{players.map(player=>{
    const [x,y]=rolePosition[player.assigned_role]||[50,50]
    return <div className="pitch-player" key={player.player_id} style={{left:`${x}%`,top:`${y}%`}}><b>{player.assigned_role}</b><span>{player.player_name.split(' ').at(-1)}</span></div>
  })}</div>
}

function OwnerPanel({open,onClose,onFixture}:{open:boolean;onClose:()=>void;onFixture:()=>void}) {
  const [email,setEmail]=useState('adi.asif19@gmail.com'), [code,setCode]=useState(''), [stage,setStage]=useState<'email'|'code'|'admin'>('email')
  const [message,setMessage]=useState(''), [query,setQuery]=useState(''), [results,setResults]=useState<Fixture[]>([])
  const [manual,setManual]=useState({home_name:'Spain',away_name:'Argentina',kickoff_at:'2026-07-19T20:00'})
  useEffect(()=>{ if(open) api<{authenticated:boolean}>('/api/auth/me').then(()=>setStage('admin')).catch(()=>setStage('email')) },[open])
  if(!open) return null
  const request=async(e:FormEvent)=>{e.preventDefault();try{const r=await api<{message:string}>('/api/auth/request-code',{method:'POST',body:JSON.stringify({email})});setMessage(r.message);setStage('code')}catch(e){setMessage((e as Error).message)}}
  const verify=async(e:FormEvent)=>{e.preventDefault();try{await api('/api/auth/verify-code',{method:'POST',body:JSON.stringify({email,code})});setStage('admin');setMessage('Owner verified.')}catch(e){setMessage((e as Error).message)}}
  const search=async()=>{try{const r=await api<{results:Fixture[]}>(`/api/admin/fixtures/search?q=${encodeURIComponent(query)}`);setResults(r.results)}catch(e){setMessage((e as Error).message)}}
  const select=async(item:Partial<Fixture>)=>{try{await api('/api/admin/fixture',{method:'POST',body:JSON.stringify(item)});setMessage('Fixture selected.');onFixture()}catch(e){setMessage((e as Error).message)}}
  return <div className="modal-backdrop" onMouseDown={onClose}><aside className="owner-panel" onMouseDown={e=>e.stopPropagation()}>
    <button className="close" onClick={onClose}>×</button><p className="eyebrow">OWNER CONTROL</p><h2>{stage==='admin'?'Set the stage':'Secure access'}</h2>
    {stage==='email'&&<form onSubmit={request}><label>Email address<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></label><button className="primary">Send verification code</button></form>}
    {stage==='code'&&<form onSubmit={verify}><label>Four-digit code<input className="code" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,4))} inputMode="numeric" required /></label><button className="primary">Verify owner</button></form>}
    {stage==='admin'&&<><div className="notice">Fixture search uses your normalized database. Automated FotMob search is disabled until licensed access is available.</div>
      <div className="search-row"><input placeholder="Search team" value={query} onChange={e=>setQuery(e.target.value)} /><button onClick={search}>Search</button></div>
      <div className="fixture-results">{results.map(item=><button key={item.external_id} onClick={()=>select(item)}><b>{item.home_name} vs {item.away_name}</b><span>{formatUKKickoff(item.kickoff_at)} · {item.timing_accuracy}</span></button>)}</div>
      <h3>Or enter a fixture</h3><label>Home<input value={manual.home_name} onChange={e=>setManual({...manual,home_name:e.target.value})}/></label><label>Away<input value={manual.away_name} onChange={e=>setManual({...manual,away_name:e.target.value})}/></label><label>Kickoff (UK time — BST/GMT)<input type="datetime-local" value={manual.kickoff_at} onChange={e=>setManual({...manual,kickoff_at:e.target.value})}/></label>
      <button className="primary" onClick={()=>select({provider:'manual',external_id:'',home_name:manual.home_name,away_name:manual.away_name,kickoff_at:ukLocalToISOString(manual.kickoff_at),timing_accuracy:'exact'})}>Set active fixture</button>
    </>}
    {message&&<p className="form-message">{message}</p>}
  </aside></div>
}

export default function App() {
  const [fixture,setFixture]=useState<Fixture|null>(null), [prediction,setPrediction]=useState<Prediction|null>(null), [matchups,setMatchups]=useState<Matchups|null>(null), [lineups,setLineups]=useState<Lineups|null>(null), [live,setLive]=useState<Live|null>(null)
  const [ownerOpen,setOwnerOpen]=useState(false), [loading,setLoading]=useState(true), [error,setError]=useState('')
  const load=async()=>{setLoading(true);try{const f=await api<Fixture|null>('/api/public/fixture');setFixture(f);if(f){const [p,m,l,v]=await Promise.all([api<Prediction|null>('/api/public/prediction'),api<Matchups|null>('/api/public/matchups'),api<Lineups|null>('/api/public/lineups'),api<Live>('/api/public/live')]);setPrediction(p);setMatchups(m);setLineups(l);setLive(v)}}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  useEffect(()=>{load()},[])
  useEffect(()=>{const id=setInterval(()=>api<Live>('/api/public/live').then(setLive).catch(()=>{}),15000);return()=>clearInterval(id)},[])
  const countdown=useCountdown(fixture?.kickoff_at)
  const modelInputs=useMemo(()=>prediction?Object.entries(prediction.model_inputs).filter(([,v])=>v!==null):[],[prediction])
  return <><OwnerPanel open={ownerOpen} onClose={()=>setOwnerOpen(false)} onFixture={()=>{setOwnerOpen(false);load()}}/><header><a className="brand" href="#top"><span>FI</span><b>FINAL<br/>INTELLIGENCE</b></a><nav><a href="#lineups">Lineups</a><a href="#matchups">Matchups</a><a href="#method">Method</a></nav><button className="owner" onClick={()=>setOwnerOpen(true)}>Owner access</button></header>
  <main id="top">{error&&<div className="error">{error}</div>}{loading&&!fixture&&<div className="loader">Loading match intelligence…</div>}{!loading&&!fixture&&<section className="empty-state"><p className="eyebrow">NO ACTIVE FIXTURE</p><h1>The stage is waiting.</h1><button className="primary" onClick={()=>setOwnerOpen(true)}>Set fixture</button></section>}
  {fixture&&<><section className="hero"><div className="hero-glow"/><p className="eyebrow">FIFA WORLD CUP 26 · THE FINAL</p><div className="fixture-title"><div><span className="flag spain">ES</span><h1>{fixture.home_name}</h1></div><strong>VS</strong><div><span className="flag argentina">AR</span><h1>{fixture.away_name}</h1></div></div>
    <p className="kickoff">{formatUKKickoff(fixture.kickoff_at)} · UK time</p>
    {countdown&&!countdown.ended?<div className="countdown">{[['DAYS',countdown.days],['HOURS',countdown.hours],['MIN',countdown.minutes],['SEC',countdown.seconds]].map(([label,value])=><div key={label}><b>{String(value).padStart(2,'0')}</b><span>{label}</span></div>)}</div>:<div className="live-pill"><i/> KICKOFF REACHED</div>}
    {prediction&&<div className="hero-forecast">
      <div className="projected-score"><span><b>{prediction.projected_home_goals}</b><small>{prediction.expected_goals_home.toFixed(2)} xG</small></span><em>PROJECTED 90'</em><span><b>{prediction.projected_away_goals}</b><small>{prediction.expected_goals_away.toFixed(2)} xG</small></span></div>
      <div className="knockout-outcome"><div className="knockout-labels"><b>{fixture.home_name} {pct(prediction.home_qualification_probability)}</b><span>TO LIFT THE CUP</span><b>{pct(prediction.away_qualification_probability)} {fixture.away_name}</b></div><div className="knockout-bar"><i style={{width:pct(prediction.home_qualification_probability)}}/><i style={{width:pct(prediction.away_qualification_probability)}}/></div><small>Extra time {pct(prediction.extra_time_probability)} · Penalties {pct(prediction.penalties_probability)} · 90-min wins: {pct(prediction.home_win_probability)} / {pct(prediction.away_win_probability)}</small></div>
    </div>}
    <div className="hero-live"><span className="live-status"><i/>{live?.status.replaceAll('_',' ')||'scheduled'}</span>{live?.events.length?<div className="ticker compact">{live.events.slice(0,3).map((event,i)=><div key={i}><b>{event.minute}'</b><span>{event.type} · {event.player}</span></div>)}</div>:<p>Live ticker begins when the approved match feed connects.</p>}</div>
  </section>
  {lineups&&<section id="lineups" className="section compact-section"><div className="section-head"><div><p className="eyebrow">02 · {lineups.mode.toUpperCase().replace('_',' ')}</p><h2>Lineup intelligence</h2><p>{lineups.provider_status}</p></div><span className={`status ${lineups.mode}`}>{lineups.mode==='confirmed'?'Confirmed':'Modelled'}</span></div><div className="lineup-grid"><div><h3>{fixture.home_name}</h3><Pitch players={lineups.home}/></div><div><h3>{fixture.away_name}</h3><Pitch players={lineups.away} flip/></div></div></section>}
  {matchups&&<section id="matchups" className="section dark compact-section"><div className="section-head"><div><p className="eyebrow">03 · SPATIAL MATCHUP ENGINE</p><h2>Player-by-player edges</h2><p className="evidence-note">H2H currently covers the {matchups.evidence_scope}. Club meetings are not counted until a club-event provider is connected.</p></div><div className="confidence-ring" style={{'--confidence':`${matchups.average_confidence*360}deg`} as React.CSSProperties}><b>{pct(matchups.average_confidence)}</b><span>AVG CONF.</span></div></div>
    <div className="matchup-grid">{matchups.battles.map((battle,index)=>{const advantage=battle.home_advantage||0;const homeShare=50+advantage*50;const awayShare=100-homeShare;const edgeName=Math.abs(advantage)<.005?'Even':advantage>0?(battle.home_player?.player_name||fixture.home_name):(battle.away_player?.player_name||fixture.away_name);return <article className="battle" key={`${battle.label}-${index}`}><div className="battle-head"><span>#{String(index+1).padStart(2,'0')}</span><b>{battle.label}</b><em>{pct(battle.confidence)} confidence</em></div><div className="heatmaps"><HeatmapView map={battle.home_heatmap}/><div className="overlap"><b>{pct(battle.spatial_overlap||0)}</b><span>SPACE OVERLAP</span></div><HeatmapView map={battle.away_heatmap}/></div><div className="duel-score"><div><b>{homeShare.toFixed(1)}%</b><span>{battle.home_player?.player_name}</span></div><strong>{edgeName==='Even'?'EVEN':`${edgeName} +${pct(Math.abs(advantage))}`}</strong><div><b>{awayShare.toFixed(1)}%</b><span>{battle.away_player?.player_name}</span></div></div><div className="advantage-split"><i style={{width:`${homeShare}%`}}/><i style={{width:`${awayShare}%`}}/></div><p>{battle.explanation}</p><small>World Cup H2H: {battle.direct_h2h?.sample_matches||0} · Club H2H: not loaded · Similar-player analogues: {battle.similarity_evidence?.analogous_players?.length||0}</small></article>})}</div>
  </section>}
  <section id="method" className="section method compact-section"><p className="eyebrow">04 · MODEL TRANSPARENCY</p><h2>From evidence to probability.</h2><div className="method-grid">{[['01','FORM','Leakage-safe recent form becomes team-strength features.'],['02','SPACE','Heatmap overlap finds each player’s most likely opponent.'],['03','GOALS','LightGBM estimates each side’s 90-minute scoring rate.'],['04','KNOCKOUT','Extra time uses one-third goal rates; a tied shootout is treated as 50/50.']].map(([n,t,d])=><article key={n}><b>{n}</b><h3>{t}</h3><p>{d}</p></article>)}</div>{prediction&&<details className="inputs"><summary>Inspect all {modelInputs.length} model inputs <span>+</span></summary><div className="input-grid">{modelInputs.map(([key,value])=><div key={key}><span>{pretty(key)}</span><b>{typeof value==='number'?value.toFixed(3):value}</b><small>{key.startsWith('home_')?'Spain history':key.startsWith('away_')?'Argentina history':key.startsWith('delta_')?'Spain minus Argentina':'Match context'}</small></div>)}</div></details>}<div className="caveat">The qualification forecast adds a transparent extra-time and penalty layer to the 90-minute model. It still cannot know red cards, late injuries or shootout takers.</div></section>
  </>}</main><footer><span>FINAL INTELLIGENCE · 2026</span><p>Built for transparency. Every number has an evidence trail.</p><button onClick={()=>setOwnerOpen(true)}>Owner</button></footer></>
}
