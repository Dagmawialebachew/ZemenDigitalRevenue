import type { Language, PolicyDocument } from '../api/types'

export function PolicyView({ document, language, onSupport }: { document: PolicyDocument; language: Language; onSupport: () => void }) {
  return <div className="view-stack policy-view">
    <section className="page-heading"><p className="eyebrow">ZEMEN DIGITAL · TRUST CENTER</p><h1>{document.title}</h1><p>{language==='am'?`Policy version ${document.version}`:`Policy version ${document.version}`}</p></section>
    <section className="content-card policy-document">{document.sections.map(section=><article key={section.heading}><h2>{section.heading}</h2><p>{section.body}</p></article>)}</section>
    <section className="trust-contact"><div><b>{language==='am'?'ጥያቄ አለዎት?':'Need clarification?'}</b><span>{language==='am'?'ከመክፈልዎ በፊት Zemen Supportን ያነጋግሩ።':'Contact Zemen Support before paying.'}</span></div><button onClick={onSupport}>{language==='am'?'Support ይክፈቱ':'Open support'}</button></section>
  </div>
}
