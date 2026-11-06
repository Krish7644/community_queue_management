import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { api } from './api'
const Context=createContext(null)
const pretty=(s='')=>s.replaceAll('_',' ').toLowerCase().replace(/\b\w/g,x=>x.toUpperCase())
const when=s=>s ? new Date(s).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'}) : '—'
const f=(name,label,type='text',extra={})=>({name,label,type,...extra})
const req={required:true}
const statusField=f('status','Status','select',{options:['ACTIVE','INACTIVE']})
const optionsFor=(rows,label)=>[{value:'',label:'Select…'},...(rows||[]).map(x=>({value:x.id,label:x[label]}))]
function useData(path) {
  const [data,setData]=useState(null), [error,setError]=useState(''), [loading,setLoading]=useState(true), [version,setVersion]=useState(0)
  useEffect(()=>{let active=true;setLoading(true);setError('');api(path).then(x=>{if(active)setData(x)}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[path,version])
  return {data,error,loading,refresh:()=>setVersion(x=>x+1)}
}
function Badge({value}){return <span className={'badge-tag '+String(value).toLowerCase()}>{pretty(value)}</span>}
function ErrorBox({error}){return error ? <div role="alert" className="error-box">{error}</div>:null}
function Header({title,description,children,eyebrow='DARSHAN SEVA PORTAL'}){
 const context=useContext(Context),home=context?.user?.role==='ADMIN'?'dashboard':context?.user?.role==='AUTHORITY'?'home':'scan'
 const current=location.hash.slice(2).split('?')[0]
 return <>{current&&current!==home&&<a className="back-link" href={'#/'+home}>← Back</a>}<header className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description&&<p>{description}</p>}</div><div className="actions">{children}</div></header></>
}

function CameraCapture({onCapture}) {
 const video=useRef(null),stream=useRef(null),[active,setActive]=useState(false),[error,setError]=useState(''),[captured,setCaptured]=useState(false)
 function stop(){stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;setActive(false)}
 useEffect(()=>()=>{stream.current?.getTracks().forEach(track=>track.stop())},[])
 async function start(){setError('');try{stream.current=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false});video.current.srcObject=stream.current;setActive(true);await video.current.play()}catch(e){setError('Camera unavailable. Allow camera access, or choose a photo file.');stop()}}
 function capture(){if(!video.current.videoWidth)return;const canvas=document.createElement('canvas');canvas.width=video.current.videoWidth;canvas.height=video.current.videoHeight;canvas.getContext('2d').drawImage(video.current,0,0);canvas.toBlob(blob=>{if(blob){onCapture(new File([blob],'webcam-photo.jpg',{type:'image/jpeg'}));setCaptured(true);stop()}},'image/jpeg',0.9)}
 return <div className="camera-capture"><video ref={video} hidden={!active} autoPlay playsInline muted style={{width:'100%',borderRadius:8,marginTop:8}}/>{error&&<small role="alert">{error}</small>}{active?<div className="actions"><button className="btn-secondary" type="button" onClick={capture}>Capture photo</button><button type="button" className="btn-secondary" onClick={stop}>Cancel camera</button></div>:<button className="btn-secondary" style={{marginTop:8}} type="button" onClick={start}>Take photo with webcam</button>}{captured&&<small>Camera photo captured. Save the form to use it.</small>}</div>
}

function Form({fields,initial={},onSave,submit='Save changes'}) {
  const [values,setValues]=useState(initial),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  async function save(e){e.preventDefault();setBusy(true);setError('');const body={};fields.forEach(item=>{let v=values[item.name]??(item.type==='checkbox'?false:item.type==='select'?(typeof item.options[0]==='object'?item.options[0].value:item.options[0]):'');if((item.type==='password'||item.type==='file')&&!v&&!item.required)return;if(item.type==='number')v=v===''?null:Number(v);if(item.nullable&&v==='')v=null;body[item.name]=v});try{if(Object.values(body).some(v=>v instanceof File)){const form=new FormData();Object.entries(body).forEach(([k,v])=>{if(v!==null)form.append(k,v)});await onSave(form)}else await onSave(body)}catch(err){setError(err.message)}finally{setBusy(false)}}
  return <form onSubmit={save}><ErrorBox error={error}/><div className="form-grid">{fields.map(item=><label key={item.name} className={(item.wide?'wide ':'')+(item.type==='checkbox'?'checkbox-label':'')}><span>{item.label}{item.required?' *':''}</span>{item.type==='select'?<select required={item.required} value={values[item.name]??(typeof item.options[0]==='object'?item.options[0].value:item.options[0])??''} onChange={e=>setValues({...values,[item.name]:e.target.value})}>{item.options.map(o=><option key={typeof o==='object'?o.value:o} value={typeof o==='object'?o.value:o}>{typeof o==='object'?o.label:pretty(o)}</option>)}</select>:item.type==='textarea'?<textarea rows="3" value={values[item.name]??''} onChange={e=>setValues({...values,[item.name]:e.target.value})}/>:item.type==='checkbox'?<input type="checkbox" checked={Boolean(values[item.name])} onChange={e=>setValues({...values,[item.name]:e.target.checked})}/>:<input type={item.type} required={item.required&&!(item.type==='file'&&values[item.name] instanceof File)} min={item.min} max={item.max} minLength={item.type==='password'?8:undefined} accept={item.accept} {...(item.type==='file'?{}:{value:values[item.name]??''})} onChange={e=>setValues({...values,[item.name]:item.type==='file'?e.target.files[0]:e.target.value})}/>}{item.type==='file'&&item.accept?.startsWith('image')&&<CameraCapture onCapture={photo=>setValues({...values,[item.name]:photo})}/>}<small>{item.hint}</small></label>)}</div><button className="btn-main form-submit" disabled={busy}>{busy?'Saving…':submit}</button></form>
}
function Table({columns,rows=[],loading}){return <div className="table-shell"><table><thead><tr>{columns.map(c=><th key={c.key}>{c.label}</th>)}</tr></thead><tbody>{loading?<tr><td className="empty" colSpan={columns.length}>Loading…</td></tr>:rows.length?rows.map((row,i)=><tr key={String(row.kind||'')+String(row.id||i)}>{columns.map(c=><td key={c.key}>{c.render?c.render(row):row[c.key]??'—'}</td>)}</tr>):<tr><td className="empty" colSpan={columns.length}>No matching records.</td></tr>}</tbody></table></div>}
function Pager({data,page,setPage}){return <div className="pager"><span>{Number(data?.count||0).toLocaleString('en-IN')} records · Page {page}</span><div><button disabled={!data?.previous} onClick={()=>setPage(page-1)}>Previous</button><button disabled={!data?.next} onClick={()=>setPage(page+1)}>Next</button></div></div>}
const entryColumns=[{key:'entry_time',label:'Time',render:r=>when(r.entry_time)},{key:'subject_name',label:'Member / pass',render:r=><div><strong>{r.subject_name||r.devotee_id||'Community member'}</strong><small>{r.reference_code||r.devotee_id}</small></div>},{key:'entry_type',label:'Entry',render:r=><div>{pretty(r.entry_type)}<small>{r.result==='ALLOWED'?(r.member&&r.entry_type==='FAMILY'?r.guest_count:r.guest_count+1)+' people':r.reason}</small></div>},{key:'gate_name',label:'Gate'},{key:'scanner_name',label:'Scanner',render:r=>r.scanner_name||r.volunteer_name||'—'},{key:'result',label:'Result',render:r=><Badge value={r.result}/>}]

export {Context,pretty,when,f,req,optionsFor,useData,Badge,ErrorBox,Header,Form,Table,Pager,entryColumns}
