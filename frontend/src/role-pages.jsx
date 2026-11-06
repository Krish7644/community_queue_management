import { useContext, useEffect, useRef, useState } from 'react'
import { api, download } from './api'
import PortalIcon from './PortalIcon'
import { Context, Header, Form, Table, Pager, ErrorBox, Badge, useData, pretty, when, f, req, optionsFor } from './ui'

const gateOptions=rows=>[{value:'',label:'Select gate'},...(rows||[]).map(r=>({value:r.id,label:r.gate_name}))]
const passCount=value=>value==null?'—':Number(value).toLocaleString('en-IN')
const shareIcon=<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20c1.7-6.3 5.4-9.5 11.5-9.8V5l7 6.5-7 6.5v-5.1C9 13.4 5.8 15.7 3 20Z"/></svg>

export function AdminDashboard(){
 const {data,error}=useData('dashboard/')
 const cards=[['HODs','HODs','hods','people','rose'],['Congregations','Congregations','congregations','community','teal'],['VVIPs','VVIP passes','vvips','crown','gold'],['Volunteers','Volunteer passes','volunteer-passes','heart','violet'],['Immediate Pass','Immediate passes','immediate','bolt','gold'],['Scanners','Scanners','scanners','scan','blue'],['Gates','Gates','gates','gate','teal']]
 return <>
  <Header title="Live Dashboard"/>
  <ErrorBox error={error}/>
  <div className="dashboard-grid">{cards.map(([label,key,route,icon,tone])=><a className={'dashboard-tile tone-'+tone} key={key} href={'#/'+route}>
   <div className="tile-top"><span className="tile-symbol"><PortalIcon name={icon}/></span><span className="tile-arrow"><PortalIcon name="arrow"/></span></div>
   <span>{label}</span><strong>{Number(data?.counts?.[key]||0).toLocaleString('en-IN')}</strong>
  </a>)}</div>
  <div className="allocation-totals">{[['Congregation Passes','Combined passes','community'],['5 Member Entry Passes','Five-member passes','ticket']].map(([label,key,icon])=><div className="dashboard-tile allocation-card" key={key}>
   <span className="allocation-symbol"><PortalIcon name={icon}/></span><div><span>{label}</span><strong>{Number(data?.counts?.[key]||0).toLocaleString('en-IN')}</strong></div>
  </div>)}</div>
 </>
}

