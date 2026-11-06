"""One-time local UI refinement for the original portal workflows."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = root / "frontend/src/role-pages.jsx"
source = path.read_text(encoding="utf-8")
source = source.replace('<div className="profile-grid">', '<div className={"profile-grid "+(resource===\'gates\'?\'gates-grid\':\'\')}>')
start, end = source.index('export function Reports(){'), source.index('export function ProfilePage(){')
reports = '''export function Reports(){
 const {options}=useContext(Context),[page,setPage]=useState(1)
 const [filters,setFilters]=useState({search:'',pass_type:'',category:'',authority_id:'',scanner_id:'',gate_id:''}),[applied,setApplied]=useState(filters)
 const params=new URLSearchParams({...applied,page,page_size:250}),{data,error,loading}=useData('passes/?'+params)
 const change=(key,value)=>setFilters({...filters,[key]:value})
 const columns=[{key:'name',label:'Recipient / Pass ID',render:r=><div><strong>{r.name}</strong><small>{r.code}</small></div>},{key:'pass_type',label:'Pass type',render:r=>pretty(r.pass_type)},{key:'category',label:'Category / Authority',render:r=><div>{pretty(r.category)}<small>{r.authority}</small></div>},{key:'shared_at',label:'Sharing',render:r=><Badge value={r.shared_at?'SHARED':'UNSHARED'}/>},{key:'status',label:'Entry status',render:r=><div><Badge value={r.status}/>{r.kind==='COMBINED'&&<small>Family {r.family_available?'available':'used'} · Single entry unlimited</small>}</div>},{key:'entries_used',label:'Entries',render:r=>r.kind==='COMBINED'?r.entries_used+' single · '+(r.family_used_at?'1':'0')+' family':r.people_per_entry===5?(r.status==='USED'?'1':'0')+' / 1':r.entries_used+' / '+(r.unlimited?'Unlimited':r.entry_limit)},{key:'last_entry',label:'Last entry',render:r=>when(r.last_entry)}]
 return <><Header title="Reports"><a className="btn-main" href={'/api/passes/export/?filetype=xlsx&'+params}>Download Excel</a></Header><div className="metrics report-metrics">{Object.entries(data?.stats||{}).map(([label,value])=><div className="metric" key={label}><strong>{Number(value).toLocaleString('en-IN')}</strong><span>{pretty(label)}</span></div>)}</div><form className="filters report-filters" onSubmit={e=>{e.preventDefault();setApplied({...filters});setPage(1)}}><label>Search pass recipient or pass ID<input value={filters.search} onChange={e=>change('search',e.target.value)}/></label><label>Pass type<select value={filters.pass_type} onChange={e=>change('pass_type',e.target.value)}><option value="">All pass types</option>{['FIVE_MEMBER','VVIP','VOLUNTEER','CONGREGATION_COMBINED'].map(x=><option key={x}>{x}</option>)}</select></label><label>Category<select value={filters.category} onChange={e=>change('category',e.target.value)}><option value="">All categories</option>{['TEMPLE_AUTHORITY','HOD','CONGREGATION','BRAHMACHARI'].map(x=><option key={x}>{x}</option>)}</select></label>{[['authority_id',options?.authorities,'name','Authority name'],['scanner_id',options?.scanners,'name','Scanner'],['gate_id',options?.gates,'gate_name','Gate']].map(([key,rows,label])=><label key={key}>{label}<select value={filters[key]} onChange={e=>change(key,e.target.value)}><option value="">All</option>{rows?.map(row=><option value={row.id} key={row.id}>{row[label]}</option>)}</select></label>)}<button className="btn-main" type="submit">Apply Filters</button></form><ErrorBox error={error}/><Table columns={columns} rows={data?.results} loading={loading}/>{(data?.next||data?.previous)&&<Pager data={data} page={page} setPage={setPage}/>}</>
}

'''
source = source[:start] + reports + source[end:]
source = source.replace('<div><dt>Password</dt>', "{user.role==='VOLUNTEER'&&<div><dt>Gate</dt><dd>{data.gate_name||'Unassigned'}</dd></div>}<div><dt>Password</dt>")
path.write_text(source, encoding="utf-8")

path = root / "frontend/src/App.jsx"
source = path.read_text(encoding="utf-8")
source = source.replace("[code,setCode]=useState(''),", "[code,setCode]=useState(''),[entryMode,setEntryMode]=useState('SINGLE'),")
source = source.replace("setPass(checked)", "setEntryMode('SINGLE');setPass(checked)")
source = source.replace("{pass.people_per_entry}<small>{pass.people_per_entry===5?'members':'person'}</small>", "{entryMode==='FAMILY'?pass.family_people:pass.people_per_entry}<small>{(entryMode==='FAMILY'?pass.family_people:pass.people_per_entry)>1?'people':'person'}</small>")
source = source.replace("<p>{pass.unlimited?'Unlimited single entry remains available.'", "<p>{entryMode==='FAMILY'?'Verify this complete family group before confirming. This privilege can be used once.':pass.unlimited?'Unlimited single entry remains available.'")
source = source.replace("disabled={busy} onClick={()=>confirm('SINGLE')}>{pass.kind==='COMBINED'?'SINGLE ENTRY':'Confirm & Allow Entry'}</button>", "disabled={busy||(entryMode==='SINGLE'&&pass.single_available===false)} onClick={()=>confirm(entryMode)}>{entryMode==='FAMILY'?'CONFIRM FAMILY ENTRY':pass.single_available===false?'SINGLE ENTRY NOT AVAILABLE':pass.kind==='COMBINED'?'SINGLE ENTRY':'Confirm & Allow Entry'}</button>")
source = source.replace("(pass.kind==='COMBINED'||(user.role==='VOLUNTEER'&&pass.family_available))", "entryMode==='SINGLE'&&(pass.kind==='COMBINED'||(user.role==='VOLUNTEER'&&pass.family_configured))")
source = source.replace("onClick={()=>confirm('FAMILY')}>FAMILY ENTRY {pass.kind==='COMBINED'?'(5)':''}", "onClick={()=>pass.kind==='MEMBER'?setEntryMode('FAMILY'):confirm('FAMILY')}>FAMILY ENTRY ({pass.family_people})")
source = source.replace("5 MEMBER PASS OVER", "FAMILY ENTRY ALREADY USED")
source = source.replace("Family entry has already been used. Single entry remains available.", "This one-time family entry has already been used.")
source = source.replace("onClick={()=>setPass(null)}>Cancel", "onClick={()=>{if(entryMode==='FAMILY')setEntryMode('SINGLE');else setPass(null)}}>Cancel")
path.write_text(source, encoding="utf-8")

path = root / "frontend/src/ui.jsx"
source = path.read_text(encoding="utf-8")
source = source.replace("(r.guest_count+1)+' people'", "(r.member&&r.entry_type==='FAMILY'?r.guest_count:r.guest_count+1)+' people'")
path.write_text(source, encoding="utf-8")
