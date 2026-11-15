import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';

export interface SearchPlace {
  name: string; area: string; country: string; lat: number; lng: number; population: number; kind: string;
}
export const searchPlaceLabel = (place: SearchPlace) =>
  [...new Set([place.name, place.area, place.country].filter(Boolean))].join(', ');
const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

export function LocationSearch({ onSelect }: {onSelect: (place: SearchPlace) => void}) {
  const [query,setQuery]=useState('');
  const [places,setPlaces]=useState<SearchPlace[] | null>(null);
  const [focused,setFocused]=useState(false);
  const [failed,setFailed]=useState(false);
  const [active,setActive]=useState(0);
  const load = () => {
    setFocused(true);
    if (places) return;
    setFailed(false);
    fetch('/data/search-places.json').then(response => {
      if (!response.ok) throw new Error('Search unavailable');
      return response.json();
    }).then(setPlaces).catch(()=>setFailed(true));
  };
  const matches=useMemo(() => {
    const q=normalize(query);
    if (q.length<2 || !places) return [];
    const tokens=q.split(/\s+/);
    return places.filter(p=>{const text=normalize(searchPlaceLabel(p));return tokens.every(token=>text.includes(token));})
      .sort((a,b)=>{
        const score=(p:SearchPlace)=>{const n=normalize(p.name);return n===q?0:n.startsWith(q)?1:2;};
        return score(a)-score(b)||(b.population||0)-(a.population||0)||a.name.localeCompare(b.name);
      }).slice(0,8);
  },[places,query]);
  const choose=(place:SearchPlace) => {setQuery(searchPlaceLabel(place));setFocused(false);setActive(0);onSelect(place);};
  return <div className="relative w-36 sm:w-64 lg:w-80" onBlur={event=>{if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false);}}>
    <label className="sr-only" htmlFor="location-search">Search for a location</label>
    <div className="flex items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-1.5">
      <Search size={15} className="shrink-0 text-cyan-700" />
      <input id="location-search" role="combobox" aria-expanded={focused && matches.length>0} aria-controls="location-search-results"
        aria-autocomplete="list" aria-activedescendant={focused && matches[active] ? `location-result-${active}` : undefined}
        value={query} placeholder="Search a place" autoComplete="off" onFocus={load}
        onChange={event=>{setQuery(event.target.value);setActive(0);setFocused(true);}}
        onKeyDown={event=>{
          if (event.key==='ArrowDown' && matches.length) {event.preventDefault();setActive(index=>(index+1)%matches.length);}
          else if(event.key==='ArrowUp' && matches.length) {event.preventDefault();setActive(index=>(index+matches.length-1)%matches.length);}
          else if(event.key==='Enter' && matches[active]) {event.preventDefault();choose(matches[active]);}
          else if(event.key==='Escape') {event.stopPropagation();setFocused(false);}
        }}
        className="min-w-0 flex-1 bg-transparent text-xs text-slate-900 outline-none placeholder:text-slate-500" />
    </div>
    {focused && query.trim().length>=2 && <div className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
      {failed ? <p className="px-3 py-3 text-xs text-slate-600">Search is unavailable.</p> : !places ? <p className="px-3 py-3 text-xs text-slate-600">Loading places…</p> : matches.length ?
        <ul id="location-search-results" role="listbox" aria-label="Search results" className="max-h-72 overflow-y-auto py-1">
          {matches.map((place,index)=><li id={`location-result-${index}`} role="option" aria-selected={index===active} key={`${place.kind}-${place.name}-${place.lat}-${place.lng}`}>
            <button type="button" onMouseDown={event=>event.preventDefault()} onClick={()=>choose(place)}
              className={`w-full px-3 py-2 text-left text-xs text-slate-700 hover:bg-cyan-50 ${index===active?'bg-cyan-50':''}`}>
              {searchPlaceLabel(place)}
            </button>
          </li>)}
        </ul> : <p className="px-3 py-3 text-xs text-slate-600">No matching places found.</p>}
    </div>}
  </div>;
}