export function Directory({resource}){
 const {open,close,notify,options,refreshOptions}=useContext(Context),[page,setPage]=useState(1)
 const authority=['hods','congregations'].includes(resource),type=resource==='congregations'?'CONGREGATION':'HOD',endpoint=authority?'authorities':resource
 const {data,error,loading,refresh}=useData(endpoint+'/?page='+page+(authority?'&account_type='+type:''))
 const heading={hods:'HOD & Brahmachari Profiles',congregations:'Congregation Profiles',scanners:'Scanner Profiles',gates:'Gates'}[resource]
 const addLabel={hods:'Add Profile',congregations:'Add Congregation',scanners:'Add Scanner',gates:'Add Gate'}[resource]
 const eyebrow={hods:'HOD & BRAHMACHARI MANAGEMENT',congregations:'CONGREGATION MANAGEMENT',scanners:'SCANNER MANAGEMENT',gates:'GATE MANAGEMENT'}[resource]
 function done(){close();refresh();refreshOptions();notify('Changes saved.')}
 function edit(row){
  let fields=resource==='gates'?[f('gate_name','Gate name','text',req),f('gate_code','Gate code','text',req)]:[f('name','Name','text',req),...(authority?[f('mobile','Mobile number','tel')]:[]),f('username','Login ID','text',req),f('new_password',row?'Password (leave blank to keep)':'Password','password',{required:!row})]
  if(authority)fields.push(...(type==='HOD'?[f('profile_type','Profile type','select',{nullable:true,options:[{value:'',label:'HOD'},{value:'BRAHMACHARI',label:'Brahmachari'}]})]:[]),f('photo','Profile photo','file',{accept:'image/jpeg,image/png,image/webp'}),f('can_add_members',type==='CONGREGATION'?'Allow member profiles':'Allow members and entry passes','checkbox'),f(row?'additional_passes':'initial_passes',(row?'Additional ':'Initial ')+(type==='CONGREGATION'?'combined passes':'5-member entry passes'),'number',{min:0,max:500,hint:row?'Current '+(type==='CONGREGATION'?'active combined passes: '+passCount(row.combined_passes):'assigned passes: '+passCount(row.assigned_passes))+'. This adds to the existing allocation.':undefined}))
  if(resource==='scanners')fields.push(f('gate','Gate','select',{options:gateOptions(options?.gates),required:true}))
  open(row?'Edit profile':'Add '+(resource==='gates'?'gate':resource==='scanners'?'scanner':'profile'),<Form fields={fields} initial={{initial_passes:0,additional_passes:0,...row}} onSave={async body=>{if(authority){if(body instanceof FormData)body.set('account_type',type);else body.account_type=type}await api(endpoint+'/'+(row?row.id+'/':''),{method:row?'PATCH':'POST',body});done()}}/>)
 }
 async function deactivate(row){if(!window.confirm('Deactivate this profile? Existing records will be preserved.'))return;try{await api(endpoint+'/'+row.id+'/',{method:'DELETE'});done()}catch(e){notify(e.message,true)}}
 async function toggleGate(row){try{await api('gates/'+row.id+'/',{method:'PATCH',body:{status:row.status==='ACTIVE'?'INACTIVE':'ACTIVE'}});done()}catch(e){notify(e.message,true)}}
 return <section className="profile-directory" data-directory={resource}>
  <Header title={heading} eyebrow={eyebrow}><button className="btn-main directory-add" onClick={()=>edit(null)}>{addLabel}</button></Header>
  <ErrorBox error={error}/>
  <div className={'profile-grid '+(resource==='gates'?'gates-grid':'')}>
   {loading?<p>Loading profiles…</p>:data?.results?.length?data.results.map(row=><DirectoryCard key={row.id} row={row} resource={resource} options={options} onEdit={()=>edit(row)} onDeactivate={()=>deactivate(row)} onToggleGate={()=>toggleGate(row)}/>):!error&&<div className="gallery-empty">No {resource==='gates'?'gates':'profiles'} yet.</div>}
  </div>
  {(data?.next||data?.previous)&&<Pager data={data} page={page} setPage={setPage}/>}
 </section>
}

function DirectoryCard({row,resource,options,onEdit,onDeactivate,onToggleGate}){
 const {open,user}=useContext(Context)
 const authority=['hods','congregations'].includes(resource),congregation=resource==='congregations'
 const category=authority?(row.profile_type==='BRAHMACHARI'?'Brahmachari':congregation?'Congregation':'HOD'):resource==='scanners'?'Scanner':'Gate'
 const name=row.name||row.gate_name,gate=options?.gates?.find(item=>item.id===row.gate)?.gate_name||'Unassigned'
 return <article className="profile-card">
  <div className="profile-card-main">
   <span className="avatar profile-avatar">{resource==='gates'?<PortalIcon name="gate"/>:name.trim().charAt(0).toUpperCase()}{authority&&row.photo_path&&<img src={'/api/authorities/'+row.id+'/photo/'} alt={name} onError={e=>{e.currentTarget.style.display='none'}}/>}</span>
   <div className="profile-card-details">
    <div className="profile-name-row"><h2>{name}</h2><span className={'profile-status '+row.status.toLowerCase()}>{row.status}</span></div>
    <span className={'profile-kind '+category.toLowerCase()}>{category}</span>
    <small className="profile-identity">{authority?row.authority_id:resource==='gates'?row.gate_code:'Login: '+row.username}</small>
    {authority&&<small className="profile-mobile">{row.mobile||'No mobile number'}</small>}
    {resource==='scanners'&&<small className="profile-mobile">Gate: {gate}</small>}
    {user.role==='ADMIN'&&resource!=='gates'&&<div className="profile-login-row"><small>Login: {row.username}</small><button type="button" className="profile-credentials-button" aria-label={'View password for '+name} onClick={()=>open('Account login details',<AccountCredentials endpoint={(authority?'authorities':'scanners')+'/'+row.id+'/credentials/'}/>)}>View password</button></div>}
   </div>
  </div>
  <footer className="profile-card-footer">
   <div className="profile-allocation">{authority?<>
    <span>Member access {row.can_add_members?'on':'off'}</span><span className="allocation-dot" aria-hidden="true">·</span>
    {congregation?<span>Combined passes: <strong>{passCount(row.combined_passes)}</strong></span>:<><span>Assigned: <strong>{passCount(row.assigned_passes)}</strong></span><span className="allocation-dot" aria-hidden="true">·</span><span>Available: <strong>{passCount(row.available_passes)}</strong></span></>}
   </>:<span>{resource==='scanners'?'Scanner account':'Gate management'}</span>}</div>
   <div className="profile-actions">
    <button type="button" className="profile-edit" aria-label={'Edit '+name} onClick={onEdit}>Edit</button>
    <button type="button" className={resource==='gates'&&row.status!=='ACTIVE'?'profile-enable':'profile-deactivate'} aria-label={(resource==='gates'&&row.status!=='ACTIVE'?'Activate ':'Deactivate ')+name} onClick={resource==='gates'?onToggleGate:onDeactivate}>{resource==='gates'&&row.status!=='ACTIVE'?'Activate':'Deactivate'}</button>
   </div>
  </footer>
 </article>
}

