import html, json, sys, os
HEAD=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'_head.html'),encoding='utf8').read()
# Pastilles : vert Hi-Res, jaune CD, orange Lossy, violet Partiel, rouge vif Absent, gris Non vérifié / Indisponible
P={'HR':('hr','Hi-Res'),'CD':('cd','CD'),'AB':('ab','Absent'),'LO':('lo','Lossy'),'PA':('pa','Partiel'),
   'NV':('nv','Non vérifié'),'IN':('nv','Indisponible'),'LU':('lo','Lossy uniquement')}
def pill(k):
    # plusieurs étiquettes possibles : liste ['CD','HR','PA'] ou chaîne 'CD+HR+PA'
    ks=k if isinstance(k,(list,tuple)) else str(k).split('+')
    return ' '.join(f'<span class="pill {P[x][0]}">{P[x][1]}</span>' for x in ks)
def e(s): return s  # contenu écrit à la main, HTML autorisé
def title(t,sub=None): return f'<td class="t">{e(t)}'+(f'<small>{e(sub)}</small>' if sub else '')+'</td>'
def tbl(heads,rows):
    th="".join(f'<th>{x}</th>' for x in heads)
    return f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
def build(d):
    out=[HEAD.replace('__NAME__',html.escape(d["name"])),'<div class="wrap">']
    out.append(f'<header style="display:grid;gap:8px"><h1>{e(d["h1"])}</h1><p class="sub">{e(d["sub"])}</p></header>')
    out.append('<dl class="recap">'+"".join(f'<div><dt>{k}</dt><dd>{e(v)}</dd></div>' for k,v in d['recap'])+'</dl>')
    L1=[f'<tr><td class="y">{y}</td><td>{ty}</td>{title(t,s)}<td>{pill(di)}</td><td>{pill(q)}</td><td class="c">{e(c)}</td></tr>' for y,ty,t,s,di,q,c in d['l1']]
    T=tbl(["Année","Type","Titre","Discothèque","Qualité dispo","Commentaire"],L1) if L1 else ''
    out.append(f'<section><h2>Liste d\'achat</h2><p class="note">Livrable 1 · {e(d["l1note"])}</p>{T}</section>')
    if d.get('l1b'):
        R=[f'<tr><td class="y">{y}</td>{title(t,s)}<td>{pill(di)}</td><td>{pill(q)}</td><td class="c">{e(c)}</td></tr>' for y,t,s,di,q,c in d['l1b']]
        out.append(f'<section><h2>Bandes originales</h2><p class="note">Livrable 1 bis · BO composées et créditées à l\'artiste.</p>{tbl(["Année","Titre","Discothèque","Qualité dispo","Commentaire"],R)}</section>')
    if d.get('l2'):
        R=[f'<tr><td class="y">{y}</td>{title(t)}<td>{a}</td><td>{pill(di)}</td><td class="c">{e(c)}</td></tr>' for y,t,a,di,c in d['l2']]
        out.append(f'<section><h2>Titres crédités à d\'autres artistes</h2><p class="note">Livrable 2 · à ranger dans le dossier de l\'artiste principal.</p>{tbl(["Année","Titre","Artiste principal","Discothèque","Commentaire"],R)}</section>')
    else:
        out.append(f'<section><h2>Titres crédités à d\'autres artistes</h2><p class="note">Livrable 2 · {e(d.get("l2none","aucun titre concerné trouvé."))}</p></section>')
    if d.get('l3'):
        R=[f'<tr><td class="y">{y}</td><td>{ty}</td>{title(t,s)}<td>{pill(di)}</td><td class="c">{e(c)}</td></tr>' for y,ty,t,s,di,c in d['l3']]
        out.append(f'<section><h2>Sorties écartées</h2><p class="note">Livrable 3 · tout ce qui existe mais n\'est pas à acheter.</p>{tbl(["Année","Type","Titre","Discothèque","Raison de l’écart"],R)}</section>')
    else:
        out.append('<section><h2>Sorties écartées</h2><p class="note">Livrable 3 · aucune sortie écartée.</p></section>')
    out.append('<section><h2>Points à vérifier</h2><ul class="checks">'+"".join(f'<li>{e(p)}</li>' for p in d['points'])+'</ul></section>')
    out.append('</div>\n</body></html>\n')
    return "\n".join(out)
if __name__=='__main__':
    # usage : python gen.py recap.json [...]  -> écrit recap.html à côté de chaque JSON
    #         python gen.py donnees.py [...]  -> écrit donnees.html (dict D)
    import importlib.util
    for f in sys.argv[1:]:
        if f.endswith('.json'):
            d=json.load(open(f,encoding='utf8')); out=f[:-5]+'.html'
        else:
            spec=importlib.util.spec_from_file_location('d',f); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            d=m.D; out=f[:-3]+'.html'
        open(out,'w',encoding='utf8').write(build(d)); print('ok',out)
