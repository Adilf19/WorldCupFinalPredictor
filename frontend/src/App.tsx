import { FormEvent, useEffect, useMemo, useState } from 'react'

type Fixture = { id:number; provider:string; external_id:string; home_name:string; away_name:string; kickoff_at:string; match_id:number|null; home_team_id:number|null; away_team_id:number|null; timing_accuracy:string; status:string; competition_id:number|null; competition_name:string|null; competition_format:'league'|'knockout'; home_logo_url?:string|null; away_logo_url?:string|null; home_manager?:string|null; away_manager?:string|null; home_manager_photo_url?:string|null; away_manager_photo_url?:string|null }
type Competition = { provider:string; external_id:string; code:string|null; name:string; country:string|null; format:string; team_type:string; current_season:number|null }
type Prediction = { model_version:string; match_format:'league'|'knockout'; expected_goals_home:number; expected_goals_away:number; home_win_probability:number; draw_probability:number; away_win_probability:number; home_qualification_probability:number|null; away_qualification_probability:number|null; extra_time_probability:number|null; penalties_probability:number|null; projected_home_goals:number; projected_away_goals:number; model_inputs:Record<string,number|null>; top_feature_importance:Record<string,[string,number][]> }
type Heatmap = { columns:number; rows:number; cells:number[]; sample_events:number; sample_matches:number; orientation:string }
type Player = { player_id:number; player_name:string; confidence:number; photo_url?:string|null; shirt_number?:number|null; club_form?:number|null; country_form?:number|null; blended_form?:number|null; form_coverage?:number; availability_status?:string; availability_reason?:string|null }
type KeeperMetrics = { starts:number; minutes:number; goals_conceded_per_90:number|null; clean_sheet_rate:number|null; xg_prevented_per_90:number|null; average_rating:number|null }
type Battle = { label:string; method:string; home_player:Player|null; away_player:Player|null; home_advantage:number|null; confidence:number; spatial_overlap:number|null; explanation:string; home_heatmap:Heatmap|null; away_heatmap:Heatmap|null; direct_h2h?:{sample_matches:number; confidence:number}; similarity_evidence?:{analogous_players:string[]; confidence:number}; goalkeeper_evidence?:{home:KeeperMetrics;away:KeeperMetrics}|null }
type Matchups = { average_confidence:number; evidence_coverage:number; overall_home_advantage:number|null; evidence_scope:string; club_h2h_available:boolean; battles:Battle[]; warnings:string[] }
type Lineups = { mode:string; provider_status:string; home:Player[]; away:Player[]; predicted_home:Player[]; predicted_away:Player[]; actual_home:Player[]; actual_away:Player[]; actual_status:'pending'|'confirmed' }
type Live = { status:string; minute:number|null; home_score:number|null; away_score:number|null; events:{minute:number|null; extra_minute?:number|null; type:string; player?:string; team?:string; comments?:string}[] }

const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const assetUrl = (url?:string|null):string|undefined => url ? (url.startsWith('/api/') ? `${API_BASE_URL}${url}` : url) : undefined
const api = async <T,>(path:string, options?:RequestInit):Promise<T> => {
  const response = await fetch(`${API_BASE_URL}${path}`, { credentials:'include', headers:{'Content-Type':'application/json'}, ...options })
  const contentType=response.headers.get('content-type')||''
  if (!contentType.includes('application/json')) {
    throw new Error(API_BASE_URL
      ? 'The configured API URL did not return the application API. Check VITE_API_URL and the backend deployment.'
      : 'Owner controls need the FastAPI backend. This static site is not connected to one yet; set VITE_API_URL to your hosted API URL and rebuild.')
  }
  const body=await response.json().catch(()=>({detail:''}))
  if (!response.ok) throw new Error(body.detail || 'Request failed')
  return body as T
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
  if (!map) return <div className="heatmap empty">Spatial data unavailable</div>
  const max=Math.max(...map.cells,0.001)
  return <div className="heatmap" style={{gridTemplateColumns:`repeat(${map.columns},1fr)`}} title={`${map.sample_events} events across ${map.sample_matches} matches`}>
    {map.cells.map((cell,index)=><i key={index} style={{opacity:.08+.92*cell/max}} />)}
  </div>
}

