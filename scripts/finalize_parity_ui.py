from pathlib import Path

path = Path(__file__).resolve().parent.parent / "frontend/src/role-pages.jsx"
source = path.read_text(encoding="utf-8")
source = source.replace("...(immediate?{workspace:'immediate'}:{})", "...(immediate?{workspace:'immediate'}:shared?{workspace:'shared'}:{})")
source = source.replace("const change=(key,value)=>setFilters({...filters,[key]:value})", "const change=(key,value)=>setFilters({...filters,[key]:value,...(key==='category'?{authority_id:''}:{})})\n const authorityRows=(options?.authorities||[]).filter(row=>row.status==='ACTIVE'&&(filters.category==='BRAHMACHARI'?row.profile_type==='BRAHMACHARI':filters.category==='HOD'?row.account_type==='HOD'&&row.profile_type!=='BRAHMACHARI':filters.category==='CONGREGATION'?row.account_type==='CONGREGATION'&&row.profile_type!=='BRAHMACHARI':false))")
source = source.replace("[['authority_id',options?.authorities,'name','Authority name']", "[['authority_id',authorityRows,'name','Authority name']")
source = source.replace('<Header title="Reports"><a', '<Header title="Reports"><a className="btn-secondary" href="#/entries">Entry Logs</a><a')
source = source.replace('<span>{pretty(label)}</span></div>)}</div><form', "<span>{label==='issued'?'Passes issued':pretty(label)}</span></div>)}</div><form")
source = source.replace('<button className="btn-main" type="submit">Apply Filters</button></form>', '<div className="actions report-actions"><button className="btn-main" type="submit">Apply Filters</button><button className="btn-secondary" type="button" onClick={()=>{const empty={search:\'\',pass_type:\'\',category:\'\',authority_id:\'\',scanner_id:\'\',gate_id:\'\'};setFilters(empty);setApplied(empty);setPage(1)}}>Reset</button></div></form>')
path.write_text(source, encoding="utf-8")