function AccountCredentials({endpoint}){
 const {data,error,loading}=useData(endpoint)
 return <div className="account-credentials"><ErrorBox error={error}/>{loading?<p>Loading account details…</p>:data&&<><h3>{data.name}</h3><dl><div><dt>Login ID</dt><dd><code>{data.login_id}</code></dd></div><div><dt>Password</dt><dd>{data.needs_reset?<span>The original is unavailable. Set a new password using Edit.</span>:<code>{data.password}</code>}</dd></div></dl></>}</div>
}

export function AuthorityHome(){
 const {user,options}=useContext(Context)
 const combined=options?.account_type==='CONGREGATION'
 return <><Header title={'Welcome, '+user.name}/><div className="assignment-summary"><span className="assignment-symbol"><PortalIcon name="ticket"/></span><div><small>{combined?'Assigned passes from Temple Authority':'5-member entry passes'}</small><strong>{Number(options?.assigned_passes||0).toLocaleString('en-IN')}</strong></div><PortalIcon name="lotus" className="assignment-decoration"/></div>{options&&<PassGallery kind={combined?'COMBINED':'HOD'} authorityHome/>}</>
}

export function SharedPasses(){return <><Header title="Shared Passes"/><PassGallery shared/></>}

function ShareConfirmation({count=1,onConfirm}){
 const [busy,setBusy]=useState(false),[error,setError]=useState('')
 return <div className="share-success"><div>✓</div><h3>{count===1?'Pass shared successfully.':count+' passes shared successfully.'}</h3><ErrorBox error={error}/><button className="btn-main" disabled={busy} onClick={async()=>{setBusy(true);try{await onConfirm()}catch(e){setError(e.message);setBusy(false)}}}>Okay</button></div>
}

