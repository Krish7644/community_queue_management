const shapes = {
  home: <><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/></>,
  user: <><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></>,
  people: <><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 4v2"/></>,
  community: <><circle cx="12" cy="6" r="3"/><path d="M7 17v-1a5 5 0 0 1 10 0v1M3 20v-3m18 3v-3M4 9a3 3 0 0 0 0 6m16-6a3 3 0 0 1 0 6"/></>,
  crown: <><path d="m3 6 4 4 5-6 5 6 4-4-2 12H5ZM6 21h12"/></>,
  heart: <><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0l-1 1-1-1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></>,
  bolt: <><path d="m13 2-9 12h7l-1 8 10-13h-7Z"/></>,
  scan: <><path d="M8 3H4a1 1 0 0 0-1 1v4m13-5h4a1 1 0 0 1 1 1v4M3 16v4a1 1 0 0 0 1 1h4m8 0h4a1 1 0 0 0 1-1v-4M3 12h18M8 7v2m4-2v2m4-2v2m-8 6v2m4-2v2m4-2v2"/></>,
  gate: <><path d="M3 21h18M6 21V5l12-2v18M6 7h12m-7 6h.01"/></>,
  ticket: <><path d="M3 7a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v3a2 2 0 0 0 0 4v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3a2 2 0 0 0 0-4Zm12-1v2m0 3v2m0 3v2"/></>,
  share: <><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 10.5 6.8-4m-6.8 7 6.8 4"/></>,
  list: <><path d="M9 5h12M9 12h12M9 19h12M3 5h.01M3 12h.01M3 19h.01"/></>,
  chart: <><path d="M4 3v18h17M9 16v-4m5 4V8m5 8V5"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  arrow: <><path d="M6 18 18 6M6 6h12v12"/></>,
  close: <><path d="m6 6 12 12M6 18 18 6"/></>,
  menu: <><path d="M4 6h16M4 12h16M4 18h16"/></>,
  logout: <><path d="M9 4H4a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h5m6-14 6 6-6 6M8 12h13"/></>,
  lotus: <><path d="M12 19c-7 0-10-4-10-9 5 0 8 3 10 9Zm0 0c7 0 10-4 10-9-5 0-8 3-10 9Zm0 0C7 14 7 8 12 3c5 5 5 11 0 16Z"/></>,
}

export default function PortalIcon({ name, className = '' }) {
  return <svg className={'portal-icon ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{shapes[name] || shapes.ticket}</svg>
}