function GoalkeeperComparison({battle}:{battle:Battle}) {
  const evidence=battle.goalkeeper_evidence
  if(!evidence)return <div className="keeper-unavailable">Goalkeeper history unavailable</div>
  const value=(metric:keyof KeeperMetrics,raw:number|null)=>raw==null?'—':metric==='clean_sheet_rate'?pct(raw):metric==='average_rating'?raw.toFixed(2):metric==='goals_conceded_per_90'||metric==='xg_prevented_per_90'?raw.toFixed(2):String(raw)
  const rows:[keyof KeeperMetrics,string][]= [['starts','STARTS'],['goals_conceded_per_90','GA / 90'],['clean_sheet_rate','CLEAN SHEETS'],['xg_prevented_per_90','xG PREVENTED / 90'],['average_rating','AVG RATING']]
  return <div className="keeper-comparison"><div className="keeper-name">{battle.home_player?.player_name}</div><div className="keeper-name away">{battle.away_player?.player_name}</div>{rows.map(([metric,label])=><div className="keeper-row" key={metric}><b>{value(metric,evidence.home[metric])}</b><span>{label}</span><b>{value(metric,evidence.away[metric])}</b></div>)}</div>
}

function LineupList({players,teamName,matchups,side}:{players:Player[];teamName:string;matchups:Matchups|null;side:'home'|'away'}) {
  const [openPlayer,setOpenPlayer]=useState<number|null>(null)
  const battleFor=(player:Player)=>matchups?.battles.filter(battle=>(side==='home'?battle.home_player?.player_id:battle.away_player?.player_id)===player.player_id).sort((a,b)=>b.confidence-a.confidence)[0]
  return <div className="squad-list"><h3>{teamName}</h3>{players.map(player=>{const battle=battleFor(player);const opponent=side==='home'?battle?.away_player:battle?.home_player;const playerAdvantage=(side==='home'?1:-1)*(battle?.home_advantage||0);const expanded=openPlayer===player.player_id;return <article className={`squad-row ${expanded?'open':''}`} key={player.player_id}>
    <button className="player-summary" onClick={()=>setOpenPlayer(expanded?null:player.player_id)} aria-expanded={expanded}>
      {player.photo_url?<img src={assetUrl(player.photo_url)} alt="" loading="lazy"/>:<span className="player-avatar">{player.player_name.split(' ').map(name=>name[0]).slice(0,2).join('')}</span>}
      <span className="shirt">#{player.shirt_number||'—'}</span><span className="player-name"><b>{player.player_name}</b><small>{player.availability_status&&player.availability_status!=='unknown'?`${player.availability_status}${player.availability_reason?` · ${player.availability_reason}`:''}`:player.blended_form!=null?`${pct(player.blended_form)} recent form`:'recent form pending'}</small></span>
      <span className="opposition-button">{battle?`${expanded?'Hide':'View'} matchup`:'No matchup'} <b>{battle?'›':''}</b></span>
    </button>
    {expanded&&battle&&<div className="player-matchup"><div className="matchup-copy"><span>{battle.method==='goalkeeper_form_comparison'?'GOALKEEPER COMPARISON':'PREDICTED OPPONENT'}</span><h4>{opponent?.player_name||'Unavailable'}</h4><p>{battle.home_advantage===null?'Edge not scored':playerAdvantage===0?'Even matchup':`${playerAdvantage>0?player.player_name:opponent?.player_name} has a ${pct(Math.abs(playerAdvantage))} modelled edge`} · {pct(battle.confidence)} confidence{battle.spatial_overlap!==null?` · ${pct(battle.spatial_overlap)} average overlap.`:'.'}</p><small>Country form {player.country_form!=null?pct(player.country_form):'not loaded'} · Club form {player.club_form!=null?pct(player.club_form):'not loaded'}</small></div>{battle.method==='goalkeeper_form_comparison'?<GoalkeeperComparison battle={battle}/>:<div className="list-heatmaps"><HeatmapView map={side==='home'?battle.home_heatmap:battle.away_heatmap}/><span>VS</span><HeatmapView map={side==='home'?battle.away_heatmap:battle.home_heatmap}/></div>}</div>}
  </article>})}</div>
}