export function PassGallery({kind='',shared=false,authorityHome=false,immediate=false,batchId=null}){
 const {user,options,open,close,notify}=useContext(Context),[page,setPage]=useState(1),[selected,setSelected]=useState([])
 const params=new URLSearchParams({kind,shared:shared?'yes':'no',page,page_size:shared?5000:24,...(immediate?{workspace:'immediate'}:shared?{workspace:'shared'}:{}),...(batchId?{batch_id:batchId}:{})})
 const {data,error,loading,refresh}=useData('passes/?'+params)
 const bulk=authorityHome&&kind==='COMBINED'&&!shared
 const rows=data?.results||[]
 const marked=rows.filter(row=>selected.includes(row.id))
 function saved(){close();setSelected([]);refresh();notify('Passes moved to Shared Passes.')}
 function edit(row){open('Pass recipient · '+row.code,<Form fields={[f('name','Recipient name','text',{required:true})]} initial={{name:row.recipient_name||''}} onSave={async body=>{await api('passes/'+row.kind+'/'+row.id+'/',{method:'PATCH',body});close();refresh();notify('Recipient saved.')}}/>)}
 async function share(row){
  try{
   let sent=false
   if(navigator.share&&navigator.canShare){const response=await fetch(row.card_url);if(!response.ok)throw Error('Pass image is unavailable.');const file=new File([await response.blob()],row.code+'-pass.png',{type:'image/png'});if(navigator.canShare({files:[file]})){await navigator.share({title:'Janmashtami Entry Pass '+row.code,text:options?.share_message||'',files:[file]});sent=true}}
   if(!sent&&navigator.share){await navigator.share({title:'Janmashtami Entry Pass '+row.code,text:options?.share_message||'',url:location.origin+row.card_url+'?download=1'});sent=true}
   if(!sent){notify('Share sheet is not available in this browser. Open the portal on mobile Chrome, Edge or Safari and tap Share again.',true);return}
   open('Pass shared',<ShareConfirmation onConfirm={async()=>{await api('passes/'+row.kind+'/'+row.id+'/',{method:'POST',body:{}});saved()}}/>)
  }catch(e){if(e.name!=='AbortError')notify(e.message,true)}
 }
 async function shareSelected(){
  try{
   if(!marked.length)return
   if(!navigator.share||!navigator.canShare){notify('This device cannot share multiple pass images at once. Share the cards individually.',true);return}
   const files=await Promise.all(marked.map(async row=>{const response=await fetch(row.card_url);if(!response.ok)throw Error('A selected pass image is unavailable.');return new File([await response.blob()],row.code+'-pass.png',{type:'image/png'})}))
   if(!navigator.canShare({files})){notify('This device cannot share multiple pass images at once. Share the cards individually.',true);return}
   await navigator.share({title:'Janmashtami Entry Passes',text:options?.share_message||'',files})
   open('Passes shared',<ShareConfirmation count={marked.length} onConfirm={async()=>{await api('passes/share-bulk/',{method:'POST',body:{passes:marked.map(row=>({kind:row.kind,id:row.id}))}});saved()}}/>)
  }catch(e){if(e.name!=='AbortError')notify(e.message,true)}
 }
 const groups=immediate?['FIVE_MEMBER','VVIP','VOLUNTEER','CONGREGATION_COMBINED'].map(type=>({title:{FIVE_MEMBER:'5 Member Passes',VVIP:'VVIP Passes',VOLUNTEER:'Volunteer Passes',CONGREGATION_COMBINED:'Congregation Combined Passes'}[type],rows:rows.filter(row=>row.pass_type===type)})):[{title:authorityHome?(kind==='COMBINED'?'Combined Passes':'5 Member Entry Passes'):null,rows}]
 return <><ErrorBox error={error}/>{groups.map((group,index)=><section className="pass-section" key={group.title||index}>{group.title&&<div className="gallery-heading"><div><div className="eyebrow">{authorityHome?'ASSIGNED PASSES':group.title.toUpperCase()}</div><h2>{group.title}{authorityHome?' ('+(data?.count||0)+')':''}</h2></div>{bulk&&!!marked.length&&<div className="actions"><small>{marked.length} selected</small><button className="btn-main" onClick={shareSelected}>Share selected</button></div>}</div>}{loading?<div className="gallery-empty">Loading passes…</div>:group.rows.length?<div className={'pass-gallery '+(kind==='VOLUNTEER'?'volunteer-gallery':'')}>{group.rows.map(row=><article className={'pass-tile '+(row.status!=='ACTIVE'?'is-used':'')} key={row.kind+':'+row.id}><a href={row.card_url+'?download=1'} title={'Download '+row.code}><img key={row.recipient_name} className="pass-thumbnail" src={row.thumb_url || (row.card_url + '?thumb=1')} alt={row.code+' entry pass'} loading="lazy"/></a><div className="pass-tile-actions"><small title={row.code}>{row.code}</small><span>{bulk&&<input type="checkbox" aria-label={'Select '+row.code+' for sharing'} checked={selected.includes(row.id)} onChange={e=>setSelected(e.target.checked?[...selected,row.id]:selected.filter(id=>id!==row.id))}/>} {!shared&&(row.kind==='HOD'||row.kind==='COMBINED'||row.kind==='VVIP'||(row.kind==='IMMEDIATE'&&row.pass_type==='FIVE_MEMBER'))&&<button className="pass-icon" title="Edit recipient" aria-label={'Edit recipient for '+row.code} onClick={()=>edit(row)}>✎</button>}{!shared?<button className="pass-icon" title="Share pass" aria-label={'Share '+row.code} onClick={()=>share(row)}>{shareIcon}</button>:<a className="pass-icon" href={row.card_url+'?download=1'} aria-label={'Download '+row.code}>↓</a>}</span></div></article>)}</div>:<div className="gallery-empty">{shared?'No shared passes yet.':batchId?'All passes in this batch have been shared.':'No passes are currently assigned.'}</div>}</section>)}{(data?.next||data?.previous)&&<Pager data={data} page={page} setPage={value=>{setPage(value);setSelected([])}}/>}</>
}

