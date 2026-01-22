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
    for sep in [';', ',']:
        for enc in ['latin1','utf-8']:
            try:
                return pd.read_csv(path, sep=sep, encoding=enc, low_memory=False)
            except Exception:
                pass
    raise RuntimeError(f"Não consegui ler CSV: {path}")

def geo_from_path(malha_path):
    """
    Aceita:
      - ZIP (inclusive .zip.download.zip) com shapefile dentro
      - SHP direto (malha já descompactada no raw_data)
    """
    import geopandas as gpd

    if malha_path.lower().endswith(".shp"):
        shp = malha_path
    else:
        tmp = "_tmp_geo"
        safe_unzip(malha_path, tmp)
        shp = None
        for root,_,files in os.walk(tmp):
            for fn in files:
                if fn.lower().endswith(".shp"):
                    shp = os.path.join(root, fn)
                    break
            if shp:
                break
        if not shp:
            raise RuntimeError("Não encontrei .shp na malha municipal (ZIP).")

    gdf = gpd.read_file(shp).to_crs(4326)
    geojson_path = os.path.join(OUT, "municipios_al.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")
    return geojson_path

def build_metrics(votacao_zip, perfil_zip):
    tmp = "_tmp_tse"
    safe_unzip(votacao_zip, tmp)
    safe_unzip(perfil_zip, tmp)

    csvs = [p for p in glob.glob(tmp + "/**/*.csv", recursive=True) if "__MACOSX" not in p]
    if not csvs:
        csvs = [p for p in glob.glob(tmp + "/**/*.txt", recursive=True) if "__MACOSX" not in p]
    if not csvs:
        raise RuntimeError("Não encontrei CSV/TXT dentro dos ZIPs do TSE.")

    vot_paths = [p for p in csvs if re.search(r"(vot|votacao).*(sec)", os.path.basename(p).lower())]
    if not vot_paths:
        vot_paths = csvs[:1]
    vot_path = vot_paths[0]

    df = try_read_csv(vot_path)

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

    if uf and uf in df.columns:
        df = df[df[uf].astype(str).str.upper().eq("AL")]

    def cargo_key(x):
        x = str(x).lower()
        if 'govern' in x: return 'GOV'
        if 'senad' in x: return 'SEN'
        if 'feder' in x: return 'DF'
        if 'estad' in x: return 'DE'
        return None

    df['cargo_key'] = df[cargo].map(cargo_key)
    df = df[df['cargo_key'].notna()]

    df[votos] = pd.to_numeric(df[votos], errors='coerce').fillna(0).astype(int)

    municipios = {}
    for (m,),_ in df.groupby([cod_mun]):
        municipios[m] = {"nome": m, "secoes": 0, "abst": None, "winner": {}, "zonas": {}}

    sec_counts = df.groupby([cod_mun,zona])[secao].nunique().reset_index().rename(columns={secao:'secoes'})
    for _,r in sec_counts.iterrows():
        m=str(r[cod_mun]); z=str(r[zona])
        municipios[m]["zonas"].setdefault(z, {"zona": int(z), "secoes": int(r['secoes']), "abst": None, "brancos": None, "nulos": None, "top": {}})
        municipios[m]["secoes"] = int(df[df[cod_mun]==m][secao].nunique())

    top = df.groupby([cod_mun,zona,'cargo_key',turno,nome, partido])[votos].sum().reset_index()
    top['rank'] = top.groupby([cod_mun,zona,'cargo_key',turno])[votos].rank(method='first', ascending=False)
    top = top[top['rank']<=5]

    totals = df.groupby([cod_mun,zona,'cargo_key',turno])[votos].sum().reset_index().rename(columns={votos:'tot'})
    top = top.merge(totals, on=[cod_mun,zona,'cargo_key',turno], how='left')
    top['pct'] = (top[votos]/top['tot']).where(top['tot']>0, 0.0)

    for _,r in top.iterrows():
        m=str(r[cod_mun]); z=str(r[zona]); ck=str(r['cargo_key']); t=str(r[turno])
        municipios[m]["zonas"].setdefault(z, {"zona": int(z), "secoes": 0, "abst": None, "brancos": None, "nulos": None, "top": {}})
        municipios[m]["zonas"][z]["top"].setdefault(ck, {}).setdefault(t, [])
        municipios[m]["zonas"][z]["top"][ck][t].append({"nome": str(r[nome]), "partido": str(r[partido]) if partido else None, "pct": float(r['pct'])})

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
    # malha: aceita zip OU shp direto (se você já subiu os arquivos descompactados)
    malha = find_one([
        "AL_Municipios_2024.zip", "AL_Municipios_2024.zip.*", "*Municipios*AL*.zip*",
        "AL_Municipios_2024.shp", "*Municipios*AL*.shp"
    ])

    # TSE: aceita .zip e .zip.download.zip automaticamente
    votacao = find_one([
        "votacao_secao_2022_AL.zip", "votacao_secao_2022_AL.zip.*", "*vot*secao*AL*2022*.zip*"
    ])
    perfil = find_one([
        "perfil_eleitor_secao_2022_AL.zip", "perfil_eleitor_secao_2022_AL.zip.*", "*perfil*secao*AL*2022*.zip*"
    ])

    if not malha or not votacao or not perfil:
        raise SystemExit(f"Faltam arquivos em raw_data/. Encontrados: malha={bool(malha)} votacao={bool(votacao)} perfil={bool(perfil)}")

    geo_from_path(malha)
    build_metrics(votacao, perfil)

    print("OK: arquivos gerados em public/data/")

if __name__ == "__main__":
    main()