function Weaknesses({matchups,homeName,awayName}:{matchups:Matchups;homeName:string;awayName:string}) {
  const ranked=[...matchups.battles].filter(battle=>battle.home_advantage!==null)
  const homeWeaknesses=ranked.sort((a,b)=>(a.home_advantage||0)-(b.home_advantage||0)).slice(0,3)
  const awayWeaknesses=[...ranked].sort((a,b)=>(b.home_advantage||0)-(a.home_advantage||0)).slice(0,3)
  const column=(team:string,battles:Battle[],homeIsWeak:boolean)=><div className="weakness-column"><span>{team.toUpperCase()} · THREE PRESSURE POINTS</span>{battles.length?battles.map((battle,index)=>{const advantage=battle.home_advantage||0;const opponentDominates=homeIsWeak?advantage<0:advantage>0;const dominant=homeIsWeak?battle.away_player:battle.home_player;const exposed=homeIsWeak?battle.home_player:battle.away_player;const teamPlayer=homeIsWeak?battle.home_player:battle.away_player;return <article key={`${team}-${index}`}><b>0{index+1}</b><div><strong>{opponentDominates?dominant?.player_name:`${dominant?.player_name} pressure`}</strong><p>{opponentDominates?`projects a ${pct(Math.abs(advantage))} edge over ${exposed?.player_name}`:`is the next-closest contest; ${teamPlayer?.player_name} retains a ${pct(Math.abs(advantage))} edge`}</p></div><small>{pct(battle.spatial_overlap||0)} overlap<br/>{pct(battle.confidence)} confidence</small></article>}):<p className="no-weakness">No player evidence is available yet.</p>}</div>
  return <div className="weakness-grid">{column(homeName,homeWeaknesses,true)}{column(awayName,awayWeaknesses,false)}</div>
}

