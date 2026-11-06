import { useContext, useEffect, useRef, useState } from 'react'
import { api } from './api'
import PortalIcon from './PortalIcon'
import { Context, Header, Table, Pager, ErrorBox, useData, pretty, when, entryColumns } from './ui'
import { AdminDashboard, Directory, AuthorityHome, SharedPasses, BatchPage, ImmediatePage, Reports, ProfilePage } from './role-pages'
import './App.css'
import './role-pages.css'
import './portal-theme.css'
import './profile-directory.css'

function Scan(){
 const {user}=useContext(Context),[code,setCode]=useState(''),[entryMode,setEntryMode]=useState('SINGLE'),[pass,setPass]=useState(null),[result,setResult]=useState(null),[busy,setBusy]=useState(false),[camera,setCamera]=useState(false),[message,setMessage]=useState('')
 const scanner=useRef(null),request=useRef(null),method=useRef('QR'),starting=useRef(false),decoding=useRef(false)
 async function stop(){const current=scanner.current;scanner.current=null;if(current){try{await current.stop()}catch{}try{await current.clear()}catch{}}setCamera(false)}
 useEffect(()=>()=>{const current=scanner.current;if(current)current.stop().then(()=>current.clear()).catch(()=>{})},[])
 function sound(allowed){new Audio('/brand/'+(allowed?'entry-allowed.mp3':'entry-denied.wav')).play().catch(()=>{})}
 async function lookup(value,manual=false){if(decoding.current)return;decoding.current=true;setBusy(true);setPass(null);setResult(null);try{await stop();const checked=await api('scan/lookup/',{method:'POST',body:manual?{code:value}:{token:value}});request.current=crypto.randomUUID();method.current=manual?'MANUAL_ID':'QR';setEntryMode('SINGLE');setPass(checked)}catch(e){setResult({allowed:false,message:e.message});sound(false)}finally{setBusy(false);decoding.current=false}}
 async function start(){if(starting.current||scanner.current)return;starting.current=true;setPass(null);setResult(null);setCamera(true);setMessage('Opening camera…');try{const {Html5Qrcode}=await import('html5-qrcode');scanner.current=new Html5Qrcode('qr-reader');const config={fps:15,qrbox:{width:240,height:240}};try{await scanner.current.start({facingMode:'environment'},config,decoded=>lookup(decoded),()=>{})}catch{try{await scanner.current.clear()}catch{}scanner.current=new Html5Qrcode('qr-reader');await scanner.current.start({facingMode:'user'},config,decoded=>lookup(decoded),()=>{})}setMessage('Keep the complete QR code inside the frame.')}catch(e){await stop();setMessage('Unable to open camera. Allow camera access in browser settings. '+(e.message||''))}finally{starting.current=false}}
 async function confirm(mode){if(busy)return;setBusy(true);try{const answer=await api('scan/confirm/',{method:'POST',body:{kind:pass.kind,id:pass.id,mode,method:method.current,request_id:request.current}});setResult(answer);setPass(null);sound(true)}catch(e){setResult({allowed:false,message:e.message});setPass(null);sound(false)}finally{setBusy(false)}}
 return <><Header title="Scan & Physical Check" description="Scan a QR code or enter the Community Card ID / Pass ID. Check the displayed number of people physically, then confirm entry."/><section className="panel scanner-workspace" aria-live="polite">{!pass&&!result&&<><div id="qr-reader" className={'reader '+(camera?'active':'')}/><button className="btn-main full" disabled={busy} onClick={camera?stop:start}>{camera?'STOP CAMERA':'SCAN QR CODE'}</button><p className="camera-message" role="status">{message}</p><div className="divider">OR ENTER ID</div><form onSubmit={e=>{e.preventDefault();lookup(code,true)}}><input aria-label="Community Card ID / Pass ID" required value={code} onChange={e=>setCode(e.target.value)} placeholder="Community ID / CG-... / H5-... / VVIP-... / VOL-..."/><button className="btn-gold full form-submit" disabled={busy}>{busy?'CHECKING…':'CHECK PASS'}</button></form></>}{pass&&<div className="verification"><div className="eyebrow">{pass.kind==='COMBINED'?'CONGREGATION COMBINED PASS':'PHYSICAL VERIFICATION REQUIRED'}</div><h2>{pass.name}</h2><p>Pass ID: {pass.code}</p><div className="admission-count">{entryMode==='FAMILY'?pass.family_people:pass.people_per_entry}<small>{(entryMode==='FAMILY'?pass.family_people:pass.people_per_entry)>1?'people':'person'}</small></div><p>{entryMode==='FAMILY'?'Verify this complete family group before confirming. This privilege can be used once.':pass.unlimited?'Unlimited single entry remains available.':pass.people_per_entry===5?'Allow only after checking the physical group count.':Math.max(0,pass.entry_limit-pass.entries_used)+' entries remaining.'}</p><div className="stack"><button className="btn-main full" disabled={busy||(entryMode==='SINGLE'&&pass.single_available===false)} onClick={()=>confirm(entryMode)}>{entryMode==='FAMILY'?'CONFIRM FAMILY ENTRY':pass.single_available===false?'SINGLE ENTRY NOT AVAILABLE':pass.kind==='COMBINED'?'SINGLE ENTRY':'Confirm & Allow Entry'}</button>{entryMode==='SINGLE'&&(pass.kind==='COMBINED'||(user.role==='VOLUNTEER'&&pass.family_configured))&&(pass.family_available?<button className="btn-gold full" disabled={busy} onClick={()=>pass.kind==='MEMBER'?setEntryMode('FAMILY'):confirm('FAMILY')}>FAMILY ENTRY ({pass.family_people})</button>:<><button className="btn-secondary full" disabled>FAMILY ENTRY ALREADY USED</button><small>This one-time family entry has already been used.</small></>)}<button className="btn-secondary full" onClick={()=>{if(entryMode==='FAMILY')setEntryMode('SINGLE');else setPass(null)}}>Cancel</button></div></div>}{result&&<div className={result.allowed?'admission verification allowed':'admission verification denied'}><div className="result-icon">{result.allowed?'✓':'!'}</div><div className="eyebrow">{result.allowed?'GOVINDA!':'HARI BOL'}</div><h2>{result.allowed?'ENTRY ALLOWED':'ENTRY DENIED'}</h2><p>{result.allowed?result.pass.name+' · '+result.people+' people':result.message}</p><button className="btn-main full" onClick={()=>{setResult(null);setCode('')}}>{result.allowed?'SCAN NEXT':'TRY AGAIN'}</button></div>}</section></>
}

