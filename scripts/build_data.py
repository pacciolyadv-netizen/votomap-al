import os, zipfile, glob, json, re
import pandas as pd

RAW = os.path.join(os.getcwd(), "raw_data")
OUT = os.path.join(os.getcwd(), "public", "data")
os.makedirs(OUT, exist_ok=True)

def find_one(patterns):
    for p in patterns:
        hits = glob.glob(os.path.join(RAW, p))
        if hits:
            return hits[0]
    return None

def safe_unzip(zip_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)

def try_read_csv(path):
    # many TSE files use ';' and latin-1
    for sep in [';', ',']:
        for enc in ['latin1','utf-8']:
            try:
                return pd.read_csv(path, sep=sep, encoding=enc, low_memory=False)
            except Exception:
                pass
    raise RuntimeError(f"Não consegui ler CSV: {path}")

def geo_from_zip(zip_path):
    # convert shapefile -> geojson using geopandas (installed in workflow)
    import geopandas as gpd
    tmp = "_tmp_geo"
    safe_unzip(zip_path, tmp)
    # find .shp
    shp = None
    for root,_,files in os.walk(tmp):
        for fn in files:
            if fn.lower().endswith(".shp"):
                shp = os.path.join(root, fn)
                break
        if shp: break
    if not shp:
        raise RuntimeError("Não encontrei .shp na malha municipal.")
    gdf = gpd.read_file(shp)
    # attempt to standardize id/name fields
    # common IBGE fields: CD_MUN, NM_MUN
    gdf = gdf.to_crs(4326)
    geojson_path = os.path.join(OUT, "municipios_al.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")
    return geojson_path

