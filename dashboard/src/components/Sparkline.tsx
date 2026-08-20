export function Sparkline({values}:{values:number[]}){
  const w=660,h=190,p=10,max=Math.max(...values,1),min=Math.min(...values,0),range=Math.max(max-min,1)
  const pts=values.map((v,i)=>`${p+(i*(w-2*p)/Math.max(values.length-1,1))},${h-p-((v-min)/range)*(h-2*p)}`).join(' ')
  const area=values.length?`${p},${h-p} ${pts} ${w-p},${h-p}`:''
  return <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"><defs><linearGradient id="zfill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".22"/><stop offset="1" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs><polygon points={area} fill="url(#zfill)"/><polyline points={pts} fill="none" stroke="currentColor" strokeWidth="3" vectorEffect="non-scaling-stroke"/></svg>
}
