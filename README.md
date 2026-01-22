# VotoMap - AL

Painel territorial (Estado → Municípios → Zonas → Seções) com dados públicos do **TSE** e **IBGE**.

## O que este MVP faz
- Mapa de Alagoas (municípios clicáveis)
- Drilldown: município → zonas → indicadores da zona (e top 5 por cargo/turno)
- Indicadores agregados (ex.: abstenção, brancos, nulos) quando existirem nos arquivos
- Perfil do eleitorado por seção (quando disponível no dataset)

**Importante:** este projeto não recomenda “discurso”/“abordagem” para persuadir eleitores. Ele é um observatório baseado em dados agregados.

---

## 1) Coloque os arquivos em `raw_data/`
Você vai adicionar os ZIPs oficiais (baixados do TSE/IBGE) aqui:

- `raw_data/votacao_secao_2022_AL.zip`
- `raw_data/perfil_eleitor_secao_2022_AL.zip`
- `raw_data/AL_Municipios_2024.zip`

> Dica: os ZIPs do TSE/IBGE costumam ser grandes (dezenas/centenas de MB).  
> Se o arquivo estiver com poucos KB/MB, provavelmente o download foi interrompido.

**Presidente (BR 1T/2T)** é opcional no MVP inicial. Se você adicionar depois, o pipeline já está preparado.

---

## 2) Gerar os dados do painel (sem programar): GitHub Actions
Este repositório inclui um workflow:
- **Actions → "Build data (TSE/IBGE)" → Run workflow**

Ele vai:
- descompactar os ZIPs
- converter a malha municipal para GeoJSON
- processar os CSVs do TSE
- gerar:
  - `public/data/municipios_al.geojson`
  - `public/data/metrics_2022.json`

---

## 3) Publicar (Vercel)
1. Crie uma conta na Vercel e conecte com GitHub
2. "Add New Project" → selecione este repositório
3. Deploy

Pronto: você terá um link do tipo `https://votomap-al.vercel.app`.

---

## 4) Rodar local (opcional)
```bash
npm install
npm run dev
```
