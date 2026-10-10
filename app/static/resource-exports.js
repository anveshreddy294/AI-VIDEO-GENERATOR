/* Export only already-authorized, visible resource content. No network calls. */
(() => {
    'use strict';
    function filename(topic, resource, extension) {
        const stem = String(topic || 'lesson').normalize('NFKC').replace(/[\x00-\x1f\x7f<>:"/\\|?*]/g, '-').replace(/[^\p{L}\p{N}._ -]/gu, '').replace(/^[^\p{L}\p{N}]+|[. -]+$/gu, '').slice(0,80) || 'lesson';
        return stem + '-' + resource + '.' + extension;
    }
    const xml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
    function diagramSVG(spec) {
        if (!spec || !['FLOWCHART','CONCEPT_MAP','RELATIONSHIP_MAP'].includes(spec.type) || !Array.isArray(spec.nodes) || !spec.nodes.length || spec.nodes.length > 32 || !Array.isArray(spec.edges) || spec.edges.length > 64) throw Error('Generate a valid flowchart before downloading.');
        const label = value => { if(typeof value !== 'string' || !value.trim() || value.length > 4096) throw Error('Invalid flowchart label. Regenerate the diagram.'); return value; };
        const title = label(typeof spec.title === 'string' ? spec.title : spec.title?.text);
        const nodes = spec.nodes.map(n => ({id:label(n.node_id ?? n.id), text:label(n.item?.text ?? n.label), description:typeof n.description === 'string' ? n.description : ''}));
        const indices = new Map(nodes.map((n,i)=>[n.id,i]));
        if(indices.size !== nodes.length) throw Error('Invalid flowchart nodes. Regenerate the diagram.');
        const wrap = value => {
            const lines=[]; for(const paragraph of String(value).split(/\r?\n/)) {
                const chars=Array.from(paragraph); if(!chars.length) lines.push('');
                while(chars.length) lines.push(chars.splice(0,72).join(''));
            } return lines;
        };
        const text = (value,x,y,size=16) => wrap(value).map((line,i)=>`<text x="${x}" y="${y+i*22}" font-family="sans-serif" font-size="${size}" fill="#162c25">${xml(line)}</text>`).join('');
        let y=30; const pieces=[text(title,24,y,20)]; y+=wrap(title).length*22+24;
        const boxes=[];
        for(const n of nodes) {const lines=wrap(n.text+'\n'+n.description);const height=Math.max(64,lines.length*22+22);boxes.push({y,height});pieces.push(`<rect x="36" y="${y}" width="768" height="${height}" rx="10" fill="#eef6f1" stroke="#417765"/>`+text(n.text+(n.description?'\n'+n.description:''),52,y+26));y+=height+28;}
        // Side lanes preserve back-edges, cycles and arbitrary graph connectivity.
        const width=840+spec.edges.length*12;
        spec.edges.forEach((e,i)=>{
            const from=indices.get(e.from_node),to=indices.get(e.to_node);
            if(from===undefined || to===undefined) throw Error('Invalid flowchart connection. Regenerate the diagram.');
            const a=boxes[from],b=boxes[to],lane=824+i*12;
            const ay=a.y+a.height/2,by=b.y+b.height/2;
            pieces.push(`<path d="M 804 ${ay} H ${lane} V ${by+(from===to?20:0)} H 804" fill="none" stroke="#26634f" stroke-width="2" marker-end="url(#arrow)"/>`);
        });
        pieces.push(text('Connections',24,y,18));y+=32;
        spec.edges.forEach(e=>{const value=nodes[indices.get(e.from_node)].text+' → '+nodes[indices.get(e.to_node)].text+(e.item?.text || e.label ? ': '+label(e.item?.text ?? e.label) : '');pieces.push(text(value,24,y));y+=wrap(value).length*22+16;});
        return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${y+24}" viewBox="0 0 ${width} ${y+24}" role="img" aria-label="${xml(title)}"><title>${xml(title)}</title><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#26634f"/></marker></defs><rect width="100%" height="100%" fill="white"/>${pieces.join('')}</svg>`;
    }
    function serialize(element, markdown=true) {
        const escape = value => markdown ? value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : value;
        function visit(el) {
            if(typeof el==='string') return escape(el);
            if(el.nodeType===3) return escape(el.textContent || '');
            const tag=String(el.tagName || el.tag || '').toLowerCase();
            if(['button','input','select','textarea','script','style','img','svg'].includes(tag)) return '';
            const children=Array.from(el.childNodes || el.children || []);
            const value=children.length ? children.map(visit).join('') : escape(el.textContent || '');
            if(/^h[1-6]$/.test(tag)) return '\n\n'+(markdown?'#'.repeat(Number(tag[1]))+' ':'')+value+'\n\n';
            if(tag==='li') return '\n- '+value.trim()+'\n';
            if(tag==='pre') {const raw=el.textContent || '';const runs=raw.match(/`+/g) || [];const fence='`'.repeat(Math.max(3,...runs.map(v=>v.length+1)));return '\n\n'+(markdown?fence+'\n':'')+raw+(markdown?'\n'+fence:'')+'\n\n';}
            if(tag==='br') return '\n';
            return ['p','article','section','div','ul','ol'].includes(tag) ? value+'\n\n' : value;
        }
        const result=visit(element).replace(/\n{3,}/g,'\n\n').trim();
        if(!result) throw Error('Generate this resource before downloading.');
        return result+'\n';
    }
    function download(doc, blob, name) {
        const url=URL.createObjectURL(blob),a=doc.createElement('a');
        a.href=url;a.download=name;doc.body.append(a);
        try {a.click();} finally {a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
    }
    async function png(svg) {
        // SVG is built only by diagramSVG: no imported markup, URLs or active content.
        const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml;charset=utf-8'}));
        try {
            const image=new Image();await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('Flowchart image could not be rendered. Download SVG instead.'));image.src=url;});
            const width=image.naturalWidth,height=image.naturalHeight;
            if(!width || !height || width*height>16000000) throw Error('This diagram is too large for PNG. Download SVG instead.');
            const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
            const context=canvas.getContext('2d');if(!context) throw Error('PNG export is unavailable. Download SVG instead.');context.drawImage(image,0,0);
            return await new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error('PNG export failed. Download SVG instead.')),'image/png'));
        } finally {URL.revokeObjectURL(url);}
    }
    const api={filename,diagramSVG,serialize,download,png};
    if(typeof module!=='undefined') module.exports=api;
    if(typeof window!=='undefined') window.VisualAIResources=api;
})();
