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

    df[votos] = pd.to_numeric(df[votos], errors='coerce').fillna(0)_