function OwnerPanel({open,onClose,onFixture}:{open:boolean;onClose:()=>void;onFixture:()=>void}) {
  const [password,setPassword]=useState(''), [stage,setStage]=useState<'login'|'admin'>('login')
  const [message,setMessage]=useState(''), [query,setQuery]=useState(''), [results,setResults]=useState<Fixture[]>([])
  const [manual,setManual]=useState({home_name:'Spain',away_name:'Argentina',kickoff_at:'2026-07-19T20:00',competition_format:'knockout' as 'league'|'knockout'})
  const [competitions,setCompetitions]=useState<Competition[]>([]), [competitionCode,setCompetitionCode]=useState('')
  const [authMissing,setAuthMissing]=useState<string[]>([])
  useEffect(()=>{ if(open){api<{configured:boolean;missing:string[]}>('/api/auth/status').then(r=>setAuthMissing(r.missing));api<{authenticated:boolean}>('/api/auth/me').then(()=>setStage('admin')).catch(()=>setStage('login'))} },[open])
  useEffect(()=>{if(stage==='admin')api<{configured:boolean;results:Competition[];reason?:string}>('/api/admin/competitions').then(r=>{setCompetitions(r.results);if(!r.configured)setMessage(r.reason||'Fixture provider is not configured.')}).catch(e=>setMessage((e as Error).message))},[stage])
  if(!open) return null
  const login=async(e:FormEvent)=>{e.preventDefault();try{await api('/api/auth/login',{method:'POST',body:JSON.stringify({password})});setPassword('');setStage('admin');setMessage('Owner verified.')}catch(e){setMessage((e as Error).message)}}
  const selectedCompetition=competitions.find(item=>(item.code||item.external_id)===competitionCode)
  const sync=async()=>{if(!selectedCompetition)return;const season=selectedCompetition.current_season||new Date().getFullYear();try{setMessage('Syncing two seasons of match history…');await api('/api/admin/competitions/sync',{method:'POST',body:JSON.stringify({competition:competitionCode,seasons:[season-1,season]})});setMessage('History synced. Search upcoming fixtures now.')}catch(e){setMessage((e as Error).message)}}
  const syncApiFootball=async()=>{try{setMessage('Syncing active-team headshots, logos and manager photos…');const r=await api<{media:{players_updated:number;managers_updated:number;teams_updated:number;requests_used:number};note:string}>('/api/admin/providers/api-football/sync',{method:'POST'});setMessage(`API-Football synced ${r.media.players_updated} player photos, ${r.media.managers_updated} manager photos and ${r.media.teams_updated} team logos using ${r.media.requests_used} requests. ${r.note}`);onFixture()}catch(e){setMessage((e as Error).message)}}
  const search=async()=>{try{const path=competitionCode?`/api/admin/provider-fixtures?competition=${encodeURIComponent(competitionCode)}&q=${encodeURIComponent(query)}`:`/api/admin/fixtures/search?q=${encodeURIComponent(query)}`;const r=await api<{results:Fixture[]}>(path);setResults(r.results)}catch(e){setMessage((e as Error).message)}}
  const select=async(item:Partial<Fixture>)=>{try{await api('/api/admin/fixture',{method:'POST',body:JSON.stringify(item)});setMessage('Fixture selected.');onFixture()}catch(e){setMessage((e as Error).message)}}
  return <div className="modal-backdrop" onMouseDown={onClose}><aside className="owner-panel" onMouseDown={e=>e.stopPropagation()}>
    <button className="close" onClick={onClose}>×</button><p className="eyebrow">OWNER CONTROL</p><h2>{stage==='admin'?'Set the stage':'Secure access'}</h2>
    {stage==='login'&&<form onSubmit={login}><label>Owner password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" minLength={8} required /></label><button className="primary" disabled={authMissing.length>0}>Unlock owner controls</button><p className="security-copy">Three failed attempts trigger a 15-minute lockout for this address.</p>{authMissing.length>0&&<div className="notice">Password login needs: {authMissing.join(' and ')}. Add these values to <code>.env</code>, then restart the API.</div>}</form>}
    {stage==='admin'&&<><div className="notice">Choose a licensed competition, sync its last two seasons, then select an upcoming fixture. FotMob scraping remains disabled.</div>
      <button className="secondary" onClick={syncApiFootball}>Sync active fixture media</button>
      <label>Competition<select value={competitionCode} onChange={e=>{setCompetitionCode(e.target.value);setResults([])}}><option value="">Local database</option>{competitions.map(item=><option key={item.external_id} value={item.code||item.external_id}>{item.name} · {item.country}</option>)}</select></label>
      {selectedCompetition&&<button className="secondary" onClick={sync}>Sync {selectedCompetition.current_season ? `${selectedCompetition.current_season-1}–${selectedCompetition.current_season}`:'last two seasons'}</button>}
      <div className="search-row"><input placeholder="Search team" value={query} onChange={e=>setQuery(e.target.value)} /><button onClick={search}>Search</button></div>
      <div className="fixture-results">{results.map(item=><button key={item.external_id} onClick={()=>select(item)}><b>{item.home_name} vs {item.away_name}</b><span>{formatUKKickoff(item.kickoff_at)} · {item.timing_accuracy}</span></button>)}</div>
      <h3>Or enter a fixture</h3><label>Home<input value={manual.home_name} onChange={e=>setManual({...manual,home_name:e.target.value})}/></label><label>Away<input value={manual.away_name} onChange={e=>setManual({...manual,away_name:e.target.value})}/></label><label>Format<select value={manual.competition_format} onChange={e=>setManual({...manual,competition_format:e.target.value as 'league'|'knockout'})}><option value="league">League · 90 minutes</option><option value="knockout">Knockout · ET and pens</option></select></label><label>Kickoff (UK time — BST/GMT)<input type="datetime-local" value={manual.kickoff_at} onChange={e=>setManual({...manual,kickoff_at:e.target.value})}/></label>
      <button className="primary" onClick={()=>select({provider:'manual',external_id:'',home_name:manual.home_name,away_name:manual.away_name,kickoff_at:ukLocalToISOString(manual.kickoff_at),timing_accuracy:'exact',competition_name:'Manual fixture',competition_format:manual.competition_format})}>Set active fixture</button>
    </>}
    {message&&<p className="form-message">{message}</p>}
  </aside></div>
}

export default function App() {
  const [fixture,setFixture]=useState<Fixture|null>(null), [prediction,setPrediction]=useState<Prediction|null>(null), [matchups,setMatchups]=useState<Matchups|null>(null), [lineups,setLineups]=useState<Lineups|null>(null), [live,setLive]=useState<Live|null>(null)
  const [lineupView,setLineupView]=useState<'predicted'|'actual'>('predicted')
  const [ownerOpen,setOwnerOpen]=useState(false), [loading,setLoading]=useState(true), [error,setError]=useState('')
  const load=async()=>{setLoading(true);try{const f=await api<Fixture|null>('/api/public/fixture');setFixture(f);if(f){const [p,m,l,v]=await Promise.all([api<Prediction|null>('/api/public/prediction'),api<Matchups|null>('/api/public/matchups'),api<Lineups|null>('/api/public/lineups'),api<Live>('/api/public/live')]);setPrediction(p);setMatchups(m);setLineups(l);setLive(v)}}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  useEffect(()=>{load()},[])
  useEffect(()=>{const id=setInterval(()=>api<Live>('/api/public/live').then(setLive).catch(()=>{}),15000);return()=>clearInterval(id)},[])
  const countdown=useCountdown(fixture?.kickoff_at)
  useEffect(()=>{if(!countdown?.ended)return;const refresh=()=>api<Lineups|null>('/api/public/lineups').then(value=>{setLineups(value);if(value?.actual_status==='confirmed')setLineupView('actual')}).catch(()=>{});refresh();const id=setInterval(refresh,30000);return()=>clearInterval(id)},[countdown?.ended])
  const modelInputs=useMemo(()=>prediction?Object.entries(prediction.model_inputs).filter(([,v])=>v!==null):[],[prediction])
  return <><OwnerPanel open={ownerOpen} onClose={()=>setOwnerOpen(false)} onFixture={()=>{setOwnerOpen(false);load()}}/><header><a className="brand" href="#top"><span>AF</span><b>ADIL'S FOOTBALL<br/>GAME PREDICTOR</b></a><nav><a href="#lineups">Lineups</a><a href="#matchups">Matchups</a><a href="#method">Method</a></nav><button className="owner" onClick={()=>setOwnerOpen(true)}>Owner access</button></header>
  <main id="top">{error&&<div className="error">{error}</div>}{loading&&!fixture&&<div className="loader">Loading match intelligence…</div>}{!loading&&!fixture&&<section className="empty-state"><p className="eyebrow">NO ACTIVE FIXTURE</p><h1>The stage is waiting.</h1><button className="primary" onClick={()=>setOwnerOpen(true)}>Set fixture</button></section>}
  {fixture&&<><section className="hero"><div className="hero-glow"/><p className="eyebrow">{fixture.competition_name||'MATCH INTELLIGENCE'} · {fixture.competition_format.toUpperCase()}</p><div className="fixture-title"><div>{fixture.home_logo_url?<img className="team-logo" src={assetUrl(fixture.home_logo_url)} alt={`${fixture.home_name} logo`}/>:<span className={`flag ${fixture.home_name==='Spain'?'spain':''}`}>{fixture.home_name.slice(0,2).toUpperCase()}</span>}<span className="team-heading"><h1>{fixture.home_name}</h1>{fixture.home_manager&&<small>{fixture.home_manager_photo_url&&<img src={assetUrl(fixture.home_manager_photo_url)} alt=""/>}Manager · {fixture.home_manager}</small>}</span></div><strong>VS</strong><div>{fixture.away_logo_url?<img className="team-logo" src={assetUrl(fixture.away_logo_url)} alt={`${fixture.away_name} logo`}/>:<span className={`flag ${fixture.away_name==='Argentina'?'argentina':''}`}>{fixture.away_name.slice(0,2).toUpperCase()}</span>}<span className="team-heading"><h1>{fixture.away_name}</h1>{fixture.away_manager&&<small>{fixture.away_manager_photo_url&&<img src={assetUrl(fixture.away_manager_photo_url)} alt=""/>}Manager · {fixture.away_manager}</small>}</span></div></div>
    <p className="kickoff">{formatUKKickoff(fixture.kickoff_at)} · UK time</p>
    {countdown&&!countdown.ended?<div className="countdown">{[['DAYS',countdown.days],['HOURS',countdown.hours],['MIN',countdown.minutes],['SEC',countdown.seconds]].map(([label,value])=><div key={label}><b>{String(value).padStart(2,'0')}</b><span>{label}</span></div>)}</div>:<div className="live-pill"><i/> KICKOFF REACHED</div>}
    {prediction&&<div className="hero-forecast">
      <div className="score-prediction"><span><b>{prediction.projected_home_goals}</b><small>{fixture.home_name} · {prediction.expected_goals_home.toFixed(2)} xG</small></span><em>PROJECTED 90-MINUTE SCORE</em><span><b>{prediction.projected_away_goals}</b><small>{fixture.away_name} · {prediction.expected_goals_away.toFixed(2)} xG</small></span></div>
      {prediction.match_format==='knockout'&&prediction.home_qualification_probability!==null&&prediction.away_qualification_probability!==null?<div className="knockout-outcome"><div className="knockout-labels"><b>{fixture.home_name} {pct(prediction.home_qualification_probability)}</b><span>TO WIN</span><b>{pct(prediction.away_qualification_probability)} {fixture.away_name}</b></div><div className="knockout-bar"><i style={{width:pct(prediction.home_qualification_probability)}}/><i style={{width:pct(prediction.away_qualification_probability)}}/></div><small>Extra time {pct(prediction.extra_time_probability||0)} · Penalties {pct(prediction.penalties_probability||0)} · 90-min wins: {pct(prediction.home_win_probability)} / {pct(prediction.away_win_probability)}</small></div>:<div className="knockout-outcome"><div className="knockout-labels"><b>{fixture.home_name} {pct(prediction.home_win_probability)}</b><span>90 MINUTES</span><b>{pct(prediction.away_win_probability)} {fixture.away_name}</b></div><div className="league-bar"><i style={{width:pct(prediction.home_win_probability)}}/><i style={{width:pct(prediction.draw_probability)}}/><i style={{width:pct(prediction.away_win_probability)}}/></div><small>Home win {pct(prediction.home_win_probability)} · Draw {pct(prediction.draw_probability)} · Away win {pct(prediction.away_win_probability)}</small></div>}
    </div>}
    <div className="hero-live"><span className="live-status"><i/>{live?.status.replaceAll('_',' ')||'scheduled'}</span>{live?.events.length?<div className="ticker compact">{live.events.slice(0,3).map((event,i)=><div key={i}><b>{event.minute==null?'LIVE':`${event.minute}${event.extra_minute?`+${event.extra_minute}`:''}'`}</b><span>{event.player?`${event.type} · ${event.player}`:event.comments||event.type}</span></div>)}</div>:<p>Live ticker is waiting for the selected fixture’s connected match feed.</p>}</div>
  </section>
  {lineups&&<section id="lineups" className="section compact-section"><div className="section-head"><div><p className="eyebrow">02 · {lineups.mode.toUpperCase().replace('_',' ')}</p><h2>Lineup intelligence</h2><p>{lineups.provider_status}. Selection is evidence-first; internal role labels never decide who makes the XI.</p></div><div className="lineup-controls"><button className={lineupView==='predicted'?'active':''} onClick={()=>setLineupView('predicted')}>Predicted XI</button><button className={lineupView==='actual'?'active':''} onClick={()=>setLineupView('actual')}>Actual XI · {lineups.actual_status}</button></div></div>{lineupView==='actual'&&lineups.actual_status==='pending'?<div className="actual-pending"><b>Actual lineup pending</b><p>The app checks the approved lineup feed every 30 seconds after kickoff. Until confirmation arrives, the predicted XI stays available.</p></div>:<div className="lineup-lists"><LineupList players={lineupView==='actual'?lineups.actual_home:lineups.predicted_home} teamName={fixture.home_name} matchups={matchups} side="home"/><LineupList players={lineupView==='actual'?lineups.actual_away:lineups.predicted_away} teamName={fixture.away_name} matchups={matchups} side="away"/></div>}</section>}
  {matchups&&<section id="matchups" className="section dark compact-section"><div className="section-head"><div><p className="eyebrow">03 · SPATIAL MATCHUP ENGINE</p><h2>Player-by-player edges</h2><p className="evidence-note">H2H currently covers the {matchups.evidence_scope}. Club meetings are not counted until a club-event provider is connected.</p></div><div className="confidence-ring" style={{'--confidence':`${matchups.average_confidence*360}deg`} as React.CSSProperties}><b>{pct(matchups.average_confidence)}</b><span>AVG CONF.</span></div></div>
    <Weaknesses matchups={matchups} homeName={fixture.home_name} awayName={fixture.away_name}/>
    <div className="matchup-grid">{matchups.battles.map((battle,index)=>{const hasEdge=battle.home_advantage!==null;const advantage=battle.home_advantage||0;const homeShare=50+advantage*50;const awayShare=100-homeShare;const edgeName=!hasEdge?'Not scored':Math.abs(advantage)<.005?'Even':advantage>0?(battle.home_player?.player_name||fixture.home_name):(battle.away_player?.player_name||fixture.away_name);return <article className={`battle ${battle.method==='goalkeeper_form_comparison'?'keeper-battle':''}`} key={`${battle.label}-${index}`}><div className="battle-head"><span>#{String(index+1).padStart(2,'0')}</span><b>{battle.label}</b><em>{pct(battle.confidence)} confidence</em></div>{battle.method==='goalkeeper_form_comparison'?<GoalkeeperComparison battle={battle}/>:<div className="heatmaps"><HeatmapView map={battle.home_heatmap}/><div className="overlap"><b>{battle.spatial_overlap===null?'—':pct(battle.spatial_overlap)}</b><span>SPACE OVERLAP</span></div><HeatmapView map={battle.away_heatmap}/></div>}<div className={`duel-score ${!hasEdge?'unscored':''}`}><div><b>{hasEdge?`${homeShare.toFixed(1)}%`:'—'}</b><span>{battle.home_player?.player_name}</span></div><strong>{edgeName==='Even'?'EVEN':hasEdge?`${edgeName} +${pct(Math.abs(advantage))}`:'NOT SCORED'}</strong><div><b>{hasEdge?`${awayShare.toFixed(1)}%`:'—'}</b><span>{battle.away_player?.player_name}</span></div></div>{hasEdge&&<div className="advantage-split"><i style={{width:`${homeShare}%`}}/><i style={{width:`${awayShare}%`}}/></div>}<p>{battle.explanation}</p><small>{battle.method==='goalkeeper_form_comparison'?'Keeper comparison: recent country and club appearances where loaded':`World Cup H2H: ${battle.direct_h2h?.sample_matches||0} · Club H2H: not loaded · Similar-player analogues: ${battle.similarity_evidence?.analogous_players?.length||0}`}</small></article>})}</div>
  </section>}
  <section className="section philosophy-section"><p className="eyebrow">DECISION PHILOSOPHY</p><h2>Evidence proportionality, not false certainty.</h2><p>Adil’s Football Game Predictor gives recent and context-relevant evidence the most influence, while missing information lowers confidence instead of becoming a fabricated zero. Team strength, player availability and club-versus-country form are evaluated separately; the matchup engine then tests where opponents actually share space before combining direct meetings, analogous-player evidence and probabilistic score simulation. Every output keeps its evidence trail visible—strong enough to support a decision, but honest about what the model still cannot know.</p></section>
  <section id="method" className="section method compact-section"><p className="eyebrow">04 · MODEL TRANSPARENCY</p><h2>From evidence to probability.</h2><div className="model-story"><h3>LightGBM, explained simply.</h3><p>Two gradient-boosted tree models learn the expected scoring rate for the home and away teams. Each new tree concentrates on the errors left by the earlier trees, so interactions such as strong recent xG plus high shot volume—but weaker opposition—can be learned without a hand-written rule. A Poisson objective keeps the target aligned with football goals. Those two expected-goal rates then power thousands of Monte Carlo score simulations, producing the win, draw, extra-time and penalty probabilities above.</p><small>Leakage control: every training feature is calculated strictly before its match. Missing provider fields reduce coverage; they are never silently replaced with invented performance.</small></div><div className="method-grid">{[['01','FORM','Recent results, xG, shots, possession, passing and opponent strength become leakage-safe team features.'],['02','LINEUPS','Starts, minutes, combinations, form and availability estimate who actually plays; formation slots only label the chosen XI.'],['03','SPACE','Heatmaps, direct meetings and similar opponents estimate the most relevant outfield contests.'],['04','SIMULATION','LightGBM goal rates feed Monte Carlo; knockout fixtures add transparent extra-time and shootout layers.']].map(([n,t,d])=><article key={n}><b>{n}</b><h3>{t}</h3><p>{d}</p></article>)}</div>{prediction&&<details className="inputs"><summary>Inspect all {modelInputs.length} model inputs <span>+</span></summary><div className="input-grid">{modelInputs.map(([key,value])=><div key={key}><span>{pretty(key)}</span><b>{typeof value==='number'?value.toFixed(3):value}</b><small>{key.startsWith('home_')?`${fixture.home_name} history`:key.startsWith('away_')?`${fixture.away_name} history`:key.startsWith('delta_')?`${fixture.home_name} minus ${fixture.away_name}`:'Match context'}</small></div>)}</div></details>}<div className="caveat">Coverage is fixture-specific. Friendlies, leagues and knockouts share the same pipeline, while competition format changes only the post-90-minute simulation. Live injuries, confirmed lineups and events require an approved connected feed.</div></section>
  </>}</main><footer><span>ADIL'S FOOTBALL GAME PREDICTOR · 2026</span><p>Built for transparency. Every number has an evidence trail.</p><button onClick={()=>setOwnerOpen(true)}>Owner</button></footer></>
}