export function BatchPage({kind,batchId=null}){
 const {open,close,notify}=useContext(Context),{data,error,loading,refresh}=useData('batches/')
 const rows=(data||[]).filter(row=>row.kind===kind),batch=rows.find(row=>String(row.id)===String(batchId))
 function upload(){open('Upload names CSV',<Form fields={[f('batch_name','Batch name','text',req),...(kind==='VOLUNTEER'?[f('entry_limit','Allowed entry count per pass (0 = unlimited)','number',{required:true,min:0})]:[]),f('file','CSV file','file',{required:true,accept:'.csv,text/csv',hint:kind==='VVIP'?'One name per row, or a CSV with a name column. Each name receives one single-use 5-member pass.':'One name per row, with an optional name header.'})]} initial={{entry_limit:1}} submit="Upload names CSV" onSave={async body=>{body.set('kind',kind);await api('batches/',{method:'POST',body});close();refresh();notify('Pass batch created.')}}/>)}
 async function deactivate(row){if(!window.confirm('Deactivate the passes in this batch? Existing history will be preserved.'))return;try{await api('batches/'+kind+'/'+row.id+'/',{method:'DELETE'});refresh();notify('Batch deactivated.')}catch(e){notify(e.message,true)}}
 const label=kind==='VVIP'?'VVIP':'Volunteer'
 if(batchId)return <><Header title={batch?.name||label+' pass batch'} description={kind==='VOLUNTEER'?(batch?.entry_limit===0?'Unlimited entries':(batch?.entry_limit||1)+' entries each'):undefined}><a className="btn-main" href={'/api/batches/'+kind+'/'+batchId+'/'}>Download all</a></Header><PassGallery kind={kind} batchId={batchId}/></>
 return <><Header title={label+' Passes'}><button className="btn-main" onClick={upload}>Upload names CSV</button></Header><ErrorBox error={error}/><div className="batch-grid">{loading?<p>Loading batches…</p>:rows.length?rows.map(row=><article className="batch-card" key={row.id}><div className="batch-symbol" aria-hidden="true">▤</div><h2>{row.name}</h2><p>{row.passes} passes{kind==='VOLUNTEER'?' · '+(row.entry_limit===0?'Unlimited entries':row.entry_limit+' entries each'):''}</p><div className="actions"><a className="btn-main" href={'#/batch/'+kind+'/'+row.id}>Open passes</a><a className="btn-secondary" href={'/api/batches/'+kind+'/'+row.id+'/'}>Download all</a><button className="text-action" onClick={()=>deactivate(row)}>Deactivate</button></div></article>):<div className="gallery-empty">No {label.toLowerCase()} pass batches yet.</div>}</div></>
}

export function ImmediatePage(){
 const {user,options,notify}=useContext(Context),[revision,setRevision]=useState(0)
 return <><Header title="Immediate Passes"/><section className="panel immediate-form"><PassForm user={user} options={options} onSave={async body=>{await api('passes/',{method:'POST',body:{...body,count:1}});setRevision(x=>x+1);notify('Pass generated.')}}/></section><PassGallery key={revision} immediate/></>
}