function Logs({audit=false}){
 const [page,setPage]=useState(1),{data,error,loading}=useData((audit?'audit':'entries')+'/?page='+page)
 const columns=audit?[{key:'created_at',label:'Time',render:r=>when(r.created_at)},{key:'action',label:'Action',render:r=>pretty(r.action)},{key:'entity_type',label:'Item',render:r=>pretty(r.entity_type)+' #'+r.entity_id},{key:'admin',label:'Actor',render:r=>r.admin?'Administrator #'+r.admin:r.authority?'Authority #'+r.authority:'Scanner / system'},{key:'reason',label:'Reason'}]:entryColumns
 return <><Header title={audit?'Audit Logs':'Entry Logs'}/><ErrorBox error={error}/><Table columns={columns} rows={data?.results} loading={loading}/>{(data?.next||data?.previous)&&<Pager data={data} page={page} setPage={setPage}/>}</>
}

function Login({onLogin}){
 const [error,setError]=useState(''),[busy,setBusy]=useState(false)
 async function submit(e){e.preventDefault();const body=Object.fromEntries(new FormData(e.currentTarget));setBusy(true);setError('');try{const session=await api('auth/login/',{method:'POST',body});onLogin(session.user)}catch(err){setError(err.message)}finally{setBusy(false)}}
 return <main className="login-layout"><section className="login-art"><div className="art-shade"/><div className="art-copy"><div className="eyebrow">ISKCON TIRUPATI</div><h1>Graceful entry.<br/>Seamless service.</h1><p>A thoughtful community queue experience, in service of every devotee.</p><small>HARE KRISHNA · DARSHAN SEVA PORTAL</small></div></section><section className="login-panel"><div className="login-card"><div className="login-star">✦</div><div className="eyebrow">DARSHAN SEVA PORTAL</div><h2>Hare Krishna</h2><p>Welcome back. Sign in to continue your seva.</p><form onSubmit={submit}><ErrorBox error={error}/><label>Login ID<input name="username" required autoComplete="username" placeholder="Enter your Login ID" autoFocus/></label><label>Password<input name="password" type="password" required autoComplete="current-password" placeholder="Enter your password"/></label><input type="hidden" name="role" value="COMMON"/><button className="btn-main full" disabled={busy}>{busy?'Signing in…':'Secure login →'}</button></form><small className="login-footer">Authorised access · ISKCON Tirupati</small></div></section></main>
}

