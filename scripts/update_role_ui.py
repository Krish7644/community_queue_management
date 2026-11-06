from pathlib import Path
import re

root=Path('frontend/src')
old=(root/'App.jsx').read_text(encoding='utf-8')
def function(name):
    match=re.search(r'(?m)^function '+re.escape(name)+r'\(',old)
    end=re.search(r'(?m)^(?:function |export default function )',old[match.end():])
    return old[match.start():match.end()+end.start()] if end else old[match.start():]

shared=old[old.index('const Context=createContext(null)'):old.index('function Dashboard()')]
shared=re.sub(r'function Header\(\{title,description,children\}\)\{.*?\}\n',"""function Header({title,description,children}){
 const context=useContext(Context),home=context?.user?.role==='ADMIN'?'dashboard':context?.user?.role==='AUTHORITY'?'home':'scan'
 const current=location.hash.slice(2).split('?')[0]
 return <>{current&&current!==home&&<a className="back-link" href={'#/'+home}>← Back</a>}<header className="page-header"><div><div className="eyebrow">DARSHAN SEVA PORTAL</div><h1>{title}</h1>{description&&<p>{description}</p>}</div><div className="actions">{children}</div></header></>
}
""",shared,count=1)
ui="import { createContext, useContext, useEffect, useRef, useState } from 'react'\nimport { api } from './api'\n"+shared+"\nexport {Context,pretty,when,f,req,optionsFor,useData,Badge,ErrorBox,Header,Form,Table,Pager,entryColumns}\n"
(root/'ui.jsx').write_text(ui,encoding='utf-8')
role=(root/'role-pages.jsx').read_text(encoding='utf-8')
role=role.replace('when, f, req }','when, f, req, optionsFor }')
pass_form=function('PassForm')
pass_form=pass_form.replace(",f('count','Number of passes','number',{min:1,max:500})","")
pass_form=pass_form.replace("f('name','Recipient name'","f('name','Pass holder name'")
role+='\n'+pass_form
(root/'role-pages.jsx').write_text(role,encoding='utf-8')
login=function('Login')
login=re.sub(r'<label>Account role<select.*?</select></label>', '<input type="hidden" name="role" value="COMMON"/>',login,flags=re.S)
scan=function('Scan')
render=scan.index(' return <>')
scan=scan[:render]+""" return <><Header title="Scan & Physical Check" description="Scan a QR code or enter the Community Card ID / Pass ID. Check the displayed number of people physically, then confirm entry."/><section className="panel scanner-workspace" aria-live="polite">{!pass&&!result&&<><div id="qr-reader" className={'reader '+(camera?'active':'')}/><button className="btn-main full" disabled={busy} onClick={camera?stop:start}>{camera?'STOP CAMERA':'SCAN QR CODE'}</button><p className="camera-message" role="status">{message}</p><div className="divider">OR ENTER ID</div><form onSubmit={e=>{e.preventDefault();lookup(code,true)}}><input aria-label="Community Card ID / Pass ID" required value={code} onChange={e=>setCode(e.target.value)} placeholder="Community ID / CG-... / H5-... / VVIP-... / VOL-..."/><button className="btn-gold full form-submit" disabled={busy}>{busy?'CHECKING…':'CHECK PASS'}</button></form></>}{pass&&<div className="verification"><div className="eyebrow">{pass.kind==='COMBINED'?'CONGREGATION COMBINED PASS':'PHYSICAL VERIFICATION REQUIRED'}</div><h2>{pass.name}</h2><p>Pass ID: {pass.code}</p><div className="admission-count">{pass.people_per_entry}<small>{pass.people_per_entry===5?'members':'person'}</small></div><p>{pass.unlimited?'Unlimited single entry remains available.':pass.people_per_entry===5?'Allow only after checking the physical group count.':Math.max(0,pass.entry_limit-pass.entries_used)+' entries remaining.'}</p><div className="stack"><button className="btn-main full" disabled={busy} onClick={()=>confirm('SINGLE')}>{pass.kind==='COMBINED'?'SINGLE ENTRY':'Confirm & Allow Entry'}</button>{(pass.kind==='COMBINED'||(user.role==='VOLUNTEER'&&pass.family_available))&&(pass.family_available?<button className="btn-gold full" disabled={busy} onClick={()=>confirm('FAMILY')}>FAMILY ENTRY {pass.kind==='COMBINED'?'(5)':''}</button>:<><button className="btn-secondary full" disabled>5 MEMBER PASS OVER</button><small>Family entry has already been used. Single entry remains available.</small></>)}<button className="btn-secondary full" onClick={()=>setPass(null)}>Cancel</button></div></div>}{result&&<div className={result.allowed?'admission verification allowed':'admission verification denied'}><div className="result-icon">{result.allowed?'✓':'!'}</div><div className="eyebrow">{result.allowed?'GOVINDA!':'HARI BOL'}</div><h2>{result.allowed?'ENTRY ALLOWED':'ENTRY DENIED'}</h2><p>{result.allowed?result.pass.name+' · '+result.people+' people':result.message}</p><button className="btn-main full" onClick={()=>{setResult(null);setCode('')}}>{result.allowed?'SCAN NEXT':'TRY AGAIN'}</button></div>}</section></>
}
"""
scan=scan.replace("const {options}=useContext(Context)", "const {user}=useContext(Context)")
logs="""function Logs({audit=false}){
 const [page,setPage]=useState(1),{data,error,loading}=useData((audit?'audit':'entries')+'/?page='+page)
 const columns=audit?[{key:'created_at',label:'Time',render:r=>when(r.created_at)},{key:'action',label:'Action',render:r=>pretty(r.action)},{key:'entity_type',label:'Item',render:r=>pretty(r.entity_type)+' #'+r.entity_id},{key:'admin',label:'Actor',render:r=>r.admin?'Administrator #'+r.admin:r.authority?'Authority #'+r.authority:'Scanner / system'},{key:'reason',label:'Reason'}]:entryColumns
 return <><Header title={audit?'Audit Logs':'Entry Logs'}/><ErrorBox error={error}/><Table columns={columns} rows={data?.results} loading={loading}/>{(data?.next||data?.previous)&&<Pager data={data} page={page} setPage={setPage}/>}</>
}
"""
app="""function homeFor(role){return role==='ADMIN'?'dashboard':role==='AUTHORITY'?'home':'scan'}
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
 const nav=admin?[['profile','○','Profile'],['dashboard','◈','Home'],['shared','↗','Shared Passes'],['entries','≡','Entry Logs'],['reports','▥','Reports'],['audit','◷','Audit Logs']]:authority?[['profile','○','Profile'],['home','◈','Home'],['shared','↗','Shared Passes']]:user.role==='VOLUNTEER'?[['profile','○','Profile'],['scan','⌗','Home']]:[['scan','⌗','Home']]
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
 return <Context.Provider value={{user,options,open:(title,body)=>setModal({title,body}),close:()=>setModal(null),notify,refreshSession,refreshOptions:()=>setOptionVersion(x=>x+1)}}><div className={'app-shell '+(menu?'menu-open':'')}><button className="mobile-shade" aria-label="Close navigation" onClick={()=>setMenu(false)}/><aside className="sidebar"><a className="brand" href={'#/'+home}><span>✦</span><div>DARSHAN SEVA<small>ISKCON TIRUPATI</small></div></a><div className="nav-caption">{admin?'TEMPLE AUTHORITY':authority?(options?.profile_type==='BRAHMACHARI'?'BRAHMACHARI':options?.account_type==='CONGREGATION'?'CONGREGATION':'HOD'):'ENTRY SCANNER'}</div><nav>{nav.map(([key,icon,label])=><a key={key} href={'#/'+key} className={page===key?'active':''}><span aria-hidden="true">{icon}</span>{label}</a>)}</nav><div className="sidebar-user"><span className="avatar">{user.name[0]}</span><div><strong>{user.name}</strong><small>{admin?'Temple Authority':pretty(user.role)}</small></div><button title="Logout" aria-label="Logout" onClick={signOut}>⇥</button></div></aside><div className="workspace"><div className="topbar"><button className="mobile-menu" aria-label="Open menu" onClick={()=>setMenu(true)}>☰</button><a className="portal-wordmark" href={'#/'+home}>Darshan Seva Portal <span>✦</span></a><div className="session-label">{user.name}<small>{admin?'Temple Authority':authority?'Authority':'Scanner'}</small></div></div><main className="main-content">{content}<footer>ISKCON Tirupati <span>Darshan Seva Portal</span></footer></main></div></div>{toast&&<div className={'toast-note '+(toast.error?'failure':'')} role="status">{toast.message}<button aria-label="Dismiss" onClick={()=>setToast(null)}>×</button></div>}{modal&&<div className="modal-backdrop-custom" onMouseDown={e=>{if(e.target===e.currentTarget)setModal(null)}}><section className="dialog-panel" role="dialog" aria-modal="true" aria-label={modal.title}><header><h2>{modal.title}</h2><button aria-label="Close dialog" onClick={()=>setModal(null)}>×</button></header>{modal.body}</section></div>}</Context.Provider>
}
"""
imports="""import { useContext, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { Context, Header, Table, Pager, ErrorBox, useData, pretty, when, entryColumns } from './ui'
import { AdminDashboard, Directory, AuthorityHome, SharedPasses, BatchPage, ImmediatePage, Reports, ProfilePage } from './role-pages'
import './App.css'
"""
(root/'App.jsx').write_text(imports+'\n'+scan+'\n'+logs+'\n'+login+'\n'+app,encoding='utf-8')
print('Role-specific navigation, profile permissions and original gallery workflows connected.')