export function Reports(){
 const {options}=useContext(Context),[page,setPage]=useState(1)
 const [filters,setFilters]=useState({search:'',pass_type:'',category:'',authority_id:'',scanner_id:'',gate_id:''}),[applied,setApplied]=useState(filters)
 const params=new URLSearchParams({...applied,page,page_size:250}),{data,error,loading}=useData('passes/?'+params)
 const change=(key,value)=>setFilters({...filters,[key]:value,...(key==='category'?{authority_id:''}:{})})
 const authorityRows=(options?.authorities||[]).filter(row=>row.status==='ACTIVE'&&(filters.category==='BRAHMACHARI'?row.profile_type==='BRAHMACHARI':filters.category==='HOD'?row.account_type==='HOD'&&row.profile_type!=='BRAHMACHARI':filters.category==='CONGREGATION'?row.account_type==='CONGREGATION'&&row.profile_type!=='BRAHMACHARI':false))
 const columns=[{key:'name',label:'Recipient / Pass ID',render:r=><div><strong>{r.name}</strong><small>{r.code}</small></div>},{key:'pass_type',label:'Pass type',render:r=>pretty(r.pass_type)},{key:'category',label:'Category / Authority',render:r=><div>{pretty(r.category)}<small>{r.authority}</small></div>},{key:'shared_at',label:'Sharing',render:r=><Badge value={r.shared_at?'SHARED':'UNSHARED'}/>},{key:'status',label:'Entry status',render:r=><div><Badge value={r.status}/>{r.kind==='COMBINED'&&<small>Family {r.family_available?'available':'used'} · Single entry unlimited</small>}</div>},{key:'entries_used',label:'Entries',render:r=>r.kind==='COMBINED'?r.entries_used+' single · '+(r.family_used_at?'1':'0')+' family':r.people_per_entry===5?(r.status==='USED'?'1':'0')+' / 1':r.entries_used+' / '+(r.unlimited?'Unlimited':r.entry_limit)},{key:'last_entry',label:'Last entry',render:r=>when(r.last_entry)}]
 return <><Header title="Reports"><a className="btn-secondary" href="#/entries">Entry Logs</a><a className="btn-main" href={'/api/passes/export/?filetype=xlsx&'+params}>Download Excel</a></Header><div className="metrics report-metrics">{Object.entries(data?.stats||{}).map(([label,value])=><div className="metric" key={label}><strong>{Number(value).toLocaleString('en-IN')}</strong><span>{label==='issued'?'Passes issued':pretty(label)}</span></div>)}</div><form className="filters report-filters" onSubmit={e=>{e.preventDefault();setApplied({...filters});setPage(1)}}><label>Search pass recipient or pass ID<input value={filters.search} onChange={e=>change('search',e.target.value)}/></label><label>Pass type<select value={filters.pass_type} onChange={e=>change('pass_type',e.target.value)}><option value="">All pass types</option>{['FIVE_MEMBER','VVIP','VOLUNTEER','CONGREGATION_COMBINED'].map(x=><option key={x}>{x}</option>)}</select></label><label>Category<select value={filters.category} onChange={e=>change('category',e.target.value)}><option value="">All categories</option>{['TEMPLE_AUTHORITY','HOD','CONGREGATION','BRAHMACHARI'].map(x=><option key={x}>{x}</option>)}</select></label>{[['authority_id',authorityRows,'name','Authority name'],['scanner_id',options?.scanners,'name','Scanner'],['gate_id',options?.gates,'gate_name','Gate']].map(([key,rows,label])=><label key={key}>{label}<select value={filters[key]} onChange={e=>change(key,e.target.value)}><option value="">All</option>{rows?.map(row=><option value={row.id} key={row.id}>{row[label]}</option>)}</select></label>)}<div className="actions report-actions"><button className="btn-main" type="submit">Apply Filters</button><button className="btn-secondary" type="button" onClick={()=>{const empty={search:'',pass_type:'',category:'',authority_id:'',scanner_id:'',gate_id:''};setFilters(empty);setApplied(empty);setPage(1)}}>Reset</button></div></form><ErrorBox error={error}/><Table columns={columns} rows={data?.results} loading={loading}/>{(data?.next||data?.previous)&&<Pager data={data} page={page} setPage={setPage}/>}</>
}