function homeFor(role){return role==='ADMIN'?'dashboard':role==='AUTHORITY'?'home':'scan'}
export default function App(){
 const [user,setUser]=useState(null),[ready,setReady]=useState(false),[bootError,setBootError]=useState(''),[route,setRoute]=useState(location.hash.slice(2)||'dashboard'),[modal,setModal]=useState(null),[toast,setToast]=useState(null),[menu,setMenu]=useState(false),[options,setOptions]=useState(null),[optionVersion,setOptionVersion]=useState(0)
 const notify=(message,error=false)=>setToast({message,error,key:Date.now()})
 const refreshSession=()=>api('auth/session/').then(s=>{setUser(s.user);if(s.user&&(!location.hash||(s.user.role==='AUTHORITY'&&['/dashboard','/passes'].includes(location.hash.slice(1).split('?')[0]))))location.hash='/'+homeFor(s.user.role);setReady(true)}).catch(e=>{setBootError(e.message);setReady(true)})
 useEffect(()=>{refreshSession()},[])
 useEffect(()=>{const change=()=>{setRoute(location.hash.slice(2)||'dashboard');setMenu(false);setModal(null)};window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change)},[])
 useEffect(()=>{if(user)api('options/').then(setOptions).catch(e=>setToast({message:e.message,error:true,key:Date.now()}))},[user,optionVersion])
 useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(null),5500);return()=>clearTimeout(timer)},[toast])
 useEffect(()=>{if(!modal)return;const previous=document.activeElement,dialog=document.querySelector('.dialog-panel');dialog?.querySelector('button,input,select,textarea')?.focus();const oldOverflow=document.body.style.overflow;document.body.style.overflow='hidden';const listener=e=>{if(e.key==='Escape')setModal(null);if(e.key==='Tab'){const elements=[...dialog.querySelectorAll('button,input,select,textarea,a[href]')].filter(x=>!x.disabled);const first=elements[0],last=elements.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}};window.addEventListener('keydown',listener);return()=>{window.removeEventListener('keydown',listener);document.body.style.overflow=oldOverflow;previous?.focus()}},[modal])
 async function signOut(){try{await api('auth/logout/',{method:'POST',body:{}});setUser(null);setOptions(null);await api('auth/session/')}catch(e){notify(e.message,true)}}
 if(!ready)return <div className="boot"><span>✦</span><p>Preparing your seva portal…</p></div>
 if(bootError)return <div className="boot"><h1>Unable to reach the portal</h1><p>{bootError}</p><p>Start the Django backend and refresh this page.</p><button className="btn-main" onClick={()=>location.reload()}>Try again</button></div>
 if(!user)return <Login onLogin={u=>{setUser(u);location.hash='/'+homeFor(u.role)}}/>
 const admin=user.role==='ADMIN',authority=user.role==='AUTHORITY',[rawPage,rawQuery='']=route.split('?')
 const page=authority&&['dashboard','passes'].includes(rawPage)?'home':rawPage
 const segments=page.split('/'),home=homeFor(user.role)
 const nav=admin?[['profile','user','Profile'],['dashboard','home','Home'],['shared','share','Shared Passes'],['entries','list','Entry Logs'],['reports','chart','Reports'],['audit','clock','Audit Logs']]:authority?[['profile','user','Profile'],['home','home','Home'],['shared','share','Shared Passes']]:user.role==='VOLUNTEER'?[['profile','user','Profile'],['scan','scan','Home']]:[['scan','scan','Home']]
 const allowed=admin?['profile','dashboard','shared','entries','reports','audit','hods','congregations','scanners','gates','vvips','volunteer-passes','immediate','batch']:nav.map(([key])=>key)
 let content
 if(!allowed.includes(segments[0]))content=<section className="panel"><h1>Page unavailable</h1><a href={'#/'+home}>Return home</a></section>
 else if(page==='dashboard')content=<AdminDashboard/>
 else if(page==='home')content=<AuthorityHome/>
 else if(['hods','congregations','scanners','gates'].includes(page))content=<Directory key={page} resource={page}/>
 else if(page==='shared')content=<SharedPasses/>
 else if(page==='vvips'||page==='volunteer-passes')content=<BatchPage key={page} kind={page==='vvips'?'VVIP':'VOLUNTEER'}/>
 else if(segments[0]==='batch'&&['VVIP','VOLUNTEER'].includes(segments[1]))content=<BatchPage key={page} kind={segments[1]} batchId={segments[2]}/>
 else if(page==='immediate')content=<ImmediatePage/>
 else if(page==='reports')content=<Reports/>
 else if(page==='entries'||page==='audit')content=<Logs key={page} audit={page==='audit'}/>
 else if(page==='scan')content=<Scan/>
 else if(page==='profile')content=<ProfilePage/>
 return <Context.Provider value={{user,options,open:(title,body)=>setModal({title,body}),close:()=>setModal(null),notify,refreshSession,refreshOptions:()=>setOptionVersion(x=>x+1)}}>
  <div className={'app-shell '+(menu?'menu-open':'')}>
   <button className="mobile-shade" aria-label="Close navigation" onClick={()=>setMenu(false)}/>
   <aside className="sidebar" id="portal-navigation" aria-label="Main navigation">
    <div className="sidebar-brand-row">
     <a className="brand" href={'#/'+home} onClick={()=>setMenu(false)}><span className="brand-emblem"><PortalIcon name="lotus"/></span><div>DARSHAN SEVA<small>ISKCON TIRUPATI</small></div></a>
     <button className="sidebar-close" aria-label="Close navigation" onClick={()=>setMenu(false)}><PortalIcon name="close"/></button>
    </div>
    <div className="nav-caption">{admin?'TEMPLE AUTHORITY':authority?(options?.profile_type==='BRAHMACHARI'?'BRAHMACHARI':options?.account_type==='CONGREGATION'?'CONGREGATION':'HOD'):'ENTRY SCANNER'}</div>
    <nav>{nav.map(([key,icon,label])=><a key={key} href={'#/'+key} className={page===key?'active':''} aria-current={page===key?'page':undefined} onClick={()=>setMenu(false)}><span className="nav-icon"><PortalIcon name={icon}/></span>{label}</a>)}</nav>
    <div className="sidebar-user"><span className="avatar">{user.name[0]}</span><div><strong>{user.name}</strong><small>{admin?'Temple Authority':pretty(user.role)}</small></div><button title="Logout" aria-label="Logout" onClick={signOut}><PortalIcon name="logout"/></button></div>
   </aside>
   <div className="workspace">
    <div className="topbar"><button className="mobile-menu" aria-label="Open menu" aria-expanded={menu} aria-controls="portal-navigation" onClick={()=>setMenu(true)}><PortalIcon name="menu"/></button><a className="portal-wordmark" href={'#/'+home}>Darshan Seva Portal <span>✦</span></a><div className="session-label">{user.name}<small>{admin?'Temple Authority':authority?'Authority':'Scanner'}</small></div></div>
    <main className={'main-content '+(['hods','congregations','scanners','gates'].includes(page)?'directory-content':'')}>{content}<footer>ISKCON Tirupati <span>Darshan Seva Portal</span></footer></main>
   </div>
  </div>
  {toast&&<div className={'toast-note '+(toast.error?'failure':'')} role="status">{toast.message}<button aria-label="Dismiss" onClick={()=>setToast(null)}>×</button></div>}
  {modal&&<div className="modal-backdrop-custom" onMouseDown={e=>{if(e.target===e.currentTarget)setModal(null)}}><section className="dialog-panel" role="dialog" aria-modal="true" aria-label={modal.title}><header><h2>{modal.title}</h2><button aria-label="Close dialog" onClick={()=>setModal(null)}>×</button></header>{modal.body}</section></div>}
 </Context.Provider>
}