def build_metrics(votacao_zip, perfil_zip):
    tmp = "_tmp_tse"
    safe_unzip(votacao_zip, tmp)
    safe_unzip(perfil_zip, tmp)

    # find candidate voting file(s)
    csvs = [p for p in glob.glob(tmp + "/**/*.csv", recursive=True) if "__MACOSX" not in p]
    if not csvs:
        # sometimes extension is .txt
        csvs = [p for p in glob.glob(tmp + "/**/*.txt", recursive=True) if "__MACOSX" not in p]
    if not csvs:
        raise RuntimeError("Não encontrei CSV/TXT dentro dos ZIPs do TSE.")

    # heuristics: votacao por secao often contains "votacao_secao" or "votacao" and "secao"
    vot_paths = [p for p in csvs if re.search(r"(vot|votacao).*(sec)", os.path.basename(p).lower())]
    if not vot_paths:
        vot_paths = csvs[:1]  # fallback
    vot_path = vot_paths[0]

    df = try_read_csv(vot_path)

    # Normalize likely columns (varies by dataset export)
    cols = {c.lower(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    uf = pick('sg_uf','uf')
    cod_mun = pick('cd_municipio','cd_mun','codigo_municipio','cd_municipio_ibge')
    zona = pick('nr_zona','zona')
    secao = pick('nr_secao','secao')
    cargo = pick('ds_cargo','cargo')
    turno = pick('nr_turno','turno')
    nome = pick('nm_votavel','nm_candidato','nome_votavel','nome')
    partido = pick('sg_partido','partido')
    votos = pick('qt_votos','votos','qt_votos_nominais')

    required = [cod_mun,zona,secao,cargo,turno,nome,votos]
    if any(r is None for r in required):
        raise RuntimeError(f"Colunas inesperadas no arquivo de votação. Colunas encontradas: {list(df.columns)[:30]}")

    df[cod_mun] = df[cod_mun].astype(str).str.zfill(7)

    # keep only AL
    if uf and uf in df.columns:
        df = df[df[uf].astype(str).str.upper().eq("AL")]

    # Map cargo labels to keys
    def cargo_key(x):
        x = str(x).lower()
        if 'govern' in x: return 'GOV'
        if 'senad' in x: return 'SEN'
        if 'feder' in x: return 'DF'
        if 'estad' in x: return 'DE'
        return None
    df['cargo_key'] = df[cargo].map(cargo_key)
    df = df[df['cargo_key'].notna()]

    # aggregate by municipio/zona: compute top candidates by votes
    df[votos] = pd.to_numeric(df[votos], errors='coerce').fillna(0).astype(int)

    # totals per zona & cargo/turno
    g = df.groupby([cod_mun, zona, 'cargo_key', turno], dropna=False)[votos].sum().reset_index().rename(columns={votos:'votos_total'})
    # winner per municipio
    gmun = df.groupby([cod_mun,'cargo_key',turno,nome]).agg(votos=('cargo_key','size'), votos_soma=(votos,'sum')).reset_index()

    # Build top list per zona
    top = df.groupby([cod_mun,zona,'cargo_key',turno,nome, partido])[votos].sum().reset_index()
    top['rank'] = top.groupby([cod_mun,zona,'cargo_key',turno])[votos].rank(method='first', ascending=False)
    top = top[top['rank']<=5]
    # pct within zona-cargo-turno
    totals = df.groupby([cod_mun,zona,'cargo_key',turno])[votos].sum().reset_index().rename(columns={votos:'tot'})
    top = top.merge(totals, on=[cod_mun,zona,'cargo_key',turno], how='left')
    top['pct'] = (top[votos]/top['tot']).where(top['tot']>0, 0.0)

    # create dictionary
    municipios = {}
    # municipality names optional: could come from another file later
    for (m,),_ in df.groupby([cod_mun]):
        municipios[m] = {"nome": m, "secoes": 0, "abst": None, "winner": {}, "zonas": {}}

    # count sections per municipio & zona
    sec_counts = df.groupby([cod_mun,zona])[secao].nunique().reset_index().rename(columns={secao:'secoes'})
    for _,r in sec_counts.iterrows():
        m=str(r[cod_mun]); z=str(r[zona])
        municipios[m]["zonas"].setdefault(z, {"zona": int(z), "secoes": int(r['secoes']), "abst": None, "brancos": None, "nulos": None, "top": {}})
    municipios[m]["secoes"] = int(df[df[cod_mun]==m][secao].nunique())

    # attach top
    for _,r in top.iterrows():
        m=str(r[cod_mun]); z=str(r[zona]); ck=str(r['cargo_key']); t=str(r[turno])
        municipios[m]["zonas"].setdefault(z, {"zona": int(z), "secoes": 0, "abst": None, "brancos": None, "nulos": None, "top": {}})
        municipios[m]["zonas"][z]["top"].setdefault(ck, {}).setdefault(t, [])
        municipios[m]["zonas"][z]["top"][ck][t].append({"nome": str(r[nome]), "partido": str(r[partido]) if partido else None, "pct": float(r['pct'])})

    # winner per municipio
    w = df.groupby([cod_mun,'cargo_key',turno,nome, partido])[votos].sum().reset_index()
    w['rank'] = w.groupby([cod_mun,'cargo_key',turno])[votos].rank(method='first', ascending=False)
    w = w[w['rank']==1]
    for _,r in w.iterrows():
        m=str(r[cod_mun]); ck=str(r['cargo_key']); t=str(r[turno])
        municipios[m]["winner"].setdefault(ck, {})[t] = {"nome": str(r[nome]), "partido": str(r[partido]) if partido else None}

    out = {"meta":{"status":"ok","year":2022}, "municipios": municipios}
    with open(os.path.join(OUT,"metrics_2022.json"),"w",encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return out

def main():
    malha = find_one(["AL_Municipios_2024.zip", "*Municipios*AL*.zip"])
    votacao = find_one(["votacao_secao_2022_AL.zip", "*vot*secao*AL*2022*.zip"])
    perfil = find_one(["perfil_eleitor_secao_2022_AL.zip", "*perfil*secao*AL*2022*.zip"])

    if not malha or not votacao or not perfil:
        raise SystemExit("Faltam ZIPs em raw_data/. Veja o README.")

    geo_from_zip(malha)
    build_metrics(votacao, perfil)

    print("OK: arquivos gerados em public/data/")

if __name__ == "__main__":
    main()