export function ProfilePage(){
 const {user,open,close,notify,refreshSession}=useContext(Context),{data,error,loading,refresh}=useData('profile/'),generating=useRef(false)
 useEffect(()=>{if(data&&user.role==='AUTHORITY'&&!data.personal_card_id&&!generating.current){generating.current=true;api('profile/card/',{method:'POST',body:{}}).then(refresh).catch(e=>notify(e.message,true))}},[data?.personal_card_id,user.role])
 function viewCard(){open('Personal Community Card',<div className="card-preview"><img src={'/api/passes/MEMBER/'+data.personal_card_id+'/card/'} alt="Personal Community Card"/><a className="btn-main" href={'/api/passes/MEMBER/'+data.personal_card_id+'/card/?download=1'}>Download image</a></div>)}
 if(loading&&!data)return <p>Loading profile…</p>
 return <><Header title={user.role==='ADMIN'?'Temple Authority Profile':'My Profile'}/><ErrorBox error={error}/>{data&&(user.role==='ADMIN'?<section className="panel profile-panel"><Form key={data.updated_at} fields={[f('name','Name','text',req),f('mobile','Mobile','tel'),f('username','Login ID','text',req),f('new_password','Password (leave blank to keep)','password'),f('photo','Photo for Temple Authority Card','file',{accept:'image/jpeg,image/png,image/webp'})]} initial={data} submit="Save Profile & Generate Card" onSave={async body=>{await api('profile/',{method:'PATCH',body});await api('profile/card/',{method:'POST',body});refresh();refreshSession();notify('Profile saved and card generated.')}}/>{data.personal_card_id&&<button className="btn-gold profile-card-button" onClick={viewCard}>View Temple Authority Card</button>}</section>:<div className="readonly-profile">{data.personal_card_id&&<section className="panel personal-card-panel"><div className="eyebrow">PERSONAL COMMUNITY CARD</div><div className="actions"><button className="btn-main" onClick={viewCard}>View Community Card</button><a className="btn-secondary" href={'/api/passes/MEMBER/'+data.personal_card_id+'/card/?download=1'}>Download Card</a></div></section>}<section className="panel"><dl className="profile-details"><div><dt>Name</dt><dd>{data.name}</dd></div><div><dt>Login ID</dt><dd>{data.username}</dd></div><div><dt>Mobile</dt><dd>{data.mobile||'—'}</dd></div>{user.role==='VOLUNTEER'&&<div><dt>Gate</dt><dd>{data.gate_name||'Unassigned'}</dd></div>}<div><dt>Password</dt><dd>••••••••<small>Contact Temple Authority for password changes.</small></dd></div></dl></section></div>)}</>
}

function PassForm({options,user,onSave}){
 const [type,setType]=useState(user.role==='ADMIN'?'FIVE_MEMBER':'CONGREGATION_COMBINED')
 const fields=[f('name','Pass holder name','text',req),...(type==='FIVE_MEMBER'?[f('authority_id','HOD authority','select',{nullable:true,options:optionsFor(options?.authorities?.filter(x=>x.account_type==='HOD'),'name')}),f('custom_authority_name','Custom authority (if no HOD selected)')]:[]),...(type==='CONGREGATION_COMBINED'?[f('authority_id','Congregation','select',{required:true,options:optionsFor(options?.authorities?.filter(x=>x.account_type==='CONGREGATION'),'name')})]:[]),...(type==='VOLUNTEER'?[f('entry_limit','Allowed entries','number',{min:0,hint:'0 means unlimited entry.'})]:[])]
 return <><label className="standalone">Pass type<select value={type} onChange={e=>setType(e.target.value)}>{(user.role==='ADMIN'?['FIVE_MEMBER','VVIP','VOLUNTEER','CONGREGATION_COMBINED']:['CONGREGATION_COMBINED']).map(v=><option key={v}>{v}</option>)}</select></label><Form key={type} fields={fields} initial={{count:1,entry_limit:1}} submit="Generate pass" onSave={body=>onSave({...body,pass_type:type,kind:type==='CONGREGATION_COMBINED'?'COMBINED':'IMMEDIATE'})}/></>
}
